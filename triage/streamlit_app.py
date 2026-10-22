import os
import time

import httpx
import streamlit as st

API_URL = os.getenv("TRIAGE_API_URL", "http://localhost:8000")
CATEGORIES = ["billing_dispute", "delivery_delay", "damage_claim", "customs", "quote_request"]
URGENCIES = ["low", "normal", "high"]
TEAMS = ["finance", "ops-east", "claims", "compliance", "sales", "support"]


def api_get(path: str) -> dict:
    response = httpx.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def save_decision(ticket_id: str, payload: dict) -> None:
    response = httpx.post(f"{API_URL}/tickets/{ticket_id}/decision", json=payload, timeout=10)
    response.raise_for_status()


def load_ticket() -> None:
    st.session_state.current = api_get("/tickets/next")
    st.session_state.shown_at = time.monotonic()


st.set_page_config(page_title="TriageDesk", page_icon="✦", layout="centered")
st.title("TriageDesk")
st.caption("Rules-only triage baseline · every decision becomes labelled evaluation data")
try:
    metrics = api_get("/scoreboard")
    st.metric("Decisions", f"{metrics['decisions']} / {metrics['tickets']}")
    st.caption(f"Coverage {metrics['coverage_pct']}% · Accept rate {metrics['accept_rate_pct']}% · Accuracy against corrections {metrics['accuracy_against_corrections_pct'] if metrics['accuracy_against_corrections_pct'] is not None else 'n/a'}")
except httpx.HTTPError:
    st.error("The triage API is unavailable. Check that the API and database are running.")
    st.stop()

if "current" not in st.session_state:
    load_ticket()
current = st.session_state.current
ticket = current["ticket"]
suggestion = current["suggestion"]
if ticket is None:
    st.success("The queue is empty. Every available ticket has a recorded decision.")
    st.stop()

st.subheader(ticket["subject"])
st.caption(f"{ticket['ticket_id']} · {ticket['from_email']} · account tier: {ticket['account_tier'] or 'unknown'}")
st.write(ticket["body"])
st.divider()
if suggestion["confidence"] == 0:
    st.warning("Escalate: no rule matched. There is intentionally no guess.")
else:
    st.subheader("Rule suggestion")
    st.write(f"**{suggestion['category']}** → {suggestion['team']} · {suggestion['urgency']} urgency")
    st.caption(f"Confidence {suggestion['confidence']:.0%} · {suggestion['strategy']}")
st.info(suggestion["rationale"])

def latency() -> int:
    return int((time.monotonic() - st.session_state.shown_at) * 1000)

if st.button("Accept", type="primary", use_container_width=True):
    try:
        save_decision(ticket["ticket_id"], {"decision": "accepted", "latency_ms": latency()})
        load_ticket()
        st.rerun()
    except httpx.HTTPError as exc:
        st.error(f"Could not save the decision: {exc}")

with st.expander("Correct"):
    with st.form("correction"):
        category = st.selectbox("Correct category", CATEGORIES)
        urgency = st.selectbox("Correct urgency", URGENCIES, index=1)
        team = st.selectbox("Correct team", TEAMS)
        submitted = st.form_submit_button("Save correction")
    if submitted:
        try:
            save_decision(ticket["ticket_id"], {"decision": "corrected", "latency_ms": latency(), "correction": {"category": category, "urgency": urgency, "team": team}})
            load_ticket()
            st.rerun()
        except httpx.HTTPError as exc:
            st.error(f"Could not save the correction: {exc}")
