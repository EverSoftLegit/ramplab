from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from app.config import CURRENCY_SCALE, CURRENCY_USD_VALUE, FEE_BPS, QUOTE_TTL_SECONDS
from app.db import connect, utc_now


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def parse_amount(amount: str, currency: str) -> int:
    if currency not in CURRENCY_SCALE:
        raise DomainError("Unsupported currency")
    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError):
        raise DomainError("Amount must be a decimal string")
    if not value.is_finite() or value <= 0:
        raise DomainError("Amount must be greater than zero")
    scaled = value * (10 ** CURRENCY_SCALE[currency])
    if scaled != scaled.to_integral_value():
        raise DomainError(f"Amount has too many decimal places for {currency}")
    minor = int(scaled)
    if minor <= 0 or minor > 9_000_000_000_000_000:
        raise DomainError("Amount is outside the supported demonstration range")
    return minor


def format_minor(minor: int, currency: str) -> str:
    scale = CURRENCY_SCALE[currency]
    value = Decimal(minor) / (10 ** scale)
    return f"{value:.{scale}f}"


def calculate_target_naive(source_minor: int, source: str, target: str, rate: Decimal) -> tuple[int, int]:
    """INTENTIONALLY VULNERABLE (RAMP-015): incorrect token decimal handling.

    Multiplies minor units by the rate directly, ignoring the decimal-place
    difference between source and target, so the result is wrong by a factor of
    10**(source_scale - target_scale)."""
    gross = Decimal(source_minor) * rate
    fee = gross * Decimal(FEE_BPS) / Decimal(10000)
    net = gross - fee
    return int(net.to_integral_value(rounding=ROUND_DOWN)), int(fee.to_integral_value(rounding=ROUND_DOWN))


def fee_minor_vulnerable(source_minor: int, source: str, target: str, rate: Decimal) -> int:
    """VULNERABLE fee policy (RAMP-016): truncates the fee, so sub-threshold
    conversions pay zero and can be split to avoid fees entirely."""
    _, fee = calculate_target(source_minor, source, target, rate)
    return fee


def fee_minor_secure(source_minor: int, source: str, target: str, rate: Decimal) -> int:
    """Hardened fee policy: any conversion with positive value pays at least one
    minor unit of fee, so splitting into dust cannot avoid fees."""
    gross_major = (Decimal(source_minor) / (10 ** CURRENCY_SCALE[source])) * rate
    _, fee = calculate_target(source_minor, source, target, rate)
    if gross_major > 0 and fee == 0:
        return 1
    return fee


def demo_rate(source: str, target: str) -> Decimal:
    if source not in CURRENCY_USD_VALUE or target not in CURRENCY_USD_VALUE:
        raise DomainError("Unsupported currency pair")
    return CURRENCY_USD_VALUE[source] / CURRENCY_USD_VALUE[target]


def calculate_target(source_minor: int, source: str, target: str, rate: Decimal) -> tuple[int, int]:
    source_major = Decimal(source_minor) / (10 ** CURRENCY_SCALE[source])
    gross_target_major = source_major * rate
    fee_major = gross_target_major * Decimal(FEE_BPS) / Decimal(10000)
    net_target_major = gross_target_major - fee_major
    target_scale = 10 ** CURRENCY_SCALE[target]
    target_minor = int((net_target_major * target_scale).to_integral_value(rounding=ROUND_DOWN))
    fee_minor = int((fee_major * target_scale).to_integral_value(rounding=ROUND_DOWN))
    if target_minor <= 0:
        raise DomainError("Conversion amount is too small after fees and rounding")
    return target_minor, fee_minor


