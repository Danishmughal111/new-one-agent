"""TrendEra MVP flow tests (SQLite, deterministic mock LLM)."""


async def test_product_creation(session) -> None:
    from app.schemas.product import ProductCreate
    from app.services.product_service import ProductService

    product = await ProductService(session).create(
        ProductCreate(name="Wireless Earbuds", category="Electronics", price_currency="SAR")
    )
    assert product.id
    assert product.name == "Wireless Earbuds"


async def test_article_generation_single_call_and_qa(session) -> None:
    from app.schemas.product import ProductCreate
    from app.services.content_service import ContentService
    from app.services.product_service import ProductService
    from app.services.qa_service import validate_article

    product = await ProductService(session).create(
        ProductCreate(name="Smart Watch", category="Wearables", price_currency="SAR")
    )
    article = await ContentService(session).generate(product.id)
    assert article.id
    assert "Smart Watch" in article.content

    qa = validate_article(
        title=article.title, content=article.content, product_name=product.name
    )
    assert qa.passed is True


async def test_qa_rejects_invalid(session) -> None:
    from app.services.qa_service import validate_article

    result = validate_article(title="", content="short", product_name="X")
    assert result.passed is False


async def test_blogger_draft_preparation(session) -> None:
    from app.schemas.product import ProductCreate
    from app.services.blogger_service import BloggerService
    from app.services.content_service import ContentService
    from app.services.product_service import ProductService

    product = await ProductService(session).create(
        ProductCreate(name="Tablet", category="Electronics", price_currency="SAR")
    )
    article = await ContentService(session).generate(product.id)
    draft = await BloggerService(session).prepare_draft(article.id)

    assert draft.title == article.title
    assert draft.content.startswith("<h2>Tablet Review</h2>")
    assert "<p>" in draft.content
    assert draft.to_dict()["labels"] == ["Electronics"]