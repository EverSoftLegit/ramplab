"""Race-condition regression tests for the financial core.

These prove the secure conversion path serialises concurrent execution of the
same quote, so a race cannot double-spend — the ledger invariant must still
hold afterwards.
"""
import threading
import pytest

from app import db
from app.domain import DomainError, create_quote, execute_conversion
from app.ledger import verify_ledger_integrity


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-conc.sqlite3")
    db.initialize_database()
    yield


def test_concurrent_execution_of_same_quote_is_single_spend(seeded):
    quote = create_quote("alice", "NGN", "USDC", "100000.00")
    results, errors = [], []

    def run():
        try:
            results.append(execute_conversion("alice", quote["quote_id"]))
        except DomainError as e:
            errors.append(e.status_code)

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one conversion may succeed; the rest must be rejected (409).
    assert len(results) == 1, (results, errors)
    assert all(code == 409 for code in errors)
    # And the double-entry ledger must still be perfectly balanced.
    assert verify_ledger_integrity()["healthy"] is True


def test_concurrent_distinct_quotes_cannot_overdraw_balance(seeded):
    # Alice holds 50,000,000 NGN minor units (500,000.00). Fire several large
    # conversions concurrently; the total debited must never exceed the balance.
    start = db.account_for("alice", "NGN")["balance_minor"]
    quotes = [create_quote("alice", "NGN", "USDC", "200000.00")["quote_id"] for _ in range(4)]
    ok, rejected = [], []

    def run(qid):
        try:
            execute_conversion("alice", qid)
            ok.append(qid)
        except DomainError:
            rejected.append(qid)

    threads = [threading.Thread(target=run, args=(q,)) for q in quotes]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    end = db.account_for("alice", "NGN")["balance_minor"]
    assert end >= 0
    assert start - end == len(ok) * 20_000_000  # 200,000.00 NGN each
    assert verify_ledger_integrity()["healthy"] is True


def test_vulnerable_withdraw_double_spends_under_concurrency(seeded):
    from app.domain import withdraw_vulnerable
    # Alice holds 500,000.00 NGN. Two concurrent 300,000.00 withdrawals: only one
    # should be possible, but the non-atomic path lets both through.
    results = []

    def run():
        try:
            withdraw_vulnerable("alice", "NGN", "300000.00")
            results.append("ok")
        except DomainError:
            results.append("rejected")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Both succeeded — the double-spend is reproduced.
    assert results.count("ok") == 2


def test_secure_withdraw_prevents_double_spend(seeded):
    from app.domain import withdraw_secure
    results = []

    def run():
        try:
            withdraw_secure("alice", "NGN", "300000.00")
            results.append("ok")
        except DomainError:
            results.append("rejected")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Exactly one may succeed; the balance never goes negative.
    assert results.count("ok") == 1 and results.count("rejected") == 1
    assert db.account_for("alice", "NGN")["balance_minor"] >= 0
