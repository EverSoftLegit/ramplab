from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.chain import ChainError
from app.config import ADMIN_USERS, CURRENCY_SCALE, CURRENCY_USD_VALUE, DEMO_USERS, WEBHOOK_SECRET
from app.db import account_by_id, account_view, connect, initialize_database, reset_database
from app.domain import DomainError, cancel_quote, create_deposit, create_quote, execute_conversion, format_minor

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="RampLab API",
    version="1.3.0",
    description=(
        "Intentionally vulnerable Web3 fintech security training lab. "
        "Local synthetic data only. Never deploy this application to the public internet."
    ),
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class QuoteRequest(BaseModel):
    source_currency: str = Field(min_length=3, max_length=8)
    target_currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)


class LabQuoteRequest(QuoteRequest):
    # Deliberately unsafe: learner-controlled rate is accepted by the lab route.
    rate_override: str = Field(min_length=1, max_length=40)


class ConversionRequest(BaseModel):
    quote_id: str = Field(min_length=16, max_length=64)


class LabDepositRequest(BaseModel):
    owner: str
    account_id: str
    amount: str
    event_id: str


class DemoResetRequest(BaseModel):
    confirm: str = ""


def get_demo_user(value: str) -> str:
    if value not in DEMO_USERS:
        raise HTTPException(status_code=400, detail="Use one of the seeded demo identities: alice or bob")
    return value


