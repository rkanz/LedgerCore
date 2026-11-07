import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.transactions.models import AuditLog, LedgerEntry, Transaction
from apps.transactions.services import (
    deposit,
    get_frequent_recipients,
    get_recent_recipients,
    transfer,
    withdraw,
)
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_desposit(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    transaction=deposit(
        wallet=wallet,
        amount=Decimal("100"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("100")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED

@pytest.mark.django_db
def test_withdraw_insufficient_balance(user,wallets):

    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Insufficient wallet balance."):
        withdraw(
        wallet=wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    wallet.refresh_from_db()

    assert wallet.balance == Decimal("0")

@pytest.mark.django_db
def test_withdraw(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    transaction=withdraw(
        initiated_by=user,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        wallet=wallet
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("50")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED

@pytest.mark.django_db
def test_withdraw_create_debit_ledger_entry(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    transaction=withdraw(
        wallet= wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    ledger_entry = transaction.ledger_entries.get() # pyright: ignore[reportAttributeAccessIssue]
    assert ledger_entry.wallet == wallet
    assert ledger_entry.amount == Decimal("50")
    assert ledger_entry.entry_type == LedgerEntry.EntryType.DEBIT

@pytest.mark.django_db
def test_withdraw_idempotency(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    first_transaction=withdraw(
        initiated_by=user,
        wallet=wallet,
        idempotency_key=idempotency_key,
        amount=Decimal("50")
    )
    second_transaction=withdraw(
        initiated_by=user,
        wallet=wallet,
        idempotency_key=idempotency_key,
        amount=Decimal("50")
    )
    wallet.refresh_from_db()
    assert first_transaction == second_transaction
    assert wallet.balance == Decimal("50")
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert AuditLog.objects.filter(
    transaction__idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.django_db
def test_deposit_idempotency(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    idempotency_key=uuid.uuid4()
    first_transaction=deposit(
        wallet=wallet,
        initiated_by=user,
        amount=Decimal("150"),
        idempotency_key=idempotency_key
    )
    second_transaction=deposit(
        wallet=wallet,
        initiated_by=user,
        amount=Decimal("150"),
        idempotency_key=idempotency_key
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("150")
    assert first_transaction == second_transaction
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert AuditLog.objects.filter(
    transaction__idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.django_db
def test_deposit_zero_amount(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Deposit amount must be greater than zero",
    ):
        deposit(
            wallet=wallet,
            amount=Decimal("0"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("0")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_transfer(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    transaction=transfer(
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("100")
    assert destination_wallet.balance == Decimal("50")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED
    assert transaction.transaction_type == Transaction.TransactionType.TRANSFER
    ledger_entries=LedgerEntry.objects.all()
    assert ledger_entries.count() == 2
    source_entry=ledger_entries.get(
        wallet=source_wallet,
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    destination_entry=ledger_entries.get(
            wallet=destination_wallet,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )
    assert source_entry.amount == Decimal("50")
    assert destination_entry.amount == Decimal("50") 

@pytest.mark.django_db
def test_transfer_insufficient_balance(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Insufficient wallet balance.",):
        transfer(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                amount=Decimal("50"),
                idempotency_key=uuid.uuid4(),
                initiated_by=user
            )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert destination_wallet.balance==Decimal("0")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_transfer_idempotency(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    idempotency_key=uuid.uuid4()
    first_transaction=transfer(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("100"),
        initiated_by=user,
    )
    second_transaction=transfer(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("100"),
        initiated_by=user,
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key).count() == 1
    assert source_wallet.balance == Decimal("50")
    assert destination_wallet.balance == Decimal("100")
    assert first_transaction== second_transaction
    assert AuditLog.objects.filter(
    transaction__idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_transfer_invalid_amount(wallets,wallets_2,user,amount):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    with pytest.raises(
        ValueError,
        match="Transfer amount must be greater than zero.",
    ): 
        transfer(
            amount=amount,
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            idempotency_key=uuid.uuid4()
    )
    destination_wallet.refresh_from_db()
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("0")
    assert destination_wallet.balance == Decimal("0")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_transfer_diffrenct_currency(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.BTC]
    with pytest.raises(ValueError,match="Wallet currencies must match."):
        transfer(
            amount=Decimal("100"),
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            idempotency_key=uuid.uuid4()
    )
    destination_wallet.refresh_from_db()
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance==Decimal("0")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_same_wallet(user,wallets):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    with pytest.raises(ValueError,match="Cannot transfer to the same wallet."):
        transfer(
            source_wallet=source_wallet,
            destination_wallet=source_wallet,
            amount=Decimal("50"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0 

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_deposit_invalid_amount(user,wallets,amount):
    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Deposit amount must be greater than zero."):
        deposit(
            wallet=wallet,
            amount=amount,
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_withdraw_invalid_amount(user,wallets,amount):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    with pytest.raises(ValueError,match="Withdraw amount must be greater than zero."):
        withdraw(
            wallet=wallet,
            amount=amount,
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_get_frequent_recipients(create_transfer,user,ali_wallets,mina_wallets,wallets):
    user_wallet=wallets[Wallet.Currency.USDT]
    ali_wallet=ali_wallets[Wallet.Currency.USDT]
    mina_wallet=mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    recipients=get_frequent_recipients(
        currency=Wallet.Currency.USDT,
        user=user,
    )
    assert list(recipients) == [mina_wallet, ali_wallet]

@pytest.mark.django_db
def test_frequent_recipients_excludes_failed_transfers(create_transfer,user,ali_wallets,mina_wallets,wallets):
    user_wallet=wallets[Wallet.Currency.USDT]
    ali_wallet=ali_wallets[Wallet.Currency.USDT]
    mina_wallet=mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
        status=Transaction.TransactionStatus.FAILED
    )   
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
        status=Transaction.TransactionStatus.FAILED
    )
    recipients=get_frequent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    ) 
    assert list(recipients) == [mina_wallet]
    assert recipients[0].transfer_count == 1       # type: ignore


@pytest.mark.django_db
def test_get_frequent_recipients_different_currencies(wallets,mina_wallets,create_transfer,user):
    user_usdt_wallet=wallets[Wallet.Currency.USDT]
    user_btc_wallet=wallets[Wallet.Currency.BTC]

    mina_usdt_wallet=mina_wallets[Wallet.Currency.USDT]
    mina_btc_wallet=mina_wallets[Wallet.Currency.BTC]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_btc_wallet,
        destination_wallet=mina_btc_wallet,
    )
    recipients=get_frequent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert recipients[0].transfer_count == 2 # type: ignore

@pytest.mark.django_db
def test_get_frequent_recipients_only_counts_current_user_transfers(
    user,
    ali,
    wallets,
    ali_wallets,
    mina_wallets,
    create_transfer,
):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    mina_usdt_wallet = mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet
    )
    create_transfer(
        initiated_by=ali,
        source_wallet=ali_usdt_wallet,
        destination_wallet=mina_usdt_wallet
    )
    recipients=get_frequent_recipients(
        user=ali,
        currency=Wallet.Currency.USDT
    )
    assert list(recipients) == [mina_usdt_wallet]
    assert len(recipients) == 1
    assert recipients[0].transfer_count == 1 # type: ignore

@pytest.mark.django_db
def test_get_recent_recipients(create_transfer,wallets,user,ali_wallets,mina_wallets):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    mina_usdt_wallet = mina_wallets[Wallet.Currency.USDT]
    old_mina=create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    old_ali = create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet,
    )

    recent_mina = create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    old_mina.created_at =timezone.now() - timedelta(days=3)
    old_mina.save(update_fields=["created_at"])

    old_ali.created_at =timezone.now() - timedelta(days=2)
    old_ali.save(update_fields=["created_at"])

    recent_mina.created_at = timezone.now() - timedelta(days=1)
    recent_mina.save(update_fields=["created_at"])
    recent_recipients=get_recent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert list(recent_recipients) == [mina_usdt_wallet,ali_usdt_wallet]

@pytest.mark.django_db
def test_get_recent_recipients_excludes_failed_transfers(create_transfer,wallets,user,ali_wallets):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet,
        status=Transaction.TransactionStatus.FAILED
    )
    recent_recipients=get_recent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert list(recent_recipients) == []

@pytest.mark.django_db
def test_transfer_rolls_back_when_audit_log_fails(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet.balance=Decimal("20")
    destination_wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    with patch(  # noqa: SIM117
        "apps.transactions.audit.AuditLog.objects.create",
        side_effect=RuntimeError("Audit log write failed."),
    ):
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            transfer(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                amount=Decimal("50"),
                idempotency_key=idempotency_key,
                initiated_by=user,
            )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance == Decimal("20")

    assert not Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).exists()

    assert not LedgerEntry.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).exists()

@pytest.mark.django_db
def test_transfer_creates_audit_log(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet.balance=Decimal("20")
    destination_wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    transaction=transfer(
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            amount=Decimal("50"),
            idempotency_key=idempotency_key,
            initiated_by=user,
            )
    audit_log=AuditLog.objects.get(transaction=transaction)
    assert audit_log.actor == user
    assert audit_log.action == AuditLog.Action.TRANSFER
    assert audit_log.transaction == transaction
    assert AuditLog.objects.filter(transaction=transaction).count() == 1
    assert audit_log.details["status"] == Transaction.TransactionStatus.COMPLETED
    assert audit_log.details["source_wallet_id"] == source_wallet.pk
    assert audit_log.details["destination_wallet_id"] == destination_wallet.pk
    assert audit_log.details["amount"] == "50"
    assert audit_log.details["currency"] == source_wallet.currency

@pytest.mark.django_db
def test_deposit_creates_audit_log(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    transaction=deposit(
            wallet=wallet,
            amount=Decimal("50"),
            idempotency_key=idempotency_key,
            initiated_by=user,
            )
    audit_log=AuditLog.objects.get(transaction=transaction)
    assert audit_log.actor == user
    assert audit_log.action == AuditLog.Action.DEPOSIT
    assert audit_log.transaction == transaction
    assert AuditLog.objects.filter(transaction=transaction).count() == 1
    assert audit_log.details["status"] == Transaction.TransactionStatus.COMPLETED
    assert audit_log.details["wallet_id"] == wallet.pk
    assert audit_log.details["amount"] == "50"
    assert audit_log.details["currency"] == wallet.currency

@pytest.mark.django_db
def test_withdraw_creates_audit_log(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    transaction=withdraw(
            wallet=wallet,
            amount=Decimal("50"),
            idempotency_key=idempotency_key,
            initiated_by=user,
            )
    audit_log=AuditLog.objects.get(transaction=transaction)
    assert audit_log.actor == user
    assert audit_log.action == AuditLog.Action.WITHDRAW
    assert audit_log.transaction == transaction
    assert AuditLog.objects.filter(transaction=transaction).count() == 1
    assert audit_log.details["status"] == Transaction.TransactionStatus.COMPLETED
    assert audit_log.details["wallet_id"] == wallet.pk
    assert audit_log.details["amount"] == "50"
    assert audit_log.details["currency"] == wallet.currency

@pytest.mark.django_db
def test_deposit_rolls_back_when_audit_log_fails(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    with patch(  # noqa: SIM117
        "apps.transactions.audit.AuditLog.objects.create",
        side_effect=RuntimeError("Audit log write failed."),
    ):
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            deposit(
                wallet=wallet,
                amount=Decimal("50"),
                idempotency_key=idempotency_key,
                initiated_by=user,
            )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("150")
    assert not Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).exists()

    assert not LedgerEntry.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).exists()

@pytest.mark.django_db
def test_withdraw_rolls_back_when_audit_log_fails(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    with patch(  # noqa: SIM117
        "apps.transactions.audit.AuditLog.objects.create",
        side_effect=RuntimeError("Audit log write failed."),
    ):
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            withdraw(
                wallet=wallet,
                amount=Decimal("50"),
                idempotency_key=idempotency_key,
                initiated_by=user,
            )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("150")
    assert not Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).exists()

    assert not LedgerEntry.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).exists()

@pytest.mark.django_db(transaction=True)
def test_transfer_concurrent_idempotency(wallets,user,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("1000")
    source_wallet.save(update_fields=["balance"])
    destination_wallet.balance = Decimal("500")
    destination_wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    barrier=Barrier(2)
    def execute_transfer():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return transfer(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                idempotency_key=idempotency_key,
                initiated_by=user,
                amount=Decimal("100")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_transfer)
        future2=executor.submit(execute_transfer)

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
    assert transaction1.transaction_type == Transaction.TransactionType.TRANSFER
    assert source_wallet.balance == Decimal("900")
    assert destination_wallet.balance == Decimal("600")
    assert LedgerEntry.objects.filter(
    transaction=transaction1
    ).count() == 2

@pytest.mark.django_db(transaction=True)
def test_transfer_concurrent_insufficient_balance(wallets,user,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("100")
    source_wallet.save(update_fields=["balance"])
    destination_wallet.balance = Decimal("500")
    destination_wallet.save(update_fields=["balance"])
    barrier=Barrier(2)
    def execute_transfer():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return transfer(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                idempotency_key=uuid.uuid4(),
                initiated_by=user,
                amount=Decimal("80")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_transfer)
        future2=executor.submit(execute_transfer)

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

    assert LedgerEntry.objects.filter(
        transaction=successful_transaction
    ).count() == 2

    assert source_wallet.balance == Decimal("20")
    assert destination_wallet.balance == Decimal("580")
    assert LedgerEntry.objects.count() == 2

@pytest.mark.django_db(transaction=True)
def test_withdraw_concurrent_insufficient_balance(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    barrier=Barrier(2)
    def execute_withdraw():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return withdraw(
                wallet=wallet,
                idempotency_key=uuid.uuid4(),
                initiated_by=user,
                amount=Decimal("80")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_withdraw)
        future2=executor.submit(execute_withdraw)

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
    wallet.refresh_from_db()
    successful_transaction = results[0]

    assert Transaction.objects.count() == 1
    assert AuditLog.objects.filter(
        transaction=successful_transaction
    ).count() == 1

    assert LedgerEntry.objects.filter(
        transaction=successful_transaction
    ).count() == 1

    assert wallet.balance == Decimal("20")
    assert LedgerEntry.objects.count() == 1
    assert successful_transaction.transaction_type == Transaction.TransactionType.WITHDRAW
    assert successful_transaction.status == Transaction.TransactionStatus.COMPLETED
    assert LedgerEntry.objects.filter(
    transaction=successful_transaction,
    entry_type=LedgerEntry.EntryType.DEBIT,
    ).count() == 1
@pytest.mark.django_db(transaction=True)
def test_deposit_concurrent(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    barrier=Barrier(2)
    def execute_deposit():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return deposit(
                wallet=wallet,
                idempotency_key=uuid.uuid4(),
                initiated_by=user,
                amount=Decimal("80")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_deposit)
        future2=executor.submit(execute_deposit)

        transaction1=future1.result(timeout=15)
        transaction2=future2.result(timeout=15)
    wallet.refresh_from_db()
    assert Transaction.objects.count() == 2
    assert AuditLog.objects.count() == 2
    assert LedgerEntry.objects.count() == 2
    assert wallet.balance == Decimal("260")
    assert transaction1.pk != transaction2.pk
    assert transaction1.transaction_type == Transaction.TransactionType.DEPOSIT
    assert transaction2.transaction_type == Transaction.TransactionType.DEPOSIT

    assert transaction1.status == Transaction.TransactionStatus.COMPLETED
    assert transaction2.status == Transaction.TransactionStatus.COMPLETED
    assert LedgerEntry.objects.filter(
    transaction=transaction1,
    entry_type=LedgerEntry.EntryType.CREDIT,
    ).count() == 1
@pytest.mark.django_db(transaction=True)
def test_withdraw_concurrent_idempotency(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("1000")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    barrier=Barrier(2)
    def execute_withdraw():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return withdraw(
                wallet=wallet,
                idempotency_key=idempotency_key,
                initiated_by=user,
                amount=Decimal("600")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_withdraw)
        future2=executor.submit(execute_withdraw)
        transaction1=future1.result(timeout=15)
        transaction2=future2.result(timeout=15)
    wallet.refresh_from_db()
    assert transaction1.pk == transaction2.pk
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert AuditLog.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).count() == 1
    assert transaction1.transaction_type == Transaction.TransactionType.WITHDRAW
    assert wallet.balance == Decimal("400")
    assert LedgerEntry.objects.filter(
    transaction=transaction1
    ).count() == 1

@pytest.mark.django_db(transaction=True)
def test_deposit_concurrent_idempotency(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("1000")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    barrier=Barrier(2)
    def execute_deposit():
        close_old_connections()
        try:
            barrier.wait(timeout=5)

            return deposit(
                wallet=wallet,
                idempotency_key=idempotency_key,
                initiated_by=user,
                amount=Decimal("600")
            )
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1=executor.submit(execute_deposit)
        future2=executor.submit(execute_deposit)

        transaction1=future1.result(timeout=15)
        transaction2=future2.result(timeout=15)
    wallet.refresh_from_db()
    assert transaction1.pk == transaction2.pk
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1
    assert AuditLog.objects.filter(
        transaction__idempotency_key=idempotency_key
    ).count() == 1
    assert transaction1.transaction_type == Transaction.TransactionType.DEPOSIT
    assert wallet.balance == Decimal("1600")
    assert LedgerEntry.objects.filter(
    transaction=transaction1
    ).count() == 1
    assert LedgerEntry.objects.filter(
    transaction=transaction1,
    entry_type=LedgerEntry.EntryType.CREDIT,
    ).count() == 1


