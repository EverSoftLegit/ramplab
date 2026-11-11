"""Recovery sweep for interrupted ramp sagas.

If the process dies mid-conversion, a row can be left in an intermediate state.
This sweep resolves them deterministically and safely:

- on-ramp `fiat_reserved`: the fiat was debited but the mint was unconfirmed.
  We read the SecureRamp `FiatDepositCredited` events and match by provider
  reference. If the mint actually landed, we complete the conversion; if not, we
  refund the reserved fiat. Requires a live chain to decide safely.
- off-ramp `burned`: the USDC burn is confirmed (tx recorded) but the fiat
  credit did not complete. We credit the fiat. Safe to do without the chain.
- off-ramp `initiated`: the burn was never confirmed. We flag it for review
  rather than guessing, because a crash during the burn RPC is the one case we
  cannot settle from local state alone.

Every action is idempotent, so the sweep is safe to run repeatedly.
"""
from __future__ import annotations

from app import ramp
from app.db import connect


def _reserved_onramps(conn):
    return conn.execute(
        "SELECT * FROM ramp_conversions WHERE direction='on_ramp' AND status='fiat_reserved'"
    ).fetchall()


def _burned_offramps(conn):
    return conn.execute(
        "SELECT * FROM ramp_conversions WHERE direction='off_ramp' AND status='burned'"
    ).fetchall()


def _initiated_offramps(conn):
    return conn.execute(
        "SELECT * FROM ramp_conversions WHERE direction='off_ramp' AND status='initiated'"
    ).fetchall()


def _row_view(r):
    return {"reference": r["reference"], "owner": r["owner"], "direction": r["direction"],
            "status": r["status"], "usdc_minor": r["usdc_minor"], "fiat_minor": r["fiat_minor"]}


def scan() -> dict:
    """Report interrupted conversions and what recovery would do, without acting."""
    from app import chain
    with connect() as conn:
        reserved = [_row_view(r) for r in _reserved_onramps(conn)]
        burned = [_row_view(r) for r in _burned_offramps(conn)]
        initiated = [_row_view(r) for r in _initiated_offramps(conn)]
    chain_ok = chain.status().get("connected", False)
    return {
        "chain_available": chain_ok,
        "onramp_reserved": reserved,
        "offramp_burned": burned,
        "offramp_initiated_needs_review": initiated,
        "pending_total": len(reserved) + len(burned) + len(initiated),
    }


def run() -> dict:
    """Resolve interrupted conversions. Idempotent and safe to run repeatedly."""
    from app import chain
    actions = {"onramp_completed": 0, "onramp_refunded": 0, "offramp_settled": 0,
               "needs_review": [], "chain_available": True}

    # Off-ramp 'burned' can be settled without the chain (burn already confirmed).
    with connect() as conn:
        burned = _burned_offramps(conn)
    for r in burned:
        if ramp.settle_offramp_fiat(r["id"]):
            actions["offramp_settled"] += 1

    # On-ramp 'fiat_reserved' needs the chain to decide mint-landed vs not.
    try:
        events = chain.read_deposit_credited_events(0)
    except chain.ChainError as e:
        actions["chain_available"] = False
        actions["reason"] = e.message
        with connect() as conn:
            actions["needs_review"] = [_row_view(r) for r in _reserved_onramps(conn)]
        return actions

    credited_by_ref = {ev["provider_ref"]: ev for ev in events}
    with connect() as conn:
        reserved = _reserved_onramps(conn)
        initiated = _initiated_offramps(conn)
    for r in reserved:
        ev = credited_by_ref.get(r["reference"])
        if ev is not None:
            if ramp.complete_onramp(r["id"], ev["tx_hash"], ev["block_number"]):
                actions["onramp_completed"] += 1
        else:
            if ramp._compensate_onramp(r["owner"], r["fiat_currency"], r["fiat_minor"],
                                       r["id"], "recovery: mint not confirmed on-chain",
                                       final_status="failed_refunded"):
                actions["onramp_refunded"] += 1

    # Off-ramp 'initiated' cannot be settled from local state; flag for review.
    actions["needs_review"] = [_row_view(r) for r in initiated]
    return actions
