import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.services import register_user
from apps.transactions.models import Category, LedgerEntry, Transaction
from apps.transactions.services import deposit, withdraw
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
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def ledger_entries(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("500")
    wallet.save(update_fields=["balance"])
    deposit_transaction=deposit(
        wallet=wallet,
        amount=Decimal("100"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user
    )
    withdraw_transaction=withdraw(
            initiated_by=user,
            amount=Decimal("50"),
            idempotency_key=uuid.uuid4(),
            wallet=wallet
        )
    return LedgerEntry.objects.filter(
        wallet=wallet,
        transaction__in=[
            deposit_transaction,
            withdraw_transaction,
        ],
    )

@pytest.fixture
def ledger_entries_multiple_categories(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("500")
    wallet.save(update_fields=["balance"])
    withdraw_transaction1=withdraw(
                initiated_by=user,
                amount=Decimal("50"),
                idempotency_key=uuid.uuid4(),
                wallet=wallet
            )
    withdraw_transaction1.category=Category.FOOD
    withdraw_transaction1.save(update_fields=["category"])
    withdraw_transaction2=withdraw(
                    initiated_by=user,
                    amount=Decimal("30"),
                    idempotency_key=uuid.uuid4(),
                    wallet=wallet
                )
    withdraw_transaction2.category=Category.HEALTH
    withdraw_transaction2.save(update_fields=["category"])
    return LedgerEntry.objects.filter(
            wallet=wallet,
            transaction__in=[
                withdraw_transaction1,
                withdraw_transaction2,
            ],
        )

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