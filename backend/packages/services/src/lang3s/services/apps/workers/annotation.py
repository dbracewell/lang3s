import base64
import io
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from threading import Thread

import numpy as np
import shortuuid
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.clients.redis_client import (
    RedisClient,
    redis_get_message_batch,
)
from lang3s.core.decorators import as_sync
from lang3s.core.exceptions import NotFoundException
from lang3s.core.formatters import format_duration
from lang3s.core.logger import get_logger
from lang3s.core.parallel import (
    Event,
    JobCompleteEvent,
    QueueSource,
)
from lang3s.core.schemas import File
from lang3s.core.schemas.job import JobMessage, JobStatus, JobUpdateRequest
from lang3s.core.typing_extras import ShutdownEvent
from lang3s.data import filestore
from lang3s.data.constants import (
    ANNOTATION_QUEUE_NAME,
    CLAIM_EXTRACT_QUEUE_NAME,
    DUCKDB_QUEUE_NAME,
    ONTOLOGY_UPDATE_TOPIC,
    TOPIC_FINISHED,
    TOPIC_QUEUE_NAME,
)
from lang3s.data.db import async_db_session, create_indexes, get_ontology
from lang3s.data.events import EventType
from lang3s.data.models import TextAnnotation
from lang3s.data.repositories.job_repository import JobRepository
from lang3s.data.schemas import Document
from lang3s.data.schemas.claim import DocumentClaimRequest
from lang3s.nlp.analytics.corpus import corpus_summarization, probe_metadata
from lang3s.nlp.pipeline import pipeline
from lang3s.services.schemas.topics_api_schema import Task


def get_local_logger():
    return get_logger("ANNOTATION_WORKER")


class AnnotationTask(BaseModel):
    job_id: int
    files: list[File]


@dataclass
class WorkerResult:
    """
    Represents the result state of a worker's processing tasks.

    This class is a dataclass that encapsulates information about the number of
    completed and failed tasks, the currently active job ID (if any), and whether
    the most recent job has been completed.
    """

    completed: int = field(default=0)
    failed: int = field(default=0)
    time_taken: float = field(default=0.0)

    @property
    def processed(self):
        return self.completed + self.failed

    def __iadd__(self, other):
        if isinstance(other, WorkerResult):
            self.completed += other.completed
            self.failed += other.failed
            self.time_taken += other.time_taken
            return self
        return NotImplemented


def ontology_listener():
    from lang3s.nlp.components.ner import get_ner_model

    logger = get_local_logger()
    while True:
        try:
            with RedisClient() as client:
                p = client.subscribe(ONTOLOGY_UPDATE_TOPIC)
                for message in p.listen():
                    if message["type"] == "message":
                        if message["data"] == "update":
                            logger.info("🛜 Updating ontology")
                            get_ontology(refresh=True)
                            get_ner_model().refresh()
        except Exception as e:
            logger.error(f"Redis link dropped: {e}")
            time.sleep(5)


def init_annotation_worker():
    logger = get_local_logger()
    pid = os.getpid()
    logger.info(f"👷🏻 Worker {pid} Started.")
    thread = Thread(target=ontology_listener, daemon=True)
    thread.start()


def send_to_claim_processor(docs: list[Document]) -> None:
    logger = get_local_logger()
    with RedisClient() as redis_client:
        for doc in docs:
            try:
                claims = DocumentClaimRequest.create(doc)
                redis_client.enqueue(
                    CLAIM_EXTRACT_QUEUE_NAME,
                    claims.model_dump(),
                )
                for sentence in doc.text.sentences:
                    if "claims" in sentence.metadata_json:
                        sentence.metadata_json.pop("claims")
            except Exception as e:
                logger.error(e, exc_info=True)

        logger.info(f"Sent {len(docs)} documents to the claims queue.")


async def save_docs_to_db(docs: list[Document], session: AsyncSession) -> None:
    logger = get_local_logger()
    start_time = time.perf_counter()
    for doc in docs:
        session.add(doc.to_database())
    await session.commit()
    logger.info(
        f"Wrote {len(docs)} documents to the database: "
        f"{format_duration(start_time, time.perf_counter())} "
        f"(WORKER {os.getpid()})"
    )


