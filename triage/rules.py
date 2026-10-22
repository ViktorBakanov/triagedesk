from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Suggestion:
    category: str | None
    urgency: str | None
    team: str | None
    confidence: float
    rationale: str
    strategy: str = "rules-v1"


ESCALATE = Suggestion(None, None, None, 0.0, "no rule matched", "rules-v1")


class Triager(Protocol):
    def suggest(self, ticket: dict) -> Suggestion: ...


CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("billing_dispute", re.compile(r"\b(overcharg|double.?bill|refund|invoice.*wrong)\b", re.I)),
    ("delivery_delay", re.compile(r"\b(late|delay|still (?:hasn'?t|not) arriv|where is my)\b", re.I)),
    ("damage_claim", re.compile(r"\b(damag|broken|crushed|water.?logged)\b", re.I)),
    ("customs", re.compile(r"\b(customs|duty|clearance|hs code)\b", re.I)),
    ("quote_request", re.compile(r"\b(quote|rate card|pricing for|how much to ship)\b", re.I)),
]

CATEGORY_TEAM = {
    "billing_dispute": "finance",
    "delivery_delay": "ops-east",
    "damage_claim": "claims",
    "customs": "compliance",
    "quote_request": "sales",
}
TIER_URGENCY = {"platinum": "high", "gold": "high", "silver": "normal", "bronze": "low"}
URGENT_WORDS = re.compile(r"\b(urgent|asap|immediately|escalat|legal|solicitor)\b", re.I)


class RulesTriager:
    """The reliable baseline: keyword and account-tier rules only."""

    def __init__(self, accounts: dict[str, dict]):
        self.accounts = accounts

    def suggest(self, ticket: dict) -> Suggestion:
        text = f"{ticket.get('subject', '')}\n{ticket.get('body', '')}"
        rationale: list[str] = []
        category = None
        for name, pattern in CATEGORY_RULES:
            match = pattern.search(text)
            if match:
                category = name
                rationale.append(f"matched {name!r} on {match.group(0)!r}")
                break
        if category is None:
            return ESCALATE

        domain = (ticket.get("from_email") or "").rsplit("@", 1)[-1].lower()
        account = self.accounts.get(domain)
        if account:
            urgency = TIER_URGENCY.get(account["tier"], "normal")
            rationale.append(f"{domain} -> {account['tier']} tier -> {urgency}")
        else:
            urgency = "normal"
            rationale.append(f"unknown domain {domain!r}, defaulted to normal")

        if URGENT_WORDS.search(text):
            urgency = "high"
            rationale.append("urgent language in ticket")

        return Suggestion(
            category=category,
            urgency=urgency,
            team=CATEGORY_TEAM[category],
            confidence=0.85 if account else 0.55,
            rationale="; ".join(rationale),
        )
