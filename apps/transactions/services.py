from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.wallets.cache import invalidate_user_wallet_cache
from apps.wallets.models import Wallet

from .cache import invalidate_user_transaction_cache
from .models import LedgerEntry, Transaction


def deposit(
    *,
    wallet: Wallet,
    amount: Decimal,
    idempotency_key,
    initiated_by,
):
    if amount <= 0:
        raise ValueError("Deposit amount must be greater than zero.")
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        existing_transaction = Transaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing_transaction:
            return existing_transaction
        new_transaction = Transaction.objects.create(
            source_wallet=None,
            destination_wallet=wallet,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.TransactionStatus.PENDING,
            amount=amount,
            currency=wallet.currency,
            idempotency_key=idempotency_key,
            initiated_by=initiated_by,
        )

        LedgerEntry.objects.create(
            transaction=new_transaction,
            wallet=wallet,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount=amount,
        )
        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        new_transaction.status = Transaction.TransactionStatus.COMPLETED
        new_transaction.completed_at = timezone.now()
        new_transaction.save(update_fields=["status", "completed_at"])
        transaction.on_commit(
        lambda: invalidate_user_wallet_cache(
        user_id=wallet.user_id, # pyright: ignore[reportAttributeAccessIssue]
        wallet_id=wallet.id, # pyright: ignore[reportAttributeAccessIssue]
                )
        )
        transaction.on_commit(
        lambda: invalidate_user_transaction_cache(
        user_id=initiated_by.id,
        transaction_id=new_transaction.id, # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        return new_transaction


def withdraw(
    *,
    wallet: Wallet,
    amount: Decimal,
    idempotency_key,
    initiated_by,
):
    if amount <= 0:
        raise ValueError("Withdraw amount must be greater than zero.")
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        existing_transaction = Transaction.objects.filter(
            idempotency_key=idempotency_key).first()
        if existing_transaction:
            return existing_transaction
        if amount > wallet.balance:
            raise ValueError("Insufficent wallet balance.")
        new_transaction = Transaction.objects.create(
            source_wallet=wallet,
            destination_wallet=None,
            transaction_type=Transaction.TransactionType.WITHDRAW,
            status=Transaction.TransactionStatus.PENDING,
            amount=amount,
            currency=wallet.currency,
            idempotency_key=idempotency_key,
            initiated_by=initiated_by,
        )

        LedgerEntry.objects.create(
            transaction=new_transaction,
            wallet=wallet,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount=amount,
        )
        wallet.balance -= amount
        wallet.save(update_fields=["balance", "updated_at"])
        new_transaction.status = Transaction.TransactionStatus.COMPLETED
        new_transaction.completed_at = timezone.now()
        new_transaction.save(update_fields=["status", "completed_at"])
        transaction.on_commit(
        lambda: invalidate_user_wallet_cache(
        user_id=wallet.user_id, # pyright: ignore[reportAttributeAccessIssue]
        wallet_id=wallet.id, # pyright: ignore[reportAttributeAccessIssue]
            )
        )

        transaction.on_commit(
        lambda: invalidate_user_transaction_cache(
        user_id=initiated_by.id,
        transaction_id=new_transaction.id, # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        return new_transaction


def transfer(
    *,
    source_wallet: Wallet,
    destination_wallet: Wallet,
    amount: Decimal,
    idempotency_key,
    initiated_by,
):
    if amount <= 0:
        raise ValueError("Transfer amount must be greater than zero.")
    # Check idempotency
    with transaction.atomic():
        existing_transaction = Transaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        # Both wallets must use same currency
        if existing_transaction:
            return existing_transaction
        if source_wallet.currency != destination_wallet.currency:
            raise ValueError("Wallet currencies must match.")
        # Always lock wallets in a fixed order to prevent deadlocks
        first_wallet, second_wallet = sorted(
            [source_wallet, destination_wallet], key=lambda wallet: wallet.pk
        )
        first_wallet = Wallet.objects.select_for_update().get(pk=first_wallet.pk)
        second_wallet = Wallet.objects.select_for_update().get(pk=second_wallet.pk)
        # Use the locked wallet objects
        if source_wallet.pk == first_wallet.pk:
            source_wallet = first_wallet
            destination_wallet = second_wallet
        else:
            source_wallet = second_wallet
            destination_wallet = first_wallet
        # Check source wallet balance after locking
        if amount > source_wallet.balance:
            raise ValueError("Insufficent wallet balance.")
        if source_wallet == destination_wallet:
            raise ValueError("Cannot transfer to the same wallet.")
        # Create one transaction for the whole transfer
        new_transaction = Transaction.objects.create(
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.TransactionStatus.PENDING,
            amount=amount,
            currency=source_wallet.currency,
            idempotency_key=idempotency_key,
            initiated_by=initiated_by,
        )
        # Source wallet loses money
        LedgerEntry.objects.create(
            transaction=new_transaction,
            wallet=source_wallet,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount=amount,
        )
        # Destination wallet receives money
        LedgerEntry.objects.create(
            transaction=new_transaction,
            wallet=destination_wallet,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount=amount,
        )
        # Update balances
        source_wallet.balance -= amount
        destination_wallet.balance += amount
        source_wallet.save(update_fields=["balance", "updated_at"])
        destination_wallet.save(update_fields=["balance", "updated_at"])

        # Complete transaction
        new_transaction.status = Transaction.TransactionStatus.COMPLETED
        new_transaction.completed_at = timezone.now()
        new_transaction.save(update_fields=["status", "completed_at"])
        transaction.on_commit(
            lambda:invalidate_user_wallet_cache(
                user_id=initiated_by.id,
                wallet_id=source_wallet.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        transaction.on_commit(
            lambda:invalidate_user_wallet_cache(
                user_id=initiated_by.id,
                wallet_id=destination_wallet.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        transaction.on_commit(
            lambda:invalidate_user_transaction_cache(
                user_id=initiated_by.id,
                transaction_id=new_transaction.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        return new_transaction
