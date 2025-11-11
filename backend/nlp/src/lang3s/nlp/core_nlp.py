from collections import Counter
from typing import Dict, List

import numpy as np
import spacy
import spacy.tokens
from fastcoref import spacy_component
from more_itertools import first
from sklearn.feature_extraction.text import TfidfVectorizer
from spacy_download import load_spacy

from lang3s.types import AnnotationTypes, Metadata, Text
from lang3s.types.core_types import TextAnnotation
from lang3s.utils import filter_none

test = spacy_component

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
    if language == "en":
        __SPACY_PIPELINES[language].add_pipe(
            "fastcoref",
            config={
                # "model_architecture": "LingMessCoref",
                # "model_path": "biu-nlp/lingmess-coref",
                "device": "cpu",
            },
        )
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
        sentence_annotations = []
        for sentence in doc.sents:
            if sentence.text.strip() == "":
                continue
            sentence_annotations.append(
                text.add_annotation(
                    start=sentence.start,
                    end=sentence.end,
                    sentence_id=sentences[sentence.start],
                    text=sentence.text,
                    type=AnnotationTypes.SENTENCE.value,
                    value=sentence.lemma_,
                    metadata={
                        Metadata.IS_STOPWORD.value: is_sentence_junk(sentence),
                    },
                )
            )

        compute_sentence_weight(sentence_annotations)

        coref_map = {}
        if language == "en":
            for cluster in doc._.coref_clusters:
                spans: List[spacy.tokens.Span] = []

                for span in filter_none(
                    doc.char_span(start, end, label="UNKNOWN")
                    for start, end in cluster
                ):
                    span_ents = list(span.ents)
                    if len(span_ents) == 0:
                        for ent in doc.ents:
                            if ent.start <= span.end and ent.end > span.start:
                                span_ents.append(ent)

                    if len(span_ents) == 0:
                        spans.append(span)
                    elif len(span_ents) > 0:
                        spans.append(span_ents[0])

                most_common: str = first(
                    Counter(
                        span.label_
                        for span in spans
                        if span.label_ != "UNKNOWN"
                    ).most_common(1),
                    ["MISC", 1],
                )[0]

                if most_common == "MISC":
                    cannonical = max(
                        spans,
                        key=lambda s: s.end - s.start,
                    )
                else:
                    cannonical = max(
                        [span for span in spans if span.label_ == most_common],
                        key=lambda s: s.end - s.start,
                    )

                for span in spans:
                    start = span.start
                    if span.label_ == "UNKNOWN":
                        add_ent = True
                        for ent in doc.ents:
                            if ent.start <= span.end and ent.end > span.start:
                                span = ent
                                start = span.start
                                add_ent = False
                                break

                        if add_ent:
                            new_ent = spacy.tokens.Span(
                                doc,
                                start=span.start,
                                end=span.end,
                                label=most_common,
                            )
                            doc.ents = list(doc.ents) + [new_ent]

                    coref_map[start] = cannonical

        entity_map: Dict[int, TextAnnotation] = {}
        for entity in doc.ents:
            annotation = text.add_annotation(
                start=entity.start,
                end=entity.end,
                text=entity.text,
                sentence_id=sentences[entity.sent.start],
                type=AnnotationTypes.ENTITY.value,
                value=entity.label_,
                metadata={Metadata.LEMMA.value: entity.lemma_},
            )
            entity_map[entity.start] = annotation

        for entity in doc.ents:
            annotation = entity_map[entity.start]
            coref = coref_map.get(entity.start, None)
            if coref:
                coref_annotation = entity_map[coref.start]
                if coref_annotation.id != annotation.id:
                    annotation.metadata["coref"] = coref_annotation.id
                    annotation.metadata["coref_text"] = coref_annotation.text

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


def compute_sentence_weight(
    sentences: List[TextAnnotation],
    positional_decay: float = 0.5,
):
    num_sentences = len(sentences)
    if num_sentences == 0:
        raise ValueError("No sentences provided")

    normalized_sentences = [s.to_string(True, True, True) for s in sentences]
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_vectorizer.fit(normalized_sentences)

    # Step 2: Compute TF-IDF weight for each sentence (sum of word IDFs)
    sent_weights = []
    for norm_sent, sent in zip(normalized_sentences, sentences):
        if sent.is_stopword:
            sent_weights.append(0)
        else:
            weight = 0.0
            for word in norm_sent.split():
                if word in tfidf_vectorizer.vocabulary_:
                    idx = tfidf_vectorizer.vocabulary_[word]
                    weight += tfidf_vectorizer.idf_[idx]
            sent_weights.append(weight)

    sent_weights = np.array(sent_weights)

    pos_weights = np.linspace(1.0, positional_decay, num_sentences)
    combined_weights = sent_weights * pos_weights

    if combined_weights.sum() == 0:
        combined_weights = np.ones_like(combined_weights)
    combined_weights /= combined_weights.sum()

    for weight, sentence in zip(combined_weights, sentences):
        sentence.metadata[Metadata.WEIGHT.value] = weight


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