def save_documents_to_disk(job_id, docs: list[Document]) -> None:
    def _write_doc_to_disk(doc: Document, redis_client: RedisClient) -> None:
        doc_id = filestore.write_document(doc)
        redis_client.enqueue(
            DUCKDB_QUEUE_NAME,
            JobMessage(
                job_id=job_id,
                content={"doc_id": doc_id},
            ),
        )

    with ThreadPoolExecutor(max_workers=20) as executor:
        with RedisClient() as client:
            executor.map(partial(_write_doc_to_disk, redis_client=client), docs)


def send_to_topic_model(docs: list[Document]) -> None:
    with RedisClient() as client:
        for doc in docs:
            current_batch = [
                s.embedding
                for s in doc.text.sentences
                if not s.is_stopword and s.embedding is not None
            ]
            embeddings = np.stack(current_batch)
            with io.BytesIO() as buf:
                np.save(buf, embeddings)
                buf.seek(0)
                client.enqueue(
                    TOPIC_QUEUE_NAME,
                    Task(
                        method="add",
                        data=base64.b64encode(buf.read()).decode("utf-8"),
                        id=doc.id,
                    ),
                )


@as_sync
async def annotation_worker(event: Event[AnnotationTask]) -> Event[WorkerResult]:
    if not event.payload:
        return Event(payload=WorkerResult())

    pid = os.getpid()
    logger = get_local_logger()
    task = event.payload

    logger.info(f"Began processing {len(task.files)} files (WORKER {pid})")

    async with async_db_session() as session:
        global_start_time = time.perf_counter()
        try:
            job_repository = JobRepository(session)
            try:
                job = await job_repository.get(task.job_id)
            except NotFoundException:
                logger.error(f"Error getting Job: {task.job_id} (WORKER {pid})")
                return Event(payload=WorkerResult())

            tasks = job.metadata_json.get("tasks", None)
            if tasks:
                tasks = set(tasks)  # type: ignore

            global_start_time = time.perf_counter()
            docs = list(
                pipeline(
                    task.files,
                    tasks=tasks,
                    batch_size=len(task.files),
                    log=False,
                )
            )
            logger.info(
                f"Annotated {len(docs)} documents: "
                f"{format_duration(global_start_time, time.perf_counter())} "
                f"(WORKER {pid})"
            )

            await save_docs_to_db(docs, session)
            send_to_claim_processor(docs)
            save_documents_to_disk(job_id=job.id, docs=docs)
            send_to_topic_model(docs)

            # Ensure memory gets cleaned up
            for doc in docs or []:
                doc.detach()

            await job_repository.update(
                JobUpdateRequest(
                    id=job.id,
                    completed=len(task.files),
                ),
            )
            job.completed += len(task.files)
            async with RedisAsyncClient() as redis:
                await redis.publish_event(
                    event_type=EventType.JOB_UPDATE,
                    user_id=job.user_id,
                    payload=job.model_dump(mode="json"),
                )
            return Event(
                payload=WorkerResult(
                    completed=len(task.files),
                    failed=0,
                    time_taken=time.perf_counter() - global_start_time,
                )
            )
        except KeyboardInterrupt:
            print("KeyboardInterrupt at process_batch")
            return Event(payload=WorkerResult())
        except Exception as e:
            logger.info(
                f"❌ Exception {str(e)} "
                f"{format_duration(global_start_time, time.perf_counter())} "
                f"(WORKER {pid})"
            )
            import traceback

            traceback.print_exc(file=sys.stdout)
            await job_repository.update(
                JobUpdateRequest(
                    id=job.id,
                    failed=len(task.files),
                ),
            )
            job.failed += len(task.files)
            async with RedisAsyncClient() as redis:
                await redis.publish_event(
                    event_type=EventType.JOB_UPDATE,
                    user_id=job.user_id,
                    payload=job.model_dump(mode="json"),
                )
            return Event(payload=WorkerResult(failed=len(task.files)))


