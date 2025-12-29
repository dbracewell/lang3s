import gzip
import importlib.resources
import json
from collections import Counter
from typing import Dict, List, Optional

import numpy as np
import spacy
import spacy.tokens
from fastcoref import spacy_component
from more_itertools.more import first
from sklearn.feature_extraction.text import TfidfVectorizer
from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Token
from spacy.util import filter_spans
from spacy_download import load_spacy

from lang3s import config
from lang3s.shared_types import AnnotationTypes, Metadata
from lang3s.shared_types.text import Text
from lang3s.shared_types.text_annotation import TextAnnotation
from lang3s.utils import decorators, filter_none

test = spacy_component

SPACY_MODELS = {
    "en": "en_core_web_lg",
    "ja": "ja_core_news_lg",
    "es": "es_core_news_lg",
}


@decorators.singleton
class CoreLanguageProcessor:
    def __init__(self):
        self.pipelines = {}
        self.patterns = {}
        self.matchers = {}

        with (
            importlib.resources.files("lang3s.nlp")
            .joinpath("mwe.json.gz")
            .open("rb") as f_in
        ):
            with gzip.open(f_in, "rt") as f_gz:
                mwe_dict = json.load(f_gz)
                for k, mwe in mwe_dict.items():
                    patterns = []
                    for phrase in mwe:
                        tokens = phrase.split()
                        pattern = [{"LEMMA": t} for t in tokens]
                        patterns.append(pattern)
                    self.patterns[k] = patterns

    def get_matcher(self, language: str) -> Optional[Matcher]:
        return self.matchers.get(language, None)

    def get_pipeline(self, language: str):
        if language in self.pipelines:
            return self.pipelines[language]

        model_name = SPACY_MODELS.get(language, SPACY_MODELS["en"])
        nlp = load_spacy(model_name)
        self.pipelines[language] = nlp

        patterns = self.patterns.get(language, [])
        if len(patterns) > 0:
            Token.set_extension("is_mwv", default=False, force=True)
            Token.set_extension("lemma", default=False, force=True)
            matcher = Matcher(nlp.vocab)
            matcher.add("MWV", patterns)
            self.matchers[language] = matcher
            nlp.add_pipe("merge_mwv", last=True)
            nlp.add_pipe("fix_mwv", last=True)

        if language == "en" and config.USE_COREFERENCE:
            nlp.add_pipe(
                "fastcoref",
                config={
                    "device": "cpu",
                },
                last=True,
            )

        return self.pipelines[language]


@Language.component("merge_mwv")
def merge_mwv(doc):
    processor = CoreLanguageProcessor()
    matcher = processor.get_matcher(doc.lang_)
    if matcher is None:
        return doc
    matches = matcher(doc)
    spans = [doc[start:end] for _, start, end in matches]

    spans = filter_spans(spans)

    with doc.retokenize() as retok:
        for span in spans:
            retok.merge(
                span,
                attrs={
                    "_": {
                        "is_mwv": True,
                        "lemma": " ".join([t.lemma_ for t in span]),
                    }
                },
            )
    return doc


@Language.component("fix_mwv")
def fix_mwv(doc):
    for token in doc:
        if token._.is_mwv:
            token.pos_ = "VERB"
            token.tag_ = "VB"
            token.lemma_ = token._.lemma
    return doc


def core_nlp(language: str, texts: List[Text]):
    core = CoreLanguageProcessor()
    spacy_docs = core.get_pipeline(language).pipe(
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
                source="core",
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
                    source="core",
                    metadata={
                        Metadata.IS_STOPWORD.value: is_sentence_junk(sentence),
                    },
                )
            )

        compute_sentence_weight(sentence_annotations)

        coref_map: Dict[int, spacy.tokens.Span] = {}
        handle_coreference(language, doc, coref_map)

        entity_map: Dict[int, TextAnnotation] = {}
        for entity in doc.ents:
            annotation = text.add_annotation(
                start=entity.start,
                end=entity.end,
                text=entity.text,
                sentence_id=sentences[entity.sent.start],
                type=AnnotationTypes.ENTITY.value,
                source="coref",
                value=entity.label_,
                metadata={Metadata.LEMMA.value: entity.lemma_},
            )
            entity_map[entity.start] = annotation

        for entity in doc.ents:
            annotation = entity_map[entity.start]
            coref = coref_map.get(entity.start, None)
            if coref is not None:
                coref_annotation = entity_map[coref.start]
                if coref_annotation.id != annotation.id:
                    annotation["coref"] = coref_annotation.id
                    annotation["coref_text"] = coref_annotation.lemma

        try:
            for chunk in doc.noun_chunks:
                text.add_annotation(
                    start=chunk.start,
                    end=chunk.end,
                    sentence_id=sentences[chunk.sent.start],
                    text=chunk.text,
                    source="coref",
                    type=AnnotationTypes.NOUN_CHUNK.value,
                    value=chunk.label_,
                    metadata={Metadata.LEMMA.value: chunk.lemma_},
                )
        except Exception:
            pass


def handle_coreference(language, doc, coref_map):
    if language == "en" and config.USE_COREFERENCE:
        for cluster in doc._.coref_clusters:
            spans: List[spacy.tokens.Span] = []

            for span in filter_none(
                doc.char_span(start, end, label="UNKNOWN") for start, end in cluster
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

            if len(spans) == 0:
                continue

            most_common: str = first(
                Counter(
                    span.label_ for span in spans if span.label_ != "UNKNOWN"
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

    stopwords = sum([1 for t in sentence if is_token_stopword(t) and t.pos_ != "VERB"])
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
        sentence[Metadata.WEIGHT.value] = weight
