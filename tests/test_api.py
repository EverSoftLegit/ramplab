import hashlib
import hmac
import json

from app.config import WEBHOOK_SECRET


def get_account(client, user, currency):
    response = client.get("/api/accounts", headers={"X-Demo-User": user})
    assert response.status_code == 200
    return next(a for a in response.json()["accounts"] if a["currency"] == currency)


def test_health_and_supported_currencies(client):
    assert client.get("/api/health").json()["status"] == "ok"
    codes = {item["code"] for item in client.get("/api/markets").json()["currencies"]}
    assert codes == {"NGN", "GHS", "KES", "ZAR", "USD", "EUR", "GBP", "USDC"}


def test_user_can_convert_fiat_to_usdc_and_ledger_is_written(client):
    before_ngn = get_account(client, "alice", "NGN")["balance_minor"]
    before_usdc = get_account(client, "alice", "USDC")["balance_minor"]
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1000.00"
    })
    assert quote.status_code == 200, quote.text
    data = quote.json()
    result = client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": data["quote_id"]})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "completed"
    after_ngn = get_account(client, "alice", "NGN")["balance_minor"]
    after_usdc = get_account(client, "alice", "USDC")["balance_minor"]
    assert before_ngn - after_ngn == 100_000
    assert after_usdc - before_usdc == int(float(data["target_amount"]) * 1_000_000)
    txs = client.get("/api/transactions", headers={"X-Demo-User": "alice"}).json()["transactions"]
    assert txs[0]["reference"] == result.json()["reference"]
    ledger = client.get(f"/api/transactions/{result.json()['transaction_id']}/ledger", headers={"X-Demo-User": "alice"})
    assert ledger.status_code == 200
    assert len(ledger.json()["entries"]) == 4
    assert sum(row["amount_minor"] for row in ledger.json()["entries"] if row["currency"] == "NGN") == 0
    assert sum(row["amount_minor"] for row in ledger.json()["entries"] if row["currency"] == "USDC") == 0


def test_quote_is_one_time_only(client):
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "USDC", "target_currency": "NGN", "amount": "10.000000"
    }).json()
    first = client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": quote["quote_id"]})
    second = client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": quote["quote_id"]})
    assert first.status_code == 200
    assert second.status_code == 409


def test_bola_lab_and_hardened_account_read(client):
    bob_account = get_account(client, "bob", "NGN")
    vulnerable = client.get(f"/api/lab/accounts/{bob_account['id']}", headers={"X-Demo-User": "alice"})
    hardened = client.get(f"/api/accounts/{bob_account['id']}", headers={"X-Demo-User": "alice"})
    assert vulnerable.status_code == 200
    assert vulnerable.json()["account"]["owner"] == "bob"
    assert hardened.status_code == 403


def test_lab_quote_accepts_client_controlled_rate(client):
    normal = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1000.00"
    }).json()
    vulnerable = client.post("/api/lab/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1000.00", "rate_override": "1"
    })
    assert vulnerable.status_code == 200
    assert float(vulnerable.json()["target_amount"]) > float(normal["target_amount"]) * 100


def test_unsigned_lab_webhook_can_be_replayed(client):
    account = get_account(client, "alice", "NGN")
    start = account["balance_minor"]
    payload = {"owner": "alice", "account_id": account["id"], "amount": "100.00", "event_id": "evt-replay-lab"}
    first = client.post("/api/lab/webhooks/deposit", json=payload)
    second = client.post("/api/lab/webhooks/deposit", json=payload)
    assert first.status_code == second.status_code == 200
    end = get_account(client, "alice", "NGN")["balance_minor"]
    assert end - start == 20_000


def test_hardened_webhook_rejects_bad_signature_and_deduplicates(client):
    account = get_account(client, "alice", "NGN")
    start = account["balance_minor"]
    payload = {"owner": "alice", "account_id": account["id"], "amount": "100.00", "event_id": "evt-secure-1"}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    bad = client.post("/api/webhooks/deposit", content=raw, headers={"Content-Type": "application/json", "X-Ramp-Signature": "bad"})
    assert bad.status_code == 401
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Ramp-Signature": f"sha256={signature}"}
    first = client.post("/api/webhooks/deposit", content=raw, headers=headers)
    second = client.post("/api/webhooks/deposit", content=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "credited"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_ignored"
    end = get_account(client, "alice", "NGN")["balance_minor"]
    assert end - start == 10_000


def test_decimal_precision_is_enforced(client):
    response = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1.001"
    })
    assert response.status_code == 400