def poll_redis(
    shutdown_event: ShutdownEvent,
    queue: QueueSource[Event[AnnotationTask]],
    batch_size: int,
):
    try:
        while not shutdown_event.is_set():
            batch, completed_message = redis_get_message_batch(
                ANNOTATION_QUEUE_NAME,
                batch_size=batch_size,
                batch_timeout=10,
                shutdown_event=shutdown_event,
            )
            if batch:
                job_id = batch[0].job_id
                task = AnnotationTask(
                    job_id=job_id,
                    files=[File.model_validate(msg.content) for msg in batch],
                )
                queue.put(Event(payload=task))

            if completed_message:
                queue.job_complete(completed_message.job_id)
                continue

            time.sleep(1)
    except KeyboardInterrupt:
        return


@as_sync
async def on_annotation_job_complete(event: JobCompleteEvent):
    logger = get_local_logger()

    async with async_db_session(autocommit=True) as session:
        job_repository = JobRepository(session)
        await job_repository.update(JobUpdateRequest(id=event.job_id, total=20))

    logger.info("Constructing Indexes")
    try:
        await create_indexes(
            TextAnnotation,
            [
                "idx_text_annotations_embedding_hnsw",
                "ix_text_annotations_sentence_non_stopword_hnsw",
            ],
        )
        logger.info("Indexes created")
    except Exception as e:
        logger.error(f"Index creation failed ({e})")
        traceback.print_exc(file=sys.stdout)

    logger.info("Sending JobComplete message to analytics server")
    try:
        with RedisClient() as redis_client:
            redis_client.enqueue(
                DUCKDB_QUEUE_NAME,
                JobMessage(
                    job_id=event.job_id,
                    status=JobStatus.Completed,
                ),
            )
        logger.info("Sent JobComplete message to analytics server")
    except Exception as e:
        logger.error(f"Failed to send JobComplete message to analytics server ({e})")
        traceback.print_exc(file=sys.stdout)

    logger.info("Finalizing Topics")
    try:
        with RedisClient() as redis_client:
            uid = shortuuid.uuid()
            redis_client.enqueue(
                TOPIC_QUEUE_NAME,
                Task(
                    method="finalize",
                    data=None,
                    id=uid,
                ),
            )
            p = redis_client.subscribe(TOPIC_FINISHED)
            for msg in p.listen():
                if msg.get("type") == "message":
                    data = msg.get("data").decode("utf-8")
                    if data == uid:
                        break
        logger.info("Topics finalized")
    except Exception as e:
        logger.error(f"Topic finalization failed ({e})")
        traceback.print_exc(file=sys.stdout)

    logger.info("Generating corpus summary")
    try:
        await corpus_summarization()
        logger.info("Corpus summary generated")
    except Exception as e:
        logger.error(f"Corpus summary failed ({e})")
        traceback.print_exc(file=sys.stdout)

    logger.info("Probing metadata")
    try:
        await probe_metadata()
        logger.info("Probe metadata completed")
    except Exception as e:
        logger.error(f"Probing metadata failed ({e})")
        traceback.print_exc(file=sys.stdout)

    try:
        async with async_db_session() as session:
            repository = JobRepository(session)
            await repository.update(
                JobUpdateRequest(
                    id=event.job_id,
                    status=JobStatus.Completed,
                ),
            )
            job = await repository.get(event.job_id)
            async with RedisAsyncClient() as redis:
                await redis.publish_event(
                    event_type=EventType.JOB_UPDATE,
                    user_id=job.user_id,
                    payload=job.model_dump(mode="json"),
                )

    except Exception as e:
        logger.error(f"Updating Job Status failed ({e})")
        traceback.print_exc(file=sys.stdout)

    async with async_db_session(autocommit=True) as session:
        job_repository = JobRepository(session)
        await job_repository.update(
            JobUpdateRequest(
                id=event.job_id,
                completed=20,
                status=JobStatus.Completed,
            )
        )

    logger.info(f"🏁 Job completed {event.job_id}")