def create_quote(owner: str, source: str, target: str, amount: str, rate_override: str | None = None) -> dict:
    if source not in CURRENCY_SCALE or target not in CURRENCY_SCALE:
        raise DomainError("Unsupported currency pair")
    if source == target:
        raise DomainError("Source and target currencies must differ")
    source_minor = parse_amount(amount, source)
    try:
        rate = Decimal(rate_override) if rate_override is not None else demo_rate(source, target)
    except (InvalidOperation, TypeError):
        raise DomainError("Rate must be a valid decimal string")
    if not rate.is_finite() or rate <= 0 or rate > Decimal("1000000000000"):
        raise DomainError("Rate must be a positive finite demonstration value")
    from app.db import account_for
    source_account = account_for(owner, source)
    target_account = account_for(owner, target)
    if source_account is None or target_account is None:
        raise DomainError("Demo account not found", 404)
    target_minor, fee_minor = calculate_target(source_minor, source, target, rate)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(seconds=QUOTE_TTL_SECONDS)
    quote_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """INSERT INTO quotes(id,owner,source_account_id,target_account_id,source_amount_minor,
               target_amount_minor,rate,fee_minor,status,expires_at,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (quote_id, owner, source_account["id"], target_account["id"], source_minor,
             target_minor, str(rate), fee_minor, "open", expires.isoformat(timespec="seconds"),
             created.isoformat(timespec="seconds")),
        )
    return {
        "quote_id": quote_id,
        "owner": owner,
        "source_currency": source,
        "target_currency": target,
        "source_amount": format_minor(source_minor, source),
        "target_amount": format_minor(target_minor, target),
        "rate": str(rate),
        "fee": format_minor(fee_minor, target),
        "fee_bps": FEE_BPS,
        "expires_at": expires.isoformat(timespec="seconds"),
        "rate_notice": "Fictional fixed teaching rate. Not a live FX or crypto price.",
    }


QUOTE_TRANSITIONS = {
    "open": {"consumed", "expired", "cancelled"},
    "consumed": set(),
    "expired": set(),
    "cancelled": set(),
}


def cancel_quote(owner: str, quote_id: str) -> dict:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        quote = conn.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
        if quote is None or quote["owner"] != owner:
            raise DomainError("Quote not found", 404)
        if "cancelled" not in QUOTE_TRANSITIONS.get(quote["status"], set()):
            raise DomainError(f"Quote in state '{quote['status']}' cannot be cancelled", 409)
        conn.execute("UPDATE quotes SET status='cancelled' WHERE id=?", (quote_id,))
        conn.commit()
    return {"quote_id": quote_id, "status": "cancelled"}


def execute_conversion(owner: str, quote_id: str, allow_expired: bool = False) -> dict:
    """Execute a quoted conversion.

    allow_expired exists only to power the RAMP-017 lab endpoint: when True the
    expiry check is skipped, so a stale quote can be executed at an outdated rate.
    The default (and the hardened path) always enforces expiry.
    """
    tx_id = uuid.uuid4().hex
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        quote = conn.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
        if quote is None or quote["owner"] != owner:
            raise DomainError("Quote not found", 404)
        if quote["status"] != "open":
            raise DomainError("Quote has already been used", 409)
        expires = datetime.fromisoformat(quote["expires_at"])
        if expires < datetime.now(timezone.utc) and not allow_expired:
            conn.execute("UPDATE quotes SET status='expired' WHERE id=?", (quote_id,))
            raise DomainError("Quote has expired", 409)
        source = conn.execute("SELECT * FROM accounts WHERE id=?", (quote["source_account_id"],)).fetchone()
        target = conn.execute("SELECT * FROM accounts WHERE id=?", (quote["target_account_id"],)).fetchone()
        treasury_source = conn.execute("SELECT * FROM accounts WHERE owner='treasury' AND currency=?", (source["currency"],)).fetchone()
        treasury_target = conn.execute("SELECT * FROM accounts WHERE owner='treasury' AND currency=?", (target["currency"],)).fetchone()
        if source["owner"] != owner or target["owner"] != owner:
            raise DomainError("Account ownership mismatch", 403)
        if source["balance_minor"] < quote["source_amount_minor"]:
            raise DomainError("Insufficient demo balance", 409)

        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?",
                     (quote["source_amount_minor"], source["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?",
                     (quote["source_amount_minor"], treasury_source["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?",
                     (quote["target_amount_minor"], treasury_target["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?",
                     (quote["target_amount_minor"], target["id"]))

        reference = f"RAMP-{tx_id[:12].upper()}"
        conn.execute(
            """INSERT INTO transactions(id,owner,kind,source_currency,target_currency,source_amount_minor,
               target_amount_minor,fee_minor,status,reference,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (tx_id, owner, "conversion", source["currency"], target["currency"],
             quote["source_amount_minor"], quote["target_amount_minor"], quote["fee_minor"],
             "completed", reference, now),
        )
        entries = [
            (source["id"], -quote["source_amount_minor"], source["currency"], "Customer conversion debit"),
            (treasury_source["id"], quote["source_amount_minor"], source["currency"], "Treasury conversion source"),
            (treasury_target["id"], -quote["target_amount_minor"], target["currency"], "Treasury conversion destination"),
            (target["id"], quote["target_amount_minor"], target["currency"], "Customer conversion credit"),
        ]
        for account_id, amount_minor, currency, description in entries:
            conn.execute(
                "INSERT INTO ledger_entries(id,transaction_id,account_id,amount_minor,currency,description,created_at) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, tx_id, account_id, amount_minor, currency, description, now),
            )
        conn.execute("UPDATE quotes SET status='consumed' WHERE id=?", (quote_id,))
        conn.commit()
    return {
        "transaction_id": tx_id,
        "reference": reference,
        "status": "completed",
        "source_currency": source["currency"],
        "source_amount": format_minor(quote["source_amount_minor"], source["currency"]),
        "target_currency": target["currency"],
        "target_amount": format_minor(quote["target_amount_minor"], target["currency"]),
    }


