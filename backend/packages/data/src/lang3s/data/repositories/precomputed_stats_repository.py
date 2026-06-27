from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.exceptions import NotFoundException
from lang3s.data.models.precomputed_stats import (
    PreComputedStats as PreComputedStatsModel,
)
from lang3s.data.schemas.precomputed_stats import (
    PreComputedStats as PreComputedStatsSchema,
)


class PreComputedStatsRepository:
    def __init__(self, client: AsyncSession):
        self.client = client

    async def get_by_id(self, id: int) -> PreComputedStatsSchema:
        r = await self.client.get(PreComputedStatsModel, id)
        if not r:
            raise NotFoundException()
        return PreComputedStatsSchema.model_validate(r)

    async def get_by_name(self, name: str) -> PreComputedStatsSchema:
        item = await self.client.scalar(
            select(PreComputedStatsModel).where(PreComputedStatsModel.name == name)
        )
        if not item:
            raise NotFoundException()
        return PreComputedStatsSchema.model_validate(item)
