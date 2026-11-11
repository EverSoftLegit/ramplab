# RampLab

**Break it. Understand it. Secure it.**

RampLab is an intentionally vulnerable, local-only Web3 fintech security lab. It simulates crypto-to-fiat and fiat-to-crypto flows so beginners and experienced security practitioners can study vulnerabilities across APIs, payment callbacks, conversion logic, ledgers and smart contracts.

> **Safety warning:** RampLab intentionally contains vulnerable code. It is a training application, not a financial product. Use only synthetic data. Do not connect real wallets, real funds, banking/payment providers, production credentials or public chains. Do not deploy this application to the public internet.

## MVP scope

- Demo identities: Alice and Bob (not authenticated users).
- Synthetic currencies: NGN, GHS, KES, ZAR, USD, EUR, GBP and mock USDC.
- Fiat/crypto conversion quote and confirmation flow using fictional fixed rates.
- Integer minor-unit balances and `Decimal` calculations.
- SQLite accounts, quotes, transactions and ledger entries.
- Vulnerable and hardened examples for BOLA, client-controlled quote rates and webhook replay.
- Foundry exercises for vault reentrancy, ramp deposit-confirmation authorization, and synthetic token behaviour.
- Browser dashboard and FastAPI Swagger docs.

## Start locally with Python

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. API docs: <http://127.0.0.1:8000/docs>.

The database is created under `data/ramplab.sqlite3`. To reset in the UI, use **Reset demo data**. API reset requires the explicit confirmation string.

## Start with Docker Compose

```bash
cp .env.example .env
# Keep the app local. Do not change the published host binding to 0.0.0.0.
docker compose up --build
```

Open <http://127.0.0.1:8000>. The published port is bound to `127.0.0.1`; containers use an internal Compose network. Docker is an isolation aid, not a guarantee against unsafe host configuration.

## Run tests

```bash
python -m pytest -q
```

## Run the local smart-contract lab

Install Foundry using the official instructions, then:

```bash
cd contracts
forge test -vv
```

## Local Web3 integration (Anvil)

The backend connects to a local Anvil chain (chain id `31337`) for real
on-chain minting of synthetic USDC. It **fails closed**: any chain whose id is
not `31337`, and any non-local RPC host, is refused.

