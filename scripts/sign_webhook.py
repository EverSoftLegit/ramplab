#!/usr/bin/env python3
"""Create a local-only HMAC for the RampLab mock webhook exercise."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=["alice", "bob"], default="alice")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--amount", default="100.00")
    parser.add_argument("--event-id", default="evt-local-demo-001")
    args = parser.parse_args()
    body = {
        "owner": args.owner,
        "account_id": args.account_id,
        "amount": args.amount,
        "event_id": args.event_id,
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    secret = os.getenv("RAMP_LAB_WEBHOOK_SECRET", "local-only-change-me").encode()
    signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    print(json.dumps(body, separators=(",", ":")))
    print(f"sha256={signature}")
    print("LOCAL TRAINING ONLY: never reuse this secret or pattern as a production key-management design.")


if __name__ == "__main__":
    main()
