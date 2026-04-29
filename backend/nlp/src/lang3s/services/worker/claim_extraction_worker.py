import asyncio
import math
import os
import time

from pydantic import ValidationError
from transformers import AutoTokenizer

import lang3s.data.db.database as db
from lang3s.data.db.models import ClaimsTable
from lang3s.llm import Message
from lang3s.models.embedder import Embedder
from lang3s.nlp.claim_extractor import (
    DocumentClaimRequest,
    DocumentClaims,
)
from lang3s.parallel.core import Engine, Event
from lang3s.parallel.manager import TaskManager
from lang3s.parallel.queue import QueueFactory, QueueType
from lang3s.services.client.local_llm_client import LocalLLMClient
from lang3s.services.client.redis_client import (
    CLAIM_EXTRACT_QUEUE_NAME,
)
from lang3s.utils.logger import get_logger

logger = get_logger("CLAIM_EXTRACTION_WORKER")
_local_llm: LocalLLMClient | None = None
_embedder: Embedder | None = None
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")


def get_llm() -> LocalLLMClient:
    global _local_llm
    if _local_llm is None:
        _local_llm = LocalLLMClient()
    return _local_llm  # type: ignore


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder  # type: ignore


def init_worker():
    logger.info(f"Initialized Claim Extraction Worker: pid={os.getpid()}")
    get_embedder()
    get_llm()


MAX_TOKENS = 3000
MAX_PROMPT_TOKENS = math.floor(MAX_TOKENS / 2)


def chunk_text(
    sentences: list[str],
    chunk_size: int = MAX_PROMPT_TOKENS,
):
    chunks = []
    total_tokens = 0
    current_chunk = ""
    current_chunk_tokens = 0
    sentence_count = 0
    for sentence in sentences:
        num_tokens = len(tokenizer(current_chunk + "\n" + sentence)["input_ids"])

        if sentence_count < 5 and num_tokens < chunk_size:
            sentence_count += 1
            current_chunk_tokens = num_tokens
            current_chunk += sentence + "\n"
        else:
            total_tokens += current_chunk_tokens
            sentence_count = 1
            current_chunk_tokens = len(tokenizer(sentence)["input_ids"])
            chunks.append(current_chunk)
            current_chunk = sentence

    if current_chunk:
        total_tokens += current_chunk_tokens
        chunks.append(current_chunk.strip())
    return total_tokens, chunks


async def process_task(item: Event[dict]):
    try:
        request = DocumentClaimRequest.model_validate(item.data)
        if not request.sentences:
            return 0
        token_count, batches = chunk_text(request.sentences)
        all_claims = []
        for batch in batches:
            batch_token_size = len(tokenizer(batch)["input_ids"])
            response = await get_llm().generate(
                messages=[Message.user(f"Extract claims from: {batch}")],
                adapter_name="claim",
                temperature=0.0,
                max_tokens=MAX_TOKENS - batch_token_size,
                response_model=DocumentClaims,
                presence_penalty=1.5,
            )
            if response.parsed:
                all_claims.extend(response.parsed.claims)
        embs = get_embedder()([claim.claim for claim in all_claims]).sentence_embeddings
        db.insert_many_objects(
            [
                ClaimsTable(
                    documentId=request.documentId,
                    claim=claim.claim,
                    source=claim.source or "UNKNOWN",
                    embedding=emb,
                )
                for claim, emb in zip(all_claims, embs)
                if claim.claim
            ]
        )
        return token_count
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
    return 0


async def main():
    total_documents = 0
    total_tokens = 0
    WORKER_COUNT = 3
    with QueueFactory() as factory:
        with TaskManager(
            Engine.ASYNC,
            workers=WORKER_COUNT,
            initializer=init_worker,
        ) as runner:
            queue = factory(
                queue_type=QueueType.REDIS,
                queue_name=CLAIM_EXTRACT_QUEUE_NAME,
            )
            start_time = time.perf_counter()
            async for r in runner.async_map(
                process_task,
                queue,
            ):
                total_tokens += r
                total_documents += 1 if r > 0 else 0
                total_time = time.perf_counter() - start_time
                if total_documents % 10 == 0:
                    logger.info(
                        f"Claim Extractor: Processed {total_documents} documents in {total_time:.2f} ({total_documents / total_time:.2f} docs / second) ({total_tokens / total_time:.2f} tokens / second)"
                    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
