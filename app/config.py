from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

DB_PATH = Path(os.getenv("RAMP_DB_PATH", BASE_DIR / "data" / "ramplab.sqlite3"))
WEBHOOK_SECRET = os.getenv("RAMP_LAB_WEBHOOK_SECRET", "local-only-change-me")

# ----- Local blockchain (Anvil) configuration -----
# RampLab only ever talks to a local development chain. These defaults match
# Anvil's out-of-the-box chain ID and first funded account. The operator key
# below is Anvil/Hardhat's publicly documented test key — it is safe precisely
# because it must never hold real funds. Deployments fail closed on any chain
# whose ID is not LOCAL_CHAIN_ID and any RPC host that is not local.
RPC_URL = os.getenv("RAMP_RPC_URL", "http://127.0.0.1:8545")
LOCAL_CHAIN_ID = int(os.getenv("RAMP_CHAIN_ID", "31337"))
# Well-known Anvil account #0 — a public test key, never for real value.
OPERATOR_KEY = os.getenv(
    "RAMP_OPERATOR_KEY",
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
)
DEPLOYMENT_PATH = Path(os.getenv("RAMP_DEPLOYMENT_PATH", BASE_DIR / "data" / "deployment.json"))
# Hosts we consider local. Anything else is refused unless explicitly allowed,
# which this lab never does.
LOCAL_RPC_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "anvil", "host.docker.internal"}
# Demo customers mapped to Anvil's deterministic funded accounts, so the
# integrated on/off-ramp has a stable on-chain address per demo identity.
DEMO_ADDRESSES = {
    "alice": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",  # Anvil #1
    "bob": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",    # Anvil #2
}
# Publicly documented Anvil test keys for the demo identities. Used only to sign
# demo authorizations in a local lab; safe precisely because they hold no value.
DEMO_KEYS = {
    "alice": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "bob": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
}

# All rates are fictional teaching fixtures, not market prices or financial advice.
# Values represent approximate USD value of one unit of the named currency.
CURRENCY_USD_VALUE: dict[str, Decimal] = {
    "NGN": Decimal("0.00066"),
    "GHS": Decimal("0.0667"),
    "KES": Decimal("0.0077"),
    "ZAR": Decimal("0.0556"),
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
    "USDC": Decimal("1"),
}
CURRENCY_SCALE: dict[str, int] = {
    "NGN": 2,
    "GHS": 2,
    "KES": 2,
    "ZAR": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "USDC": 6,
}
FEE_BPS = 50  # 0.50% demonstration fee
QUOTE_TTL_SECONDS = 120
DEMO_USERS = ("alice", "bob")
# Elevated demo identities for administrative/observability screens. These are
# lab selectors, not authentication; a real system needs verified server-side roles.
ADMIN_USERS = ("admin", "operations")
