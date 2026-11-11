#!/usr/bin/env python3
"""Send a signed synthetic webhook to the local RampLab API."""
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=["alice", "bob"], default="alice")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--amount", default="100.00")
    parser.add_argument("--event-id", default="evt-local-demo-001")
    args = parser.parse_args()
    payload = {"owner": args.owner, "account_id": args.account_id,
               "amount": args.amount, "event_id": args.event_id}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    secret = os.getenv("RAMP_LAB_WEBHOOK_SECRET", "local-only-change-me").encode()
    signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
    req = Request("http://127.0.0.1:8000/api/webhooks/deposit", data=raw, method="POST", headers={
        "Content-Type": "application/json", "X-Ramp-Signature": f"sha256={signature}"
    })
    try:
        with urlopen(req, timeout=5) as response:
            print(response.read().decode())
            return 0
    except HTTPError as exc:
        print(exc.read().decode())
        return 1
    except URLError as exc:
        print(f"Could not reach local RampLab at 127.0.0.1:8000: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
