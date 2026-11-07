import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
import responses
from django.db import close_old_connections
from django.utils import timezone

from apps.exchange.models import ExchangeRate, ExchangeTransaction
from apps.exchange.services import (
    calculate_exchange_fee,
    exchange,
    get_exchange_rate,
    save_exchange_rate,
)
from apps.transactions.models import AuditLog, LedgerEntry, Transaction


@responses.activate
def test_get_exchange_rate_error():
    responses.add(
        responses.GET,
        "https://api.frankfurter.dev/v2/rate/EUR/USD",
        json={
            "amount": 1.0,
            "base": "EUR",
            "date": "2026-08-24",
            "rate": 1.17,
            "quote": "USD",
        },status=200
    )
    rate=get_exchange_rate(
        base_currency="EUR",
        quote_currency="USD"
    )
    assert rate == Decimal("1.17")

@pytest.mark.django_db
@responses.activate
def test_save_exchange_rate():
    responses.add(
        responses.GET,
        "https://api.frankfurter.dev/v2/rate/EUR/USD",
        json={
            "amount": 1.0,
            "base": "EUR",
            "date": "2026-08-24",
            "rate": 1.17,
            "quote": "USD",
        },status=200
    )
    exchange_rate=save_exchange_rate(
        base_currency="EUR",
        quote_currency="USD"
    )

    assert exchange_rate.base_currency == "EUR"
    assert exchange_rate.quote_currency == "USD"
    assert exchange_rate.rate == Decimal("1.17")
    assert exchange_rate.fetched_at is not None

@pytest.mark.parametrize(
    ("base_currency","quote_currency"),
    [
        ("EUR","EUR"),
        ("BTC","USD"),
        ("USD","BTC")
    ],
)
def test_exchange_rate_rejects_unspported_pair_currency(base_currency,quote_currency):
     with pytest.raises(ValueError):
        get_exchange_rate(
            base_currency=base_currency,
            quote_currency=quote_currency,
        )

def test_exchange_fee():
    fee=calculate_exchange_fee(
        converted_amount=Decimal("117")
    )
    assert fee == Decimal("0.2925")

def test_caculate_exchange_fee_zero():
    fee=calculate_exchange_fee(
        converted_amount=Decimal("0")
    )
    assert fee == Decimal("0")

