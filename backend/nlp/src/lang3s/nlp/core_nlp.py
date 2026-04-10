import gzip
import importlib.resources
import json
import os.path
import re
from typing import Dict, List, Optional

import numpy as np
import spacy.tokens
from sklearn.feature_extraction.text import TfidfVectorizer
from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans
from spacy_download import load_spacy

from lang3s import config
from lang3s.nlp.language import is_person_pronoun
from lang3s.nlp.metadata import Metadata
from lang3s.nlp.shared_types import (
    AnnotationTypes,
    Document,
    TextAnnotation,
)
from lang3s.utils.meta import SingletonMeta
from lang3s.utils.urls import normalize_url

SPACY_MODELS = {
    "en": "en_core_web_sm",
    "ja": "ja_core_news_sm",
    "es": "es_core_news_sm",
}


@Language.factory("social_media_matcher")
class SocialMatcher:
    def __init__(self, nlp, name):
        self.nlp = nlp
        self.tag_pattern = re.compile(r"(?u)(?<!\w)([#@])\w+")
        self.url_pattern = re.compile(r"(https?://\S+|www\.\S+)")

    def __call__(self, doc):
        matches = []

        # --- A. Find Hashtags and Mentions ---
        for match in self.tag_pattern.finditer(doc.text):
            start, end = match.span()
            span = doc.char_span(start, end, alignment_mode="expand")
            if span:
                label = "hashtag" if span.text.startswith("#") else "mention"
                span.label_ = label
                matches.append(span)

        # --- B. Find URLs ---
        for match in self.url_pattern.finditer(doc.text):
            start, end = match.span()
            span = doc.char_span(start, end, alignment_mode="expand")
            if span:
                span.label_ = "url"
                matches.append(span)

        # --- C. Update Entities ---
        # Filter duplicates and overwrite entities
        doc.ents = filter_spans(list(doc.ents) + matches)

        # --- D. Merge and Fix POS ---
        with doc.retokenize() as retokenizer:
            for ent in doc.ents:
                # We only want to touch our specific entities
                if ent.label_ in ["hashtag", "mention", "url"]:
                    # 1. Determine the correct POS tag
                    if ent.label_ == "url":
                        target_pos = "X"  # Universal Dependency for "Other"
                    else:
                        target_pos = "PROPN"  # Proper Noun for hashtags/mentions

                    # 2. Define the attributes to overwrite
                    attrs = {"POS": target_pos, "ENT_TYPE": ent.label_}

                    # 3. Merge and apply the POS tag
                    retokenizer.merge(ent, attrs=attrs)

        return doc


class CoreLanguageProcessor(metaclass=SingletonMeta):
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

    def get_pipeline(self, language: str) -> Language:
        if language in self.pipelines:
            return self.pipelines[language]

        model_name = SPACY_MODELS.get(language, SPACY_MODELS["en"])
        disabled = []
        # if language == "en":
        #     disabled.append("ner")

        nlp = load_spacy(model_name, disable=disabled)
        if language == "en":
            verbs = spacy.load(
                os.path.join(config.MODELS_DIR, "spacy", "en"),
            )
            for pipe in ["tok2vec", "ner"]:
                if pipe in nlp.pipe_names:
                    nlp.remove_pipe(pipe)
            nlp.add_pipe("tok2vec", source=verbs, before="tagger")
            nlp.add_pipe("ner", source=verbs, last=True)

        self.pipelines[language] = nlp
        nlp.add_pipe("social_media_matcher", last=True)
        # patterns = self.patterns.get(language, [])

        # if len(patterns) > 0:
        # Token.set_extension("is_mwv", default=False, force=True)
        # Token.set_extension("lemma", default=False, force=True)
        # matcher = Matcher(nlp.vocab)
        # matcher.add("MWV", patterns)
        # self.matchers[language] = matcher
        # nlp.add_pipe("merge_mwv", last=True)
        # nlp.add_pipe("fix_mwv", last=True)

        return self.pipelines[language]


# @Language.component("merge_mwv")
# def merge_mwv(doc):
#     processor = CoreLanguageProcessor()
#     matcher = processor.get_matcher(doc.lang_)
#     if matcher is None:
#         return doc
#     matches = matcher(doc)
#     spans = [doc[start:end] for _, start, end in matches]
#
#     spans = filter_spans(spans)
#
#     with doc.retokenize() as retok:
#         for span in spans:
#             retok.merge(
#                 span,
#                 attrs={
#                     "_": {
#                         "is_mwv": True,
#                         "lemma": " ".join([t.lemma_ for t in span]),
#                     }
#                 },
#             )
#     return doc
#
#
# @Language.component("fix_mwv")
# def fix_mwv(doc):
#     for token in doc:
#         if token._.is_mwv:
#             token.pos_ = "VERB"
#             token.tag_ = "VB"
#             token.lemma_ = token._.lemma
#     return doc
#