def withdraw_vulnerable(owner: str, currency: str, amount: str) -> dict:
    """INTENTIONALLY VULNERABLE (RAMP-007): check-then-act with no transaction.

    Reads the balance, yields, then writes — widening the race window so two
    concurrent withdrawals both pass the check and overdraw (double-spend).
    """
    import time
    amount_minor = parse_amount(amount, currency)
    # Phase 1: read balance on its own connection.
    with connect() as conn:
        acct = conn.execute("SELECT id, balance_minor FROM accounts WHERE owner=? AND currency=?",
                            (owner, currency)).fetchone()
        if acct is None:
            raise DomainError("Account not found", 404)
        account_id, bal = acct["id"], acct["balance_minor"]
    if bal < amount_minor:
        raise DomainError("Insufficient funds", 409)
    # Non-atomic gap: another request can read the same balance here.
    time.sleep(0.05)
    # Phase 2: write the decremented balance on a fresh connection.
    with connect() as conn:
        conn.execute("UPDATE accounts SET balance_minor=? WHERE id=?", (bal - amount_minor, account_id))
    return {"status": "withdrawn", "amount": format_minor(amount_minor, currency), "currency": currency}


def withdraw_secure(owner: str, currency: str, amount: str) -> dict:
    """Hardened: the check and the debit happen inside one serialised transaction."""
    amount_minor = parse_amount(amount, currency)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        acct = conn.execute("SELECT * FROM accounts WHERE owner=? AND currency=?", (owner, currency)).fetchone()
        if acct is None:
            raise DomainError("Account not found", 404)
        if acct["balance_minor"] < amount_minor:
            raise DomainError("Insufficient funds", 409)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (amount_minor, acct["id"]))
        conn.commit()
    return {"status": "withdrawn", "amount": format_minor(amount_minor, currency), "currency": currency}


def transaction_by_id(tx_id: str, owner: str | None = None) -> dict:
    """Fetch a transaction. When owner is given, scope to it (hardened); otherwise
    return it regardless of owner (the lab/IDOR behaviour)."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id=?", (tx_id,)).fetchone()
    if row is None:
        raise DomainError("Transaction not found", 404)
    if owner is not None and row["owner"] != owner:
        raise DomainError("Transaction not found", 404)
    return {k: row[k] for k in row.keys()}


PROFILE_COLUMNS = ("display_name", "email", "role", "status", "kyc_level")
# Only these may be set by the account holder themselves.
PROFILE_SELF_EDITABLE = ("display_name", "email")


def get_profile(owner: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE owner=?", (owner,)).fetchone()
    if row is None:
        raise DomainError("Profile not found", 404)
    return {k: row[k] for k in ("owner",) + PROFILE_COLUMNS}


def _apply_profile(owner: str, fields: dict, allowed: tuple) -> dict:
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_profile(owner)
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT owner FROM profiles WHERE owner=?", (owner,)).fetchone() is None:
            raise DomainError("Profile not found", 404)
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE profiles SET {sets}, updated_at=? WHERE owner=?",
                     (*updates.values(), utc_now(), owner))
        conn.commit()
    return get_profile(owner)


def update_profile_vulnerable(owner: str, fields: dict) -> dict:
    """INTENTIONALLY VULNERABLE: binds every known column from the request body,
    so a caller can escalate role/status/kyc_level via mass assignment."""
    return _apply_profile(owner, fields, PROFILE_COLUMNS)


def update_profile_secure(owner: str, fields: dict) -> dict:
    """Hardened: only self-editable fields are bound; privileged fields are ignored."""
    return _apply_profile(owner, fields, PROFILE_SELF_EDITABLE)


def admin_credit_vulnerable(owner: str, currency: str, amount: str) -> dict:
    """INTENTIONALLY VULNERABLE (RAMP-021): bumps the balance column directly with
    no ledger entry, so the cached balance and the ledger silently diverge."""
    amount_minor = parse_amount(amount, currency)
    with connect() as conn:
        row = conn.execute("SELECT id FROM accounts WHERE owner=? AND currency=?", (owner, currency)).fetchone()
        if row is None:
            raise DomainError("Account not found", 404)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (amount_minor, row["id"]))
    return {"status": "credited", "amount": format_minor(amount_minor, currency), "currency": currency,
            "lab_warning": "Balance bumped with no ledger entry — the invariant is now broken."}


def admin_credit_secure(owner: str, currency: str, amount: str) -> dict:
    """Hardened: credits via a balanced double-entry posting (equity → customer),
    so the ledger remains the source of truth and the invariant holds."""
    amount_minor = parse_amount(amount, currency)
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cust = conn.execute("SELECT id FROM accounts WHERE owner=? AND currency=?", (owner, currency)).fetchone()
        equity = conn.execute("SELECT id FROM accounts WHERE owner='equity' AND currency=?", (currency,)).fetchone()
        if cust is None or equity is None:
            raise DomainError("Account not found", 404)
        tx_id = uuid.uuid4().hex
        reference = f"ADJ-{tx_id[:12].upper()}"
        conn.execute(
            """INSERT INTO transactions(id,owner,kind,source_currency,target_currency,source_amount_minor,
               target_amount_minor,fee_minor,status,reference,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (tx_id, owner, "admin_credit", currency, currency, amount_minor, amount_minor, 0,
             "completed", reference, now),
        )
        for account_id, delta, desc in [
            (equity["id"], -amount_minor, "Admin credit equity debit"),
            (cust["id"], amount_minor, "Admin credit customer credit"),
        ]:
            conn.execute(
                "INSERT INTO ledger_entries(id,transaction_id,account_id,amount_minor,currency,description,created_at) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, tx_id, account_id, delta, currency, desc, now),
            )
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (amount_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (amount_minor, equity["id"]))
        conn.commit()
    return {"status": "credited", "amount": format_minor(amount_minor, currency), "currency": currency, "reference": reference}


