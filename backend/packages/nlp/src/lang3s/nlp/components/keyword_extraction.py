import textwrap
from collections import Counter
from typing import NamedTuple, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from lang3s.agent.llm import LLMClient, Message
from lang3s.core.exceptions import try_catch
from lang3s.core.logger import get_logger
from lang3s.data.schemas import Text


class KeywordItem(NamedTuple):
    id: str
    keyword: str
    embedding: np.ndarray


def mmr_rank(
    doc_embedding, candidate_embeddings, candidates, top_n=5, diversity=0.7
) -> list[Tuple[str, np.ndarray]]:
    """
    Selects keywords using Maximal Marginal Relevance.

    Args:
        doc_embedding (np.array): The embedding of the full document (1, dim).
        candidate_embeddings (np.array): Embeddings of all candidate keywords (N, dim).
        candidates (list): List of candidate strings.
        top_n (int): Number of keywords to extract.
        diversity (float): 0.0 (minimal diversity) to 1.0 (max diversity).
    """

    candidate_similarity = cosine_similarity(candidate_embeddings, doc_embedding)
    candidate_similarity = candidate_similarity.reshape(-1, 1)
    weighting = np.linspace(0, 0.2, 5)  # weight longer keywords a little more
    weights = np.array([weighting[min(len(c.split()), 4)] for c in candidates]).reshape(
        -1, 1
    )
    candidate_similarity += weights
    keywords_idx = [np.argmax(candidate_similarity).item()]
    candidates_idx = [i for i in range(len(candidates)) if i != keywords_idx[0]]

    for _ in range(top_n - 1):
        # 1. Get relevance of remaining candidates to the document
        candidate_similarities = candidate_similarity[candidates_idx, :]

        # 2. Get similarity of remaining candidates to ALREADY selected keywords
        # Result shape: (remaining_candidates, selected_keywords)
        target_similarities = cosine_similarity(
            candidate_embeddings[candidates_idx], candidate_embeddings[keywords_idx]
        )
        target_similarities = target_similarities.reshape(
            len(candidates_idx), len(keywords_idx)
        )
        # 3. Calculate MMR score
        # We take the max similarity to any selected keyword (redundancy penalty)
        mmr_score = (
            1 - diversity
        ) * candidate_similarities - diversity * target_similarities.max(
            axis=1
        ).reshape(-1, 1)

        # 4. Pick the candidate with the highest MMR score
        mmr_idx = candidates_idx[np.argmax(mmr_score)]

        keywords_idx.append(mmr_idx)
        candidates_idx.remove(mmr_idx)
        if len(candidates_idx) == 0:
            break

    return [(candidates[idx], candidate_embeddings[idx]) for idx in keywords_idx]


def extract_keywords(text: Text, top_n=5, diversity=0.5):
    candidates = []
    candidate_embeddings = []
    for sentence in text.sentences:
        buffer_text = []
        buffer_embedding = []
        buffer_pos = []
        for token in sentence.tokens:
            if (
                (token.value == "NOUN" or token.value == "ADJ")
                and len(token.entities) == 0
                and not token.is_stopword
            ):
                buffer_pos.append(token.value)
                buffer_text.append(token.lemma.lower())
                buffer_embedding.append(token.embedding)
            elif len(buffer_text) > 0:
                if "NOUN" in buffer_pos:
                    candidates.append(" ".join(buffer_text))
                    candidate_embeddings.append(
                        np.sum(buffer_embedding, axis=0) / len(buffer_embedding)
                    )
                buffer_text = []
                buffer_embedding = []
                buffer_pos = []
        if len(buffer_text) > 0 and "NOUN" in buffer_pos:
            candidates.append(" ".join(buffer_text))
            candidate_embeddings.append(
                np.sum(buffer_embedding, axis=0) / len(buffer_embedding)
            )

    final_candidates = []
    final_candidate_embeddings = []
    for idx, (c, e) in enumerate(zip(candidates, candidate_embeddings)):
        if len(c.split()) > 1:
            final_candidates.append(c)
            final_candidate_embeddings.append(e)
        else:
            add = True
            for c2 in candidates[idx + 1 :]:
                if len(c2.split()) == 1:
                    continue
                if c in c2.split():
                    add = False
                    break
            if add:
                final_candidates.append(c)
                final_candidate_embeddings.append(e)

    if len(final_candidates) < top_n:
        return [
            (keyword, embedding)
            for keyword, embedding in zip(final_candidates, final_candidate_embeddings)
        ]

    keywords = mmr_rank(
        text.embedding.reshape(1, -1),
        np.stack(final_candidate_embeddings),
        final_candidates,
        top_n=top_n,
        diversity=diversity,
    )
    return keywords


def _create_label(keywords: list[KeywordItem]) -> list[Tuple[str, str]]:
    client = LLMClient()
    cnt = Counter(k.keyword for k in keywords)
    topn = [c for c, v in cnt.most_common(100)]
    logger = get_logger("KEYWORD_EXTRACTION")
    topn_str = "\n".join(topn)
    prompt = textwrap.dedent(f"""
                    Given the following list of keywords come up with a short noun phrase no more than four words describing the concept/topic. 
                    Make the noun phrase generic and not specific to ONE keyword it should be generic enough to cover any keyword in the category.
                    Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.

                    Keywords:
                    {topn_str}
                """).strip()  # noqa: E501

    with try_catch(on_error=lambda e: logger.error(e)):
        response = client.sync_chat_last_event([Message.user(prompt)])
        if not response.exception and response.content:
            return [(k.id, response.content) for k in keywords]

    return [(k.id, k.keyword) for k in keywords]


def generate_keyword_categories():
    return []
    # stmt = (
    #     select(KeywordsTable)
    #     .where(KeywordsTable.category.is_(None))
    #     .execution_options(yield_per=100)
    # )
    # keywords: list[KeywordItem] = []
    # embeddings: list[np.ndarray] = []
    # with db.get_session() as session:
    #     keyword: KeywordsTable
    #     for keyword in session.execute(stmt).scalars():
    #         keywords.append(
    #             KeywordItem(
    #                 id=keyword.id,
    #                 keyword=keyword.keyword,
    #                 embedding=keyword.embedding,
    #             )
    #         )
    #         embeddings.append(keyword.embedding.to_numpy())
    #
    # clusterer = DefaultOfflineClusterer[KeywordItem](
    #     min_cluster_size=10,
    #     metric="cosine",
    #     n_components=64,
    #     clustering_algorithm="hdbscan",
    # )
    # clusters = clusterer.fit(keywords, embeddings)
    # parallel: Parallel
    # with Parallel(
    #     n_jobs=-1,
    #     backend="threading",
    #     inner_max_num_threads=1,
    # ) as parallel:
    #     results = parallel([delayed(_create_label)(c.items) for c in clusters])
    #
    # return [{"id": kid, "category": category} for r in results for kid, category in r]
