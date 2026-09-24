from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api import auth, compat, events, hooks, media, now, schedule
from app.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    root = Path(settings.media_root)
    for sub in ("temp", "air", "thumbs", "posters"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Mirror API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(media.router)
app.include_router(events.router)
app.include_router(schedule.router)
app.include_router(hooks.router)
app.include_router(now.router)
app.include_router(compat.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
