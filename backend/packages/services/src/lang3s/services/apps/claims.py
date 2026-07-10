import argparse
import time

from pydantic import ValidationError
from sqlalchemy_utils import refresh_materialized_view
from transformers import AutoTokenizer

from lang3s.core.logger import get_logger
from lang3s.core.parallel import Event, ThreadingManager
from lang3s.core.parallel.atomic import ThreadSafeCounter
from lang3s.core.parallel.redis_queue import RedisQueueSource
from lang3s.data.constants import CLAIM_EXTRACT_QUEUE_NAME
from lang3s.data.db import sync_db_session
from lang3s.data.models import Claim as ClaimModel
from lang3s.data.models import DocumentKeywords, KeywordSimilarities
from lang3s.data.schemas.claim import DocumentClaimRequest
from lang3s.nlp import Embedder
from lang3s.nlp.components.claim_extractor import ClaimExtractor

logger = get_logger("CLAIM_EXTRACTION_WORKER")
claim_extractor: ClaimExtractor = ClaimExtractor()
embedder: Embedder = Embedder()
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

_threads_working = ThreadSafeCounter()
_processed_count = ThreadSafeCounter()
REFRESH_INTERVAL = 100


def create_views():
    with sync_db_session(autocommit=True) as session:
        refresh_materialized_view(
            session=session,
            name=DocumentKeywords.__table__.name,
            concurrently=True,
        )
        refresh_materialized_view(
            session=session,
            name=KeywordSimilarities.__table__.name,
            concurrently=True,
        )


def process_task(item: Event[dict]):
    global _threads_working
    global _processed_count

    try:
        request = DocumentClaimRequest.model_validate(item.payload)

        if request.documentId == "job:complete":
            while _threads_working.value > 0:
                time.sleep(1)

            logger.info("Finishing claim processing...")
            with sync_db_session(autocommit=True) as session:
                create_views()
            logger.info("Finished claim processing")
            return Event(
                payload={
                    "tokens": 0,
                    "time": 0,
                },
            )

        if _processed_count.value % REFRESH_INTERVAL == 0:
            create_views()

        if not request.sentences:
            return Event(
                payload={
                    "tokens": 0,
                    "time": 0,
                },
            )

        _threads_working.increment(1)

        start_time = time.perf_counter()
        try:
            token_count = len(tokenizer(" ".join(request.sentences))["input_ids"])
            all_claims = claim_extractor.extract(
                request.documentId,
                request.sentences,
            )
            if all_claims:
                embs = embedder([c.claim for c in all_claims]).sentence_embeddings
                for claim, emb in zip(all_claims, embs):
                    claim.embedding = emb

                try:
                    with sync_db_session() as session:
                        for claim in all_claims:
                            session.add(ClaimModel(**claim.model_dump()))
                        session.commit()
                except Exception as e:
                    logger.error(f"Exception during database writing: {e}")
                    return Event(
                        payload={
                            "tokens": 0,
                            "time": 0,
                        },
                    )
                _processed_count.increment(1)

        finally:
            _threads_working.decrement(1)

        return Event(
            payload={
                "tokens": token_count,
                "time": (time.perf_counter() - start_time),
            },
        )

    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")

    return Event(
        payload={
            "tokens": 0,
            "time": 0,
        },
    )


def main(workers: int):
    total_documents = 0
    total_tokens = 0
    total_time = 0
    logger.info(f"Claim Worker started with {workers} workers")
    with ThreadingManager(
        workers=workers,
    ) as manager:
        queue = RedisQueueSource(
            workers=workers,
            queue_name=CLAIM_EXTRACT_QUEUE_NAME,
        )
        r: Event
        for r in manager.imap(process_task, queue):
            total_documents += 1
            total_tokens += r.payload["tokens"]
            total_time += r.payload["time"]
            avg_worker_time = total_time / workers
            docs_per_minute = total_documents / avg_worker_time * 60
            tokens_per_second = total_tokens / avg_worker_time

            if total_documents % 10 == 0:
                logger.info(
                    f"Claim Extractor: Processed {total_documents} documents in "
                    f"{avg_worker_time:.2f} "
                    f"({docs_per_minute:.2f} docs / minute) "
                    f"({tokens_per_second:.2f} tokens / second)"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_workers",
        help="The number of worker processes to use",
        default=4,
        type=int,
    )
    args = parser.parse_args()
    main(args.num_workers)
