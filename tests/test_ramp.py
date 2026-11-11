"""Saga tests for the integrated fiat <-> USDC on/off-ramp.

The on-chain step is mocked so these run without Anvil. They assert the
compensation guarantees: a failed mint refunds reserved fiat, a failed burn
leaves fiat untouched, and the ledger stays balanced in every case.
"""
import pytest

from app import db, chain
from app.chain import ChainError
from app.domain import DomainError
from app.ledger import verify_ledger_integrity


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-ramp.sqlite3")
    db.initialize_database()
    yield


def _ngn(owner="alice"):
    return db.account_for(owner, "NGN")["balance_minor"]


def test_onramp_success_debits_fiat_and_records_mint(seeded, monkeypatch):
    from app import ramp

    def fake_mint(address, usdc_minor, ref):
        return {"customer": address, "minted": usdc_minor, "token_amount": usdc_minor,
                "balance_after": usdc_minor, "tx_hash": "0xabc123", "block_number": 7}

    monkeypatch.setattr(chain, "confirm_deposit_onchain", fake_mint)
    before = _ngn()
    result = ramp.on_ramp("alice", "NGN", "100000.00")
    assert result["status"] == "completed"
    assert before - _ngn() == 100_000_00  # 100,000.00 NGN debited
    with db.connect() as conn:
        conv = conn.execute("SELECT status, tx_hash FROM ramp_conversions WHERE id=?",
                            (result["conversion_id"],)).fetchone()
        mint = conn.execute("SELECT token_amount FROM onramp_mints WHERE tx_hash='0xabc123'").fetchone()
    assert conv["status"] == "completed" and conv["tx_hash"] == "0xabc123"
    assert mint is not None
    assert verify_ledger_integrity()["healthy"] is True


def test_onramp_refunds_fiat_when_mint_fails(seeded, monkeypatch):
    from app import ramp

    def failing_mint(address, usdc_minor, ref):
        raise ChainError("simulated chain outage", status_code=502)

    monkeypatch.setattr(chain, "confirm_deposit_onchain", failing_mint)
    before = _ngn()
    with pytest.raises(ChainError):
        ramp.on_ramp("alice", "NGN", "100000.00")
    # Fiat must be fully refunded — no value reserved without a mint.
    assert _ngn() == before
    with db.connect() as conn:
        conv = conn.execute("SELECT status FROM ramp_conversions WHERE owner='alice'").fetchone()
        mints = conn.execute("SELECT COUNT(*) n FROM onramp_mints").fetchone()["n"]
    assert conv["status"] == "failed"
    assert mints == 0
    assert verify_ledger_integrity()["healthy"] is True


def test_offramp_success_credits_fiat_after_burn(seeded, monkeypatch):
    from app import ramp

    def fake_burn(address, usdc_minor):
        return {"customer": address, "burned": usdc_minor, "token_amount": usdc_minor,
                "balance_after": 0, "tx_hash": "0xdead", "block_number": 9}

    monkeypatch.setattr(chain, "redeem_offchain", fake_burn)
    before = _ngn()
    result = ramp.off_ramp("alice", "NGN", "30.000000")
    assert result["status"] == "completed"
    assert _ngn() > before  # fiat credited
    assert verify_ledger_integrity()["healthy"] is True


def test_offramp_credits_no_fiat_when_burn_fails(seeded, monkeypatch):
    from app import ramp

    def failing_burn(address, usdc_minor):
        raise ChainError("insufficient on-chain balance", status_code=409)

    monkeypatch.setattr(chain, "redeem_offchain", failing_burn)
    before = _ngn()
    with pytest.raises(ChainError):
        ramp.off_ramp("alice", "NGN", "30.000000")
    # No fiat created without a confirmed burn.
    assert _ngn() == before
    with db.connect() as conn:
        conv = conn.execute("SELECT status FROM ramp_conversions WHERE owner='alice'").fetchone()
    assert conv["status"] == "failed"
    assert verify_ledger_integrity()["healthy"] is True


def test_onramp_rejects_unmapped_identity(seeded, monkeypatch):
    from app import ramp
    with pytest.raises(DomainError):
        ramp.on_ramp("bob_unmapped", "NGN", "100.00")
