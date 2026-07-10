import asyncio
import base64
import io

import numpy as np

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.logger import get_logger
from lang3s.data.constants import TOPIC_FINISHED, TOPIC_QUEUE_NAME
from lang3s.data.db import async_db_session
from lang3s.nlp.components.topics import Lang3sTopicModel
from lang3s.services.schemas.topics_api_schema import Task


async def main():
    logger = get_logger("TOPIC_SERVER")
    logger.info("Topic server started")
    async with RedisAsyncClient() as client, async_db_session() as session:
        topic_model = Lang3sTopicModel(session)
        await topic_model.load_topics()
        while True:
            try:
                task = await client.dequeue(TOPIC_QUEUE_NAME, timeout=0.5)
                if task is None:
                    await asyncio.sleep(5)
                    continue

                task = Task.model_validate(task)

                if task.method == "add":
                    raw_bytes = base64.b64decode(task.data)
                    with io.BytesIO(raw_bytes) as buf:
                        embeddings = np.load(buf, allow_pickle=False)
                        topic_model.partial_fit_sentence_embeddings(embeddings)

                elif task.method == "finalize":
                    try:
                        logger.info("Finalizing topics (flushing and saving)")
                        topic_model.flush()
                        await topic_model.save_topics()
                    finally:
                        logger.info("Topic finalization finished")
                        await client.publish_message(TOPIC_FINISHED, task.id)

            except Exception:
                import traceback

                traceback.print_exc()
                continue


if __name__ == "__main__":
    asyncio.run(main())
