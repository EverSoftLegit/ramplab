"""Integrated fiat <-> on-chain USDC conversions (on-ramp and off-ramp).

These span two systems that cannot share a transaction — the internal SQLite
ledger and the local blockchain — so each flow is a saga with an explicit state
machine and a compensating action. The invariants:

- On-ramp debits internal fiat *first* (reliable, local), then mints on-chain.
  If the mint fails, the fiat debit is compensated (refunded). We never mint
  without a confirmed fiat reservation, and never keep fiat reserved without a
  mint.
- Off-ramp burns on-chain USDC *first* (external, the irreversible step), then
  credits internal fiat. We never credit fiat without a confirmed burn.

Fiat moves between the customer and the internal `treasury` account; on-chain
USDC is minted/burned by the authorised operator. USDC is tracked on-chain, not
in the internal ledger, so the double-entry fiat invariant still holds.
"""
from __future__ import annotations

import uuid

from app import chain
from app.config import CURRENCY_SCALE, DEMO_ADDRESSES
from app.db import connect, utc_now
from app.domain import DomainError, calculate_target, demo_rate, format_minor, parse_amount

USDC = "USDC"


def _address_for(owner: str) -> str:
    addr = DEMO_ADDRESSES.get(owner)
    if not addr:
        raise DomainError(f"No on-chain address mapped for demo identity '{owner}'", 400)
    return addr


def _accounts(conn, owner, currency):
    cust = conn.execute("SELECT * FROM accounts WHERE owner=? AND currency=?", (owner, currency)).fetchone()
    treas = conn.execute("SELECT * FROM accounts WHERE owner='treasury' AND currency=?", (currency,)).fetchone()
    if cust is None or treas is None:
        raise DomainError("Demo account not found", 404)
    return cust, treas


