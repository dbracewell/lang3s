from typing import Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from lang3s.shared_types import Text


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
