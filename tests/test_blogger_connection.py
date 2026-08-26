"""Tests for Blogger connection persistence and TrendEra list/activity endpoints."""

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.blogger_connection import BloggerConnection
from app.services.blogger_connection_service import BloggerConnectionService


async def test_connection_not_connected_by_default(session):
    service = BloggerConnectionService(session)
    assert await service.is_connected() is False
    assert (await service.status())["connected"] is False


async def test_connect_persists_refresh_token(session, monkeypatch):
    settings.google_blog_id = "blog-1"

    async def fake_exchange(code, transport=None):
        return {"access_token": "at", "refresh_token": "rt-secret"}

    async def fake_email(access_token, transport=None):
        return "owner@example.com"

    async def fake_blog(access_token, blog_id, transport=None):
        return "My TrendEra Blog"

    monkeypatch.setattr("app.services.blogger_connection_service.exchange_code_for_token", fake_exchange)
    monkeypatch.setattr("app.services.blogger_connection_service.fetch_user_email", fake_email)
    monkeypatch.setattr("app.services.blogger_connection_service.fetch_blog_name", fake_blog)

    await BloggerConnectionService(session).connect("code-123")

    service = BloggerConnectionService(session)
    assert await service.is_connected() is True
    status = await service.status()
    assert status["connected"] is True
    assert status["email"] == "owner@example.com"
    assert status["blog_name"] == "My TrendEra Blog"
    # Tokens must never be exposed through the status response.
    assert "refresh_token" not in status
    assert "access_token" not in status


async def test_refresh_token_survives_new_session(session):
    session.add(BloggerConnection(refresh_token="persisted-token", blog_id="blog-1"))
    await session.commit()

    from app.core.database import async_session_factory

    async with async_session_factory() as session2:
        service2 = BloggerConnectionService(session2)
        assert await service2.is_connected() is True
        assert await service2.get_refresh_token() == "persisted-token"


async def test_disconnect_removes_connection(session):
    session.add(BloggerConnection(refresh_token="persisted-token", blog_id="blog-1"))
    await session.commit()
    service = BloggerConnectionService(session)
    await service.disconnect()
    assert await service.is_connected() is False


async def test_get_refresh_token_raises_when_not_connected(session):
    service = BloggerConnectionService(session)
    try:
        await service.get_refresh_token()
        raise AssertionError("should have raised")
    except ValidationError as exc:
        assert "not connected" in str(exc).lower()


async def test_products_and_articles_list(client):
    from app.core.database import async_session_factory
    from app.schemas.product import ProductCreate
    from app.services.content_service import ContentService
    from app.services.product_service import ProductService

    async with async_session_factory() as session:
        product = await ProductService(session).create(ProductCreate(name="List Gadget", category="Electronics"))
        await ContentService(session).generate(product.id)

    products = (await client.get("/trendera/products")).json()
    assert any(p["name"] == "List Gadget" for p in products)

    articles = (await client.get("/trendera/articles")).json()
    assert any(a["title"] == "List Gadget Review" for a in articles)
    assert any(a["product_name"] == "List Gadget" for a in articles)


async def test_activity_endpoint(client):
    from app.core.database import async_session_factory
    from app.services.audit_service import AuditService

    async with async_session_factory() as session:
        await AuditService(session).record(
            action="product.discovered",
            resource_type="trendera",
            metadata={"message": "Product discovered: X"},
        )
        await session.commit()

    items = (await client.get("/activity")).json()
    assert any(i["message"] == "Product discovered: X" for i in items)
    assert any(i["type"] == "product.discovered" for i in items)


async def test_blogger_status_and_disconnect_endpoints(client):
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        session.add(BloggerConnection(refresh_token="persisted-token", blog_id="blog-1"))
        await session.commit()

    status = (await client.get("/auth/blogger/status")).json()
    assert status["connected"] is True
    assert "refresh_token" not in status

    r = await client.post("/auth/blogger/disconnect")
    assert r.status_code == 200

    status = (await client.get("/auth/blogger/status")).json()
    assert status["connected"] is False
