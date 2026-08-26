"""Autonomous TrendEra run: discover -> research -> article -> image -> QA -> publish."""

from app.core.config import settings
from app.core.llm import generate_article_text
from app.core.logging import get_logger
from app.models.article import Article
from app.repositories.article import ArticleRepository
from app.schemas.product import ProductCreate
from app.services.audit_service import AuditService
from app.services.affiliate_providers import AffiliateDiscoveryService, AffiliateOffer
from app.services.affiliate_service import add_affiliate_cta, is_valid_affiliate_url
from app.services.blogger_connection_service import BloggerConnectionService
from app.services.blogger_service import BloggerService
from app.services.html_converter import insert_image_after_intro, markdown_to_blogger_html
from app.services.image_service import ImageService
from app.services.opportunity_service import score_opportunity
from app.services.product_discovery import CATALOG, ProductDiscoveryService, build_research_lines
from app.services.product_service import ProductService
from app.services.qa_service import validate_article
from app.services.research_service import ResearchService
from app.services.seo_service import (
    add_internal_links,
    add_sources_section,
    build_labels,
    build_seo_plan,
    validate_seo,
)

logger = get_logger("trendera.workflow")


def is_public_url(url: str | None) -> bool:
    """True only for http(s) URLs (rejects local/relative/filesystem paths)."""
    return bool((url or "").strip().startswith(("http://", "https://")))


def validate_publication_html(html: str, image_url: str | None, alt: str | None) -> list[str]:
    """Extended publication QA checks on the final Blogger HTML."""
    errors: list[str] = []
    if not (image_url or "").strip():
        errors.append("image URL is missing")
    elif not is_public_url(image_url):
        errors.append("image URL must be a public http(s) URL, not a local path")
    if not (alt or "").strip():
        errors.append("image alt text is missing")
    if "<img" not in html:
        errors.append("image HTML is missing from the article")
    elif alt and f'alt="{alt}"' not in html:
        errors.append("image alt text is missing from the image HTML")
    return errors


def _result(status: str, **fields) -> dict:
    data = {
        "status": status,
        "selected_product": None,
        "product_id": None,
        "research_status": None,
        "duplicate_check": None,
        "discovery_status": None,
        "research": None,
        "opportunity": None,
        "seo_score": None,
        "primary_keyword": None,
        "labels": None,
        "sources": [],
        "article_id": None,
        "article_generated": False,
        "image_status": None,
        "image_url": None,
        "image_generated": False,
        "qa_result": {"passed": False, "errors": []},
        "blogger_result": None,
        "published": False,
        "publish_status": None,
        "affiliate_status": None,
        "affiliate_provider": None,
        "affiliate_product_name": None,
        "affiliate_match_score": None,
        "affiliate_url": None,
        "affiliate_cta_inserted": False,
        "error": None,
    }
    data.update({k: v for k, v in fields.items() if k in data})
    return data


def _affiliate_status(offer) -> str:
    """Map a resolved AffiliateOffer to a stable status label."""
    if offer is None:
        return "not_found"
    if offer.source == "manual":
        return "manual"
    if offer.source == "cached":
        return "cached"
    if offer.status == "found":
        return "found"
    if offer.status == "failed":
        return "failed"
    return "not_found"


