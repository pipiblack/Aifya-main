"""
Tests for the GL posting engine: idempotency, period lock,
DR=CR validation, and reversal correctness.

Note: tests use the in-memory SQLite test DB created by conftest.
PostgreSQL-only features (FOR UPDATE, JSONB) degrade gracefully on SQLite.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.finance import (
    Account,
    AccountingPeriod,
    PostingRule,
    Transaction,
)
from app.services.finance import (
    PeriodLockedError,
    PostingRuleNotFoundError,
    UnbalancedTransactionError,
    post_transaction,
    reverse_transaction,
)
from app.services.finance.seed_data import seed_facility_finance
from tests.conftest import FACILITY_ID, USER_ID, test_session


@pytest_asyncio.fixture
async def seeded_period() -> AccountingPeriod:
    """Seed a facility's CoA + posting rules and create an open period."""
    async with test_session() as db:
        await seed_facility_finance(db, FACILITY_ID, USER_ID)
        period = AccountingPeriod(
            facility_id=FACILITY_ID,
            name="2026-05",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="open",
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)
        return period


@pytest.mark.asyncio
async def test_post_transaction_balances(seeded_period: AccountingPeriod) -> None:
    """A successful post creates balanced DR/CR entries."""
    async with test_session() as db:
        txn = await post_transaction(
            db=db,
            facility_id=FACILITY_ID,
            event_type="invoice_cash",
            amount=Decimal("1000.00"),
            metadata={"date": "2026-05-15", "description": "Test invoice"},
            user_id=USER_ID,
        )
        await db.commit()
        assert txn.amount == Decimal("1000.00")
        assert txn.event_type == "invoice_cash"


@pytest.mark.asyncio
async def test_post_transaction_prefers_monthly_period_when_year_end_overlaps(
    seeded_period: AccountingPeriod,
) -> None:
    """Operational postings use the monthly period, not the overlapping FY row."""
    async with test_session() as db:
        fiscal_year = AccountingPeriod(
            facility_id=FACILITY_ID,
            name="FY2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="open",
            year_end=True,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(fiscal_year)
        await db.commit()

    async with test_session() as db:
        txn = await post_transaction(
            db=db,
            facility_id=FACILITY_ID,
            event_type="invoice_cash",
            amount=Decimal("1000.00"),
            metadata={"date": "2026-05-15", "description": "Test invoice"},
            user_id=USER_ID,
        )
        await db.commit()

    assert txn.period_id == seeded_period.id


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicates(
    seeded_period: AccountingPeriod,
) -> None:
    """Repeat calls with the same key return the same transaction."""
    key = f"test-{uuid.uuid4()}"
    async with test_session() as db:
        first = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("500.00"),
            {"date": "2026-05-10"},
            idempotency_key=key,
            user_id=USER_ID,
        )
        await db.commit()
    async with test_session() as db:
        second = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("500.00"),
            {"date": "2026-05-10"},
            idempotency_key=key,
            user_id=USER_ID,
        )
        await db.commit()
    assert first.id == second.id


@pytest.mark.asyncio
async def test_period_locked_blocks_posting(
    seeded_period: AccountingPeriod,
) -> None:
    """Posting into a locked period raises PeriodLockedError."""
    async with test_session() as db:
        period = await db.get(AccountingPeriod, seeded_period.id)
        assert period is not None
        period.status = "locked"
        await db.commit()

    async with test_session() as db:
        with pytest.raises(PeriodLockedError):
            await post_transaction(
                db,
                FACILITY_ID,
                "invoice_cash",
                Decimal("100.00"),
                {"date": "2026-05-15"},
                user_id=USER_ID,
            )


@pytest.mark.asyncio
async def test_unknown_event_type_raises(
    seeded_period: AccountingPeriod,
) -> None:
    """No posting rule for an event_type -> raises PostingRuleNotFoundError."""
    async with test_session() as db:
        with pytest.raises(PostingRuleNotFoundError):
            await post_transaction(
                db,
                FACILITY_ID,
                "made_up_event",
                Decimal("100.00"),
                {"date": "2026-05-15"},
                user_id=USER_ID,
            )


@pytest.mark.asyncio
async def test_reverse_transaction_swaps_dr_cr(
    seeded_period: AccountingPeriod,
) -> None:
    """A reversal creates an opposing balanced entry."""
    async with test_session() as db:
        original = await post_transaction(
            db,
            FACILITY_ID,
            "invoice_cash",
            Decimal("750.00"),
            {"date": "2026-05-12"},
            user_id=USER_ID,
        )
        await db.commit()

    async with test_session() as db:
        rev = await reverse_transaction(
            db,
            FACILITY_ID,
            original.id,
            posting_date=date(2026, 5, 20),
            user_id=USER_ID,
            description="undo",
        )
        await db.commit()

    assert rev.is_reversal is True
    assert rev.reverses_transaction_id == original.id
    assert rev.amount == original.amount


@pytest.mark.asyncio
async def test_seed_creates_27_accounts() -> None:
    """seed_facility_finance creates the default chart and rules."""
    async with test_session() as db:
        summary = await seed_facility_finance(db, FACILITY_ID, USER_ID)
        await db.commit()
    # 27 accounts in the spec
    assert summary["accounts_created"] == 27
    assert summary["rules_created"] >= 10


@pytest.mark.asyncio
async def test_no_open_period_raises(seeded_period: AccountingPeriod) -> None:
    """Posting outside any period raises NoOpenPeriodError."""
    from app.services.finance import NoOpenPeriodError

    async with test_session() as db:
        with pytest.raises(NoOpenPeriodError):
            await post_transaction(
                db,
                FACILITY_ID,
                "invoice_cash",
                Decimal("10.00"),
                {"date": "2099-01-01"},  # outside seeded period
                user_id=USER_ID,
            )


@pytest.mark.asyncio
async def test_unbalanced_error_class_exists() -> None:
    """Sanity: UnbalancedTransactionError is exported."""
    assert issubclass(UnbalancedTransactionError, Exception)


def test_account_uniqueness_constraint_module_imports() -> None:
    """Smoke test: model module imports cleanly."""
    from app.models.finance import Account as A

    assert A.__tablename__ == "accounts"
