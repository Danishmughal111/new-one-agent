"""TrendEra product service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate


class ProductService:
    """Business logic for product/topic intake."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._repo = ProductRepository(session)

    async def create(self, data: ProductCreate) -> Product:
        """Persist a submitted product."""
        product = Product(
            name=data.name,
            description=data.description,
            category=data.category,
            price_amount=data.price_amount,
            price_currency=data.price_currency,
            image_url=data.image_url,
            region=data.region,
            affiliate_url=data.affiliate_url,
            metadata_=data.metadata,
        )
        product = await self._repo.add(product)
        await self.session.commit()
        return product

    async def get(self, product_id: str) -> Product:
        """Fetch a product by id."""
        product = await self._repo.get(product_id)
        if product is None:
            raise NotFoundError("Product", product_id)
        return product