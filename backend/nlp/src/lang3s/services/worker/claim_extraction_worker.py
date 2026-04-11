import asyncio
import threading
import time

import aiohttp
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
from lang3s.services.client.local_llm_client import LocalLLMClient
from lang3s.services.client.redis_client import (
    CLAIM_EXTRACT_QUEUE_NAME,
    RedisAsyncClient,
)
from lang3s.utils.logger import get_logger

logger = get_logger("CLAIM_EXTRACTION_WORKER")

local_llm = LocalLLMClient()
embedder = Embedder()
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

MAX_TOKENS = 4000
MAX_PROMPT_TOKENS = MAX_TOKENS // 2
total_time = 0
_lock = threading.Lock()


def chunk_text(
    content: str,
    chunk_size: int = MAX_PROMPT_TOKENS,
):
    chunks = []
    sentences = content.split("\n\n")
    current_chunk = ""
    for sentence in sentences:
        if len(tokenizer(current_chunk + sentence)["input_ids"]) < chunk_size:
            current_chunk += sentence + "\n"
        else:
            chunks.append(current_chunk)
            current_chunk = ""

    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


async def process_task(item: bytes):
    start_time = time.perf_counter()
    try:
        request = DocumentClaimRequest.model_validate_json(item)
        token_count = len(tokenizer(request.text)["input_ids"])
        batches = []
        if token_count <= MAX_PROMPT_TOKENS:
            batches.append(request.text)
        else:
            batches.extend(chunk_text(request.text))

        all_claims = []
        for batch in batches:
            response = await local_llm.generate(
                messages=[Message.user(f"Extract claims from: {batch}")],
                adapter_name="claim",
                temperature=0.0,
                max_tokens=max(1000, 8000 - len(tokenizer(batch)["input_ids"])),
                response_model=DocumentClaims,
            )
            if response.parsed:
                all_claims.extend(response.parsed.claims)
        embs = embedder([claim.claim for claim in all_claims]).sentence_embeddings
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
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
    except aiohttp.ClientError as e:
        logger.error(f"API request failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")

    global total_time
    with _lock:
        total_time += time.perf_counter() - start_time


async def process_wrapper(data, semaphore):
    try:
        await process_task(data)
    finally:
        semaphore.release()


async def main():
    max_concurrent_tasks = 2
    semaphore = asyncio.Semaphore(max_concurrent_tasks)
    redis_client = RedisAsyncClient()
    total_documents = 0

    try:
        while True:
            await semaphore.acquire()

            result = await redis_client.dequeue(CLAIM_EXTRACT_QUEUE_NAME, timeout=1)

            if result:
                asyncio.create_task(process_wrapper(result, semaphore))
                total_documents += 1
                if total_documents % 10 == 0:
                    logger.info(
                        f"Claim Extractor: Processed {total_documents} documents in {total_time} ({total_documents / total_time:.2})"
                    )
            else:
                semaphore.release()
                await asyncio.sleep(0.1)  #

    except asyncio.CancelledError:
        logger.info("Shutting down worker...")
    finally:
        await redis_client.close()


if __name__ == "__main__":
    try:
        logger.info("Claim Extraction Worker Started")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
