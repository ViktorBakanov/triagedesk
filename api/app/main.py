from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from triage.db import StoredSuggestion, Ticket, initialise_database, load_accounts
from triage.rules import RulesTriager, Suggestion
from triage.scoreboard import one_line_scoreboard, scoreboard

VERSION = os.getenv("GIT_SHA", "dev")
engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialise_database(engine)
    app.state.triager = RulesTriager(await load_accounts(engine))
    yield
    print(one_line_scoreboard(await scoreboard(engine, app.state.triager)))
    await engine.dispose()


app = FastAPI(title="TriageDesk API", lifespan=lifespan)


class Correction(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    urgency: str = Field(min_length=1, max_length=16)
    team: str = Field(min_length=1, max_length=64)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(accepted|corrected)$")
    latency_ms: int = Field(ge=0, le=86_400_000)
    correction: Correction | None = None


def suggestion_payload(suggestion: Suggestion) -> dict:
    return {"category": suggestion.category, "urgency": suggestion.urgency, "team": suggestion.team,
            "confidence": suggestion.confidence, "rationale": suggestion.rationale, "strategy": suggestion.strategy}


async def _db_ok() -> tuple[bool, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, type(exc).__name__


@app.get("/healthz")
async def healthz():
    ok, detail = await _db_ok()
    return {"status": "ok" if ok else "degraded", "db": detail, "version": VERSION}


@app.get("/readyz")
async def readyz(response: Response):
    ok, detail = await _db_ok()
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": ok, "db": detail}


@app.get("/tickets/next")
async def next_ticket():
    decided = exists(select(StoredSuggestion.id).where(StoredSuggestion.ticket_id == Ticket.ticket_id))
    async with engine.connect() as connection:
        ticket = (await connection.execute(
            select(Ticket.ticket_id, Ticket.subject, Ticket.body, Ticket.from_email, Ticket.account_tier)
            .where(~decided).order_by(Ticket.ticket_id).limit(1)
        )).mappings().one_or_none()
    if ticket is None:
        return {"ticket": None, "suggestion": None}
    data = dict(ticket)
    return {"ticket": data, "suggestion": suggestion_payload(app.state.triager.suggest(data))}


@app.post("/tickets/{ticket_id}/decision", status_code=status.HTTP_201_CREATED)
async def save_decision(ticket_id: str, request: DecisionRequest):
    if request.decision == "corrected" and request.correction is None:
        raise HTTPException(status_code=422, detail="A correction requires category, urgency, and team.")
    if request.decision == "accepted" and request.correction is not None:
        raise HTTPException(status_code=422, detail="An accepted suggestion cannot include a correction.")
    async with engine.begin() as connection:
        ticket = (await connection.execute(
            select(Ticket.subject, Ticket.body, Ticket.from_email).where(Ticket.ticket_id == ticket_id)
        )).mappings().one_or_none()
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        already_decided = (await connection.execute(select(StoredSuggestion.id).where(StoredSuggestion.ticket_id == ticket_id))).scalar_one_or_none()
        if already_decided is not None:
            raise HTTPException(status_code=409, detail="This ticket has already been decided.")
        ticket_data = dict(ticket)
        suggestion = app.state.triager.suggest(ticket_data)
        correction = request.correction
        await connection.execute(StoredSuggestion.__table__.insert().values(
            ticket_id=ticket_id, **suggestion_payload(suggestion), latency_ms=request.latency_ms,
            decision=request.decision, corrected_category=correction.category if correction else None,
            corrected_urgency=correction.urgency if correction else None,
            corrected_team=correction.team if correction else None,
        ))
    return {"ok": True}


@app.get("/scoreboard")
async def get_scoreboard():
    return await scoreboard(engine, app.state.triager)
