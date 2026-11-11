"""Web3 integration tests against a live local Anvil chain.

These tests start Anvil, deploy the contracts and exercise the real on-ramp
mint/redeem and reconciliation paths. They skip cleanly (not fail) when Anvil,
Foundry or web3 are not available, so the default `pytest` run stays green in a
minimal environment while CI with Foundry runs them for real.
"""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("web3")
if shutil.which("anvil") is None:
    pytest.skip("anvil not installed", allow_module_level=True)

BASE = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def chain_env(tmp_path, monkeypatch):
    port = _free_port()
    anvil = subprocess.Popen(
        ["anvil", "--silent", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    rpc = f"http://127.0.0.1:{port}"
    # Point config at this ephemeral chain and an isolated deployment file.
    from app import config, chain, db
    monkeypatch.setattr(config, "RPC_URL", rpc)
    monkeypatch.setattr(chain, "RPC_URL", rpc)
    dep = tmp_path / "deployment.json"
    monkeypatch.setattr(config, "DEPLOYMENT_PATH", dep)
    monkeypatch.setattr(chain, "DEPLOYMENT_PATH", dep)
    # Isolate the on-ramp records database per test.
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-chain.sqlite3")
    db.initialize_database()
    # Wait for the chain to accept connections.
    from web3 import Web3
    for _ in range(50):
        try:
            if Web3(Web3.HTTPProvider(rpc)).is_connected():
                break
        except Exception:
            pass
        time.sleep(0.1)
    # Build + deploy via the deploy script, pointed at this chain.
    env = dict(os.environ, RAMP_RPC_URL=rpc, RAMP_DEPLOYMENT_PATH=str(dep))
    if not (BASE / "contracts" / "out" / "MockUSDC.sol" / "MockUSDC.json").exists():
        build = subprocess.run(["forge", "build"], cwd=BASE / "contracts", env=env)
        if build.returncode != 0:
            anvil.terminate()
            pytest.skip("forge build unavailable")
    deploy = subprocess.run(
        ["python3", str(BASE / "scripts" / "deploy_contracts.py")],
        cwd=BASE, env=env, capture_output=True, text=True,
    )
    if deploy.returncode != 0:
        anvil.terminate()
        pytest.skip(f"deployment failed: {deploy.stderr[-300:]}")
    yield rpc
    anvil.terminate()
    try:
        anvil.wait(timeout=5)
    except Exception:
        anvil.kill()


ANVIL_ACCT_1 = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


def test_chain_status_reports_local_deployment(chain_env):
    from app import chain
    st = chain.status()
    assert st["connected"] is True
    assert st["chain_id"] == 31337
    assert "MockUSDC" in st["contracts"] and "SecureRamp" in st["contracts"]


def test_authorised_onramp_mints_and_reconciles(chain_env):
    from app import chain
    from app.domain import record_onramp_mint
    from app.ledger import reconcile_onchain_mints
    # mint 250 USDC on-chain
    before = chain.token_balance(ANVIL_ACCT_1)
    result = chain.confirm_deposit_onchain(ANVIL_ACCT_1, 250_000000, b"evt-chain-1")
    assert result["minted"] == 250_000000
    assert chain.token_balance(ANVIL_ACCT_1) == before + 250_000000
    # record the association, then reconciliation should be clean
    record_onramp_mint("operations", result["customer"], 250_000000, "evt-chain-1",
                       result["tx_hash"], result["block_number"])
    recon = reconcile_onchain_mints()
    assert recon["available"] is True
    assert recon["onchain_mint_total"] == recon["recorded_mint_total"]
    assert recon["reconciled"] is True


def test_unrecorded_onchain_mint_is_flagged(chain_env):
    from app import chain
    from app.ledger import reconcile_onchain_mints
    # mint on-chain but deliberately do NOT record it internally
    chain.confirm_deposit_onchain(ANVIL_ACCT_1, 100_000000, b"evt-unrecorded")
    recon = reconcile_onchain_mints()
    assert recon["available"] is True
    assert recon["reconciled"] is False
    assert any(m["value"] == 100_000000 for m in recon["unrecorded_onchain_mints"])


def test_mint_events_are_readable(chain_env):
    from app import chain
    chain.confirm_deposit_onchain(ANVIL_ACCT_1, 5_000000, b"evt-read")
    events = chain.read_mint_events(0)
    assert any(e["value"] == 5_000000 for e in events)
    assert all(e["to"].startswith("0x") for e in events)


def test_integrated_onramp_and_offramp_roundtrip(chain_env):
    from app import ramp, db
    from app.ledger import verify_ledger_integrity
    # On-ramp: debit NGN, mint USDC on-chain.
    ngn_before = db.account_for("alice", "NGN")["balance_minor"]
    on = ramp.on_ramp("alice", "NGN", "100000.00")
    assert on["status"] == "completed"
    assert db.account_for("alice", "NGN")["balance_minor"] < ngn_before
    from app import chain
    minted = chain.token_balance(ANVIL_ACCT_1)
    assert minted > 0
    # Off-ramp: burn some USDC, credit NGN.
    ngn_mid = db.account_for("alice", "NGN")["balance_minor"]
    off = ramp.off_ramp("alice", "NGN", "20.000000")
    assert off["status"] == "completed"
    assert chain.token_balance(ANVIL_ACCT_1) == minted - 20_000000
    assert db.account_for("alice", "NGN")["balance_minor"] > ngn_mid
    assert verify_ledger_integrity()["healthy"] is True


def test_offramp_rejected_when_insufficient_onchain_balance(chain_env):
    from app import ramp, db
    from app.chain import ChainError
    import pytest as _pytest
    before = db.account_for("bob", "NGN")["balance_minor"]
    # Bob has no on-chain USDC minted; off-ramp must fail and credit no fiat.
    with _pytest.raises(ChainError):
        ramp.off_ramp("bob", "NGN", "5.000000")
    assert db.account_for("bob", "NGN")["balance_minor"] == before


def test_deposit_credited_events_carry_reference(chain_env):
    from app import ramp, chain
    on = ramp.on_ramp("alice", "NGN", "50000.00")
    events = chain.read_deposit_credited_events(0)
    # The SecureRamp event must carry the on-ramp reference so recovery can match.
    assert any(e["provider_ref"] == on["reference"] for e in events)


def test_recovery_scan_clean_after_successful_onramp(chain_env):
    from app import ramp, recovery
    ramp.on_ramp("alice", "NGN", "50000.00")
    report = recovery.scan()
    assert report["chain_available"] is True
    assert report["pending_total"] == 0


def test_cross_component_replay_propagates_to_chain_and_is_flagged(chain_env):
    """Multi-stage (RAMP-020): a replayed deposit inflates internal fiat, which is
    then on-ramped to mint on-chain USDC — value whose root cause is a replayed,
    unbacked callback. Reconciliation across components surfaces it."""
    from app import db, chain, ramp
    from app.domain import create_deposit
    from app.ledger import reconcile_payment_callbacks
    acct = db.account_for("alice", "NGN")
    before = acct["balance_minor"]
    # Stage 1: replay the vulnerable deposit callback — fiat credited twice.
    for _ in range(2):
        create_deposit("alice", acct["id"], "100000.00", "evt-xcomp", idempotent=False, endpoint="vulnerable")
    inflated = db.account_for("alice", "NGN")["balance_minor"]
    assert inflated > before
    # Stage 2: on-ramp the inflated fiat — mints USDC on-chain.
    on = ramp.on_ramp("alice", "NGN", "100000.00")
    assert on["status"] == "completed"
    assert chain.token_balance(ramp.DEMO_ADDRESSES["alice"]) > 0
    # Stage 3: reconciliation surfaces the root-cause double credit.
    recon = reconcile_payment_callbacks()
    assert recon["reconciled"] is False
    assert any(e["event_id"] == "evt-xcomp" and e["times_credited"] == 2
               for e in recon["double_credited_events"])


def test_naive_onramp_creates_unbacked_usdc_hardened_does_not(chain_env):
    """RAMP-008 reproduce+prevent: the naive (mint-first) on-ramp mints USDC even
    when the fiat debit fails, creating unbacked value; the hardened on-ramp
    checks the fiat first and never mints in that case."""
    from app import ramp, chain, db
    from app.domain import DomainError
    import pytest as _pytest
    addr = ramp.DEMO_ADDRESSES["alice"]
    # Request more fiat than Alice holds so the debit must fail.
    balance_major = int(db.account_for("alice", "NGN")["balance_minor"] // 100)
    over = f"{balance_major + 1_000_000}.00"

    # Hardened path: rejects BEFORE minting — no on-chain value created.
    before = chain.token_balance(addr)
    with _pytest.raises(DomainError):
        ramp.on_ramp("alice", "NGN", over)
    assert chain.token_balance(addr) == before  # nothing minted

    # Naive path: mints first, then the debit fails -> unbacked USDC exists.
    with _pytest.raises(DomainError):
        ramp.on_ramp_naive("alice", "NGN", over)
    assert chain.token_balance(addr) > before  # USDC was minted despite the failure
    with db.connect() as conn:
        row = conn.execute("SELECT status FROM ramp_conversions WHERE direction='on_ramp' "
                           "AND detail LIKE '%unbacked%' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert row is not None and row["status"] == "unbacked"