def test_dashboard_and_challenge_catalogue_are_available(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "RampLab" in page.text
    challenges = client.get("/api/challenges").json()["challenges"]
    ids = {item["id"] for item in challenges}
    assert {"RAMP-001", "RAMP-002", "RAMP-003", "RAMP-004", "RAMP-005"} <= ids
    detail = client.get("/api/challenges/RAMP-003").json()
    assert detail["category"] and detail["root_cause"] and detail["remediation"]
    assert client.get("/api/challenges/RAMP-999").status_code == 404


def test_user_can_convert_usdc_back_to_fiat(client):
    before_usdc = get_account(client, "bob", "USDC")["balance_minor"]
    before_ngn = get_account(client, "bob", "NGN")["balance_minor"]
    quote = client.post("/api/quotes", headers={"X-Demo-User": "bob"}, json={
        "source_currency": "USDC", "target_currency": "NGN", "amount": "10.000000"
    })
    assert quote.status_code == 200, quote.text
    quote_data = quote.json()
    result = client.post("/api/conversions", headers={"X-Demo-User": "bob"}, json={"quote_id": quote_data["quote_id"]})
    assert result.status_code == 200, result.text
    assert before_usdc - get_account(client, "bob", "USDC")["balance_minor"] == 10_000_000
    assert get_account(client, "bob", "NGN")["balance_minor"] - before_ngn == int(float(quote_data["target_amount"]) * 100)


def test_conversion_quote_cannot_be_executed_by_another_demo_identity(client):
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "100.00"
    }).json()
    response = client.post("/api/conversions", headers={"X-Demo-User": "bob"}, json={"quote_id": quote["quote_id"]})
    assert response.status_code == 404


def test_ledger_integrity_holds_at_seed_and_after_conversion(client):
    assert client.get("/api/ledger/integrity").json()["healthy"] is True
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1000.00"
    }).json()
    client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": quote["quote_id"]})
    report = client.get("/api/ledger/integrity").json()
    assert report["healthy"] is True
    assert report["zero_sum_violations"] == []
    assert report["projection_violations"] == []


def test_replayed_deposit_keeps_ledger_balanced_but_fails_reconciliation(client):
    # The vulnerable callback credits the same event twice. Each credit is a
    # balanced double-entry posting, so the ledger invariant still holds...
    account = get_account(client, "alice", "NGN")
    payload = {"owner": "alice", "account_id": account["id"], "amount": "100.00", "event_id": "evt-recon-replay"}
    client.post("/api/lab/webhooks/deposit", json=payload)
    client.post("/api/lab/webhooks/deposit", json=payload)
    assert client.get("/api/ledger/integrity").json()["healthy"] is True
    # ...but reconciliation against the callback log catches the double credit.
    recon = client.get("/api/ledger/reconciliation").json()
    assert recon["reconciled"] is False
    flagged = recon["double_credited_events"]
    assert any(e["event_id"] == "evt-recon-replay" and e["times_credited"] == 2 for e in flagged)


def test_hardened_webhook_leaves_reconciliation_clean(client):
    account = get_account(client, "alice", "NGN")
    payload = {"owner": "alice", "account_id": account["id"], "amount": "100.00", "event_id": "evt-recon-clean"}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Ramp-Signature": f"sha256={signature}"}
    client.post("/api/webhooks/deposit", content=raw, headers=headers)
    client.post("/api/webhooks/deposit", content=raw, headers=headers)
    recon = client.get("/api/ledger/reconciliation").json()
    assert recon["reconciled"] is True
    assert recon["double_credited_events"] == []


def test_quote_can_be_cancelled_and_not_executed(client):
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "100.00"
    }).json()
    cancelled = client.post(f"/api/quotes/{quote['quote_id']}/cancel", headers={"X-Demo-User": "alice"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    blocked = client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": quote["quote_id"]})
    assert blocked.status_code == 409
    again = client.post(f"/api/quotes/{quote['quote_id']}/cancel", headers={"X-Demo-User": "alice"})
    assert again.status_code == 409


def test_admin_overview_requires_elevated_role(client):
    denied = client.get("/api/admin/overview", headers={"X-Demo-User": "alice"})
    assert denied.status_code == 403
    ok = client.get("/api/admin/overview", headers={"X-Demo-User": "admin"})
    assert ok.status_code == 200
    assert "accounts_by_owner" in ok.json()


def test_observability_summary_uses_real_data(client):
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "500.00"
    }).json()
    client.post("/api/conversions", headers={"X-Demo-User": "alice"}, json={"quote_id": quote["quote_id"]})
    summary = client.get("/api/observability/summary").json()
    assert summary["transactions_by_kind"].get("conversion", 0) >= 1
    assert summary["ledger_healthy"] is True
    assert summary["challenge_count"] >= 5


def test_mass_assignment_lab_allows_privilege_escalation(client):
    # Baseline: alice is a basic customer.
    before = client.get("/api/profile", headers={"X-Demo-User": "alice"}).json()
    assert before["role"] == "customer" and before["kyc_level"] == "basic"
    # Vulnerable endpoint binds privileged fields from the body (mass assignment).
    r = client.post("/api/lab/profile", headers={"X-Demo-User": "alice"},
                    json={"display_name": "Alice A", "role": "admin", "kyc_level": "verified", "status": "privileged"})
    assert r.status_code == 200
    after = r.json()
    assert after["role"] == "admin" and after["kyc_level"] == "verified" and after["status"] == "privileged"
    assert after["display_name"] == "Alice A"


