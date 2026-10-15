import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

VERSION = os.getenv("GIT_SHA", "dev")

engine = create_async_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="TriageDesk API", lifespan=lifespan)


async def _db_ok() -> tuple[bool, str]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        # Не возвращаем текст ошибки: он может содержать пароль из DSN.
        return False, type(exc).__name__


@app.get("/healthz")
async def healthz():
    ok, detail = await _db_ok()

    return {
        "status": "ok" if ok else "degraded",
        "db": detail,
        "version": VERSION,
    }


@app.get("/readyz")
async def readyz(response: Response):
    """Проверка готовности обслуживать запросы."""
    ok, detail = await _db_ok()

    if not ok:
        response.status_code = 503

    return {
        "ready": ok,
        "db": detail,
    }