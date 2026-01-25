import time
from multiprocessing import Process, Queue
from typing import Callable, Generator, TypeVar

T = TypeVar("T")


def _producer_wrapper(
    queue: Queue,
    producer_generator: Callable[[], Generator[T, None, None]],
    stop_signal: int,
):
    for item in producer_generator():
        queue.put(item)
    for _ in range(stop_signal):
        queue.put(None)


def _consumer_wrapper(
    queue: Queue,
    consumer_func: Callable[[T, int], None],
    consumer_id: int,
    consumer_timeout: int,
    consumer_batch_size: int,
    batch_wait_time: int,
):
    while True:
        batch = []
        start_time = time.time()
        while (
            len(batch) < consumer_batch_size
            and (time.time() - start_time) < batch_wait_time
        ):
            item = queue.get()

            if item is None:
                if batch:
                    consumer_func(batch, consumer_id)
                return

            batch.append(item)

        if batch:
            consumer_func(batch, consumer_id)
        if consumer_timeout > 0:
            time.sleep(consumer_timeout)


def broker(
    producer: Callable[[], Generator[T, None, None]],
    consumer: Callable[[list[T], int], None],
    num_consumers: int = 1,
    consumer_timeout: int = 0,
    consumer_batch_size: int = 1,
    max_queue_size: int = -1,
    batch_wait_time=5,
):
    queue = Queue(maxsize=max_queue_size)
    producer_process = Process(
        target=_producer_wrapper, args=(queue, producer, num_consumers)
    )
    producer_process.start()
    batch_wait_time = batch_wait_time if batch_wait_time > 0 else 1
    consumers = []
    for consumer_id in range(num_consumers):
        p = Process(
            target=_consumer_wrapper,
            args=(
                queue,
                consumer,
                consumer_id,
                consumer_timeout,
                consumer_batch_size,
                batch_wait_time,
            ),
        )
        p.start()
        consumers.append(p)

    producer_process.join()
    for consumer in consumers:
        consumer.join()
