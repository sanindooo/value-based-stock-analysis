from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.data import router as data_router
from app.api.preferences import router as preferences_router
from app.api.screening import router as screening_router

app = FastAPI(title="Stock Analyzer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_router, prefix="/api/data", tags=["data"])
app.include_router(preferences_router, prefix="/api/preferences", tags=["preferences"])
app.include_router(screening_router, prefix="/api/screening", tags=["screening"])


@app.get("/health")
async def health():
    return {"status": "ok"}
