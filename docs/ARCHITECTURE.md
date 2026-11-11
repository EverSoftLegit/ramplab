# RampLab architecture

## 1. MVP component view

```text
                    Browser (localhost only)
                             |
                             v
                  Static training dashboard
                             |
                             v
                    FastAPI application
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
  Account service      Quote/conversion     Mock payment adapter
        |                service                   |
        |                    |                    |
        +--------------------+--------------------+
                             |
                             v
                    SQLite synthetic store
          accounts · quotes · transactions · ledger
                             |
                  isolated local test environment

    Separate local-only Foundry workspace (not wired to API yet)
         VulnerableVault.sol <-> SecureVault.sol
```

## 2. Logical modules

- **Presentation:** static HTML/CSS/JavaScript dashboard served by FastAPI. The MVP deliberately avoids an extra Node runtime so contributors can run it with Python alone.
- **API:** FastAPI routes and request validation.
- **Identity adapter:** `X-Demo-User` selects Alice or Bob. This is a training selector, not authentication and not a security boundary.
- **Account service:** seeded balances and ownership-aware reads.
- **Pricing/quote service:** fixed fictional exchange rates, integer minor units, Decimal arithmetic, 50 bps demonstration fee and 120-second quote lifetime.
- **Conversion service:** one-time quote execution, atomic balance updates, transaction creation and four ledger entries.
- **Payment adapter:** two deliberately contrasted mock callback paths: unsigned/non-idempotent and HMAC/idempotent.
- **Persistence:** SQLite for one-user local labs. Move to PostgreSQL when concurrency, multi-user hosted exercise environments or database-specific labs are introduced.
- **Smart-contract workspace:** independent Foundry project for local EVM testing; deliberately not connected to a public RPC or payment service.

## 3. Trust boundaries

1. Browser to API: all client fields are untrusted. The client must never determine authoritative rates or ownership.
2. API to database: parameterised SQL and transaction boundaries protect persistence; domain invariants must be enforced server-side.
3. Mock provider to webhook endpoint: the callback is an untrusted external message and must be authenticated, replay-safe and idempotent.
4. API to EVM: future integration must treat transaction receipts, chain IDs, confirmations and token decimals as untrusted until verified.
5. Lab boundary: intentionally vulnerable routes/contracts are available only inside a disposable local environment.

## 4. Key design decisions

### ADR-001: Modular monolith for MVP

A modular monolith is easier to run, debug and contribute to than six microservices. Split modules only when there is evidence that independent deployment or scaling is needed.

### ADR-002: SQLite for the first release

SQLite gives a zero-setup, reproducible environment. PostgreSQL is the planned next persistence target for concurrent multi-user exercises.

### ADR-003: Integer minor units and Decimal

Balances are stored as integers in currency-specific minor units. Rates are parsed as `Decimal`. Binary float is not used for money calculations.

### ADR-004: Static frontend first

A small static UI makes the lab accessible without a JavaScript package toolchain. React/Next.js can replace it later without changing API contracts.

### ADR-005: Local-only blockchain

The first contract exercises use Foundry tests and Anvil-compatible local execution. No public chain is required.

### ADR-006: Paired vulnerable and hardened paths

Every deliberate vulnerability has a corresponding secure example and regression expectation. Vulnerable code is marked in source and exposed only through explicitly named `/api/lab/` routes or the local Foundry workspace.

## 5. Evolution target

```text
Web UI (React/Next.js optional)
          |
API gateway / lab router
          |
+---------+----------+----------+-----------+
| Identity | Wallet   | Ramp     | Payments  |
| adapter  | service  | engine   | simulator |
+---------+----------+----------+-----------+
| Ledger / reconciliation | KYC simulator | Risk / limits |
+-------------------------+-----------------+
          |
PostgreSQL + event journal + deterministic mock providers
          |
Local EVM: Anvil + Solidity contracts + mock oracle
          |
Lab orchestrator: reset, seed, scenario, hints, scoring
```

The target architecture is a learning roadmap, not a claim that these components exist in 0.1.0.
