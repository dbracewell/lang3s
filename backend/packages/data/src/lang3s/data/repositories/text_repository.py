import numpy as np
from sqlalchemy import Boolean, cast, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.data.models import TextAnnotation as TextAnnotationModel
from lang3s.data.schemas import TextAnnotation as TextAnnotationSchema


class TextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
