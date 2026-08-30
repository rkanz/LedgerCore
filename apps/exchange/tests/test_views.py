import uuid
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.services import register_user
from apps.exchange.cache import invalidate_exchange_rate_cache
from apps.exchange.models import ExchangeTransaction
from apps.transactions.models import Transaction
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_exchange_rate_list(api_client,exchange_rates):
    response=api_client.get(reverse('exchange-rate-list'))
    assert response.status_code == 200
    assert response.data["count"] == 3


@pytest.mark.django_db
def test_exchange_rate_filter(api_client,exchange_rates):
    response=api_client.get("/api/exchange/rates/?base_currency=EUR")
    assert response.status_code == 200
    assert response.data["count"] == 2
    for item in response.data["results"]:
        assert item["base_currency"] == "EUR"


@pytest.mark.django_db
def test_exchange_rate_pair_filter(api_client,exchange_rates):
    response=api_client.get(
        "/api/exchange/rates/"
        "?base_currency=EUR&quote_currency=USD"
    )
    assert response.status_code == 200
    assert response.data["count"] == 2

@pytest.mark.django_db
def test_exchange_rate_ordering(api_client,exchange_rates):
    response=api_client.get(
        "/api/exchange/rates/?ordering=rate"
    )

    assert response.status_code == 200
    rates=[
        item["rate"]
        for item in response.data["results"]
    ]
    assert rates == sorted(rates)

@pytest.mark.django_db
def test_exchange_rate_list_cache(api_client,exchange_rates):
    cache.clear()
    response_1 = api_client.get(
        "/api/exchange/rates/"
    )

    assert response_1.status_code == 200

    response_2 = api_client.get(
        "/api/exchange/rates/"
    )

    assert response_2.status_code == 200
    assert response_1.data == response_2.data


@pytest.mark.django_db
def test_exchange_rate_cache_invalidation():
    cache.set(
        "exchange:rates:test",
        {"rate": "1.17"},
        timeout=60,
    )

    assert cache.get("exchange:rates:test") is not None

    invalidate_exchange_rate_cache()

    assert cache.get("exchange:rates:test") is None

@pytest.mark.django_db
def test_exchange_view(wallets,api_client,exchange_rate):
    source_wallet,destination_wallet=wallets
    idempotency_key=uuid.uuid4()
    response=api_client.post(reverse('exchange-transaction'),{
        'source_currency':'EUR',
        'destination_currency':'USD',
        'amount':'100'
    },format="json",HTTP_IDEMPOTENCY_KEY=str(idempotency_key))
    assert response.status_code == 201
    assert response.data["transaction_id"] is not None
    assert response.data["source_currency"] == "EUR"
    assert response.data["destination_currency"] == "USD"
    assert response.data["source_amount"] == "100.00000000"
    assert response.data["exchange_rate_value"] == "1.170000000000"
    assert response.data["fee_amount"] == "0.29250000"
    assert response.data["fee_currency"] == "USD"
    assert response.data["status"] == "COMPLETED"
    assert response.data["destination_amount"] == "116.70750000"
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("900")
    assert destination_wallet.balance == Decimal("616.7075")
    assert Transaction.objects.count() == 1
    assert ExchangeTransaction.objects.count() == 1

@pytest.mark.django_db
def test_exchange_idempotency_key(api_client):
    response=api_client.post(reverse('exchange-transaction'),{
        'source_currency':'EUR',
        'destination_currency':'USD',
        'amount':'100'
    },format="json")
    assert response.status_code == 400
    assert response.data["detail"] == (
        "Idempotency-Key header is required."
    )

@pytest.mark.django_db
def test_exchange_authentication_eror():
    api_client=APIClient()
    response=api_client.post(reverse('exchange-transaction'),{
            'source_currency':'EUR',
            'destination_currency':'USD',
            'amount':'100'
        },format="json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_exchange_view_idempotency(wallets,exchange_rate,api_client):
    idempotency_key=uuid.uuid4()
    response1=api_client.post(reverse('exchange-transaction'),{
        'source_currency':'EUR',
        'destination_currency':'USD',
        'amount':'100'
    },format="json",HTTP_IDEMPOTENCY_KEY=str(idempotency_key))
    response2=api_client.post(reverse('exchange-transaction'),{
        'source_currency':'EUR',
        'destination_currency':'USD',
        'amount':'100'
    },format="json",HTTP_IDEMPOTENCY_KEY=str(idempotency_key))
    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.data["transaction_id"] == response2.data["transaction_id"]
    assert Transaction.objects.count() == 1
    assert ExchangeTransaction.objects.count() == 1

@pytest.mark.django_db
def test_exchange_invalid_idempotency(api_client):
    idempotency_key='hello'
    response=api_client.post(reverse('exchange-transaction'),{
            'source_currency':'EUR',
            'destination_currency':'USD',
            'amount':'100'
        },format="json",HTTP_IDEMPOTENCY_KEY=str(idempotency_key))
    assert response.status_code == 400
    assert Transaction.objects.count() == 0
    assert ExchangeTransaction.objects.count() == 0

@pytest.mark.django_db
def test_exchange_invalid_currency(api_client):
    response=api_client.post(reverse('exchange-transaction'),{
            'source_currency':'ABC',
            'destination_currency':'USD',
            'amount':'100'
        },format="json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 400
    assert Transaction.objects.count() == 0
    assert ExchangeTransaction.objects.count() == 0

@pytest.mark.django_db
def test_exchange_insufficient_balance(api_client,wallets):
    source_wallet,destination_wallet=wallets
    response=api_client.post(reverse('exchange-transaction'),{
            'source_currency':'EUR',
            'destination_currency':'USD',
            'amount':'1001'
        },format="json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 400
    assert source_wallet.balance == Decimal("1000")
    assert destination_wallet.balance == Decimal("500")
    assert Transaction.objects.count() == 0
    assert ExchangeTransaction.objects.count() == 0

@pytest.mark.django_db
def test_exchange_view_rate_not_available(
    api_client,
    wallets,
):
    response = api_client.post(
        reverse("exchange-transaction"),
        {
            "source_currency": "EUR",
            "destination_currency": "USD",
            "amount": "100",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Exchange rate is not available."

    assert Transaction.objects.count() == 0
    assert ExchangeTransaction.objects.count() == 0