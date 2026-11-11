"""Tests for RAMP-014 signed-withdrawal authorization.

Pure ECDSA — no chain needed. The vulnerable path accepts a replayed
authorization (double withdrawal); the secure path binds a nonce and rejects the
replay.
"""
import pytest

pytest.importorskip("eth_account")

from eth_account import Account
from eth_account.messages import encode_defunct

from app import db
from app.config import DEMO_KEYS
from app.domain import DomainError
from app.signing import (
    get_nonce, signed_withdraw_secure, signed_withdraw_vulnerable, withdraw_message,
)


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-sig.sqlite3")
    db.initialize_database()
    yield


def _sign(owner, currency, amount, nonce):
    msg = withdraw_message(owner, currency, amount, nonce)
    sig = Account.sign_message(encode_defunct(text=msg), DEMO_KEYS[owner]).signature
    return "0x" + sig.hex()


def _ngn(owner="alice"):
    return db.account_for(owner, "NGN")["balance_minor"]


def test_vulnerable_signed_withdraw_is_replayable(seeded):
    sig = _sign("alice", "NGN", "100000.00", 0)
    before = _ngn()
    # The same signed authorization is accepted twice (signature replay).
    signed_withdraw_vulnerable("alice", "NGN", "100000.00", 0, sig)
    signed_withdraw_vulnerable("alice", "NGN", "100000.00", 0, sig)
    assert before - _ngn() == 2 * 100_000_00  # debited twice


def test_secure_signed_withdraw_rejects_replay(seeded):
    sig = _sign("alice", "NGN", "100000.00", 0)
    before = _ngn()
    out = signed_withdraw_secure("alice", "NGN", "100000.00", 0, sig)
    assert out["next_nonce"] == 1
    # Replaying the same authorization (nonce 0) is now rejected.
    with pytest.raises(DomainError) as exc:
        signed_withdraw_secure("alice", "NGN", "100000.00", 0, sig)
    assert exc.value.status_code == 409
    assert before - _ngn() == 100_000_00  # debited exactly once
    # A fresh authorization at the advanced nonce works.
    sig1 = _sign("alice", "NGN", "100000.00", 1)
    signed_withdraw_secure("alice", "NGN", "100000.00", 1, sig1)
    assert before - _ngn() == 2 * 100_000_00


def test_signed_withdraw_rejects_wrong_signer(seeded):
    # Bob signs an authorization claiming to be Alice's.
    msg = withdraw_message("alice", "NGN", "100000.00", 0)
    bob_sig = "0x" + Account.sign_message(encode_defunct(text=msg), DEMO_KEYS["bob"]).signature.hex()
    with pytest.raises(DomainError) as exc:
        signed_withdraw_secure("alice", "NGN", "100000.00", 0, bob_sig)
    assert exc.value.status_code == 401


def test_tampered_amount_breaks_signature(seeded):
    # Signature authorises 100,000 but the request claims 500,000.
    sig = _sign("alice", "NGN", "100000.00", 0)
    with pytest.raises(DomainError) as exc:
        signed_withdraw_secure("alice", "NGN", "500000.00", 0, sig)
    assert exc.value.status_code == 401
