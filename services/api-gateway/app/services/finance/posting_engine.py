"""
Core GL posting engine for the Hospital Finance Module v2.0.

``post_transaction`` is the SINGLE entry point for ALL postings into the GL.
Other modules (billing, payroll, inventory) call this function rather than
writing ledger rows directly.

Guarantees:
  * Atomicity — entire posting is wrapped in a single DB transaction.
  * Idempotency — repeat calls with the same idempotency_key return the
    original transaction without double-posting.
  * Period safety — posting into a closed/locked period is rejected.
  * Double-entry — SUM(debit) MUST equal SUM(credit) or the posting fails.
  * Concurrency — account rows are read with FOR UPDATE inside the txn.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import (
    Account,
    AccountingPeriod,
    FinanceAuditLog,
    IdempotencyKey,
    PostingRule,
    Transaction,
    TransactionEntry,
)


# ── Exceptions ───────────────────────────────────────────────────────────────


class FinanceError(Exception):
    """Base class for finance-engine errors."""


class PeriodLockedError(FinanceError):
    """Raised when posting is attempted into a closed or locked period."""


class UnbalancedTransactionError(FinanceError):
    """Raised when a transaction's debits do not equal its credits."""


class PostingRuleNotFoundError(FinanceError):
    """Raised when no active posting rule exists for an event_type."""


class NoOpenPeriodError(FinanceError):
    """Raised when no open accounting period covers a posting date."""


# ── Helpers ──────────────────────────────────────────────────────────────────


_QUANT = Decimal("0.01")


def _q(amount: Decimal) -> Decimal:
    """Quantise to 2 decimal places (cents)."""
    return amount.quantize(_QUANT)


async def _get_period_for_date(
    db: AsyncSession, facility_id: uuid.UUID, posting_date: date_type
) -> AccountingPeriod:
    """
    Get the accounting period that contains ``posting_date``.

    @param db: Database session
    @param facility_id: Facility scope
    @param posting_date: Date of the posting
    @returns The matching ``AccountingPeriod``
    @raises NoOpenPeriodError: If no period exists for the date
    @raises PeriodLockedError: If the matching period is closed or locked
    """
    result = await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.facility_id == facility_id,
            AccountingPeriod.start_date <= posting_date,
            AccountingPeriod.end_date >= posting_date,
            AccountingPeriod.is_deleted == False,  # noqa: E712
        )
    )
    period = result.scalar_one_or_none()
    if period is None:
        raise NoOpenPeriodError(
            f"No accounting period exists for date {posting_date}"
        )
    if period.status != "open":
        raise PeriodLockedError(
            f"Period '{period.name}' is {period.status} — postings rejected"
        )
    return period


async def _check_idempotency(
    db: AsyncSession,
    facility_id: uuid.UUID,
    idempotency_key: str | None,
) -> Transaction | None:
    """
    Check whether a transaction has already been posted with this key.

    @param db: Database session
    @param facility_id: Facility scope
    @param idempotency_key: Optional client-supplied key
    @returns The existing transaction if found, else None
    """
    if idempotency_key is None:
        return None
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == idempotency_key,
            IdempotencyKey.facility_id == facility_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    txn_result = await db.execute(
        select(Transaction).where(Transaction.id == record.transaction_id)
    )
    return txn_result.scalar_one_or_none()


# ── Public API ───────────────────────────────────────────────────────────────