def core_nlp(language: str, texts: List[Document]):
    core = CoreLanguageProcessor()
    nlp = core.get_pipeline(language)
    with nlp.memory_zone():
        _core_nlp(nlp, texts)


def convert_to_lang3s(spacy_doc: Doc, lang3s_doc: Document):
    all_mentions = []
    all_hashtags = []
    all_urls = []
    text = lang3s_doc.text
    text[Metadata.LANGUAGE] = spacy_doc.lang_

    sentences = {
        s.start: i for i, s in enumerate(spacy_doc.sents) if s.text.strip() != ""
    }
    if len(sentences) == 0:
        return
    for token in spacy_doc:
        metadata = {
            Metadata.HEAD: token.head.i,
            Metadata.RELATION: token.dep_,
            Metadata.LEMMA: token.lemma_,
            Metadata.START_CHAR: token.idx,
            Metadata.END_CHAR: token.idx + len(token.text),
            Metadata.IS_STOPWORD: is_token_stopword(token),
        }

        gender_feats = token.morph.get("Gender", None)
        if gender_feats:
            metadata[Metadata.GENDER] = gender_feats[0]

        number_feats = token.morph.get("Number", None)
        if number_feats:
            metadata[Metadata.NUMBER] = number_feats[0]

        text.add_annotation(
            start=token.i,
            end=token.i + 1,
            text=token.text,
            type=AnnotationTypes.TOKEN.value,
            value=token.pos_,
            sentence_id=sentences[token.sent.start],
            source="core",
            embedding=None,
            metadata=metadata,
        )

    sentence_annotations = []
    for sentence in spacy_doc.sents:
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

    entity_map: Dict[int, TextAnnotation] = {}
    entity: Span
    for entity in spacy_doc.ents:
        label = entity.label_
        if is_person_pronoun(entity) and entity.text != "US":
            label = "PERSON"

        metadata = {Metadata.LEMMA.value: entity.lemma_}
        if label == "hashtag":
            metadata["hashtag"] = entity.text[1:]
            all_hashtags.append(entity.text[1:])
        if label == "mention":
            metadata["mention"] = entity.text[1:]
            all_mentions.append(entity.text[1:])
        if label == "url":
            metadata["url"] = normalize_url(entity.text)
            all_urls.append(metadata["url"])

        annotation_type = AnnotationTypes.ENTITY.value
        if spacy_doc.lang_ == "en":
            annotation_type = AnnotationTypes.SENSE.value
        annotation = text.add_annotation(
            start=entity.start,
            end=entity.end,
            text=entity.text,
            sentence_id=sentences[entity.sent.start],
            type=annotation_type,
            source="core",
            value=label,
            metadata=metadata,
        )
        entity_map[entity.start] = annotation

    try:
        for chunk in spacy_doc.noun_chunks:
            text.add_annotation(
                start=chunk.start,
                end=chunk.end,
                sentence_id=sentences[chunk.sent.start],
                text=chunk.text,
                source="core",
                type=AnnotationTypes.NOUN_CHUNK.value,
                value=chunk.label_,
                metadata={Metadata.LEMMA.value: chunk.lemma_},
            )
    except Exception:
        pass
    finally:
        del spacy_doc

    if all_mentions:
        lang3s_doc["mentions"] = all_mentions
    if all_hashtags:
        lang3s_doc["hashtags"] = all_hashtags
    if all_urls:
        lang3s_doc["urls"] = all_urls


def _core_nlp(nlp: Language, docs: List[Document]):
    batch_size = 50
    spacy_docs = nlp.pipe((doc.text.text for doc in docs), batch_size=batch_size)

    for lang3s_doc, spacy_doc in zip(docs, spacy_docs):
        convert_to_lang3s(spacy_doc, lang3s_doc)

    del spacy_docs


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

    normalized_sentences = [s.to_string(True, True, True).strip() for s in sentences]
    total_len = sum(len(text) for text in normalized_sentences)
    if total_len >= 256:
        try:
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
            else:
                combined_weights /= combined_weights.sum()
        except ValueError:
            combined_weights = np.ones(len(normalized_sentences))
    else:
        combined_weights = np.ones(len(normalized_sentences))

    for weight, sentence in zip(combined_weights, sentences):
        sentence[Metadata.WEIGHT.value] = weight