def handle_domain_error(exc: DomainError):
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@app.exception_handler(DomainError)
async def domain_error_handler(_, exc: DomainError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(ChainError)
async def chain_error_handler(_, exc: ChainError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "project": "RampLab", "version": "1.3.0", "environment": "local-training-only"}


@app.get("/api/demo/users")
def demo_users():
    return {"users": list(DEMO_USERS), "notice": "These are synthetic identities, not authenticated users."}


@app.get("/api/markets")
def markets():
    return {
        "currencies": [
            {"code": code, "decimals": CURRENCY_SCALE[code], "illustrative_usd_value": str(value)}
            for code, value in CURRENCY_USD_VALUE.items()
        ],
        "notice": "All rates are fictional teaching fixtures. They are not live market prices or financial advice.",
    }


@app.get("/api/accounts")
def list_accounts(x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    with connect() as conn:
        rows = conn.execute("SELECT * FROM accounts WHERE owner=? ORDER BY currency", (owner,)).fetchall()
    return {"accounts": [account_view(row) for row in rows], "identity_notice": "X-Demo-User is a lab selector, not authentication."}


@app.get("/api/accounts/{account_id}")
def get_account_secure(account_id: str, x_demo_user: Annotated[str, Header()] = "alice"):
    """Hardened example: enforce account ownership (identity remains simulated)."""
    owner = get_demo_user(x_demo_user)
    row = account_by_id(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if row["owner"] != owner:
        raise HTTPException(status_code=403, detail="You do not own this account")
    return {"account": account_view(row)}


@app.get("/api/lab/accounts/{account_id}")
def get_account_vulnerable(account_id: str):
    """RAMP-001: intentionally vulnerable BOLA/IDOR example. No owner check."""
    row = account_by_id(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"account": account_view(row), "lab_warning": "INTENTIONALLY VULNERABLE: ownership was not checked."}


@app.post("/api/quotes")
def quote_conversion(payload: QuoteRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    return create_quote(owner, payload.source_currency.upper(), payload.target_currency.upper(), payload.amount)


@app.post("/api/lab/quotes")
def quote_conversion_vulnerable(payload: LabQuoteRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """RAMP-002: intentionally trusts a caller-supplied exchange rate."""
    owner = get_demo_user(x_demo_user)
    result = create_quote(owner, payload.source_currency.upper(), payload.target_currency.upper(),
                          payload.amount, rate_override=payload.rate_override)
    result["lab_warning"] = "INTENTIONALLY VULNERABLE: caller-controlled rate accepted."
    return result


@app.post("/api/conversions")
def convert(payload: ConversionRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    return execute_conversion(owner, payload.quote_id)


@app.post("/api/lab/conversions")
def convert_lab(payload: ConversionRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-017): executes a quote without enforcing
    expiry, so a stale quote can be settled at an outdated rate."""
    owner = get_demo_user(x_demo_user)
    result = execute_conversion(owner, payload.quote_id, allow_expired=True)
    result["lab_warning"] = "Quote expiry is not enforced on this endpoint."
    return result


class DecimalQuoteRequest(BaseModel):
    source_currency: str = Field(min_length=3, max_length=8)
    target_currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)


@app.post("/api/lab/decimal-quote")
def decimal_quote_lab(payload: DecimalQuoteRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-015): prices a conversion with naive decimal
    handling (minor units multiplied by rate), alongside the correct result."""
    get_demo_user(x_demo_user)
    from app.domain import calculate_target, calculate_target_naive, demo_rate, parse_amount
    src, tgt = payload.source_currency.upper(), payload.target_currency.upper()
    if src not in CURRENCY_SCALE or tgt not in CURRENCY_SCALE:
        raise HTTPException(status_code=400, detail="Unsupported currency")
    rate = demo_rate(src, tgt)
    source_minor = parse_amount(payload.amount, src)
    naive_minor, _ = calculate_target_naive(source_minor, src, tgt, rate)
    correct_minor, _ = calculate_target(source_minor, src, tgt, rate)
    return {
        "source": f"{payload.amount} {src}", "target_currency": tgt,
        "naive_target_minor": naive_minor, "naive_target": format_minor(max(naive_minor, 0), tgt),
        "correct_target_minor": correct_minor, "correct_target": format_minor(correct_minor, tgt),
        "lab_warning": "Naive handling ignores the source/target decimal-place difference.",
    }


@app.post("/api/fee-preview")
def fee_preview(payload: DecimalQuoteRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """Compares the truncating fee policy (RAMP-016 vulnerable) with the
    minimum-fee policy (hardened) for a given amount."""
    get_demo_user(x_demo_user)
    from app.domain import demo_rate, fee_minor_secure, fee_minor_vulnerable, parse_amount
    src, tgt = payload.source_currency.upper(), payload.target_currency.upper()
    if src not in CURRENCY_SCALE or tgt not in CURRENCY_SCALE:
        raise HTTPException(status_code=400, detail="Unsupported currency")
    rate = demo_rate(src, tgt)
    source_minor = parse_amount(payload.amount, src)
    vuln = fee_minor_vulnerable(source_minor, src, tgt, rate)
    secure = fee_minor_secure(source_minor, src, tgt, rate)
    return {
        "amount": f"{payload.amount} {src}", "target_currency": tgt,
        "fee_truncated_minor": vuln, "fee_truncated": format_minor(vuln, tgt),
        "fee_with_minimum_minor": secure, "fee_with_minimum": format_minor(secure, tgt),
        "note": "Truncated fee can round to zero for dust amounts; the minimum-fee policy cannot.",
    }


@app.post("/api/quotes/{quote_id}/cancel")
def cancel(quote_id: str, x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    return cancel_quote(owner, quote_id)


@app.get("/api/transactions")
def list_transactions(x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE owner=? AND kind!='opening_balance' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 100", (owner,)
        ).fetchall()
    return {"transactions": [
        {
            "id": row["id"], "reference": row["reference"], "kind": row["kind"],
            "source_currency": row["source_currency"],
            "source_amount": format_minor(row["source_amount_minor"], row["source_currency"]),
            "target_currency": row["target_currency"],
            "target_amount": format_minor(row["target_amount_minor"], row["target_currency"]),
            "status": row["status"], "created_at": row["created_at"],
        } for row in rows
    ]}


@app.get("/api/transactions/{transaction_id}/ledger")
def transaction_ledger(transaction_id: str, x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    with connect() as conn:
        tx = conn.execute("SELECT id FROM transactions WHERE id=? AND owner=?", (transaction_id, owner)).fetchone()
        if tx is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        rows = conn.execute(
            "SELECT le.*, a.owner FROM ledger_entries le JOIN accounts a ON a.id=le.account_id WHERE le.transaction_id=?",
            (transaction_id,),
        ).fetchall()
    return {"entries": [dict(row) for row in rows]}


@app.post("/api/lab/webhooks/deposit")
def deposit_vulnerable(payload: LabDepositRequest):
    """RAMP-003: intentionally unsigned and non-idempotent payment callback."""
    owner = get_demo_user(payload.owner)
    result = create_deposit(owner, payload.account_id, payload.amount, payload.event_id,
                            idempotent=False, endpoint="vulnerable")
    result["lab_warning"] = "INTENTIONALLY VULNERABLE: unsigned callback; repeated event IDs are credited again."
    return result


@app.post("/api/webhooks/deposit")
async def deposit_hardened(request: Request, x_ramp_signature: Annotated[str | None, Header()] = None):
    """Hardened teaching example: HMAC verification and event-level idempotency."""
    raw = await request.body()
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    supplied = (x_ramp_signature or "").removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
        owner = get_demo_user(str(payload["owner"]))
        account_id = str(payload["account_id"])
        amount = str(payload["amount"])
        event_id = str(payload["event_id"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed webhook payload")
    if not event_id or len(event_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid event ID")
    return create_deposit(owner, account_id, amount, event_id, idempotent=True, endpoint="hardened")


@app.get("/api/lab/debug")
def lab_debug():
    """INTENTIONALLY VULNERABLE (RAMP-018): leaks internal configuration and
    secrets. A real debug endpoint must never expose this."""
    from app.config import OPERATOR_KEY, RPC_URL
    with connect() as conn:
        emails = [r["email"] for r in conn.execute("SELECT email FROM profiles").fetchall()]
    return {
        "webhook_secret": WEBHOOK_SECRET,
        "operator_key": OPERATOR_KEY,
        "rpc_url": RPC_URL,
        "all_customer_emails": emails,
        "lab_warning": "Information disclosure: secrets and PII must never be served.",
    }


class LoginRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=32)


@app.post("/api/lab/login")
def lab_login(payload: LoginRequest):
    """INTENTIONALLY VULNERABLE (RAMP-019): issues a forgeable base64 token."""
    owner = get_demo_user(payload.owner)
    from app.sessions import issue_weak_token
    return {"token": issue_weak_token(owner), "lab_warning": "Token has no integrity protection."}


@app.get("/api/lab/whoami")
def lab_whoami(x_session: Annotated[str, Header()] = ""):
    """Resolves identity from a weak token with no integrity check."""
    from app.sessions import read_weak_token
    try:
        return {"owner": read_weak_token(x_session)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/login")
def login(payload: LoginRequest):
    """Hardened: issues an HMAC-signed token."""
    owner = get_demo_user(payload.owner)
    from app.sessions import issue_signed_token
    return {"token": issue_signed_token(owner)}


@app.get("/api/whoami")
def whoami(x_session: Annotated[str, Header()] = ""):
    """Verifies the token's HMAC before trusting the identity."""
    from app.sessions import read_signed_token
    try:
        return {"owner": read_signed_token(x_session)}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session token")


class CreditRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)


@app.post("/api/lab/admin/credit")
def lab_admin_credit(payload: CreditRequest, x_demo_user: Annotated[str, Header()] = "operations"):
    """INTENTIONALLY VULNERABLE (RAMP-021): credits a balance with no ledger entry."""
    require_admin(x_demo_user)
    from app.domain import admin_credit_vulnerable
    return admin_credit_vulnerable("alice", payload.currency.upper(), payload.amount)


@app.post("/api/admin/credit")
def admin_credit(payload: CreditRequest, x_demo_user: Annotated[str, Header()] = "operations"):
    """Hardened: credits via a balanced double-entry posting."""
    require_admin(x_demo_user)
    from app.domain import admin_credit_secure
    return admin_credit_secure("alice", payload.currency.upper(), payload.amount)


@app.get("/api/profile")
def get_my_profile(x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    from app.domain import get_profile
    return get_profile(owner)


@app.post("/api/profile")
def update_my_profile(payload: dict, x_demo_user: Annotated[str, Header()] = "alice"):
    """Hardened profile update: only self-editable fields are bound (allowlist)."""
    owner = get_demo_user(x_demo_user)
    from app.domain import update_profile_secure
    return update_profile_secure(owner, payload)


@app.post("/api/lab/profile")
def update_my_profile_lab(payload: dict, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-006): mass assignment binds every column,
    so a customer can escalate role/status/kyc_level from the request body."""
    owner = get_demo_user(x_demo_user)
    from app.domain import update_profile_vulnerable
    result = update_profile_vulnerable(owner, payload)
    result["lab_warning"] = "Mass assignment: privileged fields were bound from the request body."
    return result


def require_admin(value: str) -> str:
    if value not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Administrative role required (use admin or operations)")
    return value


@app.get("/api/transactions/{tx_id}")
def get_transaction(tx_id: str, x_demo_user: Annotated[str, Header()] = "alice"):
    """Hardened: returns a transaction only if it belongs to the caller."""
    owner = get_demo_user(x_demo_user)
    from app.domain import transaction_by_id
    return transaction_by_id(tx_id, owner=owner)


@app.get("/api/lab/transactions/{tx_id}")
def get_transaction_lab(tx_id: str, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-009): returns any transaction by id with no
    ownership check (IDOR / broken object-level authorization)."""
    get_demo_user(x_demo_user)
    from app.domain import transaction_by_id
    result = transaction_by_id(tx_id, owner=None)
    result["lab_warning"] = "No ownership check: any transaction id is readable."
    return result


@app.get("/api/lab/admin/users")
def lab_admin_users(x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-011): an administrative listing with no role
    check (broken function-level authorization). Hardened counterpart: /api/admin/overview."""
    get_demo_user(x_demo_user)
    with connect() as conn:
        rows = conn.execute("SELECT owner, display_name, email, role, status, kyc_level FROM profiles").fetchall()
    return {"users": [dict(r) for r in rows],
            "lab_warning": "No function-level authorization: any customer can call this admin listing."}


class WithdrawRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)


class SignedWithdrawRequest(BaseModel):
    currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)
    nonce: int = Field(ge=0)
    signature: str = Field(min_length=2, max_length=200)


@app.get("/api/signing/nonce")
def signing_nonce(x_demo_user: Annotated[str, Header()] = "alice"):
    """The account's current signing nonce, for building a secure authorization."""
    owner = get_demo_user(x_demo_user)
    from app.signing import get_nonce, withdraw_message
    nonce = get_nonce(owner)
    return {"owner": owner, "nonce": nonce,
            "message_template": withdraw_message(owner, "<currency>", "<amount>", nonce)}


@app.post("/api/signed-withdraw")
def signed_withdraw(payload: SignedWithdrawRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """Hardened signed withdrawal: authorization is bound to the current nonce."""
    owner = get_demo_user(x_demo_user)
    from app.signing import signed_withdraw_secure
    return signed_withdraw_secure(owner, payload.currency.upper(), payload.amount, payload.nonce, payload.signature)


@app.post("/api/lab/signed-withdraw")
def signed_withdraw_lab(payload: SignedWithdrawRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-014): verifies the signature but consumes no
    nonce, so a captured authorization can be replayed."""
    owner = get_demo_user(x_demo_user)
    from app.signing import signed_withdraw_vulnerable
    return signed_withdraw_vulnerable(owner, payload.currency.upper(), payload.amount, payload.nonce, payload.signature)


@app.post("/api/withdraw")
def withdraw(payload: WithdrawRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """Hardened withdrawal: check and debit inside one serialised transaction."""
    owner = get_demo_user(x_demo_user)
    from app.domain import withdraw_secure
    return withdraw_secure(owner, payload.currency.upper(), payload.amount)


@app.post("/api/lab/withdraw")
def withdraw_lab(payload: WithdrawRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-007): non-atomic check-then-act withdrawal
    that concurrent requests can race to overdraw."""
    owner = get_demo_user(x_demo_user)
    from app.domain import withdraw_vulnerable
    result = withdraw_vulnerable(owner, payload.currency.upper(), payload.amount)
    result["lab_warning"] = "Non-atomic: concurrent withdrawals can double-spend."
    return result


@app.get("/api/observability/summary")
def observability_summary():
    """Aggregated, synthetic application metrics for the observability dashboard."""
    from app.ledger import verify_ledger_integrity, reconcile_payment_callbacks
    with connect() as conn:
        tx_by_kind = conn.execute(
            "SELECT kind, COUNT(*) n FROM transactions WHERE kind!='opening_balance' GROUP BY kind"
        ).fetchall()
        cb_outcomes = conn.execute(
            "SELECT outcome, COUNT(*) n FROM payment_callbacks GROUP BY outcome"
        ).fetchall()
        vol = conn.execute(
            """SELECT target_currency currency, COUNT(*) n FROM transactions
               WHERE kind!='opening_balance' GROUP BY target_currency ORDER BY n DESC"""
        ).fetchall()
        recent = conn.execute(
            "SELECT reference, kind, status, created_at FROM transactions "
            "WHERE kind!='opening_balance' ORDER BY rowid DESC LIMIT 8"
        ).fetchall()
    return {
        "transactions_by_kind": {r["kind"]: r["n"] for r in tx_by_kind},
        "callback_outcomes": {r["outcome"]: r["n"] for r in cb_outcomes},
        "volume_by_currency": [{"currency": r["currency"], "count": r["n"]} for r in vol],
        "recent_transactions": [dict(r) for r in recent],
        "ledger_healthy": verify_ledger_integrity()["healthy"],
        "reconciled": reconcile_payment_callbacks()["reconciled"],
        "challenge_count": len(_challenge_catalogue()),
    }


@app.get("/api/admin/overview")
def admin_overview(x_demo_user: Annotated[str, Header()] = "admin"):
    """Read-only administrative overview. Restricted to elevated demo roles."""
    require_admin(x_demo_user)
    with connect() as conn:
        accounts = conn.execute(
            "SELECT * FROM accounts ORDER BY owner, currency"
        ).fetchall()
        events = conn.execute(
            """SELECT endpoint, event_id, owner, outcome, currency, amount_minor, created_at
               FROM payment_callbacks ORDER BY rowid DESC LIMIT 25"""
        ).fetchall()
        tx = conn.execute(
            "SELECT reference, owner, kind, status, created_at FROM transactions "
            "WHERE kind!='opening_balance' ORDER BY rowid DESC LIMIT 25"
        ).fetchall()
    grouped: dict[str, list] = {}
    for row in accounts:
        grouped.setdefault(row["owner"], []).append(account_view(row))
    return {
        "accounts_by_owner": grouped,
        "security_events": [dict(r) for r in events],
        "recent_transactions": [dict(r) for r in tx],
        "identity_notice": "X-Demo-User is a lab role selector, not authentication.",
    }


class OnrampRequest(BaseModel):
    customer_address: str = Field(min_length=42, max_length=42)
    token_amount: str = Field(min_length=1, max_length=40)
    provider_ref: str = Field(default="demo-provider-event", max_length=64)


@app.get("/api/chain/status")
def chain_status():
    """Local chain connectivity and deployment state. Never raises on 'not set up'."""
    from app import chain
    return chain.status()


@app.get("/api/chain/balance/{address}")
def chain_balance(address: str):
    from app import chain
    raw = chain.token_balance(address)
    return {"address": address, "balance_minor": raw, "balance": format_minor(raw, "USDC"), "currency": "USDC"}


@app.post("/api/chain/onramp")
def chain_onramp(payload: OnrampRequest, x_demo_user: Annotated[str, Header()] = "operations"):
    """Fiat-to-crypto on-ramp: an authorised confirmation mints synthetic USDC on-chain.

    Restricted to an elevated operator role. The mint is confirmed by its receipt
    before the internal association is recorded; a reverted mint is never recorded.
    """
    require_admin(x_demo_user)
    from app import chain
    from app.domain import record_onramp_mint
    amount_minor = int(Decimal(payload.token_amount) * (10 ** CURRENCY_SCALE["USDC"]))
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="token_amount must be greater than zero")
    result = chain.confirm_deposit_onchain(payload.customer_address, amount_minor, payload.provider_ref.encode())
    mint_id = record_onramp_mint(x_demo_user, result["customer"], amount_minor,
                                 payload.provider_ref, result["tx_hash"], result["block_number"])
    result["onramp_record_id"] = mint_id
    result["currency"] = "USDC"
    return result


@app.get("/api/chain/reconciliation")
def chain_reconciliation():
    """Reconcile on-chain mint events against internal on-ramp records."""
    from app.ledger import reconcile_onchain_mints
    return reconcile_onchain_mints()


class RampRequest(BaseModel):
    fiat_currency: str = Field(min_length=3, max_length=8)
    amount: str = Field(min_length=1, max_length=40)


@app.post("/api/ramp/onramp")
def ramp_onramp(payload: RampRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """Atomic fiat-to-USDC: debit internal fiat, then mint on-chain; refund fiat if the mint fails."""
    owner = get_demo_user(x_demo_user)
    from app.ramp import on_ramp
    return on_ramp(owner, payload.fiat_currency, payload.amount)


@app.post("/api/ramp/offramp")
def ramp_offramp(payload: RampRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """Atomic USDC-to-fiat: burn on-chain USDC, then credit internal fiat."""
    owner = get_demo_user(x_demo_user)
    from app.ramp import off_ramp
    return off_ramp(owner, payload.fiat_currency, payload.amount)


@app.post("/api/lab/ramp/onramp")
def ramp_onramp_lab(payload: RampRequest, x_demo_user: Annotated[str, Header()] = "alice"):
    """INTENTIONALLY VULNERABLE (RAMP-008): mints on-chain before debiting fiat, so
    a failed debit leaves unbacked USDC. Contrast with the atomic /api/ramp/onramp."""
    owner = get_demo_user(x_demo_user)
    from app.ramp import on_ramp_naive
    return on_ramp_naive(owner, payload.fiat_currency, payload.amount)


@app.get("/api/ramp/account")
def ramp_account(x_demo_user: Annotated[str, Header()] = "alice"):
    """The customer's mapped on-chain address and live USDC balance (if a chain is up)."""
    owner = get_demo_user(x_demo_user)
    from app.config import DEMO_ADDRESSES
    from app import chain
    address = DEMO_ADDRESSES.get(owner)
    out = {"owner": owner, "address": address}
    try:
        raw = chain.token_balance(address) if address else 0
        out["usdc_onchain"] = format_minor(raw, "USDC")
        out["chain_available"] = True
    except ChainError as e:
        out["chain_available"] = False
        out["reason"] = e.message
    return out


@app.get("/api/ramp/recovery/scan")
def ramp_recovery_scan(x_demo_user: Annotated[str, Header()] = "operations"):
    """Report interrupted ramp conversions without acting. Elevated role only."""
    require_admin(x_demo_user)
    from app.recovery import scan
    return scan()


@app.post("/api/ramp/recovery/run")
def ramp_recovery_run(x_demo_user: Annotated[str, Header()] = "operations"):
    """Resolve interrupted ramp conversions (idempotent). Elevated role only."""
    require_admin(x_demo_user)
    from app.recovery import run
    return run()


@app.get("/api/ramp/conversions")
def ramp_conversions(x_demo_user: Annotated[str, Header()] = "alice"):
    owner = get_demo_user(x_demo_user)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ramp_conversions WHERE owner=? ORDER BY rowid DESC LIMIT 50", (owner,)
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "reference": r["reference"], "direction": r["direction"], "status": r["status"],
            "fiat": f"{format_minor(r['fiat_minor'], r['fiat_currency'])} {r['fiat_currency']}",
            "usdc": format_minor(r["usdc_minor"], "USDC"),
            "tx_hash": r["tx_hash"], "created_at": r["created_at"],
        })
    return {"conversions": out}


@app.get("/api/ledger/integrity")
def ledger_integrity():
    """Verify double-entry invariants: zero-sum per currency and balance-vs-ledger consistency."""
    from app.ledger import verify_ledger_integrity
    return verify_ledger_integrity()


@app.get("/api/ledger/reconciliation")
def ledger_reconciliation():
    """Reconcile payment callbacks; flags any event credited more than once."""
    from app.ledger import reconcile_payment_callbacks
    return reconcile_payment_callbacks()


@app.post("/api/demo/reset")
def demo_reset(payload: DemoResetRequest):
    if payload.confirm != "RESET-DEMO-DATA":
        raise HTTPException(status_code=400, detail="Send confirm='RESET-DEMO-DATA' to reset the local lab")
    reset_database()
    return {"status": "reset", "notice": "Synthetic demo data restored."}


def _challenge_catalogue():
    from app.challenges import catalogue
    return catalogue()


@app.get("/api/challenges")
def challenges():
    from app.challenges import summary
    return {"challenges": summary(), "notice": "All challenges are for local, synthetic training only."}


@app.get("/api/challenges/export")
def challenges_export():
    """Facilitator/docs export: the full catalogue as a Markdown document."""
    from fastapi.responses import PlainTextResponse
    from app.challenges import catalogue
    lines = ["# RampLab Challenge Catalogue", "",
             "Local, synthetic security training only. Each challenge pairs a vulnerable "
             "workflow with a hardened implementation.", ""]
    for c in catalogue():
        lines += [
            f"## {c['id']} — {c['title']}", "",
            f"- **Level:** {c['level']}",
            f"- **Category:** {c['category']}",
            f"- **Component:** {c['component']}",
            f"- **Vulnerable:** `{c['vulnerable']}`",
            f"- **Hardened:** `{c['hardened']}`",
            f"- **Regression test:** `{c['regression_test']}`", "",
            f"**Context.** {c['business_context']}", "",
            "**Objectives.**"] + [f"- {o}" for o in c["objectives"]] + [
            "", f"**Root cause.** {c['root_cause']}", "",
            f"**Remediation.** {c['remediation']}", "", "---", ""]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@app.get("/api/challenges/{challenge_id}")
def challenge_detail(challenge_id: str):
    from app.challenges import by_id
    detail = by_id(challenge_id.upper())
    if detail is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return detail