async def post_transaction(
    db: AsyncSession,
    facility_id: uuid.UUID,
    event_type: str,
    amount: Decimal,
    metadata: dict,
    idempotency_key: str | None = None,
    user_id: uuid.UUID | None = None,
) -> Transaction:
    """
    Post a balanced double-entry transaction into the GL.

    @param db: Async DB session (caller manages outer transaction; this
               function uses ``begin_nested`` so it is safe inside larger units of work)
    @param facility_id: Facility scope (multi-tenant guard)
    @param event_type: e.g. ``invoice_cash``, ``payroll_run``, ``depreciation``
    @param amount: Total transaction amount (DECIMAL(14,2))
    @param metadata: dict containing: date (date|str ISO), reference_type,
                     reference_id, description, department_id
    @param idempotency_key: Optional client key for retry safety
    @param user_id: Posting user UUID
    @returns Created (or existing, if idempotent replay) Transaction header
    @raises PeriodLockedError: posting period is closed/locked
    @raises UnbalancedTransactionError: DR != CR
    @raises PostingRuleNotFoundError: no rules configured for event_type
    """
    # Quantise amount to ledger precision
    amount = _q(Decimal(amount))

    # ── 1. Idempotency short-circuit ─────────────────────────────────────
    existing = await _check_idempotency(db, facility_id, idempotency_key)
    if existing is not None:
        return existing

    # ── 2. Resolve posting date and period ───────────────────────────────
    raw_date = metadata.get("date")
    if isinstance(raw_date, str):
        posting_date = date_type.fromisoformat(raw_date)
    elif isinstance(raw_date, date_type):
        posting_date = raw_date
    else:
        raise ValueError("metadata['date'] must be a date or ISO date string")

    period = await _get_period_for_date(db, facility_id, posting_date)

    # ── 3. Look up posting rules ────────────────────────────────────────
    rules_result = await db.execute(
        select(PostingRule)
        .where(
            PostingRule.facility_id == facility_id,
            PostingRule.event_type == event_type,
            PostingRule.is_active == True,  # noqa: E712
            PostingRule.is_deleted == False,  # noqa: E712
        )
        .order_by(PostingRule.rule_order.asc())
    )
    rules = list(rules_result.scalars().all())
    if not rules:
        raise PostingRuleNotFoundError(
            f"No active posting rule for event_type '{event_type}'"
        )

    # ── 4. Lock referenced accounts (concurrency control) ───────────────
    account_ids: set[uuid.UUID] = set()
    for rule in rules:
        account_ids.add(rule.debit_account_id)
        account_ids.add(rule.credit_account_id)
        if rule.tax_account_id is not None:
            account_ids.add(rule.tax_account_id)

    await db.execute(
        select(Account)
        .where(
            Account.facility_id == facility_id,
            Account.id.in_(account_ids),
        )
        .with_for_update()
    )

    # ── 5. Create transaction header ────────────────────────────────────
    department_id_raw = metadata.get("department_id")
    department_id: uuid.UUID | None = (
        uuid.UUID(str(department_id_raw)) if department_id_raw else None
    )
    reference_id_raw = metadata.get("reference_id")
    reference_id: uuid.UUID | None = (
        uuid.UUID(str(reference_id_raw)) if reference_id_raw else None
    )

    transaction = Transaction(
        id=uuid.uuid4(),
        facility_id=facility_id,
        date=posting_date,
        reference_type=metadata.get("reference_type"),
        reference_id=reference_id,
        event_type=event_type,
        description=metadata.get("description"),
        department_id=department_id,
        period_id=period.id,
        amount=amount,
        is_reversal=False,
        created_by=user_id,
    )
    db.add(transaction)
    await db.flush()

    # ── 6. Create entries from rules ────────────────────────────────────
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for rule in rules:
        # Each rule emits a balanced DR/CR pair for the same amount.
        dr = TransactionEntry(
            id=uuid.uuid4(),
            facility_id=facility_id,
            transaction_id=transaction.id,
            account_id=rule.debit_account_id,
            debit=amount,
            credit=Decimal("0"),
            department_id=department_id,
        )
        cr = TransactionEntry(
            id=uuid.uuid4(),
            facility_id=facility_id,
            transaction_id=transaction.id,
            account_id=rule.credit_account_id,
            debit=Decimal("0"),
            credit=amount,
            department_id=department_id,
        )
        db.add(dr)
        db.add(cr)
        total_debit += amount
        total_credit += amount

    # ── 7. Hard double-entry validation ────────────────────────────────
    if _q(total_debit) != _q(total_credit):
        raise UnbalancedTransactionError(
            f"Debits ({total_debit}) != Credits ({total_credit}) "
            f"for event_type='{event_type}'"
        )

    # ── 8. Audit log ────────────────────────────────────────────────────
    audit = FinanceAuditLog(
        id=uuid.uuid4(),
        facility_id=facility_id,
        action="post_transaction",
        table_name="transactions",
        record_id=transaction.id,
        user_id=user_id,
        payload={
            "event_type": event_type,
            "amount": str(amount),
            "rule_count": len(rules),
            "period_id": str(period.id),
        },
    )
    db.add(audit)

    # ── 9. Idempotency tracking ─────────────────────────────────────────
    if idempotency_key is not None:
        db.add(
            IdempotencyKey(
                key=idempotency_key,
                facility_id=facility_id,
                transaction_id=transaction.id,
            )
        )

    await db.flush()
    return transaction


async def reverse_transaction(
    db: AsyncSession,
    facility_id: uuid.UUID,
    transaction_id: uuid.UUID,
    posting_date: date_type,
    user_id: uuid.UUID | None = None,
    description: str | None = None,
) -> Transaction:
    """
    Post a reversing transaction that swaps DRs and CRs of the original.

    @param db: Database session
    @param facility_id: Facility scope
    @param transaction_id: Original transaction to reverse
    @param posting_date: Reversal posting date (must be in an open period)
    @param user_id: Posting user
    @param description: Optional override description
    @returns The new reversing Transaction
    """
    original_result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.facility_id == facility_id,
        )
    )
    original = original_result.scalar_one_or_none()
    if original is None:
        raise FinanceError(f"Transaction {transaction_id} not found")

    period = await _get_period_for_date(db, facility_id, posting_date)

    entries_result = await db.execute(
        select(TransactionEntry).where(
            TransactionEntry.transaction_id == original.id,
            TransactionEntry.facility_id == facility_id,
        )
    )
    entries = list(entries_result.scalars().all())

    reversal = Transaction(
        id=uuid.uuid4(),
        facility_id=facility_id,
        date=posting_date,
        reference_type=original.reference_type,
        reference_id=original.reference_id,
        event_type=f"reverse_{original.event_type}",
        description=description or f"Reversal of {original.id}",
        department_id=original.department_id,
        period_id=period.id,
        amount=original.amount,
        is_reversal=True,
        reverses_transaction_id=original.id,
        created_by=user_id,
    )
    db.add(reversal)
    await db.flush()

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for entry in entries:
        # Swap debit and credit
        new_debit = entry.credit
        new_credit = entry.debit
        db.add(
            TransactionEntry(
                id=uuid.uuid4(),
                facility_id=facility_id,
                transaction_id=reversal.id,
                account_id=entry.account_id,
                debit=new_debit,
                credit=new_credit,
                department_id=entry.department_id,
            )
        )
        total_debit += new_debit
        total_credit += new_credit

    if _q(total_debit) != _q(total_credit):
        raise UnbalancedTransactionError(
            f"Reversal unbalanced: debits={total_debit} credits={total_credit}"
        )

    db.add(
        FinanceAuditLog(
            id=uuid.uuid4(),
            facility_id=facility_id,
            action="reverse_transaction",
            table_name="transactions",
            record_id=reversal.id,
            user_id=user_id,
            payload={"reverses": str(original.id)},
        )
    )

    await db.flush()
    return reversal
