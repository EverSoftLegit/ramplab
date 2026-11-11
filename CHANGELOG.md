# Changelog

## 1.3.0 — Findings and catalogue export

### Added
- Learner findings-report export: an "Export findings report" button on the
  Challenge centre compiles a Markdown report (completion table plus the
  learner's evidence notes) and downloads it client-side, plus a live
  completion counter — serving the "produce security findings and reports" goal.
- Facilitator catalogue export: `GET /api/challenges/export` returns the full
  catalogue as a Markdown document (routed before `/{challenge_id}` so it is not
  shadowed).

## 1.2.0 — RAMP-008 runnable, full contract list in the UI

### Added
- RAMP-008 now has a runnable broken variant: `POST /api/lab/ramp/onramp` mints
  on-chain before debiting fiat, so a failed debit leaves unbacked USDC. A live
  test reproduces the unbacked mint and proves the hardened on-ramp never mints
  when the fiat check fails. Every challenge now has a runnable reproduce.

### Changed
- The Observability blockchain panel lists every registered contract dynamically
  (MockUSDC, SecureRamp, SecurePriceOracle, AccessControlManager, FeeManager)
  instead of a hard-coded two.

## 1.1.0 — Complete the contract set

### Added
- `AccessControlManager.sol` — a standalone role/permission registry (admin-gated
  grant/revoke, `hasRole`/`requireRole`, admin transfer) with Foundry tests.
- `FeeManager.sol` — simulated transaction fee logic: a basis-point fee with a
  minimum-fee floor (the on-chain counterpart of the RAMP-016 hardened policy),
  owner-gated configuration, with Foundry tests.
- The deploy script now also deploys `SecurePriceOracle`, `AccessControlManager`
  and `FeeManager`, so the on-chain registry (and `GET /api/chain/status`)
  reflects the full architecture contract set.
- Contract suite is now 15 tests across 7 suites. The directive's full contract
  list is implemented.

## 1.0.0 — 21 challenges across every tier

### Added
- RAMP-018 (information disclosure): `GET /api/lab/debug` leaks the webhook
  secret, operator key and customer emails; `GET /api/health` reveals none.
- RAMP-019 (weak session management): a forgeable base64 session token
  (`GET /api/lab/whoami`) vs an HMAC-signed token (`GET /api/whoami`).
- RAMP-020 (cross-component transaction manipulation): an Expert multi-stage
  chain — a replayed deposit inflates fiat, which is on-ramped to mint on-chain
  USDC, and reconciliation traces the on-chain value to its unbacked source.
- RAMP-021 (reconciliation failure): an admin credit that bumps the balance with
  no ledger entry breaks the integrity invariant vs a balanced posting.
- `app/sessions.py`, `admin_credit_vulnerable`/`admin_credit_secure`, and a
  cross-component live integration test.

The catalogue now has **21 challenges** (6 Beginner, 4 Intermediate, 8 Advanced,
3 Expert), meeting the directive's 20+ target. 57 Python tests + 11 contract
tests pass.

## 0.9.0 — Precision, rounding and stale-rate challenges

### Added
- RAMP-015 (incorrect token decimal handling): `POST /api/lab/decimal-quote`
  prices with naive minor-unit arithmetic (wrong by the decimal-place factor)
  alongside the correct result; the hardened path normalises to major units.
- RAMP-016 (fee rounding exploitation): `POST /api/fee-preview` shows the
  truncating fee policy (dust pays zero; splittable) vs a minimum-fee policy.
- RAMP-017 (stale exchange-rate exploitation): `POST /api/lab/conversions`
  settles an expired quote (expiry not enforced) vs the hardened `/api/conversions`.
- `calculate_target_naive`, `fee_minor_vulnerable`/`fee_minor_secure`, and an
  `allow_expired` flag on `execute_conversion`, with reproduce+prevent tests.
- Catalogue now has 17 challenges (4 Beginner, 4 Intermediate, 7 Advanced, 2 Expert).

## 0.8.0 — Signed-authorization challenge (signature replay / nonce)

### Added
- RAMP-014: ECDSA-signed withdrawal authorization. The lab endpoint
  `POST /api/lab/signed-withdraw` verifies the signature but consumes no nonce,
  so a captured authorization can be replayed; `POST /api/signed-withdraw` binds
  and atomically advances a per-account nonce, rejecting the replay.
- `app/signing.py` (EIP-191 personal_sign recovery, no chain needed), an
  `auth_nonces` table, `GET /api/signing/nonce`, and public Anvil demo keys for
  signing in the lab.
- Tests prove the replay reproduces (double debit), is rejected by the secure
  path (single debit, nonce advances), and that the signature binds both the
  signer identity and the amount.
- Catalogue now has 14 challenges (4 Beginner, 3 Intermediate, 5 Advanced, 2 Expert).

## 0.7.0 — Smart-contract challenges: oracle and proxy

### Added
- RAMP-012 (price oracle manipulation): `VulnerablePriceOracle` (anyone writes,
  no freshness) with a `PriceConsumer` showing impact, vs `SecurePriceOracle`
  (authorised updater, non-zero prices, staleness revert). Foundry tests
  reproduce a 100x reprice from an unrelated account and prove the hardened
  oracle rejects it and reverts on stale/unset prices.
- RAMP-013 (insecure proxy upgrade): a minimal delegatecall `VulnerableProxy`
  whose `upgradeTo` has no access control vs `SecureProxy` with an admin check.
  Foundry tests reproduce an implementation takeover by an unrelated account and
  prove the hardened proxy rejects it while the admin can still upgrade.
- Catalogue now has 13 challenges; contract suite is 11 tests across 5 suites.

## 0.6.0 — Runnable vulnerable/secure pairs

### Added
- RAMP-009 (IDOR): `GET /api/lab/transactions/{id}` returns any transaction with
  no ownership check vs the hardened `GET /api/transactions/{id}`.
- RAMP-011 (BFLA): `GET /api/lab/admin/users` exposes an admin listing with no
  role check vs the hardened `GET /api/admin/overview`.
- RAMP-007 now ships a runnable broken variant: `POST /api/lab/withdraw`
  (non-atomic check-then-act) vs `POST /api/withdraw` (serialised). A concurrency
  test reproduces the double-spend on the lab path and proves the hardened path
  prevents it.
- Catalogue now has 11 challenges; every entry's cited regression test is
  verified to exist.

## 0.5.0 — Saga recovery and catalogue expansion

### Added
- `app/recovery.py` — idempotent recovery sweep for interrupted ramp sagas.
  Resolves `fiat_reserved` on-ramps by matching the SecureRamp
  `FiatDepositCredited` event by provider reference (complete if the mint landed,
  refund if it did not), settles `burned` off-ramps, and flags `initiated`
  off-ramps for review. Endpoints: `GET /api/ramp/recovery/scan`,
  `POST /api/ramp/recovery/run` (elevated role).
- Off-ramp now records a `burned` intermediate state, so an interruption between
  the burn and the fiat credit is recoverable.
- `read_deposit_credited_events` on the chain client (reads the provider
  reference), enabling deterministic recovery matching.
- New vulnerable/secure pair RAMP-006 (mass assignment): `POST /api/lab/profile`
  binds every field (privilege escalation) vs `POST /api/profile` allowlist,
  with reproduce + prevent regression tests and a seeded `profiles` table.
- Challenge catalogue expanded to 9: added RAMP-006 (mass assignment),
  RAMP-007 (concurrent withdrawal race), RAMP-008 (saga integrity across ledger
  and chain) — each wired to an existing regression test.

## 0.4.0 — Integrated fiat ⇄ on-chain USDC ramp

### Added
- `app/ramp.py` — atomic on-ramp and off-ramp as sagas with explicit state and
  compensation. On-ramp reserves internal fiat first, then mints on-chain, and
  **refunds the fiat if the mint fails**. Off-ramp burns on-chain USDC first,
  then credits fiat, so **no fiat is created without a confirmed burn**.
- `burn(from, amount)` on MockUSDC (operator-only) for redemption settlement,
  with supply/authorization contract tests.
- `redeem_offchain` on the chain client; demo identities mapped to deterministic
  Anvil addresses.
- API: `POST /api/ramp/onramp`, `POST /api/ramp/offramp`,
  `GET /api/ramp/account`, `GET /api/ramp/conversions`.
- Convert screen: an "On-chain ramp" panel (address, live USDC balance, on/off-ramp
  controls and conversion history).
- Saga tests proving fiat refund on mint failure and no fiat credit on burn
  failure, plus live round-trip integration tests against Anvil. The fiat
  double-entry ledger stays balanced in every path.

## 0.3.0 — Local Web3 integration (Anvil)

### Added
- `app/chain.py` — fail-closed web3 client: refuses any chain id that is not the
  configured local chain (31337) and any non-local RPC host; mints via the
  authorised SecureRamp operator, reads balances and Transfer (mint) events, and
  waits for transaction receipts before reporting success.
- `scripts/deploy_contracts.py` — deploys MockUSDC and SecureRamp to Anvil from
  Foundry build artifacts, grants the minter role and writes a deployment registry.
- Chain API: `GET /api/chain/status`, `GET /api/chain/balance/{address}`,
  `POST /api/chain/onramp` (role-restricted on-chain mint), and
  `GET /api/chain/reconciliation` (on-chain mint events vs. internal records).
- `onramp_mints` table associating each on-chain mint with its internal record.
- Web3 integration tests that start Anvil, deploy and exercise mint, balance,
  events and reconciliation — skipping cleanly when Anvil/Foundry/web3 are absent.
- Observability and Administration UI: local-chain status, on-chain reconciliation
  and an operator on-ramp mint control.

## 0.2.0 — Financial core, observability and a premium UI

### Added
- Double-entry ledger foundation: opening balances now post as balanced ledger
  entries against an internal `equity` account, so the ledger — not the cached
  balance column — is the financial source of truth.
- `GET /api/ledger/integrity` — verifies zero-sum-per-currency and
  balance-vs-ledger projection invariants.
- `GET /api/ledger/reconciliation` — reconciles the payment-callback delivery
  log against credited deposits and flags any event credited more than once.
- Append-only `payment_callbacks` log written on both webhook paths, enabling
  reconciliation of replayed, non-idempotent callbacks.
- Quote lifecycle state machine with `POST /api/quotes/{id}/cancel`.
- Elevated demo roles (`admin`, `operations`) with `GET /api/admin/overview`
  and `GET /api/observability/summary` (aggregated synthetic metrics).
- Expanded challenge catalogue with full metadata and `GET /api/challenges/{id}`;
  added multi-stage challenge RAMP-010 (on-chain/off-chain reconciliation gap).
- Race-condition regression tests proving the secure conversion path cannot be
  double-spent under concurrent execution.
- Rebuilt frontend: a multi-page application (overview, dashboard, wallets,
  convert, challenge centre, challenge workspace, observability, administration)
  with a dark-first design system, light theme, charts built from real synthetic
  data, guided/independent modes and responsive mobile navigation.

### Fixed
- `RampAuthorization.t.sol` used the Solidity reserved word `reference` as a
  parameter name, breaking compilation; renamed to `providerRef`.
- Corrected the `python -m python -m pytest` typo in the README.

## 0.1.0 — Initial MVP

- Added local synthetic wallet accounts and fiat/USDC conversion flow.
- Added integer minor-unit balances and Decimal-based quote arithmetic.
- Added quote expiry and one-time execution.
- Added transaction and ledger records.
- Added vulnerable/hardened BOLA, exchange-rate and webhook examples.
- Added local Foundry vulnerable/secure reentrancy exercise.
- Added browser dashboard, challenge catalogue, docs and CI workflows.
