import asyncio
import json
import os
import tempfile
import threading
import traceback
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from lang3s.core import config
from lang3s.core.clients.redis_client import (
    redis_get_message_batch,
)
from lang3s.core.logger import get_logger
from lang3s.data import filestore
from lang3s.data.constants import DUCKDB_QUEUE_NAME
from lang3s.data.schemas import AnnotationTypes, Document
from lang3s.data.schemas.job import JobMessage
from lang3s.services.analytics import get_analytics_db, init_analytics_db
from lang3s.services.helpers import create_fastapi_app
from lang3s.services.repositories.analytics_repository import AnalyticsRepository
from lang3s.services.routers.analytics_router import (
    analytics_router,
)
from lang3s.services.routers.charting_router import charting_router

logger = get_logger("ANALYTICS")


def ingest_documents(
    service: AnalyticsRepository,
    batch: list[JobMessage],
):
    logger.info(f"💽 WRITING {len(batch)} documents to duckdb")
    try:
        temp_file = None
        with tempfile.NamedTemporaryFile(
            mode="w+t",
            delete=False,
            suffix=".json",
        ) as f:
            annotations = []
            for job in batch:
                doc: Document = filestore.read_document(job.content["doc_id"])
                for annotation in doc.text.annotations:
                    if annotation.type_ == AnnotationTypes.TOKEN:
                        continue
                    annotations.append(
                        {
                            "id": annotation.id,
                            "content": annotation.coref.content,
                            "normalized": annotation.normalized,
                            "type": annotation.type_,
                            "mapping": annotation.mapping,
                            "value": annotation.value,
                            "sentence_id": annotation.sentence.id,
                            "document_id": annotation.document_id,
                            "embedding": annotation.embedding.tolist(),
                            "metadata_json": annotation.metadata_json,
                        }
                    )
            json.dump(annotations, f)
            del annotations
            f.close()
            temp_file = f.name
        service.ingest_annotation_batch_from_file(temp_file)
        os.remove(temp_file)
    except Exception:
        traceback.print_exc()


def analytics_worker(shared_state):
    service: AnalyticsRepository = AnalyticsRepository(get_analytics_db())
    logger.info("Analytics worker started")
    shutdown_event = threading.Event()
    try:
        while not getattr(shared_state, "should_exit", False):
            if getattr(shared_state, "should_exit", False):
                shutdown_event.set()

            batch, completed_message = redis_get_message_batch(
                DUCKDB_QUEUE_NAME,
                200,
                batch_timeout=5,
                shutdown_event=shutdown_event,
            )

            if batch:
                ingest_documents(service, batch)

            if completed_message:
                service.finish_data_ingestion()
                logger.info("🏁 Finished analytics data ingestion")

    except asyncio.CancelledError:
        logger.info("👷 Worker: Cancelled during shutdown")
    except Exception:
        traceback.print_exc()


BATCH_TIMEOUT = 30

background_tasks = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Analytics API...")
    init_analytics_db()
    worker_task = asyncio.create_task(asyncio.to_thread(analytics_worker, app.state))
    background_tasks.add(worker_task)
    worker_task.add_done_callback(background_tasks.discard)
    yield

    app.should_exit = True
    try:
        await asyncio.wait_for(worker_task, timeout=5.0)
    except asyncio.TimeoutError:
        pass


app = create_fastapi_app(
    title="Lang3s Analytics",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(analytics_router)
app.include_router(charting_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.FAST_API_ANALYTICS_PORT,
    )