```bash
pip install -e ".[chain]"      # adds web3
anvil                          # terminal 1 — local chain, id 31337
python scripts/deploy_contracts.py   # terminal 2 — deploys MockUSDC + SecureRamp
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then the chain endpoints are live:

- `GET  /api/chain/status` — connectivity, deployed addresses, token supply.
- `GET  /api/chain/balance/{address}` — on-chain MockUSDC balance.
- `POST /api/chain/onramp` — authorised operator confirmation mints USDC on-chain
  (elevated role only); the mint is confirmed by its receipt before the internal
  association is recorded.
- `GET  /api/chain/reconciliation` — compares on-chain mint events against
  internal on-ramp records and flags either side that has no match.

### Integrated fiat ⇄ USDC ramp

The ramp ties the internal fiat ledger to the chain as atomic sagas:

- `POST /api/ramp/onramp` — debits internal fiat, then mints USDC on-chain. If
  the mint fails, the fiat reservation is **refunded** (no value is minted
  without a confirmed fiat debit).
- `POST /api/ramp/offramp` — burns on-chain USDC, then credits internal fiat (no
  fiat is created without a confirmed burn).
- `GET  /api/ramp/account` / `GET /api/ramp/conversions` — the customer's mapped
  address and on-chain balance, and their ramp history.

The Convert screen exposes the ramp; Observability and Administration surface
chain status, on-chain reconciliation and an operator on-ramp control. The ramp
uses Anvil's public test operator key — safe precisely because it must never
hold real funds. The fiat double-entry ledger stays balanced through every path.

## Learning paths

- Guided exercises: `labs/` includes scenarios, hints/questions and remediation guidance.
- Independent exercises: use the challenge IDs and vulnerable routes/contracts without reading remediation first.
- Challenge catalogue: `GET /api/challenges`.

## Initial challenges

| ID | Weakness | Vulnerable target | Hardened comparison |
|---|---|---|---|
| RAMP-001 | Broken object-level authorization | `GET /api/lab/accounts/{id}` | `GET /api/accounts/{id}` |
| RAMP-002 | Caller-controlled exchange rate | `POST /api/lab/quotes` | `POST /api/quotes` |
| RAMP-015 | Incorrect token decimal handling | `POST /api/lab/decimal-quote` | `POST /api/quotes` |
| RAMP-016 | Fee rounding / precision exploitation | `POST /api/fee-preview` (truncated) | `POST /api/fee-preview` (minimum) |
| RAMP-017 | Stale exchange-rate exploitation | `POST /api/lab/conversions` | `POST /api/conversions` |
| RAMP-003 | Unsigned and replayable deposit callback | `POST /api/lab/webhooks/deposit` | `POST /api/webhooks/deposit` |
| RAMP-014 | Signature replay / weak nonce | `POST /api/lab/signed-withdraw` | `POST /api/signed-withdraw` |
| RAMP-004 | Reentrancy | `contracts/src/VulnerableVault.sol` | `contracts/src/SecureVault.sol` |
| RAMP-005 | Unauthorised fiat deposit confirmation | `contracts/src/VulnerableRamp.sol` | `contracts/src/SecureRamp.sol` |
| RAMP-018 | Information disclosure of secrets/PII | `GET /api/lab/debug` | `GET /api/health` |
| RAMP-019 | Weak session management | `GET /api/lab/whoami` | `GET /api/whoami` |
| RAMP-020 | Cross-component transaction manipulation | replay callback → on-ramp | idempotent callback + reconciliation |
| RAMP-021 | Reconciliation failure (unledgered credit) | `POST /api/lab/admin/credit` | `POST /api/admin/credit` |
| RAMP-006 | Mass assignment on profile update | `POST /api/lab/profile` | `POST /api/profile` |
| RAMP-007 | Race condition in concurrent withdrawals | `POST /api/lab/withdraw` | `POST /api/withdraw` |
| RAMP-009 | Insecure direct object reference | `GET /api/lab/transactions/{id}` | `GET /api/transactions/{id}` |
| RAMP-011 | Broken function-level authorization | `GET /api/lab/admin/users` | `GET /api/admin/overview` |
| RAMP-008 | Saga integrity across ledger and chain | naive mint-then-debit (conceptual) | `POST /api/ramp/onramp` + recovery |
| RAMP-010 | On-chain/off-chain reconciliation gap | `POST /api/lab/webhooks/deposit` + `GET /api/ledger/reconciliation` | `POST /api/webhooks/deposit` |
| RAMP-012 | Price oracle manipulation | `contracts/src/VulnerablePriceOracle.sol` | `contracts/src/SecurePriceOracle.sol` |
| RAMP-013 | Insecure proxy upgrade | `contracts/src/VulnerableProxy.sol` | `contracts/src/SecureProxy.sol` |

Full challenge metadata (root cause, remediation, regression test) is available at `GET /api/challenges` and `GET /api/challenges/{id}`.

## Ledger integrity and reconciliation

RampLab keeps the double-entry ledger — not the cached balance column — as the
financial source of truth:

- `GET /api/ledger/integrity` verifies that every currency nets to zero and that
  each account balance equals the sum of its ledger entries.
- `GET /api/ledger/reconciliation` reconciles the payment-callback log against
  credited deposits. A replayed deposit keeps the ledger internally balanced yet
  shows up here as an event credited more than once — the distinction between
  internal consistency and external backing.

## Important identity limitation

`X-Demo-User: alice|bob` is a deliberately simplified lab selector. It is not authentication and can be spoofed by any caller. The hardened account example demonstrates object ownership checks only. A production service would need real authentication, verified server-side identity claims, session security, authorization policy and independent review.

## Rates and balances

All seeded balances and FX values are fictional. The project does not fetch live prices. Mock USDC is an internal unit with six decimal places; it is not the real USDC asset or an ERC-20 token in the MVP API.

## Project documents

- Product specification: `docs/PRODUCT_SPEC.md`
- Architecture: `docs/ARCHITECTURE.md`
- Threat model: `docs/THREAT_MODEL.md`
- Security reference baseline: `docs/REFERENCE_BASELINE.md`
- Adjacent project landscape: `docs/PROJECT_LANDSCAPE.md`
- Implementation backlog: `docs/IMPLEMENTATION_BACKLOG.md`
- Lab safety: `docs/LAB_SAFETY.md`
- Contribution guide: `CONTRIBUTING.md`
- Security policy: `SECURITY.md`

## Status

This is an MVP scaffold and learning environment. It has not undergone an independent security audit. Hardened examples are educational comparisons, not production-ready implementation patterns.
