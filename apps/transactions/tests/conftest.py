import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import register_user
from apps.exchange.models import ExchangeRate
from apps.transactions.models import Transaction
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
def user_2():
        return register_user(
        validated_data={
            "username": "Bob123",
            "first_name": "Bob",
            "last_name": "Test",
            "email": "bob@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )
@pytest.fixture
def wallets_2(user_2):
     return{
        wallet.currency: wallet
            for wallet in Wallet.objects.filter(user=user_2)
     }
@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

@pytest.fixture
def wallet(user):
    source_wallet = Wallet.objects.get(
        user=user,
        currency=Wallet.Currency.EUR,
    )

    destination_wallet = Wallet.objects.get(
        user=user,
        currency=Wallet.Currency.USD,
    )

    source_wallet.balance = Decimal("1000")
    source_wallet.save(update_fields=["balance"])

    destination_wallet.balance = Decimal("500")
    destination_wallet.save(update_fields=["balance"])

    return source_wallet, destination_wallet

@pytest.fixture
def exchange_rate(db):
    return ExchangeRate.objects.create(
        base_currency="EUR",
        quote_currency="USD",
        rate=Decimal("1.17"),
    )


@pytest.fixture
def create_transfer():
    def _create_transfer(
        initiated_by,
        source_wallet,
        destination_wallet,
        amount="100",
        status=Transaction.TransactionStatus.COMPLETED,
        currency=Wallet.Currency.USDT,
    ):
        return Transaction.objects.create(
            initiated_by=initiated_by,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=status,
            amount=amount,
            currency=currency,
            idempotency_key=uuid.uuid4(),
        )

    return _create_transfer


@pytest.fixture
def ali():
    return register_user(
        validated_data={
            "username": "ali",
            "first_name": "Ali",
            "last_name": "Test",
            "email": "ali@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )
@pytest.fixture
def mina():
    return register_user(
        validated_data={
            "username": "mina",
            "first_name": "Mina",
            "last_name": "Test",
            "email": "mina@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )

@pytest.fixture
def ali_wallets(ali):
    return {
        wallet.currency: wallet
        for wallet in Wallet.objects.filter(user=ali)
    }
@pytest.fixture
def mina_wallets(mina):
    return {
        wallet.currency: wallet
        for wallet in Wallet.objects.filter(user=mina)
    }