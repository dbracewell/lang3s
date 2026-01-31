import multiprocessing
import time
from ctypes import c_bool
from multiprocessing import Process, Queue
from typing import Any, Callable, Generator, TypeVar

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


def _consolidator_wrapper(
    queue: Queue,
    finishedValue,
    consolidator_function: Callable[[list[T]], None],
    consolidator_batch_size: int,
    batch_wait_time: int,
):
    while not finishedValue.value:
        batch: list[T] = []
        start_time = time.time()
        while (
            len(batch) < consolidator_batch_size
            and (time.time() - start_time) < batch_wait_time
        ):
            item = queue.get()

            if item is None:
                if batch:
                    consolidator_function(batch)
                return

            batch.append(item)

        if batch:
            consolidator_function(batch)


def _consumer_wrapper(
    queue: Queue,
    consolidator_queue: Queue,
    consumer_func: Callable[[list[T], int], list[Any] | None],
    consumer_id: int,
    finished_value,
    processed_count,
    consumer_batch_size: int,
    batch_wait_time: int,
):
    batch = []
    start_time = time.time()
    while (
        len(batch) < consumer_batch_size
        and (time.time() - start_time) < batch_wait_time
    ):
        item = queue.get()

        if item is None:
            if batch:
                _process_and_count(
                    batch,
                    consumer_func,
                    consumer_id,
                    processed_count,
                    consolidator_queue,
                )
            with finished_value.get_lock():
                finished_value.value = True
            return

        batch.append(item)

    if batch:
        _process_and_count(
            batch,
            consumer_func,
            consumer_id,
            processed_count,
            consolidator_queue,
        )


def _process_and_count(
    batch: list,
    func: Callable[[list[T], int], list[Any] | None],
    c_id: int,
    counter,
    c_queue: Queue,
):
    results = func(batch, c_id)
    with counter.get_lock():
        counter.value += len(batch)
    if c_queue and results:
        for res in results or []:
            c_queue.put(res)


def broker(
    producer: Callable[[], Generator[T, None, None]],
    consumer: Callable[[list[T], int], list[Any] | None],
    consolidator: Callable[[list[Any]], None] | None = None,
    num_consumers: int = 1,
    consumer_timeout: int = 0,
    consumer_batch_size: int = 20,
    consumer_batch_wait_time=20,
    max_queue_size: int = -1,
    consolidator_batch_size: int = 100,
    consolidator_batch_wait_time: int = 20,
):
    queue = Queue(maxsize=max_queue_size)
    producer_process = Process(
        target=_producer_wrapper, args=(queue, producer, num_consumers)
    )
    producer_process.start()
    consumer_batch_wait_time = (
        consumer_batch_wait_time if consumer_batch_wait_time > 0 else 1
    )
    consolidator_batch_wait_time = (
        consolidator_batch_wait_time if consolidator_batch_wait_time > 0 else 1
    )

    finished_value = multiprocessing.Value(c_bool, False)
    processed_count = multiprocessing.Value("i", 0)

    consolidator_process = None
    consolidator_queue = None
    if consolidator is not None:
        consolidator_queue = Queue(maxsize=max_queue_size)
        consolidator_process = Process(
            target=_consolidator_wrapper,
            args=(
                consolidator_queue,
                finished_value,
                consolidator,
                consolidator_batch_size,
                consolidator_batch_wait_time,
            ),
        )
        consolidator_process.start()

    consumers = []
    while not finished_value.value:
        for consumer_id in range(num_consumers):
            p = Process(
                target=_consumer_wrapper,
                args=(
                    queue,
                    consolidator_queue,
                    consumer,
                    consumer_id,
                    finished_value,
                    processed_count,
                    consumer_batch_size,
                    consumer_batch_wait_time,
                ),
            )
            p.start()
            consumers.append(p)

        for c in consumers:
            c.join()
        print(f"Processed {processed_count.value} items")

        if not finished_value.value:
            time.sleep(consumer_timeout)

    producer_process.join()

    if consolidator_process:
        consolidator_process.join()
