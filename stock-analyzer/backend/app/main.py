import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update

from app.api.analysis import router as analysis_router
from app.api.data import router as data_router
from app.api.preferences import router as preferences_router
from app.api.research import router as research_router
from app.api.screening import router as screening_router
from app.db import async_session
from app.models.task import TaskStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session() as db:
        result = await db.execute(
            update(TaskStatus)
            .where(TaskStatus.status.in_(["pending", "running"]))
            .values(status="failed", error_message="Server restarted during execution.")
        )
        if result.rowcount > 0:
            logger.warning("Marked %d orphaned tasks as failed on startup", result.rowcount)
        await db.commit()
    yield


app = FastAPI(title="Stock Analyzer API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(data_router, prefix="/api/data", tags=["data"])
app.include_router(preferences_router, prefix="/api/preferences", tags=["preferences"])
app.include_router(research_router, prefix="/api/research", tags=["research"])
app.include_router(screening_router, prefix="/api/screening", tags=["screening"])


@app.get("/health")
async def health():
    return {"status": "ok"}
