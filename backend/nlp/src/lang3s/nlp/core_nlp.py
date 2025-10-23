from typing import List

import spacy
from spacy_download import load_spacy

from lang3s.core import Text
from lang3s.core.metadata import AnnotationTypes

__SPACY_MODELS = {
    "en": "en_core_web_lg",
    "ja": "ja_core_news_lg",
    "es": "es_core_news_lg",
    "de": "de_core_news_lg",
    "fr": "fr_core_news_lg",
    "nl": "nl_core_news_lg",
    "zh": "zh_core_web_lg",
}

__SPACY_PIPELINES = {}


def __get_spacy_pipeline(language: str) -> spacy.language.Language:
    if language in __SPACY_PIPELINES:
        return __SPACY_PIPELINES[language]
    model_name = __SPACY_MODELS.get(language, __SPACY_MODELS["en"])
    __SPACY_PIPELINES[language] = load_spacy(model_name)
    return __SPACY_PIPELINES[language]


def core_nlp(language: str, texts: List[Text]):
    spacy_docs = __get_spacy_pipeline(language).pipe(
        [text.text for text in texts], batch_size=100
    )
    for text, doc in zip(texts, spacy_docs):
        text.embedding = doc.vector.tolist()
        for token in doc:
            text.add_annotation(
                start=token.i,
                end=token.i + 1,
                text=token.text,
                type=AnnotationTypes.TOKEN.value,
                value=token.pos_,
                embedding=None,
                metadata={
                    "head": token.head.i,
                    "relation": token.dep_,
                    "lemma": token.lemma_,
                    "start_char": token.idx,
                    "end_char": token.idx + len(token.text),
                },
            )
        for sentence in doc.sents:
            text.add_annotation(
                start=sentence.start,
                end=sentence.end,
                text=sentence.text,
                type=AnnotationTypes.SENTENCE.value,
                value=sentence.lemma_,
                embedding=sentence.vector.tolist(),
            )
        for entity in doc.ents:
            text.add_annotation(
                start=entity.start,
                end=entity.end,
                text=entity.text,
                type=AnnotationTypes.ENTITY.value,
                value=entity.label_,
                embedding=entity.vector.tolist(),
            )

        try:
            for chunk in doc.noun_chunks:
                text.add_annotation(
                    start=chunk.start,
                    end=chunk.end,
                    text=chunk.text,
                    type=AnnotationTypes.NOUN_CHUNK.value,
                    value=chunk.label_,
                    embedding=chunk.vector.tolist(),
                )
        except Exception:
            pass


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


def overlaps(t1, t2):
    return t1.idx < t2.end_char and (t1.idx + len(t1.text)) > t2.start_char


def extract_relation_phrase(path, e1, e2):
    # Keep verbs, prepositions, or important nouns/adjectives
    rel_tokens = [
        tok.lemma_
        for tok in path
        if not overlaps(tok, e1)
        and not overlaps(tok, e2)
        and tok.pos_ in ("VERB", "ADP", "AUX", "NOUN")
    ]
    return " ".join(rel_tokens)
