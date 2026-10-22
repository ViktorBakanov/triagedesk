from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATA_DIR = Path(__file__).parent / "data"


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(16))


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String(320), index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.account_id"), nullable=True)
    account_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    loaded_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoredSuggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint("decision IN ('accepted', 'corrected')", name="suggestions_decision_valid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    team: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    strategy: Mapped[str] = mapped_column(String(64))
    proposed_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    latency_ms: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))
    corrected_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    corrected_urgency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    corrected_team: Mapped[str | None] = mapped_column(String(64), nullable=True)


async def load_accounts(engine: AsyncEngine) -> dict[str, dict[str, str]]:
    async with engine.connect() as connection:
        rows = (await connection.execute(
            select(Account.domain, Account.account_id, Account.tier)
        )).mappings().all()
    return {
        row["domain"]: {"account_id": row["account_id"], "tier": row["tier"]}
        for row in rows
    }


async def initialise_database(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        count = (await connection.execute(select(func.count()).select_from(Ticket))).scalar_one()
        if count:
            return

        accounts: dict[str, tuple[str, str]] = {}
        with (DATA_DIR / "accounts.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                accounts[row["domain"]] = (row["account_id"], row["tier"])
                await connection.execute(Account.__table__.insert().values(**row))

        with (DATA_DIR / "tickets.csv").open(encoding="utf-8", newline="") as stream:
            values = []
            for row in csv.DictReader(stream):
                domain = row["from_email"].rsplit("@", 1)[-1].lower()
                account = accounts.get(domain)
                values.append({
                    **row,
                    "account_id": account[0] if account else None,
                    "account_tier": account[1] if account else None,
                })
            await connection.execute(Ticket.__table__.insert(), values)