def test_hardened_profile_update_ignores_privileged_fields(client):
    r = client.post("/api/profile", headers={"X-Demo-User": "bob"},
                    json={"display_name": "Bob B", "email": "bob2@ramplab.test",
                          "role": "admin", "kyc_level": "verified", "status": "privileged"})
    assert r.status_code == 200
    after = r.json()
    # Self-editable fields applied; privileged fields untouched.
    assert after["display_name"] == "Bob B" and after["email"] == "bob2@ramplab.test"
    assert after["role"] == "customer" and after["kyc_level"] == "basic" and after["status"] == "active"


def test_idor_lab_exposes_other_users_transaction(client):
    # Alice makes a conversion; the resulting transaction is owned by Alice.
    quote = client.post("/api/quotes", headers={"X-Demo-User": "alice"}, json={
        "source_currency": "NGN", "target_currency": "USDC", "amount": "1000.00"}).json()
    conv = client.post("/api/conversions", headers={"X-Demo-User": "alice"},
                       json={"quote_id": quote["quote_id"]}).json()
    tx_id = client.get("/api/transactions", headers={"X-Demo-User": "alice"}).json()["transactions"][0]["id"]
    # Bob reads Alice's transaction through the lab endpoint (IDOR) — succeeds.
    leaked = client.get(f"/api/lab/transactions/{tx_id}", headers={"X-Demo-User": "bob"})
    assert leaked.status_code == 200 and leaked.json()["owner"] == "alice"
    # Hardened endpoint scopes to the caller — Bob gets 404, Alice gets 200.
    assert client.get(f"/api/transactions/{tx_id}", headers={"X-Demo-User": "bob"}).status_code == 404
    assert client.get(f"/api/transactions/{tx_id}", headers={"X-Demo-User": "alice"}).status_code == 200


def test_bfla_lab_admin_listing_has_no_role_check(client):
    # A customer can call the lab admin listing (broken function-level authz).
    leaked = client.get("/api/lab/admin/users", headers={"X-Demo-User": "alice"})
    assert leaked.status_code == 200 and len(leaked.json()["users"]) >= 2
    # The hardened administrative endpoint rejects the same customer.
    assert client.get("/api/admin/overview", headers={"X-Demo-User": "alice"}).status_code == 403


def test_info_disclosure_lab_leaks_secret_health_does_not(client):
    leak = client.get("/api/lab/debug").json()
    # The vulnerable debug endpoint exposes the webhook secret and PII.
    assert leak["webhook_secret"] == WEBHOOK_SECRET
    assert "all_customer_emails" in leak and leak["all_customer_emails"]
    # The sanitized health endpoint exposes neither.
    health = client.get("/api/health").json()
    assert WEBHOOK_SECRET not in str(health)


def test_weak_session_token_is_forgeable(client):
    import base64
    # Forge a token for Bob without logging in as Bob.
    forged = base64.urlsafe_b64encode(b"bob").decode()
    who = client.get("/api/lab/whoami", headers={"X-Session": forged})
    assert who.status_code == 200 and who.json()["owner"] == "bob"


def test_signed_session_token_rejects_forgery(client):
    import base64
    token = client.post("/api/login", json={"owner": "alice"}).json()["token"]
    ok = client.get("/api/whoami", headers={"X-Session": token})
    assert ok.status_code == 200 and ok.json()["owner"] == "alice"
    # A forged/base64 token with no valid HMAC is rejected.
    forged = base64.urlsafe_b64encode(b"bob").decode()
    assert client.get("/api/whoami", headers={"X-Session": forged}).status_code == 401
    assert client.get("/api/whoami", headers={"X-Session": "alice.deadbeef"}).status_code == 401


def test_lab_admin_credit_breaks_ledger_integrity(client):
    assert client.get("/api/ledger/integrity").json()["healthy"] is True
    # Vulnerable credit bumps the balance with no ledger entry.
    r = client.post("/api/lab/admin/credit", headers={"X-Demo-User": "operations"},
                    json={"currency": "NGN", "amount": "1000.00"})
    assert r.status_code == 200
    report = client.get("/api/ledger/integrity").json()
    assert report["healthy"] is False and report["projection_violations"]


def test_hardened_admin_credit_keeps_ledger_balanced(client):
    r = client.post("/api/admin/credit", headers={"X-Demo-User": "operations"},
                    json={"currency": "NGN", "amount": "1000.00"})
    assert r.status_code == 200
    assert client.get("/api/ledger/integrity").json()["healthy"] is True


def test_challenge_catalogue_export_is_markdown(client):
    r = client.get("/api/challenges/export")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    body = r.text
    assert "# RampLab Challenge Catalogue" in body
    assert "RAMP-001" in body and "RAMP-021" in body
    assert "Root cause" in body and "Remediation" in body
    # The /{challenge_id} route must still work and not shadow /export.
    assert client.get("/api/challenges/RAMP-003").json()["id"] == "RAMP-003"
