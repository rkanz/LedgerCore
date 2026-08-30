from decimal import Decimal

import pytest
import responses

from apps.exchange.models import ExchangeRate
from apps.exchange.tasks import update_exchange_rate


@pytest.mark.django_db
@responses.activate
def test_update_exchange_error():
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
    result=update_exchange_rate(
        base_currency="EUR",
        quote_currency="USD"
    )
    exchange_rate=ExchangeRate.objects.get(
        id=result["id"]
    )
    assert exchange_rate.rate == Decimal("1.17")
    assert exchange_rate.base_currency == "EUR"
    assert exchange_rate.quote_currency == "USD"
    