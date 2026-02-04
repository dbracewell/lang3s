import asyncio
import io
import time
from contextlib import asynccontextmanager

import numpy as np
import shortuuid
from fastapi import APIRouter, Depends, FastAPI, Request, UploadFile
from fastapi.responses import JSONResponse

from lang3s.nlp.topics import model as topics
from lang3s.services.model.topics_models import *
from lang3s.services.service_logging import get_logger
from lang3s.services.worker.topics_worker import (
    finished_queue,
    topics_worker,
    work_queue,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)


background_tasks = set()


@asynccontextmanager
async def topics_lifecycle(app: FastAPI):
    logger.info("Initializing Topic Api and Worker...")
    topics.init_topic_model()
    app.state.is_updating_task = False
    worker_task = asyncio.create_task(asyncio.to_thread(topics_worker, app.state))
    background_tasks.add(worker_task)
    worker_task.add_done_callback(background_tasks.discard)
    yield


@router.post("")
# async def add(request: AddRequest):
async def add(file: UploadFile):
    contents = await file.read()
    buf = io.BytesIO(contents)
    arr = np.load(buf)
    work_queue.put(Task(method="add", data=arr, id=shortuuid.uuid()))
    pending_count = work_queue.qsize()
    return {"status": "queued", "pending_tasks": pending_count}


@router.get("/status")
async def get_status():
    pending_count = work_queue.qsize()
    return {
        "status": "processing" if pending_count > 0 else "idle",
        "pending_tasks": pending_count,
    }


@router.get("")
async def get_all_topics(topic_model=Depends(topics.get_topic_model)):
    return [
        TopicData(
            id=t.id,
            name=t.name,
            support=t.support,
        )
        for t in topic_model.topics
    ]


@router.get("/count")
async def get_num_topics(topic_model=Depends(topics.get_topic_model)):
    return topic_model.num_topics


@router.put("/label")
async def label_topics():
    work_queue.put(Task(method="label", data=None, id=shortuuid.uuid()))
    pending_count = work_queue.qsize()
    return {"status": "queued", "pending_tasks": pending_count}


@router.put("/finalize")
async def finalize():
    task = Task(method="finalize", data=None, id=shortuuid.uuid())
    work_queue.put(task)
    pending_count = work_queue.qsize()
    while task.id not in finished_queue:
        time.sleep(1)
    return {"status": "queued", "pending_tasks": pending_count}


@router.put("/update/{topic_id}")
async def update_name(
    request: Request,
    topic_id: str,
    body: TopicUpdateRequest,
    topic_model=Depends(topics.get_topic_model),
):
    request.app.state.is_updating_task = True
    try:
        topic = topic_model.get_ranked_entities_for_topic(topic_id)

        if body.name is not None:
            topic.name = body.name
        if body.is_fixed is not None:
            topic.is_fixed = body.is_fixed

        return TopicData(
            id=topic.id,
            name=topic.name,
            support=topic.support,
        )
    except Exception:
        return JSONResponse(content="Not Found", status_code=404)
    finally:
        request.app.state.is_updating_task = False


@router.put("/merge")
async def merge():
    work_queue.put(Task(method="merge", data=None, id=shortuuid.uuid()))
    pending_count = work_queue.qsize()
    return {"status": "queued", "pending_tasks": pending_count}


@router.get("/{topic_id}")
async def get_topic(topic_id: str, topic_model=Depends(topics.get_topic_model)):
    topic = topic_model.get_ranked_entities_for_topic(topic_id)
    return TopicData(
        id=topic.id,
        name=topic.name,
        support=topic.support,
    )
