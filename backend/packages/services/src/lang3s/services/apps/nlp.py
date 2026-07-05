import argparse
from functools import partial

from lang3s.core.logger import get_logger
from lang3s.core.parallel import (
    Event,
    MultiprocessingManager,
    QueueSource,
)
from lang3s.services.apps.workers.annotation import (
    AnnotationTask,
    WorkerResult,
    annotation_worker,
    init_annotation_worker,
    on_annotation_job_complete,
    poll_redis,
)
from lang3s.services.apps.workers.topic import topic_worker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_workers",
        help="The number of worker processes to use",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--batch_size",
        help="The number of documents to process in each worker process",
        default=150,
        type=int,
    )
    args = parser.parse_args()
    logger = get_logger("NLP")
    with MultiprocessingManager(workers=args.num_workers) as manager:
        logger.info("Starting topic worker...")
        manager.submit(topic_worker)
        # logger.info("Starting claims worker...")
        # manager.submit(claims_worker)

        q: QueueSource[AnnotationTask] = manager.create_queue(maxsize=args.num_workers)
        manager.submit(
            partial(poll_redis, batch_size=args.batch_size),
            queue=q,
        )
        running_total: WorkerResult = WorkerResult()
        r: Event[WorkerResult]
        for r in manager.imap(
            annotation_worker,
            q,
            init_worker=init_annotation_worker,
            on_job_complete=on_annotation_job_complete,
        ):
            if r.payload:
                running_total += r.payload
                docs_per_minute = (
                    running_total.processed / running_total.time_taken * 60
                )
                logger.info(
                    f"💬 Processed {running_total.processed} documents "
                    f"(failed={running_total.failed}), "
                    f"{docs_per_minute:.2f} docs/minute)"
                )


if __name__ == "__main__":
    main()
