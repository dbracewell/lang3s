from typing import List

import spacy
import spacy.tokens
from spacy_download import load_spacy

from lang3s.types import AnnotationTypes, Metadata, Text

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
        sentences = {
            s.start: i for i, s in enumerate(doc.sents) if s.text.strip() != ""
        }
        if len(sentences) == 0:
            continue
        for token in doc:
            text.add_annotation(
                start=token.i,
                end=token.i + 1,
                text=token.text,
                type=AnnotationTypes.TOKEN.value,
                value=token.pos_,
                sentence_id=sentences[token.sent.start],
                embedding=None,
                metadata={
                    Metadata.HEAD.value: token.head.i,
                    Metadata.RELATION.value: token.dep_,
                    Metadata.LEMMA.value: token.lemma_,
                    Metadata.START_CHAR.value: token.idx,
                    Metadata.END_CHAR.value: token.idx + len(token.text),
                    Metadata.IS_STOPWORD.value: is_token_stopword(token),
                },
            )
        for sentence in doc.sents:
            if sentence.text.strip() == "":
                continue
            text.add_annotation(
                start=sentence.start,
                end=sentence.end,
                sentence_id=sentences[sentence.start],
                text=sentence.text,
                type=AnnotationTypes.SENTENCE.value,
                value=sentence.lemma_,
                metadata={
                    Metadata.IS_STOPWORD.value: is_sentence_junk(sentence),
                    "weight": 0.0,
                },
            )

        for entity in doc.ents:
            text.add_annotation(
                start=entity.start,
                end=entity.end,
                text=entity.text,
                sentence_id=sentences[entity.sent.start],
                type=AnnotationTypes.ENTITY.value,
                value=entity.label_,
                metadata={Metadata.LEMMA.value: entity.lemma_},
            )

        try:
            for chunk in doc.noun_chunks:
                text.add_annotation(
                    start=chunk.start,
                    end=chunk.end,
                    sentence_id=sentences[chunk.sent.start],
                    text=chunk.text,
                    type=AnnotationTypes.NOUN_CHUNK.value,
                    value=chunk.label_,
                    metadata={Metadata.LEMMA.value: chunk.lemma_},
                )
        except Exception:
            pass


def is_token_stopword(token: spacy.tokens.Token) -> bool:
    return (
        token.is_stop
        or token.is_bracket
        or token.is_digit
        or token.is_currency
        or token.is_punct
        or token.like_num
    )


def is_sentence_junk(sentence: spacy.tokens.span.Span) -> bool:
    has_verb = any(t.pos_ == "VERB" or t.pos_ == "AUX" for t in sentence)

    if not has_verb:
        return True

    stopwords = sum(
        [1 for t in sentence if is_token_stopword(t) and t.pos_ != "VERB"]
    )
    if stopwords / len(sentence) >= 0.90 or (len(sentence) - stopwords <= 3):
        return True

    return False


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
