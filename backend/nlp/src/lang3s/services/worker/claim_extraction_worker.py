import asyncio

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

MAX_CONTENT_SIZE = 3000


def chunk_text(
    content: str,
    chunk_size: int = MAX_CONTENT_SIZE,
    stride: int = 500,
):
    chunks = []
    for i in range(0, len(content), chunk_size - stride):
        chunks.append(content[i : i + chunk_size - stride])
    return chunks


async def process_task(item: bytes, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            print("Processing Claim")
            request = DocumentClaimRequest.model_validate_json(item)
            token_count = len(tokenizer(request.text)["input_ids"])
            batches = []
            if token_count <= MAX_CONTENT_SIZE:
                batches.append(request.text)
            else:
                batches.extend(chunk_text(request.text))

            all_claims = []
            for batch in batches:
                response = await local_llm.generate(
                    messages=[Message.user(f"Extract claims from: {batch}")],
                    adapter_name="claim",
                    temperature=0.0,
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


async def main():
    max_concurrent_tasks = 10
    semaphore = asyncio.Semaphore(max_concurrent_tasks)
    redis_client = RedisAsyncClient()

    try:
        while True:
            result = await redis_client.dequeue(CLAIM_EXTRACT_QUEUE_NAME, timeout=1)
            if result:
                asyncio.create_task(process_task(result, semaphore))

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
