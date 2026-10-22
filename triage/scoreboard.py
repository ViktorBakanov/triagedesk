from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from triage.db import StoredSuggestion, Ticket
from triage.rules import Triager


async def scoreboard(engine: AsyncEngine, triager: Triager) -> dict[str, float | int | None]:
    """Return conservative metrics; corrections are the labelled evaluation set."""
    async with engine.connect() as connection:
        tickets = (await connection.execute(
            select(Ticket.subject, Ticket.body, Ticket.from_email)
        )).mappings().all()
        total = len(tickets)
        decided = (await connection.execute(select(func.count()).select_from(StoredSuggestion))).scalar_one()
        accepted = (await connection.execute(select(func.count()).select_from(StoredSuggestion).where(StoredSuggestion.decision == "accepted"))).scalar_one()
        corrected = (await connection.execute(select(func.count()).select_from(StoredSuggestion).where(StoredSuggestion.decision == "corrected"))).scalar_one()
        exact = (await connection.execute(
            select(func.count()).select_from(StoredSuggestion).where(
                StoredSuggestion.decision == "corrected",
                StoredSuggestion.category == StoredSuggestion.corrected_category,
                StoredSuggestion.urgency == StoredSuggestion.corrected_urgency,
                StoredSuggestion.team == StoredSuggestion.corrected_team,
            )
        )).scalar_one()

    covered = sum(triager.suggest(dict(ticket)).confidence > 0 for ticket in tickets)
    return {
        "tickets": total,
        "decisions": decided,
        "coverage_pct": round(covered / total * 100, 1) if total else 0.0,
        "accept_rate_pct": round(accepted / decided * 100, 1) if decided else 0.0,
        "accuracy_against_corrections_pct": round(exact / corrected * 100, 1) if corrected else None,
        "corrections": corrected,
    }


def one_line_scoreboard(metrics: dict[str, float | int | None]) -> str:
    accuracy = metrics["accuracy_against_corrections_pct"]
    accuracy_text = "n/a" if accuracy is None else f"{accuracy}%"
    return f"scoreboard: coverage={metrics['coverage_pct']}% accept_rate={metrics['accept_rate_pct']}% accuracy_against_corrections={accuracy_text}"
