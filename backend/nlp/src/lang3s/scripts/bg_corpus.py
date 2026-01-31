from collections import Counter

from lang3s_job_service import File

from lang3s import config
from lang3s.data.db.filestore import FILE_STORE
from lang3s.data.db.ngram_stats import NGramDatabase
from lang3s.distributed.broker import broker
from lang3s.nlp.shared_types import TextAnnotation
from lang3s.pipeline import pipeline

config.USE_COREFERENCE = False


class NgramExtractor:
    def __init__(self, n_min: int = 1, n_max: int = 3):
        self.n_min = n_min
        self.n_max = n_max

    def extract(self, tokens: list[TextAnnotation]):
        lemmas = []
        for token in tokens:
            if " " not in token.lemma:
                lemmas.append(token.lemma.lower())
            else:
                lemma_parts = token.lemma.lower().split(" ")
                text_parts = token.text.split(" ")
                for l, t in zip(lemma_parts, text_parts):
                    lemmas.append(l)

        length = len(tokens)

        for size in range(self.n_min, self.n_max + 1):
            for i in range(length - size + 1):
                lemma_tuple = tuple(lemmas[i : i + size])
                yield lemma_tuple


def producer():
    corpuses = ["/Users/ik/Downloads/archives/archive-3/AllCombined.txt"]
    for corpus in corpuses:
        with open(corpus, "r") as f:
            buffer = []
            for line in f:
                line = line.strip()
                if line:
                    buffer.append(line)
                if len(buffer) >= 20:
                    yield File(content="\n".join(buffer))
                    buffer = []
            if buffer:
                yield File(content="\n".join(buffer))


def consumer(files: list[File], consumer_id: int):
    ngram_extractor = NgramExtractor(n_min=1, n_max=3)
    all_lemmas = []
    for doc in pipeline(files, batch_size=1000):
        for sentence in doc.text.sentences:
            for lemmas in ngram_extractor.extract(sentence.tokens):
                all_lemmas.append(lemmas)
    return all_lemmas


def consolidator(batch):
    with NGramDatabase(FILE_STORE.get_file_path("bg_corpus.db")) as ngram_db:
        lemma_counter = Counter(batch)
        n_counter = Counter([len(b) for b in batch])
        ngram_db.batch_increment(lemma_counter)
        ngram_db.increment_total_n(n_counter)


def main():
    broker(
        producer=producer,
        consumer=consumer,
        consolidator=consolidator,
        num_consumers=1,
        consolidator_batch_size=10,
        consumer_batch_size=10,
        # max_queue_size=1000000,
    )


if __name__ == "__main__":
    main()