@pytest.mark.django_db
def test_exchange_transaction(wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    exchange_transaction=exchange(
        idempotency_key=uuid.uuid4(),
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100")
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert exchange_transaction.transaction_type == Transaction.TransactionType.EXCHANGE
    assert exchange_transaction.status == Transaction.TransactionStatus.COMPLETED
    assert source_wallet.balance == Decimal("900")
    assert destination_wallet.balance == Decimal("616.7075")
    details=ExchangeTransaction.objects.get(
        transaction=exchange_transaction
    )
    assert details.source_amount == Decimal("100")
    assert details.destination_amount == Decimal("116.7075")
    assert details.fee_amount == Decimal("0.2925")
    assert details.fee_currency == "USD"
    assert LedgerEntry.objects.filter(
        transaction=exchange_transaction,
        entry_type=LedgerEntry.EntryType.DEBIT,
        wallet=source_wallet,
        amount=Decimal("100")
    ).exists()
    assert LedgerEntry.objects.filter(
        transaction=exchange_transaction,
        entry_type=LedgerEntry.EntryType.CREDIT,
        wallet=destination_wallet,
        amount=Decimal("116.7075")
    ).exists()

@pytest.mark.django_db
def test_exchange_transaction_idempotency_key(wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    idempotency_key=uuid.uuid4()
    result_1=exchange(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100")
    )
    result_2=exchange(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100")
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("900")
    assert destination_wallet.balance == Decimal("616.7075") 
    assert result_1.id == result_2.id  # pyright: ignore[reportAttributeAccessIssue]
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert ExchangeTransaction.objects.filter(
    transaction=result_1).count() == 1
    assert AuditLog.objects.filter(
    transaction__idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.django_db
def test_exchange_insufficient_balance(wallets,user,exchange_rate):
    source_wallet, destination_wallet = wallets

    with pytest.raises(ValueError, match="Insufficient wallet balance."):
        exchange(
            idempotency_key=uuid.uuid4(),
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            initiated_by=user,
            amount=Decimal("1000.01"),
        )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("1000")
    assert destination_wallet.balance == Decimal("500")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_exchange_rate_not_available(wallets,user):
    source_wallet,destination_wallet=wallets
    with pytest.raises(ValueError, match="Exchange rate is not available."):
        exchange(
            idempotency_key=uuid.uuid4(),
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            initiated_by=user,
            amount=Decimal("500"),
        )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("1000")
    assert destination_wallet.balance == Decimal("500")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_exchange_atomicity(
    wallets,
    user,
    exchange_rate,
):
    source_wallet, destination_wallet = wallets

    with patch(
        'apps.exchange.services.ExchangeTransaction.objects.create',
        side_effect=ValueError("Database error"),
    ), pytest.raises(ValueError, match="Database error"):
        exchange(
            idempotency_key=uuid.uuid4(),
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            initiated_by=user,
            amount=Decimal("100"),
        )

    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()

    assert source_wallet.balance == Decimal("1000")
    assert destination_wallet.balance == Decimal("500")

    assert Transaction.objects.count() == 0
    assert ExchangeTransaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_exchange_uses_latest_exchange_rates(api_client,wallets,user):
    source_wallet,destination_wallet=wallets
    old_rate=ExchangeRate.objects.create(
        base_currency="EUR",
        quote_currency="USD",
        rate=Decimal("1.17"),
        fetched_at=timezone.now() - timedelta(minutes=10), # pyright: ignore[reportAttributeAccessIssue]
    )
    latest_rate=ExchangeRate.objects.create(
            base_currency="EUR",
            quote_currency="USD",
            rate=Decimal("1.18"),
            fetched_at=timezone.now(), # pyright: ignore[reportAttributeAccessIssue]
        )
    result=exchange(
        idempotency_key=uuid.uuid4(),
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100")
    )
    exchange_details=result.exchange_details # pyright: ignore[reportAttributeAccessIssue]
    assert exchange_details.exchange_rate_id == latest_rate.id # pyright: ignore[reportAttributeAccessIssue]
    assert exchange_details.exchange_rate.id != old_rate.id  # pyright: ignore[reportAttributeAccessIssue]
    assert exchange_details.exchange_rate.rate == Decimal("1.18")
    assert exchange_details.source_amount == Decimal("100")
    assert exchange_details.destination_amount == Decimal("117.70500000")
    assert exchange_details.fee_amount == Decimal("0.29500000")

@pytest.mark.django_db
def test_exchange_creates_correct_ledger_entries(api_client,wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    result=exchange(
        idempotency_key=uuid.uuid4(),
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100")
    )
    entries=LedgerEntry.objects.filter(
        transaction=result
    ).order_by('entry_type')
    assert entries.count() == 2
    debit_entry=entries.get(
        entry_type=LedgerEntry.EntryType.DEBIT
    )
    credit_entry=entries.get(
            entry_type=LedgerEntry.EntryType.CREDIT
        )
    assert debit_entry.wallet_id == source_wallet.id # pyright: ignore[reportAttributeAccessIssue]
    assert credit_entry.wallet_id == destination_wallet.id # pyright: ignore[reportAttributeAccessIssue]
    assert debit_entry.amount == Decimal("100.00000000")
    assert credit_entry.amount == Decimal("116.70750000")


@pytest.mark.django_db
def test_exchange_creates_audit_log(wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    transaction=exchange(
        idempotency_key=uuid.uuid4(),
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        initiated_by=user,
        amount=Decimal("100"),
    )
    audit_log=AuditLog.objects.get(transaction=transaction)
    assert audit_log.action == AuditLog.Action.EXCHANGE
    assert audit_log.actor == user
    assert audit_log.transaction == transaction
    assert AuditLog.objects.filter(transaction=transaction).count() == 1
    assert audit_log.details["status"] == Transaction.TransactionStatus.COMPLETED
    assert audit_log.details["source_wallet_id"] == source_wallet.pk
    assert audit_log.details["destination_wallet_id"] == destination_wallet.pk
    assert audit_log.details["source_amount"] == "100"
    assert audit_log.details["destination_amount"] == str(
        transaction.exchange_details.destination_amount # type: ignore
    )
    assert audit_log.details["fee_amount"] == str(
        transaction.exchange_details.fee_amount  # type: ignore
    )

@pytest.mark.django_db
def test_withdraw_rolls_back_when_audit_log_fails(user,wallets,exchange_rate):
    source_wallet,destination_wallet=wallets
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet.balance=Decimal("100")
    destination_wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    with patch(  # noqa: SIM117
        "apps.transactions.audit.AuditLog.objects.create",
        side_effect=RuntimeError("Audit log write failed."),
    ):
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            exchange(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                amount=Decimal("50"),
                idempotency_key=idempotency_key,
                initiated_by=user,
            )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance == Decimal("100")
    assert not Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).exists()

    assert not LedgerEntry.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_exchange_concurrent_idempotency(wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    idempotency_key=uuid.uuid4()
    barrier=Barrier(2)
    def execute_exchange():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return exchange(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                idempotency_key=idempotency_key,
                initiated_by=user,
                amount=Decimal("100")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_exchange)
        future2=executor.submit(execute_exchange)

        transaction1=future1.result(timeout=15)
        transaction2=future2.result(timeout=15)
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert transaction1.pk == transaction2.pk
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert AuditLog.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).count() == 1
    assert source_wallet.balance == Decimal("900")
    assert destination_wallet.balance == Decimal("616.7075")

@pytest.mark.django_db(transaction=True)
def test_exchange_concurrent_insufficient_balance(wallets,user,exchange_rate):
    source_wallet,destination_wallet=wallets
    barrier=Barrier(2)
    def execute_exchange():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return exchange(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                idempotency_key=uuid.uuid4(),
                initiated_by=user,
                amount=Decimal("600")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_exchange)
        future2=executor.submit(execute_exchange)

        results = []
        errors = []

        for future in (future1, future2):
            try:
                results.append(future.result(timeout=15))
            except ValueError as exc:
                errors.append(exc)

        assert len(results) == 1
        assert len(errors) == 1
        assert str(errors[0]) == "Insufficient wallet balance."
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    successful_transaction = results[0]
    assert Transaction.objects.count() == 1
    assert AuditLog.objects.filter(
        transaction=successful_transaction
    ).count() == 1
    assert source_wallet.balance == Decimal("400")
    assert destination_wallet.balance == Decimal("1200.245")
    assert LedgerEntry.objects.count() == 2