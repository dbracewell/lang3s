import logging

import uvicorn
from fastapi import FastAPI

from .embeddings import router as embedding_router
from .topics import router as topic_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


app = FastAPI()


app.include_router(topic_router)
app.include_router(embedding_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
