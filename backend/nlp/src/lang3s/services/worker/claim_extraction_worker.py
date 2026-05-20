import asyncio
import math
import os
import time

import numpy as np
from pydantic import ValidationError
from transformers import AutoTokenizer

import lang3s.data.db.database as db
from lang3s.data.db.models import ClaimsTable
from lang3s.llm import Message
from lang3s.llm.client import LoRaClient
from lang3s.models.embedder import Embedder
from lang3s.nlp.claim_extractor import (
    DocumentClaimRequest,
)
from lang3s.parallel.core import Engine, Event
from lang3s.parallel.manager import TaskManager
from lang3s.parallel.queue import QueueFactory, QueueType
from lang3s.services.client.redis_client import (
    CLAIM_EXTRACT_QUEUE_NAME,
)
from lang3s.utils.logger import get_logger

logger = get_logger("CLAIM_EXTRACTION_WORKER")
_local_llm: LoRaClient | None = None
_embedder: Embedder | None = None
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

global_task_id = 0
global_processing = set()


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


def parse_claim_string(text: str) -> dict | None:
    markers = {
        "SUBJ:": "subject",
        "PRED:": "predicate",
        "OBJ:": "object",
        "STANCE:": "stance",
        "MOD:": "modality",
        "NEG:": "negation",
        "CERTAIN:": "certainty",
        "TIME:": "time",
        "LOC:": "location",
        "SOURCE:": "source",
        "KW:": "keywords",
    }

    found_markers = []
    for marker, key in markers.items():
        idx = text.find(marker)
        if idx != -1:
            found_markers.append((idx, marker, key))

    if not found_markers:
        return None

    found_markers.sort(key=lambda x: x[0])

    parsed = {key: "" for key in markers.values()}

    for i in range(len(found_markers)):
        current_idx = found_markers[i][0]
        marker_length = len(found_markers[i][1])
        key = found_markers[i][2]
        start_idx = current_idx + marker_length

        if i + 1 < len(found_markers):
            end_idx = found_markers[i + 1][0]
        else:
            end_idx = len(text)

        parsed[key] = text[start_idx:end_idx].strip()

    if not (parsed["subject"] and parsed["predicate"] and parsed["object"]):
        return None

    return parsed


def _generate_embeddings(texts: list[str]):
    return get_embedder()(texts).sentence_embeddings


def _insert_db(objects: list[ClaimsTable]):
    db.insert_many_objects(objects)


async def process_task(item: Event[dict]):
    try:
        request = DocumentClaimRequest.model_validate(item.data)
        if not request.sentences:
            return 0
        token_count = len(tokenizer(" ".join(request.sentences))["input_ids"])
        response = await get_llm().chat_completion_last_event(
            messages=[
                Message.user(f"Extract claims from: {' '.join(request.sentences)}")
            ],
            adapter_name="claim",
            temperature=0.0,
            max_tokens=4096,
            stop=["<|im_end|>", "<|endoftext|>"],
        )
        all_claims: list[ClaimsTable] = []
        if response.content:
            individual_claims = response.content.split("\n")
            for raw_claim in individual_claims:
                parsed_claim = parse_claim_string(raw_claim)
                if parsed_claim:
                    subject = parsed_claim["subject"]
                    predicate = parsed_claim["predicate"]
                    obj = parsed_claim["object"]
                    stance = parsed_claim["stance"]
                    mod = parsed_claim["modality"]
                    if mod not in (
                        "factual",
                        "normative",
                        "hypothetical",
                        "conditional",
                        "predictive",
                    ):
                        mod = "factual"
                    neg = parsed_claim["negation"]
                    certain = parsed_claim["certainty"]
                    if certain not in (
                        "certain",
                        "probable",
                        "possible",
                        "speculative",
                    ):
                        certain = "unknown"
                    time_param = parsed_claim["time"]
                    loc = parsed_claim["location"]
                    source = parsed_claim["source"]
                    keywords = [
                        item.strip("' ")
                        for item in parsed_claim["keywords"].strip("[] ").split(",")
                    ]
                    if subject and predicate and obj:
                        all_claims.append(
                            ClaimsTable(
                                documentId=request.documentId,
                                subject=subject,
                                predicate=predicate,
                                type_="Fact",
                                object=obj,
                                stance=stance,
                                claim=f"{subject} {predicate} {obj}",
                                keywords=keywords,
                                time=time_param,
                                source=source,
                                evidence="",
                                location=loc,
                                embedding=np.zeros(1),
                                modality=mod,  # type: ignore
                                negation=neg.lower() == "true",
                                certainty=certain,  # type: ignore
                                condition="",
                                sentiment="neutral",
                            )
                        )

        if all_claims:
            claim_texts = [c.claim for c in all_claims]
            embs = await asyncio.to_thread(_generate_embeddings, claim_texts)
            for claim, emb in zip(all_claims, embs):
                claim.embedding = emb
            await asyncio.to_thread(_insert_db, all_claims)

        return token_count
    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
    return 0


async def main():
    total_documents = 0
    total_tokens = 0
    WORKER_COUNT = 4

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
