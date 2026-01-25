import re
from collections import Counter

import numpy as np
from lang3s_job_service import File

from lang3s import config
from lang3s.data.db.ngram_stats import NGramDatabase
from lang3s.nlp.language import PERSON_PRONOUNS
from lang3s.pipeline import pipeline
from lang3s.shared_types import TextAnnotation

config.USE_COREFERENCE = False


class NgramExtractor:
    def __init__(self, n_min: int = 1, n_max: int = 3):
        self.n_min = n_min
        self.n_max = n_max
        self.valid_pos = [
            "NOUN",
            "PROPN",
            "VERB",
            "ADJ",
            "ADV",
            "ADP",
            "AUX",
            "CCONJ",
            "INTJ",
            "PART",
            "SYM",
            "X",
        ]

        self.non_word_filter = re.compile(r"[^a-zA-Z]+")

    def _filter_phrase(self, tokens):
        if any([t in PERSON_PRONOUNS for t in tokens]):
            return True
        if len(self.non_word_filter.sub("", tokens[0])) == 0:
            return True
        if len(self.non_word_filter.sub("", tokens[-1])) == 0:
            return True
        if all(len(self.non_word_filter.sub("", t)) == 0 for t in tokens):
            return True
        if tokens[0].startswith("'") or tokens[-1].startswith("'"):
            return True

        return False

    def extract(self, tokens: list[TextAnnotation]):
        lemmas = []
        embeddingst = []
        stopwords = []
        for token in tokens:
            if " " not in token.lemma:
                lemmas.append(token.lemma.lower())
                embeddingst.append(token.embedding.astype(np.float16))
                stopwords.append(token.is_stopword)
            else:
                lemma_parts = token.lemma.lower().split(" ")
                text_parts = token.text.split(" ")
                for l, t in zip(lemma_parts, text_parts):
                    lemmas.append(l)
                    embeddingst.append(token.embedding.astype(np.float16))
                    stopwords.append(token.is_stopword)

        length = len(tokens)

        for size in range(self.n_min, self.n_max + 1):
            for i in range(length - size + 1):
                has_entity = any(len(t.entities) > 0 for t in tokens[i : i + size])
                is_valid_pos = all(
                    token.value in self.valid_pos for token in tokens[i : i + size]
                )

                if has_entity or not is_valid_pos:
                    continue

                lemma_tuple = tuple(lemmas[i : i + size])
                stopword_tuple = tuple(stopwords[i : i + size])
                embeddings = embeddingst[i : i + size]

                if all(stopword_tuple) or self._filter_phrase(lemma_tuple):
                    continue

                yield lemma_tuple, embeddings


def main():
    ngram_db = NGramDatabase("/Users/ik/prj/Lang3s/bg_corpus.db")
    ngram_extractor = NgramExtractor(n_min=1, n_max=3)

    def batch_generator(corpus):
        batch = []
        with open(corpus, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    batch.append(File(content=line))
                    if len(batch) >= 500:
                        yield batch
                        batch = []
        if batch:
            yield batch

    def process_corpus(corpus, name):
        for batch in batch_generator(corpus):
            cntr = Counter()
            for doc in pipeline(batch, batch_size=500):
                for sentence in doc.text.sentences:
                    for lemmas, embeddings in ngram_extractor.extract(sentence.tokens):
                        cntr[lemmas] += 1

                ngram_db.batch_increment(cntr)

    process_corpus(
        "/Users/ik/Downloads/archives/archive-3/AllCombined.txt", "simplified_wiki"
    )


main()
