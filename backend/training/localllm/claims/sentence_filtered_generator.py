import os
from random import shuffle

from jsonlines import jsonlines
from lang3s.nlp.claim_extractor import create_claim_request
from lang3s.pipeline import pipeline
from lang3s_job_service import File


def main():
    files = []
    with jsonlines.open(os.path.expanduser("~/prj/data/base_corpus.jsonl")) as reader:
        for obj in reader:
            files.append(File(**obj))
    shuffle(files)
    files = files[:10_000]
    docs = pipeline(files)
    with jsonlines.open(
        os.path.expanduser("~/prj/data/claims/claims_sentence_filtered_dataset.jsonl"),
        "w",
    ) as writer:
        for doc in docs:
            claims = create_claim_request(doc)
            if claims.sentences:
                for sentence in claims.sentences:
                    writer.write({"text": sentence})


if __name__ == "__main__":
    main()
