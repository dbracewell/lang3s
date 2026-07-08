import numpy as np
from sqlalchemy import Boolean, cast, func, not_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.exceptions import NotFoundException
from lang3s.data.models import Document as DocumentModel
from lang3s.data.models import Text as TextModel
from lang3s.data.models import TextAnnotation as TextAnnotationModel
from lang3s.data.schemas import Document as DocumentSchema
from lang3s.data.schemas import TextAnnotation as TextAnnotationSchema
from lang3s.data.schemas.common import PaginatedQuery
from lang3s.data.schemas.text import DocumentInfo, DocumentListResponse


class TextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_document(self, document_id: str) -> DocumentSchema:
        doc_model: DocumentModel | None = (
            await self.session.scalars(
                select(DocumentModel).where(DocumentModel.id == document_id)
            )
        ).first()
        if not doc_model:
            raise NotFoundException()
        return DocumentSchema.from_database(doc_model)

    async def list_documents(self, query: PaginatedQuery) -> DocumentListResponse:
        if query.cursor == 1:
            total_docs = (
                await self.session.scalar(select(func.count(DocumentModel.id))) or 0
            )
        else:
            total_docs = 0

        stmt = (
            select(DocumentModel.id, DocumentModel.title, TextModel.content)
            .join(TextModel)
            .order_by(DocumentModel.id)
            .offset(query.offset)
            .limit(query.limit + 1)
        )
        result = await self.session.execute(stmt)
        next_cursor, docs = query.generate_page(
            [
                DocumentInfo(
                    id=doc_id,
                    title=title,
                    snippet=f"{snippet[:512]}...",
                )
                for doc_id, title, snippet in result
            ]
        )
        return DocumentListResponse(
            items=docs,
            total=total_docs,
            next_cursor=next_cursor,
        )

    async def get_semantically_similar_sentences(
        self,
        embedding: np.ndarray | list[float],
        randomize: bool = False,
        limit: int = 500,
        min_similarity: float = 0.1,
    ) -> list[TextAnnotationSchema]:

        embedding_list = (
            embedding if isinstance(embedding, list) else embedding.tolist()
        )
        similarity_score = 1 - TextAnnotationModel.embedding.cosine_distance(
            embedding_list
        )
        stmt = (
            select(TextAnnotationModel)
            .where(
                TextAnnotationModel.type_ == "sentence",
                similarity_score >= min_similarity,
                not_(cast(TextAnnotationModel.metadata_json["is_stopword"], Boolean)),
            )
            .order_by(func.random() if randomize else similarity_score.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        sentences = []
        annotation: TextAnnotationModel
        for annotation in result.all():
            sentences.append(annotation)
        return sentences

    async def get_random_sentences(
        self,
        limit: int = 500,
    ) -> list[TextAnnotationSchema]:
        stmt = (
            select(TextAnnotationModel)
            .where(
                TextAnnotationModel.type_ == "sentence",
                not_(cast(TextAnnotationModel.metadata_json["is_stopword"], Boolean)),
            )
            .order_by(func.random())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return [TextAnnotationSchema.model_validate(a) for a in result.all()]

    async def full_text_sentence_search(
        self,
        query: str,
        limit: int = 500,
    ) -> list[TextAnnotationSchema]:
        stmt = (
            select(TextAnnotationModel)
            .where(
                not_(TextAnnotationModel.is_stopword),
                TextAnnotationModel.type_ == "sentence",
                TextAnnotationModel.content.op("&@~")(query),
            )
            .order_by(
                func.dense_rank().over(
                    order_by=func.pgroonga_score(text("tableoid"), text("ctid")).desc()
                )
            )
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return [TextAnnotationSchema.model_validate(a) for a in result.all()]
