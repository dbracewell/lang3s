import json
import multiprocessing
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import lang3s.data.db.database as db
from lang3s.data.db.models import ClaimsTable
from lang3s.llm.local_llm import LocalLLM, get_local_llm
from lang3s.models.embedder import Embedder
from lang3s.nlp.claim_extractor import ClaimDocument, extract_claims
from lang3s.services.client.redis_client import CLAIM_EXTRACT_QUEUE_NAME, RedisClient


def caller(
    document: ClaimDocument,
    embedder: Embedder,
    llm_client: LocalLLM,
) -> None:
    valid_sentence_aids = set(
        [sentence.sentence_aid for sentence in document.sentences]
    )
    claims = extract_claims(llm_client, document)
    if not claims:
        return
    embs = embedder([claim.text for claim in claims]).sentence_embeddings
    db.insert_many_objects(
        [
            ClaimsTable(
                sentenceAid=claim.sentence_aid,
                documentId=document.document_id,
                content=claim.text,
                source=claim.source,
                entities=claim.entities,
                embedding=emb,
            )
            for claim, emb in zip(claims, embs)
            if claim.text and claim.sentence_aid in valid_sentence_aids
        ]
    )

    time.sleep(2)


def caller_wrapper(*args, **kwargs):
    try:
        return caller(*args, **kwargs)
    except Exception:
        import traceback

        traceback.print_exc()


def worker():
    redis_client = RedisClient()
    local_llm = get_local_llm()
    embedder = Embedder()

    while True:
        raw_document = redis_client.dequeue(CLAIM_EXTRACT_QUEUE_NAME)
        if not raw_document:
            time.sleep(3)
            continue

        try:
            raw_document = json.loads(raw_document)
            document = ClaimDocument.model_validate(raw_document)
            caller(document=document, embedder=embedder, llm_client=local_llm)
        except Exception as e:
            traceback.print_exc()
            print(f"Error processing document: {e}")

    # with ThreadPoolExecutor(max_workers=4) as thread_pool:
    #     while True:
    #         raw_document = redis_client.dequeue(CLAIM_EXTRACT_QUEUE_NAME)
    #         if not raw_document:
    #             time.sleep(1)
    #             continue
    #
    #         try:
    #             raw_document = json.loads(raw_document)
    #             document = ClaimDocument.model_validate(raw_document)
    #             thread_fn = partial(
    #                 caller_wrapper,
    #                 embedder=embedder,
    #                 llm_client=local_llm,
    #                 document=document,
    #             )
    #             thread_pool.submit(thread_fn)
    #
    #         except Exception as e:
    #             print(f"Error processing document: {e}")


if __name__ == "__main__":
    process = multiprocessing.Process(target=worker)
    try:
        process.start()
    except KeyboardInterrupt:
        print("Shutting down...")
        process.terminate()
        process.join()
        exit(0)
