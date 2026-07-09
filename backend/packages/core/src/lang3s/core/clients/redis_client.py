from __future__ import annotations

import json
import threading
import time
from typing import TYPE_CHECKING, Any, Awaitable, Tuple

import redis
import redis.asyncio as async_redis
from openai.resources.conversations import items
from pydantic import BaseModel
from redis.asyncio import ConnectionPool
from redis.asyncio.client import PubSub
from redis.asyncio.retry import Retry as AsyncRetry
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from lang3s.core.schemas.job import Job, JobMessage, JobStatus
from lang3s.core.typing_extras import ShutdownEvent
from lang3s.data.events import EventType

if TYPE_CHECKING:
    from redis.client import PubSub

from lang3s.core import config

_global_async_connection_pool = None
_global_sync_connection_pool = None
_lock = threading.Lock()


def get_async_connection_pool() -> ConnectionPool:
    global _global_async_connection_pool
    _lock.acquire()
    try:
        if not _global_async_connection_pool:
            _global_async_connection_pool = async_redis.ConnectionPool(
                host=config.REDIS_HOST,
                health_check_interval=30,
                retry_on_timeout=True,
                retry=AsyncRetry(ExponentialBackoff(cap=10, base=1), 3),
            )
    finally:
        _lock.release()
    return _global_async_connection_pool


def get_sync_connection_pool() -> redis.ConnectionPool:
    global _global_sync_connection_pool
    _lock.acquire()
    try:
        if not _global_sync_connection_pool:
            _global_sync_connection_pool = redis.ConnectionPool(
                host=config.REDIS_HOST,
                health_check_interval=30,
                retry_on_timeout=True,
                retry=Retry(ExponentialBackoff(cap=10, base=1), 3),
            )
    finally:
        _lock.release()
    return _global_sync_connection_pool


class RedisAsyncClient:
    def __init__(self):
        self._client = async_redis.Redis(connection_pool=get_async_connection_pool())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def flush_all(self):
        await self._client.flushall()

    async def enqueue(self, queue_name: str, item: Any) -> Awaitable[int]:
        if isinstance(item, BaseModel):
            payload = item.model_dump_json()
        else:
            payload = json.dumps(item)

        return await self._client.rpush(queue_name, payload)  # type: ignore

    async def queue_length(self, queue_name: str) -> int:
        return await self._client.llen(queue_name)  # type:ignore

    async def dequeue(self, queue_name: str, timeout: float | None = None) -> Any:
        item = None
        if timeout:
            r = await self._client.blpop([queue_name], timeout)
            if r:
                _, item = r
        else:
            item = await self._client.lpop(queue_name)

        return json.loads(item) if item else None  # type: ignore

    async def publish_message(self, channel: str, message: Any) -> int:
        payload = message
        if isinstance(message, BaseModel):
            payload = message.model_dump_json()
        elif not isinstance(message, str):
            payload = json.dumps(message)
        return await self._client.publish(channel, payload)

    async def publish_event(
        self,
        event_type: EventType,
        user_id: str,
        payload: Any,
    ) -> int:
        return await self.publish_message(
            "lang3s-events",
            {
                "type": event_type.value,
                "userId": user_id,
                "payload": payload,
            },
        )

    async def subscribe(self, channel: str) -> PubSub:
        p = self._client.pubsub()
        await p.subscribe(channel)
        return p

    async def close(self) -> None:
        await self._client.close()


class RedisClient(object):
    def __init__(self):
        self._client = redis.Redis(connection_pool=get_sync_connection_pool())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def flush_all(self):
        self._client.flushall()

    def enqueue(self, queue_name: str, item: Any) -> None:
        if isinstance(item, BaseModel):
            payload = item.model_dump_json()
        else:
            payload = json.dumps(item)
        self._client.rpush(queue_name, payload)

    def queue_length(self, queue_name: str) -> int:
        return self._client.llen(queue_name)  # type:ignore

    def dequeue(self, queue_name: str, timeout: float | None = None) -> Any:
        item = None
        if timeout:
            r = self._client.blpop([queue_name], timeout)
            if r:
                _, item = r
        else:
            item = self._client.lpop(queue_name) if items else None

        return json.loads(item) if item else None  # type: ignore

    def publish_message(self, channel: str, message: Any) -> int:
        payload = message
        if isinstance(message, BaseModel):
            payload = message.model_dump_json()
        elif not isinstance(message, str):
            payload = json.dumps(message)
        return self._client.publish(channel, payload)

    def publish_job_update(self, job: Job) -> int:
        return self.publish_message(
            "events",
            {
                "type": "job:update",
                "payload": {
                    "jobId": job.id,
                    "progress": job.progress,
                    "status": job.status,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                },
                "userid": job.user_id or "1",
            },
        )

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
) -> Tuple[list[JobMessage], JobMessage | None]:
    completed_message = None
    final_messages = []
    for message in messages:
        job = JobMessage.model_validate(message)
        if job.status == JobStatus.Completed:
            completed_message = job
        elif job.content:
            final_messages.append(job)
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
                msg_doc = redis_client.dequeue(queue_name)

                if msg_doc is None:
                    if batch:
                        yield batch
                        batch = []
                    break

                batch.append(msg_doc)

            yield batch


def redis_get_message_batch(
    queue_name,
    batch_size=250,
    batch_timeout=30,
    shutdown_event: ShutdownEvent | None = None,
) -> Tuple[list[JobMessage], JobMessage | None]:
    with RedisClient() as redis_client:
        batch = []
        start_time = time.time()

        while (time.time() - start_time) < batch_timeout and len(batch) < batch_size:
            if shutdown_event and shutdown_event.is_set():
                return process_messages_for_status(batch)

            msg_doc = redis_client.dequeue(queue_name, timeout=0.1)
            if msg_doc is None:
                continue

            batch.append(msg_doc)

        return process_messages_for_status(batch)
