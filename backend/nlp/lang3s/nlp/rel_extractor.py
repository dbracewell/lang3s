import spacy
from itertools import combinations
from sentence_transformers import SentenceTransformer, util
import numpy as np

nlp = spacy.load("en_core_web_lg")
embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


# ---------------------------
# Dependency utilities
# ---------------------------
def get_dependency_path(token1, token2):
    ancestors1 = {token1}.union(set(token1.ancestors))
    common_ancestor = None
    for ancestor in token2.ancestors:
        if ancestor in ancestors1:
            common_ancestor = ancestor
            break
    if not common_ancestor:
        return []
    path1, path2 = [], []
    tok = token1
    while tok != common_ancestor:
        path1.append(tok)
        tok = tok.head
    path1.append(common_ancestor)
    tok = token2
    while tok != common_ancestor:
        path2.append(tok)
        tok = tok.head
    path2 = list(reversed(path2))
    return path1 + path2[1:]


MAX_PATH_LEN = 4


def is_valid_relation(path):
    if not path or len(path) > MAX_PATH_LEN:
        return False
    return any(tok.pos_ == "VERB" for tok in path)


def extract_relation_phrase(path):
    if not path:
        return ""
    candidates = []
    for tok in path:
        if tok.pos_ in ("VERB", "AUX", "ADP", "PART"):
            compounds = [
                child.text
                for child in tok.children
                if child.dep_ in ("compound", "prt")
            ]
            full_verb = " ".join(compounds + [tok.lemma_])
            candidates.append(full_verb)
        elif tok.pos_ in ("NOUN", "ADJ") and tok.dep_ in ("attr", "prep", "pobj"):
            candidates.append(tok.lemma_)
    return " ".join(candidates).strip()


def extract_triples(text):
    doc = nlp(text)
    triples = []
    for e1, e2 in combinations(doc.ents, 2):
        path = get_dependency_path(e1.root, e2.root)
        print(
            e1.text,
            " <> ",
            e2.text,
            " => ",
            " -> ".join(f"{tok.text}/{tok.dep_}" for tok in path),
        )
        if is_valid_relation(path):
            rel = extract_relation_phrase(path)
            if rel:
                triples.append((e1.text, rel, e2.text))
    return triples


# ---------------------------
# Relation normalization
# ---------------------------
def normalize_relations(triples, sim_threshold=0.75):
    """
    Groups semantically similar relations together using cosine similarity.
    Returns normalized triples and cluster dictionary.
    """
    rel_phrases = list({r for _, r, _ in triples})
    rel_emb = embedder.encode(rel_phrases, normalize_embeddings=True)

    clusters = []
    used = set()

    for i, r in enumerate(rel_phrases):
        if i in used:
            continue
        cluster = [r]
        used.add(i)
        for j in range(i + 1, len(rel_phrases)):
            if j in used:
                continue
            sim = float(util.cos_sim(rel_emb[i], rel_emb[j]))
            if sim >= sim_threshold:
                cluster.append(rel_phrases[j])
                used.add(j)
        clusters.append(cluster)

    # Pick canonical representative
    canonical = {}
    for cluster in clusters:
        # heuristic: choose shortest relation phrase
        rep = min(cluster, key=len)
        for r in cluster:
            canonical[r] = rep

    # Replace in triples
    normalized_triples = [(e1, canonical.get(rel, rel), e2) for e1, rel, e2 in triples]

    return normalized_triples, clusters


# ---------------------------
# Example
# ---------------------------
text = """
Apple acquired Beats for $3 billion in 2014. 
Google bought YouTube in 2006. 
Facebook purchased Instagram for $1 billion.
Microsoft acquired LinkedIn in 2016.
Amazon took over Whole Foods in 2017.
"""

# triples = extract_triples(text)
# norm_triples, clusters = normalize_relations(triples, sim_threshold=0.7)

# print("🔹 Normalized Triples")
# for t in norm_triples:
#     print(t)

# print("\n🔹 Relation Clusters")
# for c in clusters:
#     print(c)


texts = ["Israel:GPE", "Hamas:ORG", "Jordan:GPE", "イスラエル:GPE", "Israel"]
r = embedder.encode(texts, normalize_embeddings=True)

for i in range(len(texts)):
    r1 = r[i]
    for j in range(i + 1, len(texts)):
        r2 = r[j]
        print(texts[i], " <> ", texts[j], " = ", util.cos_sim(r1, r2))
