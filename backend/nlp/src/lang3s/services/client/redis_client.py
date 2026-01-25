import json
import time
from typing import Any

import redis

from lang3s import config

DUCKDB_QUEUE_NAME = "db_queue"
ANNOTATION_QUEUE_NAME = "annotation_queue"


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
        return self._client.llen(queue_name)

    def dequeue(self, queue_name: str) -> Any:
        return self._client.lpop(queue_name)

    def publish_message(self, channel: str, message: Any) -> None:
        self._client.publish(channel, json.dumps(message))

    def close(self) -> None:
        self._client.close()


def redis_batch_generator(
    queue_name,
    batch_size=250,
    batch_timeout=30,
):
    with RedisClient() as redis_client:
        try:
            while True:
                batch = []
                start_time = time.time()

                while (time.time() - start_time) < batch_timeout and len(
                    batch
                ) < batch_size:
                    msg = redis_client.dequeue(queue_name)

                    if not msg:
                        continue

                    msg_doc = json.loads(msg)
                    if (
                        isinstance(msg_doc, dict)
                        and msg_doc.get("status", "") == "completed"
                    ):
                        if batch:
                            yield batch
                        yield [msg_doc]
                    else:
                        batch.append(msg_doc)

                yield batch
        except KeyboardInterrupt:
            print("Shutting down...")
            yield []
