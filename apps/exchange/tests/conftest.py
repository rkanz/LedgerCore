from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.services import register_user
from apps.exchange.models import ExchangeRate
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
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

@pytest.fixture
def exchange_rates(db):
    return ExchangeRate.objects.bulk_create(
        [
            ExchangeRate(
                base_currency="EUR",
                quote_currency="USD",
                rate="1.17"
            ),
            ExchangeRate(
                base_currency="EUR",
                quote_currency="USD",
                rate="1.18"
                        ),
            ExchangeRate(
                base_currency="USD",
                quote_currency="EUR",
                rate="0.85"
                        )
        ]
    )
@pytest.fixture
def exchange_rate(db):
    return ExchangeRate.objects.create(
        base_currency="EUR",
        quote_currency="USD",
        rate=Decimal("1.17"),
    )
@pytest.fixture
def wallets(user):
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


