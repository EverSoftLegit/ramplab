"""RampLab challenge catalogue.

Each entry documents a vulnerability in a believable fintech workflow with its
root cause and remediation. The emphasis is on business-logic flaws that span
the exchange engine, payment provider, wallet, ledger and blockchain, so that
understanding the architecture — not guessing an endpoint name — is what solves
the harder challenges.
"""
from __future__ import annotations

CHALLENGES: list[dict] = [
    {
        "id": "RAMP-001",
        "title": "Broken object-level authorization",
        "level": "Beginner",
        "category": "Access control",
        "component": "Accounts API",
        "business_context": (
            "A support tool looks up wallet accounts by identifier. The lookup "
            "trusts the identifier without confirming the caller owns the account."
        ),
        "objectives": [
            "Compare the lab account route with the ownership-checked route.",
            "Explain why server-side ownership scoping is required on every object read.",
        ],
        "vulnerable": "GET /api/lab/accounts/{account_id}",
        "hardened": "GET /api/accounts/{account_id}",
        "root_cause": (
            "The object is fetched by primary key and returned without comparing its "
            "owner to the authenticated identity."
        ),
        "remediation": (
            "Derive identity from a verified server-side session and scope every "
            "object query to its owner; return 404/403 on mismatch."
        ),
        "mode": "both",
        "regression_test": "tests/test_api.py::test_bola_lab_and_hardened_account_read",
    },
    {
        "id": "RAMP-002",
        "title": "Caller-controlled exchange rate",
        "level": "Intermediate",
        "category": "Business logic · pricing integrity",
        "component": "Exchange engine",
        "business_context": (
            "The quote service builds a conversion price. The lab variant accepts a "
            "rate supplied by the caller instead of pricing server-side."
        ),
        "objectives": [
            "Show how an untrusted rate breaks conversion value.",
            "Explain binding rate, amount, identity and expiry into a server-issued quote.",
        ],
        "vulnerable": "POST /api/lab/quotes",
        "hardened": "POST /api/quotes",
        "root_cause": (
            "Price is an input rather than a server-authoritative value, so the client "
            "can set the terms of trade."
        ),
        "remediation": (
            "Price every quote on the server from a controlled rate source; persist the "
            "quote and bind it to amount, identity and a short expiry."
        ),
        "mode": "both",
        "regression_test": "tests/test_api.py::test_lab_quote_accepts_client_controlled_rate",
    },
    {
        "id": "RAMP-003",
        "title": "Unsigned, replayable payment callback",
        "level": "Intermediate",
        "category": "Business logic · idempotency & authenticity",
        "component": "Payment provider · webhook",
        "business_context": (
            "A mock bank confirms deposits via callback. The lab callback is neither "
            "authenticated nor idempotent, so a replay credits the wallet again."
        ),
        "objectives": [
            "Observe that a replayed deposit keeps the ledger internally balanced.",
            "Use reconciliation against the callback log to detect the double credit.",
            "Explain HMAC verification plus event-level idempotency in one transaction.",
        ],
        "vulnerable": "POST /api/lab/webhooks/deposit",
        "hardened": "POST /api/webhooks/deposit",
        "root_cause": (
            "The callback is trusted without verifying authenticity or enforcing a "
            "unique event identifier, so the same event produces value more than once."
        ),
        "remediation": (
            "Verify a raw-body HMAC and enforce a unique event ID in the same database "
            "transaction as the credit; reconcile the delivery log on a schedule."
        ),
        "mode": "both",
        "regression_test": "tests/test_api.py::test_replayed_deposit_keeps_ledger_balanced_but_fails_reconciliation",
    },
    {
        "id": "RAMP-014",
        "title": "Signature replay and weak nonce handling",
        "level": "Intermediate",
        "category": "Web3 · signature verification",
        "component": "Signed authorization API",
        "business_context": (
            "A customer authorises a withdrawal by signing a message with their "
            "wallet key. The lab endpoint verifies the signature but never consumes "
            "a nonce, so a captured authorization can be replayed to withdraw again."
        ),
        "objectives": [
            "Submit the same signed authorization twice to the lab endpoint and see it debit twice.",
            "Explain how binding and atomically consuming a per-account nonce stops the replay.",
            "Confirm the signature binds the amount and the signer identity.",
        ],
        "vulnerable": "POST /api/lab/signed-withdraw",
        "hardened": "POST /api/signed-withdraw",
        "root_cause": (
            "The authorization is verified for authenticity but not for freshness: "
            "no nonce is bound or consumed, so the same signature is valid forever."
        ),
        "remediation": (
            "Bind a per-account nonce (or expiry) into the signed message and consume "
            "it atomically on use; reject any authorization that does not carry the "
            "current nonce."
        ),
        "mode": "both",
        "regression_test": "tests/test_signing.py::test_secure_signed_withdraw_rejects_replay",
    },
    {
        "id": "RAMP-004",
        "title": "Reentrancy in a simulated vault",
        "level": "Advanced",
        "category": "Smart contract · reentrancy",
        "component": "VulnerableVault.sol",
        "business_context": (
            "A vault lets a customer withdraw a synthetic balance. State is updated "
            "after the external transfer, so a nested call re-enters before the balance clears."
        ),
        "objectives": [
            "Run the Foundry test and read whether state changes precede the external call.",
            "Apply checks-effects-interactions and a reviewed guard.",
        ],
        "vulnerable": "contracts/src/VulnerableVault.sol",
        "hardened": "contracts/src/SecureVault.sol",
        "root_cause": "The external call happens before the balance is decremented.",
        "remediation": "Follow checks-effects-interactions; decrement state before any external call.",
        "mode": "both",
        "regression_test": "contracts/test/VaultReentrancy.t.sol",
    },
    {
        "id": "RAMP-005",
        "title": "Unauthorised fiat-deposit confirmation",
        "level": "Advanced",
        "category": "Smart contract · access control",
        "component": "VulnerableRamp.sol",
        "business_context": (
            "An on-ramp mints synthetic stablecoin when a fiat deposit is confirmed. "
            "The vulnerable contract lets anyone confirm, minting unbacked value."
        ),
        "objectives": [
            "Identify the missing trust boundary on the confirmation function.",
            "Explain why an operator allowlist is necessary but not sufficient.",
        ],
        "vulnerable": "contracts/src/VulnerableRamp.sol",
        "hardened": "contracts/src/SecureRamp.sol",
        "root_cause": "The confirmation entrypoint has no authorization on the payment trust boundary.",
        "remediation": (
            "Restrict confirmation to an authorised payment operator and, in a real "
            "system, verify provider signatures, replay controls and reconciliation."
        ),
        "mode": "both",
        "regression_test": "contracts/test/RampAuthorization.t.sol",
    },
    {
        "id": "RAMP-006",
        "title": "Mass assignment on profile update",
        "level": "Beginner",
        "category": "Access control · mass assignment",
        "component": "Profile API",
        "business_context": (
            "A customer can edit their own profile. The lab endpoint binds every "
            "known field from the request body, so a customer can set privileged "
            "fields — role, status, KYC level — that should never be self-editable."
        ),
        "objectives": [
            "Send a profile update that includes a privileged field and observe it apply.",
            "Compare with the hardened endpoint that binds only an allowlist.",
        ],
        "vulnerable": "POST /api/lab/profile",
        "hardened": "POST /api/profile",
        "root_cause": (
            "The handler binds request fields to the record by name without an "
            "allowlist, so privileged attributes are writable by the account holder."
        ),
        "remediation": (
            "Bind only an explicit allowlist of self-editable fields; privileged "
            "attributes change through a separate, authorised administrative path."
        ),
        "mode": "both",
        "regression_test": "tests/test_api.py::test_mass_assignment_lab_allows_privilege_escalation",
    },
    {
        "id": "RAMP-007",
        "title": "Race condition in concurrent withdrawals",
        "level": "Advanced",
        "category": "Business logic · concurrency",
        "component": "Conversion engine · ledger",
        "business_context": (
            "Two requests spend the same quote (or the same balance) at once. Without "
            "serialised execution and a single-use guard, both can succeed and "
            "double-spend; the hardened path serialises and allows exactly one."
        ),
        "objectives": [
            "Reason about the window between reading a balance and writing the debit.",
            "Explain how an atomic transaction plus a single-use quote guard closes it.",
        ],
        "vulnerable": "POST /api/lab/withdraw",
        "hardened": "POST /api/withdraw",
        "root_cause": (
            "A check-then-act on the balance without a transaction boundary lets two "
            "concurrent operations both pass the check before either writes."
        ),
        "remediation": (
            "Execute the check and the debit inside one serialised transaction so "
            "only one of the concurrent attempts can complete."
        ),
        "mode": "both",
        "regression_test": "tests/test_concurrency.py::test_vulnerable_withdraw_double_spends_under_concurrency",
    },
    {
        "id": "RAMP-009",
        "title": "Insecure direct object reference on transactions",
        "level": "Beginner",
        "category": "Access control · IDOR",
        "component": "Transactions API",
        "business_context": (
            "A transaction can be fetched by its identifier. The lab endpoint returns "
            "any transaction by id without checking that it belongs to the caller, so "
            "one customer can read another's financial records."
        ),
        "objectives": [
            "Read another identity's transaction through the lab endpoint.",
            "Confirm the hardened endpoint scopes the lookup to the caller.",
        ],
        "vulnerable": "GET /api/lab/transactions/{id}",
        "hardened": "GET /api/transactions/{id}",
        "root_cause": "The object is returned by id with no owner check on the lookup.",
        "remediation": "Scope every object read to the authenticated owner; return 404 on mismatch.",
        "mode": "both",
        "regression_test": "tests/test_api.py::test_idor_lab_exposes_other_users_transaction",
    },
    {
        "id": "RAMP-011",
        "title": "Broken function-level authorization",
        "level": "Beginner",
        "category": "Access control · BFLA",
        "component": "Admin API",
        "business_context": (
            "An administrative user listing is exposed without a role check, so any "
            "customer can call a function meant only for operators."
        ),
        "objectives": [
            "Call the lab admin listing as a customer and observe it succeed.",
            "Confirm the hardened administrative endpoint enforces the operator role.",
        ],
        "vulnerable": "GET /api/lab/admin/users",
        "hardened": "GET /api/admin/overview",
        "root_cause": "The administrative handler performs no authorization on the caller's role.",
        "remediation": "Enforce a server-side role check on every privileged function, not just in the UI.",
        "mode": "both",
        "regression_test": "tests/test_api.py::test_bfla_lab_admin_listing_has_no_role_check",
    },
    {
        "id": "RAMP-008",
        "title": "Saga integrity across ledger and chain",
        "level": "Expert",
        "category": "Multi-stage · distributed consistency",
        "component": "Ramp · ledger ↔ blockchain",
        "business_context": (
            "An on-ramp spans the internal ledger and the chain, which cannot share a "
            "transaction. A naive ordering can mint on-chain value while failing to "
            "debit fiat — creating unbacked value. The hardened saga reserves fiat "
            "first, mints second, and compensates (refunds) if the mint fails."
        ),
        "objectives": [
            "Trace the on-ramp state machine: fiat_reserved → completed, or → failed.",
            "Explain why the compensating refund preserves the no-unbacked-value invariant.",
            "Use the recovery sweep to resolve a conversion interrupted mid-flight.",
        ],
        "vulnerable": "POST /api/lab/ramp/onramp (mint-first)",
        "hardened": "POST /api/ramp/onramp + POST /api/ramp/recovery/run",
        "root_cause": (
            "Treating two independent systems as if one transaction spans both, with "
            "no compensating action when the second step fails. The lab endpoint mints "
            "on-chain before debiting fiat, so a failed debit leaves unbacked USDC."
        ),
        "remediation": (
            "Model the flow as a saga: reserve the reliable local side first, perform "
            "the irreversible remote step second, compensate on failure, and provide a "
            "recovery sweep for interrupted states."
        ),
        "mode": "both",
        "regression_test": "tests/test_chain.py::test_naive_onramp_creates_unbacked_usdc_hardened_does_not",
    },
    {
        "id": "RAMP-018",
        "title": "Information disclosure of secrets and PII",
        "level": "Beginner",
        "category": "Information disclosure",
        "component": "Debug/diagnostics API",
        "business_context": (
            "A diagnostics endpoint returns internal configuration to help debugging "
            "— including the webhook signing secret, the operator key and every "
            "customer's email."
        ),
        "objectives": [
            "Read the lab debug endpoint and identify the secrets and PII it exposes.",
            "Confirm the sanitized health endpoint reveals none of it.",
        ],
        "vulnerable": "GET /api/lab/debug",
        "hardened": "GET /api/health",
        "root_cause": "A diagnostics response serves secrets and personal data to any caller.",
        "remediation": "Never serve secrets or PII; keep diagnostics minimal and authenticated.",
        "mode": "both",
        "regression_test": "tests/test_api.py::test_info_disclosure_lab_leaks_secret_health_does_not",
    },
    {
        "id": "RAMP-019",
        "title": "Weak session management",
        "level": "Beginner",
        "category": "Access control · sessions",
        "component": "Session API",
        "business_context": (
            "The lab session token is just the base64 of the username, with no "
            "integrity protection, so an attacker can forge a token for any account."
        ),
        "objectives": [
            "Forge a token for another account and resolve it on the lab endpoint.",
            "Confirm the hardened endpoint rejects a token without a valid signature.",
        ],
        "vulnerable": "GET /api/lab/whoami",
        "hardened": "GET /api/whoami",
        "root_cause": "The session token carries identity without an integrity check, so it is forgeable.",
        "remediation": "Bind identity into a signed (HMAC) or random, server-stored session token and verify it.",
        "mode": "both",
        "regression_test": "tests/test_api.py::test_weak_session_token_is_forgeable",
    },
    {
        "id": "RAMP-020",
        "title": "Cross-component transaction manipulation",
        "level": "Expert",
        "category": "Multi-stage · payment → ledger → chain",
        "component": "Payment provider · ledger · blockchain",
        "business_context": (
            "A replayed deposit callback inflates internal fiat, which is then "
            "on-ramped to mint USDC on-chain — on-chain value whose root cause is an "
            "unbacked, replayed payment. The manipulation crosses three components."
        ),
        "objectives": [
            "Replay the vulnerable callback, then on-ramp the inflated balance to the chain.",
            "Explain how value propagates payment → ledger → chain when one link is weak.",
            "Use payment-callback reconciliation to trace the on-chain value to its unbacked source.",
        ],
        "vulnerable": "POST /api/lab/webhooks/deposit → POST /api/ramp/onramp",
        "hardened": "POST /api/webhooks/deposit (idempotent) + reconciliation",
        "root_cause": (
            "A weakness in one component (replayable callback) is laundered through "
            "later components (ledger credit, on-chain mint) into apparently legitimate value."
        ),
        "remediation": (
            "Make each trust boundary idempotent and authenticated, and reconcile "
            "across components so cross-stage propagation is caught."
        ),
        "mode": "independent",
        "regression_test": "tests/test_chain.py::test_cross_component_replay_propagates_to_chain_and_is_flagged",
    },
    {
        "id": "RAMP-021",
        "title": "Reconciliation failure from unledgered credit",
        "level": "Advanced",
        "category": "Business logic · ledger integrity",
        "component": "Admin adjustments · ledger",
        "business_context": (
            "An administrative credit bumps the wallet balance column directly "
            "without posting a ledger entry, so the cached balance and the "
            "double-entry ledger silently diverge."
        ),
        "objectives": [
            "Apply the lab admin credit and watch the ledger integrity check fail.",
            "Explain why every balance change must be a balanced ledger posting.",
        ],
        "vulnerable": "POST /api/lab/admin/credit",
        "hardened": "POST /api/admin/credit",
        "root_cause": "A balance is changed outside the ledger, breaking the balance-equals-ledger invariant.",
        "remediation": "Make the ledger the source of truth: every balance change is a balanced posting.",
        "mode": "both",
        "regression_test": "tests/test_api.py::test_lab_admin_credit_breaks_ledger_integrity",
    },
    {
        "id": "RAMP-015",
        "title": "Incorrect token decimal handling",
        "level": "Intermediate",
        "category": "Business logic · precision",
        "component": "Exchange engine",
        "business_context": (
            "Currencies carry different decimal places (NGN has 2, USDC has 6). The "
            "lab pricing path multiplies minor units by the rate without adjusting "
            "for that difference, so conversions are wrong by orders of magnitude."
        ),
        "objectives": [
            "Price a NGN→USDC conversion on the lab endpoint and compare with the correct amount.",
            "Explain why conversions must normalise to major units (or scale explicitly).",
        ],
        "vulnerable": "POST /api/lab/decimal-quote",
        "hardened": "POST /api/quotes",
        "root_cause": "Arithmetic on minor units ignores the source/target decimal-place difference.",
        "remediation": "Normalise to major units before applying the rate, then scale to the target's decimals.",
        "mode": "both",
        "regression_test": "tests/test_conversion_variants.py::test_naive_decimal_handling_diverges_from_correct",
    },
    {
        "id": "RAMP-016",
        "title": "Fee rounding and precision exploitation",
        "level": "Advanced",
        "category": "Business logic · rounding",
        "component": "Fee engine",
        "business_context": (
            "The fee is truncated to whole minor units, so a sufficiently small "
            "conversion pays zero fee. Splitting a large conversion into dust lets a "
            "user avoid fees entirely."
        ),
        "objectives": [
            "Preview the fee for a dust amount and observe it round to zero.",
            "Show that many dust conversions pay no aggregate fee under truncation.",
            "Explain how a minimum-fee policy defeats the split.",
        ],
        "vulnerable": "POST /api/fee-preview (truncated policy)",
        "hardened": "POST /api/fee-preview (minimum-fee policy)",
        "root_cause": "Fee truncation lets sub-threshold conversions round down to a zero fee.",
        "remediation": "Charge a minimum fee for any positive-value conversion and round fees in the house's favour.",
        "mode": "both",
        "regression_test": "tests/test_conversion_variants.py::test_split_conversions_avoid_fees_under_truncation_only",
    },
    {
        "id": "RAMP-017",
        "title": "Stale exchange-rate exploitation",
        "level": "Advanced",
        "category": "Business logic · quote lifecycle",
        "component": "Exchange engine · quotes",
        "business_context": (
            "Quotes carry an expiry so a locked rate cannot be used indefinitely. The "
            "lab conversion endpoint skips the expiry check, so a customer can settle "
            "an expired quote at a now-favourable, stale rate."
        ),
        "objectives": [
            "Execute an expired quote on the lab endpoint and watch it settle.",
            "Confirm the hardened endpoint rejects the same expired quote.",
        ],
        "vulnerable": "POST /api/lab/conversions",
        "hardened": "POST /api/conversions",
        "root_cause": "The settlement path does not re-validate the quote's expiry before executing.",
        "remediation": "Enforce quote expiry at settlement; re-price if the lock has elapsed.",
        "mode": "both",
        "regression_test": "tests/test_conversion_variants.py::test_lab_conversion_executes_expired_quote_hardened_rejects",
    },
    {
        "id": "RAMP-012",
        "title": "Price oracle manipulation",
        "level": "Advanced",
        "category": "Smart contract · oracle integrity",
        "component": "MockPriceOracle / PriceConsumer",
        "business_context": (
            "A consumer values conversions using a price oracle. The vulnerable "
            "oracle lets any account set the price and offers no freshness check, so "
            "an attacker can reprice a conversion at will."
        ),
        "objectives": [
            "Move the vulnerable oracle's price from an unrelated account and watch a quote reprice.",
            "Explain why the secure oracle's writer authorisation and staleness check defeat it.",
        ],
        "vulnerable": "contracts/src/VulnerablePriceOracle.sol",
        "hardened": "contracts/src/SecurePriceOracle.sol",
        "root_cause": (
            "Price can be written by anyone and is read without a freshness guarantee, "
            "so the value a consumer computes is attacker-controlled."
        ),
        "remediation": (
            "Restrict writes to an authorised updater, reject zero prices, and revert "
            "reads once the price is stale; production systems add multiple sources "
            "and bounded deviation."
        ),
        "mode": "both",
        "regression_test": "contracts/test/PriceOracle.t.sol",
    },
    {
        "id": "RAMP-013",
        "title": "Insecure proxy upgrade",
        "level": "Advanced",
        "category": "Smart contract · upgradeability",
        "component": "VulnerableProxy / SecureProxy",
        "business_context": (
            "The platform logic sits behind an upgradeable proxy. The vulnerable "
            "proxy's upgrade entrypoint has no access control, so any account can "
            "replace the implementation and take over all behaviour."
        ),
        "objectives": [
            "Upgrade the vulnerable proxy from an unrelated account and confirm the logic changed.",
            "Explain why the secure proxy's admin check prevents the takeover.",
        ],
        "vulnerable": "contracts/src/VulnerableProxy.sol",
        "hardened": "contracts/src/SecureProxy.sol",
        "root_cause": "The upgrade function performs no authorization on the caller.",
        "remediation": (
            "Restrict upgrades to an admin role, separate admin calls from user calls "
            "(transparent/UUPS patterns), and guard initialisation against hijack."
        ),
        "mode": "both",
        "regression_test": "contracts/test/ProxyUpgrade.t.sol",
    },
    {
        "id": "RAMP-010",
        "title": "On-chain / off-chain reconciliation gap",
        "level": "Expert",
        "category": "Multi-stage · ledger vs. events",
        "component": "Payment provider → ledger → reconciliation",
        "business_context": (
            "A fiat deposit confirmation drives an internal credit. Because the callback "
            "is replayable, the internal ledger can hold value that no single settled "
            "event backs — visible only when the delivery log is reconciled against credits."
        ),
        "objectives": [
            "Trace a deposit from callback to ledger credit.",
            "Explain why a balanced double-entry ledger alone does not prove backing.",
            "Use /api/ledger/reconciliation to detect value created by a replay.",
        ],
        "vulnerable": "POST /api/lab/webhooks/deposit + GET /api/ledger/reconciliation",
        "hardened": "POST /api/webhooks/deposit",
        "root_cause": (
            "Internal consistency (debits equal credits) is conflated with external "
            "backing (each credit maps to exactly one settled, authentic event)."
        ),
        "remediation": (
            "Reconcile internal credits against the authenticated event log; make "
            "callbacks idempotent so one event can back at most one credit."
        ),
        "mode": "independent",
        "regression_test": "tests/test_api.py::test_replayed_deposit_keeps_ledger_balanced_but_fails_reconciliation",
    },
]

_BY_ID = {c["id"]: c for c in CHALLENGES}


def catalogue() -> list[dict]:
    return CHALLENGES


def summary() -> list[dict]:
    keys = ("id", "title", "level", "category", "component", "vulnerable", "hardened")
    return [{k: c[k] for k in keys} for c in CHALLENGES]


def by_id(challenge_id: str) -> dict | None:
    return _BY_ID.get(challenge_id)
