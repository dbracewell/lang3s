import asyncio
import math
import os
import time

from pydantic import ValidationError
from transformers import AutoTokenizer

import lang3s.data.db.database as db
from lang3s.data.db.models import ClaimsTable
from lang3s.llm import Message
from lang3s.llm.client import LoRaClient
from lang3s.models.embedder import Embedder
from lang3s.nlp.claim_extractor import (
    Claim,
    ClaimList,
    DocumentClaimRequest,
)
from lang3s.parallel.core import Engine, Event
from lang3s.parallel.manager import TaskManager
from lang3s.services.client.redis_client import (
    CLAIM_EXTRACT_QUEUE_NAME,
    RedisClient,
)
from lang3s.utils.logger import get_logger

logger = get_logger("CLAIM_EXTRACTION_WORKER")
_local_llm: LoRaClient | None = None
_embedder: Embedder | None = None
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")


def get_llm() -> LoRaClient:
    global _local_llm
    if _local_llm is None:
        _local_llm = LoRaClient()
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


def sentence_chunker(
    sentences: list[str],
    window_size=15,
    overlap=2,
):
    total_tokens = 0
    chunks = []
    step = window_size - overlap
    if step <= 0:
        step = 1

    for i in range(0, len(sentences), step):
        window = sentences[i : i + window_size]
        chunk_text = " ".join(window)
        total_tokens += len(tokenizer(chunk_text)["input_ids"])
        chunks.append(chunk_text)
        if i + window_size >= len(sentences):
            break

    return total_tokens, chunks


def sentence_chunker2(
    sentences: list[str],
    max_tokens=512,
    overlap=2,
):
    total_tokens = 0
    chunks = []
    current_chunk = ""
    start = 0
    current_chunk_tokens = 0
    while start < len(sentences):
        sentence = sentences[start]
        next_sentence_token_count = len(tokenizer(sentence)["input_ids"])
        if (
            next_sentence_token_count + current_chunk_tokens >= max_tokens
            and current_chunk != ""
        ):
            chunks.append(current_chunk)
            total_tokens += current_chunk_tokens
            current_chunk_tokens = 0
            current_chunk = ""
            start = max(start - overlap, 0)
        else:
            current_chunk_tokens += next_sentence_token_count
            current_chunk += f" {sentence}"
            start += 1

    if current_chunk != "":
        chunks.append(current_chunk)
        total_tokens += current_chunk_tokens

    return total_tokens, chunks


async def generate_claims(chunk: str, semaphore):
    async with semaphore:
        try:
            response = await get_llm().chat_completion_last_event(
                messages=[Message.user(f"Extract claims from: {chunk}")],
                adapter_name="claim",
                temperature=0.0,
                response_model=ClaimList,
                presence_penalty=1.5,
            )
            if response.parsed:
                return response.parsed
        except ValidationError as e:
            logger.error(f"Validation failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during processing: {e}")
        return None


async def process_task(item: Event[dict]):
    try:
        request = DocumentClaimRequest.model_validate(item.data)
        if not request.sentences:
            return 0
        all_claims: list[Claim] = []
        token_count, chunks = sentence_chunker(request.sentences)

        for chunk in chunks:
            response = await get_llm().chat_completion_last_event(
                messages=[Message.user(f"Extract claims from: {chunk}")],
                adapter_name="claim",
                temperature=0.0,
                response_model=ClaimList,
                presence_penalty=1.5,
            )
            if response.parsed:
                all_claims.extend(response.parsed.claims)

        embs = get_embedder()(
            [claim.claim_text for claim in all_claims]
        ).sentence_embeddings
        db.insert_many_objects(
            [
                ClaimsTable(
                    documentId=request.documentId,
                    claim=claim.claim_text,
                    source=claim.claim_text,
                    embedding=emb,
                )
                for claim, emb in zip(all_claims, embs)
                if claim.claim_text
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
    total_time = 0
    WORKER_COUNT = 4
    redis_client = RedisClient()
    semaphore = asyncio.Semaphore(WORKER_COUNT)

    while True:
        item = redis_client.dequeue(CLAIM_EXTRACT_QUEUE_NAME)
        if item is None:
            time.sleep(1)
            continue

        if total_documents > 0 and total_documents % 10 == 0:
            logger.info(
                f"Claim Extractor: Processed {total_documents} documents in {total_time:.2f} ({total_documents / total_time:.2f} docs / second) ({total_tokens / total_time:.2f} tokens / second)"
            )

        start_time = time.perf_counter()
        request = DocumentClaimRequest.model_validate_json(item)
        if not request.sentences:
            continue

        all_claims: list[Claim] = []
        token_count, chunks = sentence_chunker2(request.sentences)

        total_tokens += token_count
        logger.info(f"Processing {token_count} tokens,  {len(chunks)} chunks")
        total_documents += 1

        tasks = [generate_claims(chunk, semaphore) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r is None:
                continue
            all_claims.extend(r.claims)

            # embs = get_embedder()(
            #     [claim.claim_text for claim in all_claims]
            # ).sentence_embeddings
            # db.insert_many_objects(
            #     [
            #         ClaimsTable(
            #             documentId=request.documentId,
            #             claim=claim.claim_text,
            #             source=claim.claim_text,
            #             embedding=emb,
            #         )
            #         for claim, emb in zip(all_claims, embs)
            #         if claim.claim_text
            #     ]
            # )

        total_time += time.perf_counter() - start_time
        logger.info("FINISHED")

    #
    # with QueueFactory() as factory:
    #     with TaskManager(
    #         Engine.ASYNC,
    #         workers=WORKER_COUNT,
    #         initializer=init_worker,
    #     ) as runner:
    #         queue = factory(
    #             queue_type=QueueType.REDIS,
    #             queue_name=CLAIM_EXTRACT_QUEUE_NAME,
    #         )
    #         start_time = time.perf_counter()
    #         async for r in runner.async_map(
    #             process_task,
    #             queue,
    #         ):
    #             total_tokens += r
    #             total_documents += 1 if r > 0 else 0
    #             total_time = time.perf_counter() - start_time
    #             if total_documents % 50 == 0:
    #                 logger.info(
    #                     f"Claim Extractor: Processed {total_documents} documents in {total_time:.2f} ({total_documents / total_time:.2f} docs / second) ({total_tokens / total_time:.2f} tokens / second)"
    #                 )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
