import logging
import queue
import threading
import time
from typing import Any, List, NamedTuple, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lang3s.db import Database
from lang3s.models.topic_model import Lang3sTopicModel

logger = logging.Logger(__name__)

router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)


class TopicData(BaseModel):
    id: str
    name: str
    support: int


class Task(NamedTuple):
    method: str
    data: Any


topic_model = None
work_queue = queue.Queue()

total_tasks = 0
is_updating_task = False


def worker():
    global is_updating_task
    while True:
        if is_updating_task:
            time.sleep(5)
            continue

        task = work_queue.get()  # waits until available
        try:
            if task.method == "add":
                topic_model.partial_fit_sentence_embeddings(task.data)
            elif task.method == "label":
                topic_model.label_topics()
            elif task.method == "merge":
                topic_model.flush()
                topic_model.merge_topics()
            elif task.method == "finalize":
                topic_model.flush()
                topic_model.merge_topics()
                topic_model.label_topics()
                topic_model.save_topics()
        except Exception as e:
            logger.exception(f"Error in worker: {e}", stack_info=True)
        finally:
            work_queue.task_done()
            global total_tasks
            total_tasks -= 1


def init_globals():
    """Call this ONCE when the app starts"""
    global topic_model
    # This ensures we get the singleton instance
    topic_model = Lang3sTopicModel()

    # Start the thread here, not at the top level
    t = threading.Thread(target=worker, daemon=True)
    t.start()


class AddRequest(BaseModel):
    embeddings: List[List[float]]


@router.post("/")
@router.post("")
async def add(request: AddRequest):
    global total_tasks
    work_queue.put(Task(method="add", data=request.embeddings))
    total_tasks += 1
    return {"status": "queued", "pending_tasks": total_tasks}


@router.get("/status")
@router.get("/status/")
async def get_status():
    global total_tasks
    return {
        "status": "processing" if total_tasks > 0 else "idle",
        "pending_tasks": total_tasks,
    }


@router.get("/")
@router.get("")
async def get_all_topics():
    return [
        TopicData(
            id=t.id,
            name=t.name,
            support=t.support,
        )
        for t in topic_model.topics
    ]


@router.get("/count")
@router.get("/count/")
async def get_num_topics():
    return topic_model.num_topics


@router.put("/label")
@router.put("/label/")
async def label_topics():
    global total_tasks
    work_queue.put(Task(method="label", data=None))
    total_tasks += 1
    return {"status": "queued", "pending_tasks": total_tasks}


@router.put("/finalize")
@router.put("/finalize/")
async def finalize():
    global total_tasks
    work_queue.put(Task(method="finalize", data=None))
    total_tasks += 1
    return {"status": "queued", "pending_tasks": total_tasks}


class TopicUpdateRequest(BaseModel):
    name: Optional[str]
    is_fixed: Optional[bool]


@router.put("/update/{topic_id}")
async def update_name(topic_id: str, request: TopicUpdateRequest):
    global is_updating_task
    is_updating_task = True
    try:
        topic = topic_model.get_topic(topic_id)

        if request.name is not None:
            topic.name = request.name
        if request.is_fixed is not None:
            topic.is_fixed = request.is_fixed

        return TopicData(
            id=topic.id,
            name=topic.name,
            support=topic.support,
        )
    except Exception:
        return JSONResponse(content="Not Found", status_code=404)
    finally:
        is_updating_task = False


@router.put("/merge")
@router.put("/merge/")
async def merge():
    global total_tasks
    work_queue.put(Task(method="merge", data=None))
    total_tasks += 1
    return {"status": "queued", "pending_tasks": total_tasks}


@router.get("/{topic_id}")
async def get_topic(topic_id: str):
    try:
        topic = topic_model.get_topic(topic_id)
        return TopicData(
            id=topic.id,
            name=topic.name,
            support=topic.support,
        )
    except Exception:
        return JSONResponse(status_code=404, content="Not Found")
