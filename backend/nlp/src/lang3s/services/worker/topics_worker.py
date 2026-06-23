import queue
import time

from lang3s.nlp.topics import model as topics
from lang3s.utils.logger.service_logging import get_logger

logger = get_logger(__name__)


class SetQueue(queue.Queue):
    def _init(self, maxsize):
        queue.Queue._init(self, maxsize)
        self.all_items = set()

    def _put(self, item):
        self.all_items.add(item)
        queue.Queue._put(self, item)

    def _get(self):
        item = queue.Queue._get(self)
        self.all_items.remove(item)
        return item

    def __contains__(self, item):
        return item in self.all_items


work_queue = SetQueue()
finished_queue = SetQueue(maxsize=4)


def topics_worker(shared_state):
    topic_model = topics.get_topic_model()

    while True:
        if getattr(shared_state, "is_updating_task", False):
            time.sleep(5)
            continue

        try:
            task = work_queue.get(timeout=1)
        except queue.Empty:
            continue

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
                topic_model.build_hierarchical_topics()

        except Exception as e:
            logger.exception(f"Error in worker: {e}", stack_info=True)
        finally:
            work_queue.task_done()
            if finished_queue.qsize() > 3:
                finished_queue.get()
            finished_queue.put(task.id)
