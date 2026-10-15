import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

VERSION = os.getenv("GIT_SHA", "dev")
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"timeout": 2},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="TriageDesk API", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "db": "error",
                "version": VERSION,
            },
        )

    return {
        "status": "ok",
        "db": "ok",
        "version": VERSION,
    }