class TrenderaWorkflow:
    """Runs one autonomous discovery -> publish cycle (single product)."""

    def __init__(self, session) -> None:
        self.session = session
        self._articles = ArticleRepository(session)
        self._discovery = ProductDiscoveryService(session)
        self._images = ImageService()

    async def _log(self, action: str, *, resource_type: str = "trendera", resource_id: str | None = None, message: str | None = None) -> None:
        """Record a workflow event in the activity/audit log."""
        await AuditService(self.session).record(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"message": message} if message else {},
        )
        await self.session.commit()

    @staticmethod
    def _seo_prompt_lines(plan: dict) -> list[str]:
        lines = [
            f"Primary keyword: {plan.get('primary_keyword', '')}",
            "Secondary keywords: " + "; ".join(plan.get("secondary_keywords", [])),
            f"Suggested SEO title: {plan.get('seo_title', '')}",
            f"Meta description: {plan.get('meta_description', '')}",
            "Recommended structure: " + " -> ".join(plan.get("structure", [])),
        ]
        if plan.get("questions"):
            lines.append("Answer these questions: " + "; ".join(plan["questions"]))
        return lines

    async def _select_internal_links(self, name: str, product_id: str, category: str | None) -> list[tuple[str, str]]:
        """Return up to 3 relevant existing published articles as (anchor, url)."""
        articles = await self._articles.list(limit=100)
        current_words = {w for w in (name + " " + (category or "")).lower().split() if len(w) > 3}
        links: list[tuple[str, str]] = []
        for article in articles:
            if article.product_id == product_id or not article.blogger_url:
                continue
            title_words = set((article.title or "").lower().split())
            if title_words & current_words:
                links.append((article.title, article.blogger_url))
            if len(links) >= 3:
                break
        return links

    async def run(self, *, publish_now=False, image_transport=None, blogger_transport=None, research_transport=None, affiliate_transport=None) -> dict:
        candidates = await self._discovery.discover_candidates(limit=5)
        if not candidates:
            return _result("skipped", research_status="none", duplicate_check="skipped_duplicate", error="No suitable product found (all products are duplicates or unavailable)")

        # --- Candidate pipeline: research + score each, select first above threshold ---
        selected = None
        for candidate in candidates:
            research = await ResearchService(CATALOG).research(candidate, transport=research_transport)
            opportunity = score_opportunity(research)
            if opportunity["score"] >= settings.min_opportunity_score:
                selected = (candidate, research, opportunity)
                break

        if selected is None:
            return _result("skipped", research_status="none", duplicate_check="passed", error="No candidate reached the minimum opportunity threshold")

        candidate, research, opportunity = selected
        name = candidate["name"]
        research_status = research["status"]

        # Manual affiliate URL (highest priority). Invalid/absent -> None.
        manual_url = candidate.get("affiliate_url")
        manual_url = manual_url.strip() if isinstance(manual_url, str) else None
        if manual_url and not is_valid_affiliate_url(manual_url):
            manual_url = None
        await self._log("research.completed", message=f"Research {research_status} for {name} ({research['sources_succeeded']}/{research['sources_attempted']} sources)")

        # --- SEO plan + Blogger labels ---
        seo_plan = build_seo_plan(research)
        labels = build_labels(research, seo_plan)

        product = await ProductService(self.session).create(
            ProductCreate(
                name=name,
                description=research["data"].get("description") or candidate.get("description"),
                category=candidate.get("category"),
                region=candidate.get("region"),
                affiliate_url=manual_url,
                metadata={
                    "research": research["data"],
                    "sources": research["sources"],
                    "research_status": research_status,
                    "opportunity": opportunity,
                    "seo_plan": seo_plan,
                },
            )
        )
        await self._log("product.discovered", resource_id=product.id, message=f"Product discovered: {name}")

        # Resolve the affiliate offer (manual > cached > automatic). A provider
        # failure must never block the rest of the workflow.
        try:
            offer = await AffiliateDiscoveryService(self.session).resolve(
                product_id=product.id,
                identity={"name": name, "brand": candidate.get("brand"), "category": candidate.get("category")},
                manual_url=manual_url,
                transport=affiliate_transport,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Affiliate discovery failed: %s", exc)
            offer = AffiliateOffer(status="failed", reason=f"affiliate discovery error: {exc}")

        affiliate_url = offer.url if offer.status == "found" and is_valid_affiliate_url(offer.url) else None
        if affiliate_url and affiliate_url != product.affiliate_url:
            product.affiliate_url = affiliate_url
            await self.session.commit()

        extra = ["Write in an SEO-friendly style using descriptive headings and only verifiable facts.",
                 "Use the research below as factual grounding; do not invent specifications or claims."]
        extra += build_research_lines(candidate)
        extra += self._seo_prompt_lines(seo_plan)
        if research["data"].get("live_summary"):
            extra.append("Live research summary: " + research["data"]["live_summary"][:2000])
        try:
            content = await generate_article_text(name, extra=extra)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Article generation failed for %s", name)
            await self._log("workflow.failed", message=f"Article generation failed: {exc}")
            return _result("failed", selected_product=name, product_id=product.id, research_status=research_status, opportunity=opportunity, error=f"Article generation failed: {exc}")

        title = seo_plan.get("seo_title") or f"{name} Review"
        qa = validate_article(title=title, content=content, product_name=name)
        if not qa.passed:
            await self._log("workflow.failed", message=f"Article failed QA: {qa.errors}")
            return _result("failed", selected_product=name, product_id=product.id, research_status=research_status, opportunity=opportunity, qa_result={"passed": False, "errors": qa.errors}, error="Article failed QA")

        image_url = None
        image_error = None
        try:
            image_url = await self._images.generate(
                product_name=name,
                category=candidate.get("category"),
                transport=image_transport,
            )
            await self._log("image.generated", message=f"Image generated for {name}")
        except Exception as exc:  # noqa: BLE001
            image_error = str(exc)
            logger.warning("Image generation failed for %s after retries: %s", name, exc)
            await self._log("image.failed", message=f"Image generation failed: {exc}")

        alt = f"{name} product illustration"
        final_content = insert_image_after_intro(content, image_url, alt) if image_url else content

        # --- Internal links + authoritative sources ---
        internal_links = await self._select_internal_links(name, product.id, candidate.get("category"))
        if internal_links:
            final_content = add_internal_links(final_content, internal_links)
        source_urls = [s["url"] for s in research["sources"] if s.get("url")]
        if source_urls:
            final_content = add_sources_section(final_content, source_urls)

        # Monetization: append a clearly-separated affiliate CTA when a valid
        # affiliate URL exists (deterministic, no LLM).
        if affiliate_url:
            final_content = add_affiliate_cta(final_content, affiliate_url, product_name=name)

        # --- SEO validation (advisory) ---
        seo_validation = validate_seo(content, seo_plan)
        await self._log("seo.validated", message=f"SEO score {seo_validation['seo_score']} for {name}")

        article = Article(
            product_id=product.id,
            title=title,
            content=final_content,
            status="DRAFT",
            labels=labels,
            metadata_={
                "product_name": name,
                "seo_plan": seo_plan,
                "seo_validation": seo_validation,
                "sources": research["sources"],
                "research_status": research_status,
                "opportunity": opportunity,
                "affiliate_url": affiliate_url,
                "affiliate_status": _affiliate_status(offer),
                "affiliate_provider": offer.source,
                "affiliate_match_score": offer.match_score,
            },
        )
        article = await self._articles.add(article)
        product.image_url = image_url
        await self.session.commit()
        await self._log("article.saved", resource_id=article.id, message=f"Article saved as DRAFT: {title}")

        html = markdown_to_blogger_html(final_content)
        pub_errors = validate_publication_html(html, image_url, alt) if image_url else []
        base = dict(
            selected_product=name,
            product_id=product.id,
            research_status=research_status,
            duplicate_check="passed",
            discovery_status=candidate.get("discovery_source", "catalog"),
            research=research,
            opportunity=opportunity,
            seo_score=seo_validation["seo_score"],
            primary_keyword=seo_plan["primary_keyword"],
            labels=labels,
            sources=research["sources"],
            article_id=article.id,
            affiliate_status=_affiliate_status(offer),
            affiliate_provider=offer.source,
            affiliate_product_name=offer.product_name,
            affiliate_match_score=offer.match_score,
            affiliate_url=affiliate_url,
            affiliate_cta_inserted=bool(affiliate_url),
        )
        if pub_errors:
            article.status = "FAILED"
            await self.session.commit()
            await self._log("workflow.failed", message="Publication QA failed: " + "; ".join(pub_errors))
            return _result("failed", **base, image_status="generated", image_url=image_url, qa_result={"passed": False, "errors": pub_errors}, error="Publication QA failed: " + "; ".join(pub_errors))

        if not publish_now:
            await self._log("workflow.completed", message=f"Workflow completed (DRAFT): {title}")
            if image_url:
                return _result("success", **base, image_status="generated", image_url=image_url, article_generated=True, image_generated=True, qa_result={"passed": True, "errors": []}, published=False, publish_status="draft")
            return _result("partial_success", **base, image_status="failed", image_url=None, article_generated=True, image_generated=False, qa_result={"passed": True, "errors": []}, published=False, publish_status="draft", error=f"Image generation failed: {image_error}")

        connection = BloggerConnectionService(self.session)
        if not await connection.is_connected():
            article.status = "FAILED"
            await self.session.commit()
            await self._log("blogger.not_connected", message="Blogger is not connected; live publish skipped")
            return _result("partial_success", **base, image_status="generated" if image_url else "failed", image_url=image_url, article_generated=True, image_generated=bool(image_url), qa_result={"passed": True, "errors": []}, published=False, publish_status="failed", error="Blogger is not connected. Connect Blogger before publishing live.")

        await self._log("blogger.publishing", message=f"Publishing to Blogger: {title}")
        try:
            blogger_result = await BloggerService(self.session).publish(
                article.id,
                publish_now=True,
                transport=blogger_transport,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Blogger publishing failed for article %s", article.id)
            article.status = "FAILED"
            await self.session.commit()
            await self._log("blogger.publish_failed", message=f"Blogger publishing failed: {exc}")
            return _result("partial_success", **base, image_status="generated" if image_url else "failed", image_url=image_url, article_generated=True, image_generated=bool(image_url), qa_result={"passed": True, "errors": []}, published=False, publish_status="failed", error=f"Blogger publishing failed: {exc}")

        await self._log("blogger.published", resource_id=article.id, message=f"Article published: {title}")
        if image_url:
            return _result("success", **base, image_status="generated", image_url=image_url, article_generated=True, image_generated=True, qa_result={"passed": True, "errors": []}, blogger_result=blogger_result, published=True, publish_status="live")
        return _result("partial_success", **base, image_status="failed", image_url=None, article_generated=True, image_generated=False, qa_result={"passed": True, "errors": []}, blogger_result=blogger_result, published=True, publish_status="live", error=f"Image generation failed: {image_error}")
