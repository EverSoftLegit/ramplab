from __future__ import annotations

import sqlite3
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

from app.config import CURRENCY_SCALE, DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(owner, currency)
);
CREATE TABLE IF NOT EXISTS quotes (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    source_account_id TEXT NOT NULL REFERENCES accounts(id),
    target_account_id TEXT NOT NULL REFERENCES accounts(id),
    source_amount_minor INTEGER NOT NULL,
    target_amount_minor INTEGER NOT NULL,
    rate TEXT NOT NULL,
    fee_minor INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_currency TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    source_amount_minor INTEGER NOT NULL,
    target_amount_minor INTEGER NOT NULL,
    fee_minor INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    reference TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL REFERENCES transactions(id),
    account_id TEXT NOT NULL REFERENCES accounts(id),
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_callbacks (
    id TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    event_id TEXT,
    owner TEXT,
    account_id TEXT,
    amount_minor INTEGER,
    currency TEXT,
    outcome TEXT NOT NULL,
    transaction_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_nonces (
    owner TEXT PRIMARY KEY,
    nonce INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS profiles (
    owner TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',
    status TEXT NOT NULL DEFAULT 'active',
    kyc_level TEXT NOT NULL DEFAULT 'basic',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ramp_conversions (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    direction TEXT NOT NULL,
    fiat_currency TEXT NOT NULL,
    fiat_minor INTEGER NOT NULL,
    usdc_minor INTEGER NOT NULL,
    customer_address TEXT NOT NULL,
    status TEXT NOT NULL,
    tx_hash TEXT,
    reference TEXT NOT NULL UNIQUE,
    detail TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onramp_mints (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    customer_address TEXT NOT NULL,
    token_amount INTEGER NOT NULL,
    provider_ref TEXT,
    tx_hash TEXT NOT NULL UNIQUE,
    block_number INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_owner ON accounts(owner);
CREATE INDEX IF NOT EXISTS idx_transactions_owner_created ON transactions(owner, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_transaction ON ledger_entries(transaction_id);
CREATE INDEX IF NOT EXISTS idx_ledger_account ON ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_callbacks_event ON payment_callbacks(event_id);
"""

# Owner names that are internal system accounts rather than demo customers.
SYSTEM_OWNERS = ("treasury", "clearing", "equity")
CUSTOMER_OWNERS = ("alice", "bob")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
    seed_demo_data()


# Seeded opening balances for demo customers. Internal system accounts
# (treasury, clearing, equity) start at zero and move via ledger postings.
STARTING_BALANCES = {
    "alice": {"NGN": "50000000", "GHS": "100000", "KES": "5000000", "ZAR": "1000000",
              "USD": "100000", "EUR": "100000", "GBP": "100000", "USDC": "500000000"},
    "bob": {"NGN": "25000000", "GHS": "50000", "KES": "2500000", "ZAR": "500000",
            "USD": "50000", "EUR": "50000", "GBP": "50000", "USDC": "250000000"},
}
ALL_CURRENCIES = ("NGN", "GHS", "KES", "ZAR", "USD", "EUR", "GBP", "USDC")


def _ensure_account(conn: sqlite3.Connection, owner: str, currency: str, now: str) -> str:
    row = conn.execute(
        "SELECT id FROM accounts WHERE owner=? AND currency=?", (owner, currency)
    ).fetchone()
    if row:
        return row["id"]
    account_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO accounts(id, owner, currency, balance_minor, created_at) VALUES(?,?,?,?,?)",
        (account_id, owner, currency, 0, now),
    )
    return account_id


def seed_demo_data() -> None:
    """Seed demo accounts and post opening balances as double-entry ledger rows.

    Every customer opening balance is a balanced posting against an internal
    `equity` account, so the ledger — not the cached balance column — is the
    financial source of truth and the invariant checker can verify them.
    """
    now = utc_now()
    with connect() as conn:
        # Create all accounts (customers + system owners) at zero balance.
        for owner in CUSTOMER_OWNERS + SYSTEM_OWNERS:
            for currency in ALL_CURRENCIES:
                _ensure_account(conn, owner, currency, now)

        # Seed demo customer profiles (idempotent).
        demo_profiles = {
            "alice": ("Alice Customer", "alice@ramplab.test"),
            "bob": ("Bob Customer", "bob@ramplab.test"),
        }
        for owner, (name, email) in demo_profiles.items():
            exists = conn.execute("SELECT owner FROM profiles WHERE owner=?", (owner,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO profiles(owner,display_name,email,role,status,kyc_level,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (owner, name, email, "customer", "active", "basic", now),
                )

        # Only seed opening balances once (idempotent on the opening reference).
        for owner, balances in STARTING_BALANCES.items():
            for currency, balance in balances.items():
                minor = int(balance)
                if minor == 0:
                    continue
                reference = f"OPEN-{owner}-{currency}".upper()
                exists = conn.execute(
                    "SELECT id FROM transactions WHERE reference=?", (reference,)
                ).fetchone()
                if exists:
                    continue
                _post_opening_balance(conn, owner, currency, minor, reference, now)


def _post_opening_balance(conn, owner, currency, minor, reference, now) -> None:
    customer_id = conn.execute(
        "SELECT id FROM accounts WHERE owner=? AND currency=?", (owner, currency)
    ).fetchone()["id"]
    equity_id = conn.execute(
        "SELECT id FROM accounts WHERE owner='equity' AND currency=?", (currency,)
    ).fetchone()["id"]
    tx_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO transactions(id,owner,kind,source_currency,target_currency,
           source_amount_minor,target_amount_minor,fee_minor,status,reference,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (tx_id, owner, "opening_balance", currency, currency, minor, minor, 0,
         "completed", reference, now),
    )
    for account_id, delta, desc in [
        (equity_id, -minor, "Opening balance equity debit"),
        (customer_id, minor, "Opening balance customer credit"),
    ]:
        conn.execute(
            "INSERT INTO ledger_entries(id,transaction_id,account_id,amount_minor,currency,description,created_at) VALUES(?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, tx_id, account_id, delta, currency, desc, now),
        )
    conn.execute(
        "UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (minor, customer_id)
    )
    conn.execute(
        "UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (minor, equity_id)
    )


def reset_database() -> None:
    with connect() as conn:
        conn.executescript("""
        DROP TABLE IF EXISTS auth_nonces;
        DROP TABLE IF EXISTS profiles;
        DROP TABLE IF EXISTS ramp_conversions;
        DROP TABLE IF EXISTS onramp_mints;
        DROP TABLE IF EXISTS payment_callbacks;
        DROP TABLE IF EXISTS webhook_events;
        DROP TABLE IF EXISTS ledger_entries;
        DROP TABLE IF EXISTS transactions;
        DROP TABLE IF EXISTS quotes;
        DROP TABLE IF EXISTS accounts;
        """)
        conn.executescript(SCHEMA)
    seed_demo_data()


def account_for(owner: str, currency: str, conn: sqlite3.Connection | None = None):
    owns = conn is None
    db = conn or connect()
    try:
        return db.execute(
            "SELECT * FROM accounts WHERE owner=? AND currency=?", (owner, currency)
        ).fetchone()
    finally:
        if owns:
            db.close()


def account_by_id(account_id: str, conn: sqlite3.Connection | None = None):
    owns = conn is None
    db = conn or connect()
    try:
        return db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    finally:
        if owns:
            db.close()


def account_view(row: sqlite3.Row) -> dict:
    scale = CURRENCY_SCALE[row["currency"]]
    amount = Decimal(row["balance_minor"]) / (10 ** scale)
    return {
        "id": row["id"],
        "owner": row["owner"],
        "currency": row["currency"],
        "balance": f"{amount:.{scale}f}",
        "balance_minor": row["balance_minor"],
    }
