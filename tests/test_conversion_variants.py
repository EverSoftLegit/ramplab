"""Reproduce + prevent tests for RAMP-015 (decimal handling), RAMP-016 (fee
rounding) and RAMP-017 (stale/expired quote)."""
from decimal import Decimal

import pytest

from app import db
from app.config import CURRENCY_SCALE
from app.domain import (
    DomainError, calculate_target, calculate_target_naive, create_quote, demo_rate,
    execute_conversion, fee_minor_secure, fee_minor_vulnerable, parse_amount,
)


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ramplab-cv.sqlite3")
    db.initialize_database()
    yield


def test_naive_decimal_handling_diverges_from_correct():
    # NGN has 2 decimals, USDC has 6: a scale gap of 10**4.
    src, tgt = "NGN", "USDC"
    rate = demo_rate(src, tgt)
    source_minor = parse_amount("100000.00", src)
    naive, _ = calculate_target_naive(source_minor, src, tgt, rate)
    correct, _ = calculate_target(source_minor, src, tgt, rate)
    scale_gap = 10 ** (CURRENCY_SCALE[tgt] - CURRENCY_SCALE[src])  # 10**4
    assert correct > 0 and naive >= 0
    # The naive result is off by roughly the decimal-place factor.
    assert abs(correct - naive * scale_gap) <= scale_gap  # naive is ~1/10**4 of correct
    assert naive != correct


def test_truncating_fee_rounds_to_zero_for_dust_but_minimum_does_not():
    src, tgt = "NGN", "USDC"
    rate = demo_rate(src, tgt)
    dust = parse_amount("0.10", src)  # a tiny conversion
    vuln = fee_minor_vulnerable(dust, src, tgt, rate)
    secure = fee_minor_secure(dust, src, tgt, rate)
    assert vuln == 0            # truncated fee rounds to zero
    assert secure >= 1          # minimum-fee policy still charges


def test_split_conversions_avoid_fees_under_truncation_only():
    src, tgt = "NGN", "USDC"
    rate = demo_rate(src, tgt)
    dust = parse_amount("0.10", src)
    n = 50
    total_vuln = sum(fee_minor_vulnerable(dust, src, tgt, rate) for _ in range(n))
    total_secure = sum(fee_minor_secure(dust, src, tgt, rate) for _ in range(n))
    assert total_vuln == 0        # splitting avoids all fees
    assert total_secure >= n      # minimum fee defeats the split


def test_lab_conversion_executes_expired_quote_hardened_rejects(seeded):
    quote = create_quote("alice", "NGN", "USDC", "1000.00")
    # Force the quote to be expired.
    with db.connect() as conn:
        conn.execute("UPDATE quotes SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",
                     (quote["quote_id"],))
    # Hardened path rejects the stale quote.
    with pytest.raises(DomainError) as exc:
        execute_conversion("alice", quote["quote_id"], allow_expired=False)
    assert exc.value.status_code == 409
    # Re-open it (the hardened call marked it expired) and show the lab path runs it.
    with db.connect() as conn:
        conn.execute("UPDATE quotes SET status='open' WHERE id=?", (quote["quote_id"],))
    result = execute_conversion("alice", quote["quote_id"], allow_expired=True)
    assert result["status"] == "completed"