def record_onramp_mint(owner: str, customer_address: str, token_amount: int,
                       provider_ref: str, tx_hash: str, block_number: int | None) -> str:
    """Persist the association between an on-chain mint and the internal on-ramp."""
    mint_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """INSERT INTO onramp_mints(id,owner,customer_address,token_amount,provider_ref,
               tx_hash,block_number,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (mint_id, owner, customer_address, token_amount, provider_ref, tx_hash, block_number, utc_now()),
        )
    return mint_id


def _log_callback(conn, endpoint, event_id, owner, account_id, amount_minor, currency, outcome, tx_id):
    """Append-only record of every payment callback delivery, for reconciliation.

    This is written on the vulnerable and hardened paths alike so that a
    reconciliation tool can detect a replayed event that was credited more
    than once — the vulnerable path's defining symptom.
    """
    conn.execute(
        """INSERT INTO payment_callbacks(id,endpoint,event_id,owner,account_id,amount_minor,
           currency,outcome,transaction_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (uuid.uuid4().hex, endpoint, event_id, owner, account_id, amount_minor, currency,
         outcome, tx_id, utc_now()),
    )


def create_deposit(owner: str, account_id: str, amount: str, event_id: str, *,
                   idempotent: bool, endpoint: str = "unknown") -> dict:
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        account = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if account is None:
            _log_callback(conn, endpoint, event_id, owner, account_id, None, None, "rejected_account_not_found", None)
            conn.commit()
            raise DomainError("Account not found", 404)
        if account["owner"] != owner:
            _log_callback(conn, endpoint, event_id, owner, account_id, None, account["currency"], "rejected_ownership", None)
            conn.commit()
            raise DomainError("Account ownership mismatch", 403)
        amount_minor = parse_amount(amount, account["currency"])
        if idempotent:
            already = conn.execute("SELECT event_id FROM webhook_events WHERE event_id=?", (event_id,)).fetchone()
            if already:
                _log_callback(conn, endpoint, event_id, owner, account_id, amount_minor, account["currency"], "duplicate_ignored", None)
                conn.commit()
                return {"status": "duplicate_ignored", "event_id": event_id}
            conn.execute(
                "INSERT INTO webhook_events(event_id,account_id,amount_minor,currency,created_at) VALUES(?,?,?,?,?)",
                (event_id, account_id, amount_minor, account["currency"], now),
            )
        clearing = conn.execute("SELECT * FROM accounts WHERE owner='clearing' AND currency=?", (account["currency"],)).fetchone()
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (amount_minor, account_id))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (amount_minor, clearing["id"]))
        tx_id = uuid.uuid4().hex
        reference = f"DEP-{tx_id[:12].upper()}"
        conn.execute(
            """INSERT INTO transactions(id,owner,kind,source_currency,target_currency,source_amount_minor,
               target_amount_minor,fee_minor,status,reference,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (tx_id, owner, "simulated_deposit", account["currency"], account["currency"],
             amount_minor, amount_minor, 0, "completed", reference, now),
        )
        for a_id, delta, desc in [
            (clearing["id"], -amount_minor, "Mock payment clearing debit"),
            (account_id, amount_minor, "Simulated customer deposit credit"),
        ]:
            conn.execute(
                "INSERT INTO ledger_entries(id,transaction_id,account_id,amount_minor,currency,description,created_at) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, tx_id, a_id, delta, account["currency"], desc, now),
            )
        _log_callback(conn, endpoint, event_id, owner, account_id, amount_minor, account["currency"], "credited", tx_id)
        conn.commit()
    return {"status": "credited", "event_id": event_id, "reference": reference,
            "amount": format_minor(amount_minor, account["currency"]), "currency": account["currency"]}
