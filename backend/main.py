from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.documents import router as documents_router
from backend.api.citations import router as citations_router
from backend.api.generation import router as generation_router
from backend.api.journals import router as journals_router
from backend.database import init_db
from backend.journal.database import seed_journals


async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    seed_journals()
    yield


app = FastAPI(title="Research Publication Pipeline", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(citations_router)
app.include_router(generation_router)
app.include_router(journals_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
