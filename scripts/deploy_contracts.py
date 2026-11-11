#!/usr/bin/env python3
"""Deploy RampLab contracts to the local Anvil chain and register their addresses.

Usage:
    anvil                       # in one terminal (chain id 31337)
    python scripts/deploy_contracts.py

Fail-closed: refuses any chain that is not the local development chain. Reads
ABI/bytecode from Foundry build artifacts (contracts/out/), so run `forge build`
first (or let this script attempt it).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from app.chain import get_web3, operator_account, save_deployment, ChainError  # noqa: E402
from app.config import LOCAL_CHAIN_ID  # noqa: E402

ARTIFACTS = BASE / "contracts" / "out"


def load_artifact(contract: str) -> tuple[list, str]:
    path = ARTIFACTS / f"{contract}.sol" / f"{contract}.json"
    if not path.exists():
        raise SystemExit(f"Artifact missing: {path}\nRun `forge build` in contracts/ first.")
    data = json.loads(path.read_text())
    bytecode = data["bytecode"]["object"]
    return data["abi"], bytecode


def deploy(w3, account, abi, bytecode, *args):
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor(*args).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": LOCAL_CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(raw), timeout=30)
    if receipt.status != 1:
        raise SystemExit("Deployment transaction reverted")
    return receipt.contractAddress


def send(w3, account, func):
    tx = func.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": LOCAL_CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(raw), timeout=30)
    if receipt.status != 1:
        raise SystemExit("Transaction reverted")
    return receipt


def main() -> int:
    if not ARTIFACTS.exists():
        print("Building contracts with Foundry…")
        subprocess.run(["forge", "build"], cwd=BASE / "contracts", check=True)
    try:
        w3 = get_web3()
    except ChainError as e:
        print(f"ERROR: {e.message}", file=sys.stderr)
        return 1
    operator = operator_account(w3)
    print(f"Deployer/operator: {operator.address} on chain {LOCAL_CHAIN_ID}")

    usdc_abi, usdc_bin = load_artifact("MockUSDC")
    ramp_abi, ramp_bin = load_artifact("SecureRamp")

    usdc_addr = deploy(w3, operator, usdc_abi, usdc_bin)
    print(f"MockUSDC   → {usdc_addr}")
    ramp_addr = deploy(w3, operator, ramp_abi, ramp_bin, usdc_addr, operator.address)
    print(f"SecureRamp → {ramp_addr}")

    token = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
    send(w3, operator, token.functions.setMinter(ramp_addr, True))
    print(f"Granted minter role on MockUSDC to SecureRamp")

    # Supporting contracts from the architecture: a guarded price oracle, a role
    # registry and a fee calculator. Deployed so the chain registry is complete.
    oracle_abi, oracle_bin = load_artifact("SecurePriceOracle")
    oracle_addr = deploy(w3, operator, oracle_abi, oracle_bin, operator.address, 3600)
    print(f"SecurePriceOracle → {oracle_addr}")

    acm_abi, acm_bin = load_artifact("AccessControlManager")
    acm_addr = deploy(w3, operator, acm_abi, acm_bin)
    print(f"AccessControlManager → {acm_addr}")

    fee_abi, fee_bin = load_artifact("FeeManager")
    fee_addr = deploy(w3, operator, fee_abi, fee_bin, 50, 1, operator.address)
    print(f"FeeManager → {fee_addr}")

    save_deployment({
        "chain_id": LOCAL_CHAIN_ID,
        "operator": operator.address,
        "contracts": {
            "MockUSDC": {"address": usdc_addr, "abi": usdc_abi},
            "SecureRamp": {"address": ramp_addr, "abi": ramp_abi},
            "SecurePriceOracle": {"address": oracle_addr, "abi": oracle_abi},
            "AccessControlManager": {"address": acm_addr, "abi": acm_abi},
            "FeeManager": {"address": fee_addr, "abi": fee_abi},
        },
    })
    print("Wrote deployment registry. Chain integration is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