def _post(conn, tx_id, owner, kind, fiat_currency, fiat_minor, reference, entries, now):
    conn.execute(
        """INSERT INTO transactions(id,owner,kind,source_currency,target_currency,
           source_amount_minor,target_amount_minor,fee_minor,status,reference,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (tx_id, owner, kind, fiat_currency, USDC, fiat_minor, fiat_minor, 0, "completed", reference, now),
    )
    for account_id, delta, desc in entries:
        conn.execute(
            "INSERT INTO ledger_entries(id,transaction_id,account_id,amount_minor,currency,description,created_at) VALUES(?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, tx_id, account_id, delta, fiat_currency, desc, now),
        )


def on_ramp(owner: str, fiat_currency: str, fiat_amount: str) -> dict:
    fiat_currency = fiat_currency.upper()
    if fiat_currency == USDC:
        raise DomainError("On-ramp source must be a fiat currency", 400)
    address = _address_for(owner)
    fiat_minor = parse_amount(fiat_amount, fiat_currency)
    rate = demo_rate(fiat_currency, USDC)
    usdc_minor, fee_minor = calculate_target(fiat_minor, fiat_currency, USDC, rate)
    conv_id = uuid.uuid4().hex
    reference = f"RAMPON-{conv_id[:12].upper()}"
    now = utc_now()

    # Phase 1 — reserve fiat internally (atomic, local).
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cust, treas = _accounts(conn, owner, fiat_currency)
        if cust["balance_minor"] < fiat_minor:
            raise DomainError("Insufficient demo fiat balance", 409)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (fiat_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (fiat_minor, treas["id"]))
        tx_id = uuid.uuid4().hex
        _post(conn, tx_id, owner, "onramp_fiat_reserve", fiat_currency, fiat_minor, reference,
              [(cust["id"], -fiat_minor, "On-ramp fiat reserved"),
               (treas["id"], fiat_minor, "On-ramp fiat into treasury")], now)
        conn.execute(
            """INSERT INTO ramp_conversions(id,owner,direction,fiat_currency,fiat_minor,usdc_minor,
               customer_address,status,tx_hash,reference,detail,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (conv_id, owner, "on_ramp", fiat_currency, fiat_minor, usdc_minor, address,
             "fiat_reserved", None, reference, None, now, now),
        )
        conn.commit()

    # Phase 2 — mint on-chain. On failure, compensate the fiat reservation.
    try:
        result = chain.confirm_deposit_onchain(address, usdc_minor, reference.encode())
    except Exception as exc:
        _compensate_onramp(owner, fiat_currency, fiat_minor, conv_id, str(exc))
        if isinstance(exc, (DomainError, chain.ChainError)):
            raise
        raise chain.ChainError(f"On-chain mint failed; fiat refunded: {exc}", 502)

    # Phase 3 — record success.
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE ramp_conversions SET status='completed', tx_hash=?, updated_at=? WHERE id=?",
                     (result["tx_hash"], utc_now(), conv_id))
        conn.execute(
            """INSERT INTO onramp_mints(id,owner,customer_address,token_amount,provider_ref,tx_hash,block_number,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, owner, result["customer"], usdc_minor, reference,
             result["tx_hash"], result["block_number"], utc_now()),
        )
        conn.commit()
    return {
        "conversion_id": conv_id, "reference": reference, "status": "completed",
        "direction": "on_ramp", "fiat_currency": fiat_currency,
        "fiat_amount": format_minor(fiat_minor, fiat_currency),
        "usdc_amount": format_minor(usdc_minor, USDC), "fee": format_minor(fee_minor, USDC),
        "customer_address": address, "tx_hash": result["tx_hash"],
        "onchain_balance": format_minor(result["balance_after"], USDC),
    }


def settle_offramp_fiat(conv_id: str) -> bool:
    """Credit the fiat leg of a burned off-ramp. Idempotent: only acts on 'burned'.

    Shared by the normal off-ramp flow and the recovery sweep, so an off-ramp
    interrupted after the burn but before the fiat credit can be completed safely.
    """
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM ramp_conversions WHERE id=?", (conv_id,)).fetchone()
        if row is None or row["status"] != "burned":
            conn.commit()
            return False
        cust, treas = _accounts(conn, row["owner"], row["fiat_currency"])
        fiat_minor = row["fiat_minor"]
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (fiat_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (fiat_minor, treas["id"]))
        tx_id = uuid.uuid4().hex
        _post(conn, tx_id, row["owner"], "offramp_settle", row["fiat_currency"], fiat_minor, row["reference"],
              [(treas["id"], -fiat_minor, "Off-ramp fiat payout from treasury"),
               (cust["id"], fiat_minor, "Off-ramp fiat credited")], now)
        conn.execute("UPDATE ramp_conversions SET status='completed', updated_at=? WHERE id=?", (now, conv_id))
        conn.commit()
    return True


def on_ramp_naive(owner: str, fiat_currency: str, fiat_amount: str) -> dict:
    """INTENTIONALLY VULNERABLE (RAMP-008): mints on-chain FIRST, then debits fiat.

    If the fiat debit fails (e.g. insufficient balance), the USDC has already been
    minted — unbacked value created from nothing. This is the wrong saga ordering;
    the hardened on_ramp reserves fiat first and compensates on mint failure.
    """
    fiat_currency = fiat_currency.upper()
    if fiat_currency == USDC:
        raise DomainError("On-ramp source must be a fiat currency", 400)
    address = _address_for(owner)
    fiat_minor = parse_amount(fiat_amount, fiat_currency)
    rate = demo_rate(fiat_currency, USDC)
    usdc_minor, _ = calculate_target(fiat_minor, fiat_currency, USDC, rate)
    conv_id = uuid.uuid4().hex
    reference = f"RAMPNAIVE-{conv_id[:10].upper()}"
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO ramp_conversions(id,owner,direction,fiat_currency,fiat_minor,usdc_minor,
               customer_address,status,tx_hash,reference,detail,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (conv_id, owner, "on_ramp", fiat_currency, fiat_minor, usdc_minor, address,
             "initiated", None, reference, "naive mint-first ordering", now, now),
        )

    # Phase 1 (WRONG ORDER): mint on-chain first.
    result = chain.confirm_deposit_onchain(address, usdc_minor, reference.encode())
    with connect() as conn:
        conn.execute("UPDATE ramp_conversions SET status='minted', tx_hash=?, updated_at=? WHERE id=?",
                     (result["tx_hash"], utc_now(), conv_id))
        conn.execute(
            """INSERT INTO onramp_mints(id,owner,customer_address,token_amount,provider_ref,tx_hash,block_number,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (uuid.uuid4().hex, owner, result["customer"], usdc_minor, reference,
             result["tx_hash"], result["block_number"], utc_now()),
        )

    # Phase 2: try to debit fiat — may fail AFTER the mint already happened.
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cust, treas = _accounts(conn, owner, fiat_currency)
        if cust["balance_minor"] < fiat_minor:
            conn.execute("UPDATE ramp_conversions SET status='unbacked', detail=?, updated_at=? WHERE id=?",
                         ("fiat debit failed AFTER mint — USDC is unbacked", utc_now(), conv_id))
            conn.commit()
            raise DomainError(
                "Fiat debit failed after the on-chain mint — unbacked USDC was created. "
                "This is the RAMP-008 flaw: mint-first ordering with no compensation.", 409)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (fiat_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (fiat_minor, treas["id"]))
        tx_id = uuid.uuid4().hex
        _post(conn, tx_id, owner, "onramp_fiat_reserve", fiat_currency, fiat_minor, reference,
              [(cust["id"], -fiat_minor, "Naive on-ramp fiat debit"),
               (treas["id"], fiat_minor, "Naive on-ramp fiat into treasury")], now)
        conn.execute("UPDATE ramp_conversions SET status='completed', updated_at=? WHERE id=?", (utc_now(), conv_id))
        conn.commit()
    return {"conversion_id": conv_id, "reference": reference, "status": "completed",
            "usdc_amount": format_minor(usdc_minor, USDC), "tx_hash": result["tx_hash"],
            "lab_warning": "Mint happened before the fiat debit — unbacked if the debit fails."}


def _compensate_onramp(owner, fiat_currency, fiat_minor, conv_id, detail, final_status="failed"):
    """Refund a reserved on-ramp. Idempotent: only acts while status is 'fiat_reserved'."""
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM ramp_conversions WHERE id=?", (conv_id,)).fetchone()
        if row is not None and row["status"] != "fiat_reserved":
            conn.commit()
            return False
        cust, treas = _accounts(conn, owner, fiat_currency)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (fiat_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (fiat_minor, treas["id"]))
        tx_id = uuid.uuid4().hex
        _post(conn, tx_id, owner, "onramp_refund", fiat_currency, fiat_minor, f"RAMPRF-{tx_id[:12].upper()}",
              [(treas["id"], -fiat_minor, "On-ramp refund from treasury"),
               (cust["id"], fiat_minor, "On-ramp fiat refunded")], now)
        conn.execute("UPDATE ramp_conversions SET status=?, detail=?, updated_at=? WHERE id=?",
                     (final_status, detail[:300], now, conv_id))
        conn.commit()
    return True


def complete_onramp(conv_id: str, tx_hash: str, block_number: int | None) -> bool:
    """Finish a reserved on-ramp whose mint is confirmed on-chain. Idempotent."""
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM ramp_conversions WHERE id=?", (conv_id,)).fetchone()
        if row is None or row["status"] != "fiat_reserved":
            conn.commit()
            return False
        conn.execute("UPDATE ramp_conversions SET status='completed', tx_hash=?, updated_at=? WHERE id=?",
                     (tx_hash, now, conv_id))
        exists = conn.execute("SELECT id FROM onramp_mints WHERE tx_hash=?", (tx_hash,)).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO onramp_mints(id,owner,customer_address,token_amount,provider_ref,tx_hash,block_number,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, row["owner"], row["customer_address"], row["usdc_minor"],
                 row["reference"], tx_hash, block_number, now),
            )
        conn.commit()
    return True


