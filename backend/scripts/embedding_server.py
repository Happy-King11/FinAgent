"""Small CPU-only OpenAI-compatible BGE-M3 embedding service for local tests."""

import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoTokenizer


MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
MODEL_REVISION = os.getenv("EMBEDDING_MODEL_REVISION") or None
MAX_LENGTH = int(os.getenv("EMBEDDING_MAX_LENGTH", "512"))


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str = MODEL_NAME


class EmbeddingItem(BaseModel):
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingItem]
    model: str


class ModelRuntime:
    def __init__(self) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
        self.model = AutoModel.from_pretrained(MODEL_NAME, revision=MODEL_REVISION)
        self.model.eval()
        self.dimension = int(self.model.config.hidden_size)

    def embed(self, texts: list[str]) -> list[list[float]]:
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.inference_mode():
            output = self.model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(output.dtype)
            pooled = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.cpu().tolist()


runtime: ModelRuntime | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runtime
    runtime = ModelRuntime()
    yield
    runtime = None


app = FastAPI(title="BGE-M3 CPU Embedding Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok" if runtime is not None else "loading"}


@app.get("/v1/models")
def models() -> dict:
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "local"}]}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    if runtime is None:
        raise HTTPException(status_code=503, detail="embedding model is loading")
    if request.model != MODEL_NAME:
        raise HTTPException(status_code=400, detail="model is not available")
    texts = [request.input] if isinstance(request.input, str) else request.input
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise HTTPException(status_code=400, detail="input must contain non-empty text")
    vectors = runtime.embed(texts)
    return EmbeddingResponse(
        model=MODEL_NAME,
        data=[EmbeddingItem(embedding=vector, index=index) for index, vector in enumerate(vectors)],
    )
