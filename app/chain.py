"""Local blockchain (Anvil) client for RampLab.

Fail-closed by design: every connection refuses any chain whose ID is not the
configured local development chain, and any RPC host that is not local. This
prevents the lab from ever interacting with a public testnet or mainnet.

The backend treats a successful API/RPC call as a *claim*, not a fact: minting
waits for a transaction receipt, records the on-chain tx hash alongside the
internal ledger reference, and reconciliation compares on-chain token events
against internal records.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

from app.config import (
    DEPLOYMENT_PATH, LOCAL_CHAIN_ID, LOCAL_RPC_HOSTS, OPERATOR_KEY, RPC_URL,
)


class ChainError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_local_host(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in LOCAL_RPC_HOSTS:
        raise ChainError(
            f"Refusing non-local RPC host '{host}'. RampLab only connects to a "
            f"local development chain.",
            status_code=400,
        )


def get_web3():
    """Return a connected Web3 instance bound to the local chain, or raise."""
    try:
        from web3 import Web3
    except ImportError:
        raise ChainError("web3 is not installed. Install it with: pip install web3")
    _require_local_host(RPC_URL)
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))
    if not w3.is_connected():
        raise ChainError(
            f"No local chain at {RPC_URL}. Start Anvil: `anvil` (chain id {LOCAL_CHAIN_ID})."
        )
    chain_id = w3.eth.chain_id
    if chain_id != LOCAL_CHAIN_ID:
        # Fail closed: never operate on a chain that is not the local dev chain.
        raise ChainError(
            f"Connected chain id {chain_id} is not the local development chain "
            f"({LOCAL_CHAIN_ID}). Refusing to proceed.",
            status_code=400,
        )
    return w3


def operator_account(w3):
    return w3.eth.account.from_key(OPERATOR_KEY)


# ---------- deployment registry ----------

def load_deployment() -> dict:
    if not DEPLOYMENT_PATH.exists():
        raise ChainError(
            "No deployment found. Run `python scripts/deploy_contracts.py` against "
            "a running Anvil first.",
            status_code=409,
        )
    return json.loads(DEPLOYMENT_PATH.read_text())


def save_deployment(data: dict) -> None:
    DEPLOYMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEPLOYMENT_PATH.write_text(json.dumps(data, indent=2))


# ---------- contract helpers ----------

def _contract(w3, name: str):
    dep = load_deployment()
    if name not in dep.get("contracts", {}):
        raise ChainError(f"Contract '{name}' is not in the deployment registry.")
    entry = dep["contracts"][name]
    return w3.eth.contract(address=w3.to_checksum_address(entry["address"]), abi=entry["abi"])


def _send(w3, func, account):
    """Build, sign, send a transaction and wait for its receipt.

    Returns (receipt, tx_hash_hex). Raises if the transaction reverts — a failed
    chain write must never be reported as success.
    """
    tx = func.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": LOCAL_CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise ChainError("On-chain transaction reverted", status_code=502)
    return receipt, tx_hash.hex()


# ---------- public operations ----------

def status() -> dict:
    """Report chain connectivity and deployment state without raising on 'not set up'."""
    try:
        w3 = get_web3()
    except ChainError as e:
        return {"connected": False, "reason": e.message, "chain_id_expected": LOCAL_CHAIN_ID}
    out = {
        "connected": True,
        "chain_id": LOCAL_CHAIN_ID,
        "rpc_url": RPC_URL,
        "operator": operator_account(w3).address,
        "block_number": w3.eth.block_number,
        "deployed": DEPLOYMENT_PATH.exists(),
    }
    if out["deployed"]:
        dep = load_deployment()
        out["contracts"] = {k: v["address"] for k, v in dep.get("contracts", {}).items()}
        try:
            token = _contract(w3, "MockUSDC")
            out["token_total_supply"] = token.functions.totalSupply().call()
            out["token_decimals"] = token.functions.decimals().call()
        except ChainError:
            pass
    return out


def token_balance(address: str) -> int:
    w3 = get_web3()
    token = _contract(w3, "MockUSDC")
    return token.functions.balanceOf(w3.to_checksum_address(address)).call()


def confirm_deposit_onchain(customer: str, token_amount: int, provider_ref: bytes) -> dict:
    """Mint synthetic USDC via the authorised SecureRamp operator path.

    Mirrors the fiat on-ramp: an authenticated payment confirmation causes
    issuance. Waits for the receipt before returning.
    """
    w3 = get_web3()
    operator = operator_account(w3)
    ramp = _contract(w3, "SecureRamp")
    customer = w3.to_checksum_address(customer)
    before = token_balance(customer)
    ref = provider_ref if isinstance(provider_ref, (bytes, bytearray)) else str(provider_ref).encode()
    ref32 = (ref + b"\x00" * 32)[:32]
    receipt, tx_hash = _send(w3, ramp.functions.confirmFiatDeposit(customer, token_amount, ref32), operator)
    after = token_balance(customer)
    return {
        "customer": customer,
        "minted": after - before,
        "token_amount": token_amount,
        "balance_after": after,
        "tx_hash": tx_hash,
        "block_number": receipt.blockNumber,
    }


def redeem_offchain(customer: str, token_amount: int) -> dict:
    """Burn redeemed synthetic USDC via the authorised operator (off-ramp settlement).

    Waits for the receipt before returning. A revert (e.g. insufficient balance)
    raises, so the caller must not credit fiat unless this returns successfully.
    """
    w3 = get_web3()
    operator = operator_account(w3)
    token = _contract(w3, "MockUSDC")
    customer = w3.to_checksum_address(customer)
    before = token.functions.balanceOf(customer).call()
    if before < token_amount:
        raise ChainError("Insufficient on-chain USDC balance for redemption", status_code=409)
    receipt, tx_hash = _send(w3, token.functions.burn(customer, token_amount), operator)
    after = token.functions.balanceOf(customer).call()
    return {
        "customer": customer,
        "burned": before - after,
        "token_amount": token_amount,
        "balance_after": after,
        "tx_hash": tx_hash,
        "block_number": receipt.blockNumber,
    }


def read_deposit_credited_events(from_block: int = 0) -> list[dict]:
    """Read SecureRamp FiatDepositCredited events, including the provider reference.

    Lets recovery deterministically match a reserved on-ramp to its confirmed
    on-chain mint by provider reference, rather than guessing from balances.
    """
    w3 = get_web3()
    ramp = _contract(w3, "SecureRamp")
    logs = ramp.events.FiatDepositCredited().get_logs(from_block=from_block)
    out = []
    for lg in logs:
        ref = lg["args"]["providerReference"]
        ref_str = bytes(ref).rstrip(b"\x00").decode("utf-8", "ignore")
        out.append({
            "customer": lg["args"]["customer"],
            "token_amount": int(lg["args"]["tokenAmount"]),
            "provider_ref": ref_str,
            "tx_hash": lg["transactionHash"].hex(),
            "block_number": lg["blockNumber"],
        })
    return out


def read_mint_events(from_block: int = 0) -> list[dict]:
    """Read ERC20 Transfer events from the zero address (mints)."""
    w3 = get_web3()
    token = _contract(w3, "MockUSDC")
    zero = "0x" + "0" * 40
    logs = token.events.Transfer().get_logs(
        from_block=from_block,
        argument_filters={"from": w3.to_checksum_address(zero)},
    )
    out = []
    for lg in logs:
        out.append({
            "to": lg["args"]["to"],
            "value": int(lg["args"]["value"]),
            "tx_hash": lg["transactionHash"].hex(),
            "block_number": lg["blockNumber"],
        })
    return out
