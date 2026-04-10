import json
import time
from typing import Any, Tuple

import redis
import redis.asyncio as async_redis
from redis.client import PubSub

from lang3s import config

DUCKDB_QUEUE_NAME = "db_queue"
ANNOTATION_QUEUE_NAME = "annotation_queue"
CLAIM_EXTRACT_QUEUE_NAME = "claim_extract_queue"
ONTOLOGY_UPDATE_TOPIC = "ontology_update"


class RedisAsyncClient(object):
    def __init__(self):
        self._client = async_redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def enqueue(self, queue_name: str, item: Any) -> int:
        return await self._client.rpush(queue_name, json.dumps(item))  # type: ignore

    async def queue_length(self, queue_name: str) -> int:
        return await self._client.llen(queue_name)  # type:ignore

    async def dequeue(self, queue_name: str, timeout: int | None = None) -> Any:
        result = await self._client.blpop([queue_name], timeout)  # type: ignore
        if result:
            _, data = result
            return data
        return None

    async def publish_message(self, channel: str, message: Any) -> None:
        await self._client.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str) -> PubSub:
        p = self._client.pubsub()
        await p.subscribe(channel)
        return p

    async def close(self) -> None:
        await self._client.close()


class RedisClient(object):
    def __init__(self):
        self._client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def enqueue(self, queue_name: str, item: Any) -> None:
        self._client.rpush(queue_name, json.dumps(item))

    def queue_length(self, queue_name: str) -> int:
        return self._client.llen(queue_name)  # type:ignore

    def dequeue(self, queue_name: str) -> Any:
        return self._client.lpop(queue_name)

    def publish_message(self, channel: str, message: Any) -> None:
        self._client.publish(channel, json.dumps(message))

    def subscribe(self, channel: str) -> PubSub:
        p = self._client.pubsub()
        p.subscribe(channel)
        return p

    def close(self) -> None:
        self._client.close()


def create_completed_status_message(**kwargs):
    kwargs.pop("__status", None)
    return {**kwargs, "__status": "completed"}


def is_status_completed(message: dict[str, Any] | None) -> bool:
    if not message:
        return False
    if not isinstance(message, dict):
        return False
    return message.get("__status", "") == "completed"


def process_messages_for_status(
    messages: list[dict[str, Any]],
) -> Tuple[list[dict[str, Any]], dict[str, Any] | None]:
    completed_message = None
    final_messages = []
    for message in messages:
        if "__status" not in message:
            final_messages.append(message)
        elif "__status" in message:
            completed_message = message
    return final_messages, completed_message


def redis_batch_generator(
    queue_name,
    batch_size=250,
    batch_timeout=30,
):
    with RedisClient() as redis_client:
        while True:
            batch = []
            start_time = time.time()

            while (time.time() - start_time) < batch_timeout and len(
                batch
            ) < batch_size:
                msg = redis_client.dequeue(queue_name)

                if msg is None:
                    if batch:
                        yield batch
                        batch = []
                    break

                msg_doc = json.loads(msg)
                batch.append(msg_doc)

            yield batch


def redis_get_message_batch(
    queue_name,
    batch_size=250,
    batch_timeout=30,
) -> Tuple[list[dict[str, Any]], dict[str, Any] | None]:
    with RedisClient() as redis_client:
        batch = []
        start_time = time.time()

        while (time.time() - start_time) < batch_timeout and len(batch) < batch_size:
            msg = redis_client.dequeue(queue_name)

            if msg is None:
                return process_messages_for_status(batch)

            msg_doc = json.loads(msg)
            batch.append(msg_doc)

        return process_messages_for_status(batch)
