import argparse
import time

from pydantic import ValidationError
from transformers import AutoTokenizer

from lang3s.core.logger import get_logger
from lang3s.core.parallel import Event, ThreadingManager
from lang3s.core.parallel.redis_queue import RedisQueueSource
from lang3s.data.constants import CLAIM_EXTRACT_QUEUE_NAME
from lang3s.data.db import sync_db_session
from lang3s.data.models import Claim as ClaimModel
from lang3s.data.schemas.claim import DocumentClaimRequest
from lang3s.nlp import Embedder
from lang3s.nlp.components.claim_extractor import ClaimExtractor

logger = get_logger("CLAIM_EXTRACTION_WORKER")
claim_extractor: ClaimExtractor = ClaimExtractor()
embedder: Embedder = Embedder()
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

global_task_id = 0
global_processing = set()


def process_task(item: Event[dict]):
    try:
        request = DocumentClaimRequest.model_validate(item.payload)
        if not request.sentences:
            return Event(payload=0)

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
                return Event(payload=0)

        return Event(payload=token_count)
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
    return Event(payload=0)


def main(workers: int):
    total_documents = 0
    total_tokens = 0
    logger.info(f"Claim Worker started with {workers} workers")
    with ThreadingManager(
        workers=workers,
    ) as manager:
        queue = RedisQueueSource(
            workers=workers,
            queue_name=CLAIM_EXTRACT_QUEUE_NAME,
        )
        start_time = time.perf_counter()
        for r in manager.imap(process_task, queue):
            total_documents += 1
            total_tokens += r.payload
            total_time = time.perf_counter() - start_time
            docs_per_minute = total_documents / total_time * 60
            if total_documents % 10 == 0:
                logger.info(
                    f"Claim Extractor: Processed {total_documents} documents in "
                    f"{total_time:.2f} "
                    f"({docs_per_minute:.2f} docs / minute) "
                    f"({total_tokens / total_time:.2f} tokens / second)"
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
