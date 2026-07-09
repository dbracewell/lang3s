from typing import Optional

from lang3s.core.clients import RedisClient

from .typedefs import Event, QueueSource


class RedisQueueSource[T](QueueSource[T]):
    def __init__(self, queue_name: str, workers: int) -> None:
        super().__init__(workers)
        self.queue_name = queue_name
        self._queue = RedisClient()

    def put(self, item: Event[T]) -> None:
        self._queue.enqueue(
            queue_name=self.queue_name,
            item=item,
        )

    def get(self, timeout: Optional[float] = None) -> Event[T]:
        return self._queue.dequeue(
            queue_name=self.queue_name,
            timeout=timeout,
        )

    def empty(self) -> bool:
        return self._queue.queue_length(self.queue_name) == 0
