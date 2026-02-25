import textwrap
from collections import Counter, defaultdict
from typing import Tuple

import numpy as np
import umap
from joblib import Parallel, delayed
from sklearn.cluster._hdbscan import hdbscan
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select

import lang3s.data.db.database as db
from lang3s.data.db.models import KeywordsTable
from lang3s.llm import LLMClient, Message
from lang3s.nlp.shared_types import Text


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


def _create_label(keywords: list[Tuple[str, str, np.ndarray]]) -> list[Tuple[str, str]]:
    client = LLMClient()
    cnt = Counter(k[1] for k in keywords)
    topn = [c for c, v in cnt.most_common(100)]
    prompt = textwrap.dedent(f"""
                    Given the following list of keywords come up with a short noun phrase no more than four words describing the concept/topic. 
                    Make the noun phrase generic and not specific to ONE keyword it should be generic enough to cover any keyword in the category.
                    Give no explanation or reasoning for your answer only the answer and in plain text NO MARKUP.

                    Keywords:
                    {"\n".join(topn)}
                """).strip()
    response = client.sync_chat_completion_last_event([Message.user(prompt)])
    if response.exception:
        return [(k[0], k[1]) for k in keywords]
    else:
        return [(k[0], response.content) for k in keywords]


def generate_keyword_categories():
    stmt = select(KeywordsTable).execution_options(yield_per=100)
    keywords = []
    with db.get_session() as session:
        keyword: KeywordsTable
        for keyword in session.execute(stmt).scalars():
            keywords.append((keyword.id, keyword.keyword, keyword.embedding.to_numpy()))

    reducer = umap.UMAP(
        n_neighbors=15,
        n_components=64,
        metric="cosine",
    )
    reduced = reducer.fit_transform([k[2] for k in keywords])

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=10,
        min_samples=5,
        metric="cosine",
    )
    labels = clusterer.fit_predict(reduced)

    clusters = defaultdict(list)
    for label, keyword in zip(labels, keywords):
        if label == -1:
            continue
        clusters[label].append(keyword)

    with Parallel(
        n_jobs=-1,
        backend="loky",
        inner_max_num_threads=1,
    ) as parallel:
        results = parallel([delayed(_create_label)(v) for _, v in clusters.items()])

    updates = []
    for r in results:
        for kid, category in r:
            updates.append({"id": kid, "category": category})
    return updates
