import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.services import register_user
from apps.transactions.models import Category, LedgerEntry, Transaction
from apps.wallets.models import Wallet


@pytest.fixture
def user():
    return register_user(
        validated_data={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Test",
            "email": "alice@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )


@pytest.fixture
def wallets(user):
    return {
        wallet.currency: wallet
        for wallet in Wallet.objects.filter(user=user)
    }


@pytest.fixture
def create_ledger_entry():
    def _create_ledger_entry(
        user,
        wallet,
        amount,
        entry_type,
        created_at=None,
    ):
        if created_at is None:
            created_at=timezone.now()
        transaction_type = (
                Transaction.TransactionType.DEPOSIT
                if entry_type == LedgerEntry.EntryType.CREDIT
                else Transaction.TransactionType.WITHDRAW
            )
        transaction = Transaction.objects.create(
                source_wallet=(
                    wallet
                    if transaction_type == Transaction.TransactionType.WITHDRAW
                    else None
                ),
                destination_wallet=(
                    wallet
                    if transaction_type == Transaction.TransactionType.DEPOSIT
                    else None
                ),
                transaction_type=transaction_type,
                status=Transaction.TransactionStatus.COMPLETED,
                amount=Decimal(amount),
                currency=wallet.currency,
                idempotency_key=uuid.uuid4(),
                initiated_by=user,
            )
        entry = LedgerEntry.objects.create(
                transaction=transaction,
                wallet=wallet,
                amount=Decimal(amount),
                entry_type=entry_type,
            )
        LedgerEntry.objects.filter(pk=entry.pk).update(created_at=created_at)
        return entry
    return _create_ledger_entry

@pytest.fixture
def financial_summary_data(user, wallets, create_ledger_entry):
    wallet = wallets[Wallet.Currency.USDT]

    income_1 = create_ledger_entry(  # noqa: F841
        user=user,
        wallet=wallet,
        amount="2500",
        entry_type=LedgerEntry.EntryType.CREDIT,
    )

    income_2 = create_ledger_entry( # noqa: F841
        user=user,
        wallet=wallet,
        amount="500",
        entry_type=LedgerEntry.EntryType.CREDIT,
    )

    food = create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="350",
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    food.transaction.category = Category.FOOD
    food.transaction.save(update_fields=["category"])

    transport = create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="120",
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    transport.transaction.category = Category.TRANSPORT
    transport.transaction.save(update_fields=["category"])

    bills = create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="300",
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    bills.transaction.category = Category.BILLS
    bills.transaction.save(update_fields=["category"])

    shopping = create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="180",
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    shopping.transaction.category = Category.SHOPPING
    shopping.transaction.save(update_fields=["category"])

    entertainment = create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="100",
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    entertainment.transaction.category = Category.ENTERTAINMENT
    entertainment.transaction.save(update_fields=["category"])

    return wallet