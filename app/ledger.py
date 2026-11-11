"""Double-entry ledger invariants and payment reconciliation.

The ledger — not the cached `balance_minor` column — is the financial source
of truth. These checks verify that the two never silently diverge, which is
how a real finance team would catch an exploited business-logic flaw.
"""
from __future__ import annotations

from decimal import Decimal

from app.config import CURRENCY_SCALE
from app.db import connect


def _fmt(minor: int, currency: str) -> str:
    scale = CURRENCY_SCALE.get(currency, 2)
    return f"{Decimal(minor) / (10 ** scale):.{scale}f}"


def verify_ledger_integrity() -> dict:
    """Verify the two core double-entry invariants.

    1. Zero-sum per currency: every balanced posting nets to zero, so the sum
       of all ledger entries in each currency must be exactly zero.
    2. Projection consistency: each account's cached balance must equal the
       sum of its own ledger entries.
    """
    currency_violations = []
    account_violations = []
    with connect() as conn:
        rows = conn.execute(
            "SELECT currency, COALESCE(SUM(amount_minor),0) AS total FROM ledger_entries GROUP BY currency"
        ).fetchall()
        for row in rows:
            if row["total"] != 0:
                currency_violations.append({
                    "currency": row["currency"],
                    "net_minor": row["total"],
                    "net": _fmt(row["total"], row["currency"]),
                })
        accounts = conn.execute("SELECT id, owner, currency, balance_minor FROM accounts").fetchall()
        for acct in accounts:
            posted = conn.execute(
                "SELECT COALESCE(SUM(amount_minor),0) AS total FROM ledger_entries WHERE account_id=?",
                (acct["id"],),
            ).fetchone()["total"]
            if posted != acct["balance_minor"]:
                account_violations.append({
                    "account_id": acct["id"],
                    "owner": acct["owner"],
                    "currency": acct["currency"],
                    "cached_balance_minor": acct["balance_minor"],
                    "ledger_sum_minor": posted,
                    "drift_minor": acct["balance_minor"] - posted,
                })
    healthy = not currency_violations and not account_violations
    return {
        "healthy": healthy,
        "zero_sum_violations": currency_violations,
        "projection_violations": account_violations,
        "notice": "Ledger is the source of truth; the balance column is a projection of it.",
    }


def reconcile_onchain_mints() -> dict:
    """Reconcile on-chain MockUSDC mint events against internal on-ramp records.

    A successful RPC call is not proof of settlement, so the backend never trusts
    the API result alone: it compares what the chain actually emitted (Transfer
    from the zero address) against what the database recorded, and flags either
    side that has no match. Requires a running local chain and a deployment.
    """
    from app import chain
    try:
        events = chain.read_mint_events(0)
    except chain.ChainError as e:
        return {"available": False, "reason": e.message}
    with connect() as conn:
        rows = conn.execute(
            "SELECT customer_address, token_amount, tx_hash, block_number FROM onramp_mints"
        ).fetchall()
    by_tx = {r["tx_hash"].lower().removeprefix("0x"): dict(r) for r in rows}
    onchain_total = sum(e["value"] for e in events)
    recorded_total = sum(r["token_amount"] for r in rows)
    unrecorded = []  # minted on-chain but no internal record
    for e in events:
        if e["tx_hash"].lower().removeprefix("0x") not in by_tx:
            unrecorded.append({"to": e["to"], "value": e["value"], "tx_hash": e["tx_hash"]})
    missing_onchain = []  # internal record whose tx is not in chain events
    event_txs = {e["tx_hash"].lower().removeprefix("0x") for e in events}
    for r in rows:
        if r["tx_hash"].lower().removeprefix("0x") not in event_txs:
            missing_onchain.append({"tx_hash": r["tx_hash"], "token_amount": r["token_amount"]})
    return {
        "available": True,
        "reconciled": not unrecorded and not missing_onchain and onchain_total == recorded_total,
        "onchain_mint_total": onchain_total,
        "recorded_mint_total": recorded_total,
        "unrecorded_onchain_mints": unrecorded,
        "records_without_onchain_event": missing_onchain,
        "notice": "A successful API call is not settlement; the chain event is the proof.",
    }


def reconcile_payment_callbacks() -> dict:
    """Reconcile the payment-callback delivery log against credited deposits.

    Flags any event ID that was credited to a wallet more than once — the
    hallmark of a replayed, non-idempotent callback.
    """
    double_credits = []
    with connect() as conn:
        rows = conn.execute(
            """SELECT event_id, endpoint, COUNT(*) AS credited_count,
                      COALESCE(SUM(amount_minor),0) AS total_minor, currency
               FROM payment_callbacks
               WHERE outcome='credited' AND event_id IS NOT NULL
               GROUP BY event_id, endpoint, currency
               HAVING COUNT(*) > 1""",
        ).fetchall()
        for row in rows:
            double_credits.append({
                "event_id": row["event_id"],
                "endpoint": row["endpoint"],
                "times_credited": row["credited_count"],
                "total_credited": _fmt(row["total_minor"], row["currency"]),
                "currency": row["currency"],
            })
        totals = conn.execute(
            """SELECT outcome, COUNT(*) AS n FROM payment_callbacks GROUP BY outcome"""
        ).fetchall()
    return {
        "reconciled": not double_credits,
        "double_credited_events": double_credits,
        "delivery_outcomes": {row["outcome"]: row["n"] for row in totals},
        "notice": "A replayed event credited more than once indicates a non-idempotent callback.",
    }