def off_ramp(owner: str, fiat_currency: str, usdc_amount: str) -> dict:
    fiat_currency = fiat_currency.upper()
    if fiat_currency == USDC:
        raise DomainError("Off-ramp target must be a fiat currency", 400)
    address = _address_for(owner)
    usdc_minor = parse_amount(usdc_amount, USDC)
    rate = demo_rate(USDC, fiat_currency)
    fiat_minor, fee_minor = calculate_target(usdc_minor, USDC, fiat_currency, rate)
    conv_id = uuid.uuid4().hex
    reference = f"RAMPOFF-{conv_id[:12].upper()}"
    now = utc_now()

    # Record intent before the irreversible on-chain step.
    with connect() as conn:
        conn.execute(
            """INSERT INTO ramp_conversions(id,owner,direction,fiat_currency,fiat_minor,usdc_minor,
               customer_address,status,tx_hash,reference,detail,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (conv_id, owner, "off_ramp", fiat_currency, fiat_minor, usdc_minor, address,
             "initiated", None, reference, None, now, now),
        )

    # Phase 1 — burn on-chain first (the irreversible step). No fiat moves yet.
    try:
        result = chain.redeem_offchain(address, usdc_minor)
    except Exception as exc:
        with connect() as conn:
            conn.execute("UPDATE ramp_conversions SET status='failed', detail=?, updated_at=? WHERE id=?",
                         (str(exc)[:300], utc_now(), conv_id))
        raise

    # Burn confirmed: record the tx and move to 'burned' before crediting fiat.
    # If the process dies here, recovery credits the pending fiat from this state.
    with connect() as conn:
        conn.execute("UPDATE ramp_conversions SET status='burned', tx_hash=?, updated_at=? WHERE id=?",
                     (result["tx_hash"], utc_now(), conv_id))

    # Phase 2 — credit internal fiat (atomic, local, idempotent).
    settle_offramp_fiat(conv_id)
    return {
        "conversion_id": conv_id, "reference": reference, "status": "completed",
        "direction": "off_ramp", "fiat_currency": fiat_currency,
        "usdc_amount": format_minor(usdc_minor, USDC),
        "fiat_amount": format_minor(fiat_minor, fiat_currency), "fee": format_minor(fee_minor, fiat_currency),
        "customer_address": address, "tx_hash": result["tx_hash"],
        "onchain_balance": format_minor(result["balance_after"], USDC),
    }
