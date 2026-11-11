"""Signed withdrawal authorization (RAMP-014): weak signature verification,
signature replay and nonce handling.

A customer authorises a withdrawal by signing a canonical message with their
wallet key (EIP-191 personal_sign). The server recovers the signer and checks it
matches the account's mapped address.

- Vulnerable: verifies the signature but never consumes a nonce, so the exact
  same signed authorization can be replayed to withdraw again and again.
- Secure: binds the authorization to the account's current server-side nonce and
  advances it atomically on use, so a replay (same signature, now-stale nonce) is
  rejected.

Signature recovery is pure ECDSA — it needs no chain connection.
"""
from __future__ import annotations

from app.config import DEMO_ADDRESSES
from app.db import connect
from app.domain import DomainError, withdraw_secure


def withdraw_message(owner: str, currency: str, amount: str, nonce: int) -> str:
    """Canonical authorization message. Binds account, currency, amount and nonce."""
    return f"ramplab:withdraw:{owner}:{currency}:{amount}:{nonce}"


def _recover(message: str, signature: str) -> str:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    sig = signature[2:] if signature.startswith("0x") else signature
    try:
        raw = bytes.fromhex(sig)
    except ValueError:
        raise DomainError("Malformed signature", 400)
    try:
        return Account.recover_message(encode_defunct(text=message), signature=raw)
    except Exception:
        raise DomainError("Signature could not be recovered", 400)


def _expected_address(owner: str) -> str:
    addr = DEMO_ADDRESSES.get(owner)
    if not addr:
        raise DomainError(f"No wallet address mapped for '{owner}'", 400)
    return addr


def get_nonce(owner: str) -> int:
    with connect() as conn:
        row = conn.execute("SELECT nonce FROM auth_nonces WHERE owner=?", (owner,)).fetchone()
    return row["nonce"] if row else 0


def signed_withdraw_vulnerable(owner: str, currency: str, amount: str, nonce: int, signature: str) -> dict:
    """INTENTIONALLY VULNERABLE: verifies the signature but never consumes the
    nonce, so the same authorization can be replayed indefinitely."""
    message = withdraw_message(owner, currency, amount, nonce)
    signer = _recover(message, signature)
    if signer.lower() != _expected_address(owner).lower():
        raise DomainError("Signature does not match account owner", 401)
    # No nonce consumption — replay is possible.
    withdraw_secure(owner, currency, amount)
    return {"status": "withdrawn", "amount": amount, "currency": currency,
            "lab_warning": "No nonce consumed: this authorization can be replayed."}


def signed_withdraw_secure(owner: str, currency: str, amount: str, nonce: int, signature: str) -> dict:
    """Hardened: the authorization must carry the account's current nonce, which
    is checked and advanced atomically, so a replay is rejected."""
    message = withdraw_message(owner, currency, amount, nonce)
    signer = _recover(message, signature)
    if signer.lower() != _expected_address(owner).lower():
        raise DomainError("Signature does not match account owner", 401)
    # Atomically consume the nonce: reject anything but the current value.
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT nonce FROM auth_nonces WHERE owner=?", (owner,)).fetchone()
        current = row["nonce"] if row else 0
        if nonce != current:
            conn.commit()
            raise DomainError(f"Invalid or reused nonce (expected {current})", 409)
        if row:
            conn.execute("UPDATE auth_nonces SET nonce=nonce+1 WHERE owner=?", (owner,))
        else:
            conn.execute("INSERT INTO auth_nonces(owner, nonce) VALUES(?, 1)", (owner,))
        conn.commit()
    # Nonce consumed; perform the debit.
    withdraw_secure(owner, currency, amount)
    return {"status": "withdrawn", "amount": amount, "currency": currency, "next_nonce": current + 1}
