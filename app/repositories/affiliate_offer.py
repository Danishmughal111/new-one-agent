"""Affiliate offer cache persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate_offer import AffiliateOfferRecord
from app.repositories.base import BaseRepository


class AffiliateOfferRepository(BaseRepository[AffiliateOfferRecord]):
    """Persistence operations for verified affiliate offers."""

    model = AffiliateOfferRecord

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_product(self, product_id: str) -> AffiliateOfferRecord | None:
        """Return the verified offer for a product, if any."""
        stmt = select(AffiliateOfferRecord).where(AffiliateOfferRecord.product_id == product_id)
        result = await self.session.scalars(stmt)
        return result.first()

    async def save(self, record: AffiliateOfferRecord) -> AffiliateOfferRecord:
        """Upsert a verified offer (one per product). Caller must commit."""
        existing = await self.get_by_product(record.product_id)
        if existing is not None:
            existing.affiliate_url = record.affiliate_url
            existing.provider = record.provider
            existing.provider_product_name = record.provider_product_name
            existing.match_score = record.match_score
            existing.status = record.status
            existing.verified_at = record.verified_at
            await self.session.flush()
            return existing
        self.session.add(record)
        await self.session.flush()
        return record
