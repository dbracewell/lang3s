import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from lang3s.nlp.embedding import Embedder


class EmbeddingRequest(BaseModel):
    language: str
    text: str


app = FastAPI()

embedder = Embedder()


@app.post("/embed")
@app.post("/embed/")
async def caption(request: EmbeddingRequest):
    return embedder([request.text])[0]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
