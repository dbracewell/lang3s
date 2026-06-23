from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.data.schemas import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
