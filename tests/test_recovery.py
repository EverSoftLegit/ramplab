"""Tests for the ramp recovery sweep.

The chain is mocked, so an interrupted saga's state is constructed directly and
the sweep's resolution is asserted. Recovery must never create or destroy value:
a reserved on-ramp whose mint landed is completed, one whose mint did not is
refunded, and a burned off-ramp is settled — with the ledger balanced in all.
"""
import uuid

import pytest

from app import db, chain, ramp, recovery
from app.db import connect, utc_now
from app.ledger import verify_ledger_integrity


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-rec.sqlite3")
    db.initialize_database()
    yield


def _reserve_onramp(owner, cur, fiat_minor, usdc_minor, ref, addr):
    now = utc_now()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cust, treas = ramp._accounts(conn, owner, cur)
        conn.execute("UPDATE accounts SET balance_minor=balance_minor-? WHERE id=?", (fiat_minor, cust["id"]))
        conn.execute("UPDATE accounts SET balance_minor=balance_minor+? WHERE id=?", (fiat_minor, treas["id"]))
        tx = uuid.uuid4().hex
        ramp._post(conn, tx, owner, "onramp_fiat_reserve", cur, fiat_minor, ref,
                   [(cust["id"], -fiat_minor, "reserved"), (treas["id"], fiat_minor, "to treasury")], now)
        cid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO ramp_conversions(id,owner,direction,fiat_currency,fiat_minor,usdc_minor,
               customer_address,status,tx_hash,reference,detail,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, owner, "on_ramp", cur, fiat_minor, usdc_minor, addr, "fiat_reserved", None, ref, None, now, now),
        )
        conn.commit()
    return cid


def _burned_offramp(owner, cur, fiat_minor, usdc_minor, ref, addr):
    now = utc_now()
    with connect() as conn:
        cid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO ramp_conversions(id,owner,direction,fiat_currency,fiat_minor,usdc_minor,
               customer_address,status,tx_hash,reference,detail,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, owner, "off_ramp", cur, fiat_minor, usdc_minor, addr, "burned", "0xburn", ref, None, now, now),
        )
    return cid


def _ngn(owner="alice"):
    return db.account_for(owner, "NGN")["balance_minor"]


def test_recovery_completes_reserved_onramp_when_mint_landed(seeded, monkeypatch):
    ref = "RAMPON-LANDED01"
    before = _ngn()
    cid = _reserve_onramp("alice", "NGN", 100_000_00, 65_670000, ref, ramp.DEMO_ADDRESSES["alice"])
    monkeypatch.setattr(chain, "read_deposit_credited_events", lambda f=0: [
        {"provider_ref": ref, "tx_hash": "0xmint1", "token_amount": 65_670000,
         "customer": ramp.DEMO_ADDRESSES["alice"], "block_number": 11}])
    actions = recovery.run()
    assert actions["onramp_completed"] == 1 and actions["onramp_refunded"] == 0
    # Fiat stays debited (the mint really happened) and a mint record now exists.
    assert _ngn() == before - 100_000_00
    with connect() as conn:
        conv = conn.execute("SELECT status FROM ramp_conversions WHERE id=?", (cid,)).fetchone()
        mint = conn.execute("SELECT id FROM onramp_mints WHERE tx_hash='0xmint1'").fetchone()
    assert conv["status"] == "completed" and mint is not None
    assert verify_ledger_integrity()["healthy"] is True


def test_recovery_refunds_reserved_onramp_when_mint_absent(seeded, monkeypatch):
    before = _ngn()
    cid = _reserve_onramp("alice", "NGN", 100_000_00, 65_670000, "RAMPON-GONE001", ramp.DEMO_ADDRESSES["alice"])
    assert _ngn() == before - 100_000_00  # reserved
    monkeypatch.setattr(chain, "read_deposit_credited_events", lambda f=0: [])  # no mint landed
    actions = recovery.run()
    assert actions["onramp_refunded"] == 1 and actions["onramp_completed"] == 0
    assert _ngn() == before  # fully refunded
    with connect() as conn:
        conv = conn.execute("SELECT status FROM ramp_conversions WHERE id=?", (cid,)).fetchone()
    assert conv["status"] == "failed_refunded"
    assert verify_ledger_integrity()["healthy"] is True


def test_recovery_settles_burned_offramp_without_chain(seeded, monkeypatch):
    before = _ngn()
    cid = _burned_offramp("alice", "NGN", 30_151_51, 20_000000, "RAMPOFF-BURN01", ramp.DEMO_ADDRESSES["alice"])
    monkeypatch.setattr(chain, "read_deposit_credited_events", lambda f=0: [])
    actions = recovery.run()
    assert actions["offramp_settled"] == 1
    assert _ngn() == before + 30_151_51  # fiat credited
    with connect() as conn:
        conv = conn.execute("SELECT status FROM ramp_conversions WHERE id=?", (cid,)).fetchone()
    assert conv["status"] == "completed"
    assert verify_ledger_integrity()["healthy"] is True


def test_recovery_is_idempotent(seeded, monkeypatch):
    _burned_offramp("alice", "NGN", 10_000_00, 5_000000, "RAMPOFF-IDEM01", ramp.DEMO_ADDRESSES["alice"])
    monkeypatch.setattr(chain, "read_deposit_credited_events", lambda f=0: [])
    first = recovery.run()
    after_first = _ngn()
    second = recovery.run()
    assert first["offramp_settled"] == 1
    assert second["offramp_settled"] == 0  # nothing left to do
    assert _ngn() == after_first  # no double credit
    assert verify_ledger_integrity()["healthy"] is True


def test_scan_reports_without_acting(seeded, monkeypatch):
    before = _ngn()
    _reserve_onramp("alice", "NGN", 50_000_00, 30_000000, "RAMPON-SCAN01", ramp.DEMO_ADDRESSES["alice"])
    monkeypatch.setattr(chain, "status", lambda: {"connected": True})
    report = recovery.scan()
    assert report["pending_total"] == 1
    assert len(report["onramp_reserved"]) == 1
    # scan must not change balances
    assert _ngn() == before - 50_000_00
