from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.transactions.models import LedgerEntry
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_income_api(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"USDT",
        "period":"month"
    })
    assert response.status_code == 200
    assert response.data["currency"] == "USDT"
    assert response.data["income"] == Decimal("100")
    assert response.data["period"] == "month"

@pytest.mark.django_db
def test_expense_api(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"USDT",
        "period":"month"
    })
    assert response.status_code == 200
    assert response.data["currency"] == "USDT"
    assert response.data["expense"] == Decimal("50")
    assert response.data["period"] == "month"

@pytest.mark.django_db
def test_summary_api(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"USDT",
        "period":"month"
    })
    assert response.data["currency"] == "USDT"
    assert response.status_code == 200
    assert response.data["summary"] == {
    "income": Decimal("100.00000000"),
    "expense": Decimal("50.00000000"),
    }
    assert response.data["period"] == "month"
    assert response.data["summary"]["income"] == Decimal("100")
    assert response.data["summary"]["expense"] == Decimal("50")

@pytest.mark.django_db
def test_income_custom_date_range(api_client,ledger_entries,current_month):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"USDT",
        "start_date": current_month["start_date"].isoformat(),
        "end_date": current_month["end_date"].isoformat(),
    })
    assert response.status_code == 200
    assert response.data["income"] == Decimal("100")
    assert response.data["currency"] == "USDT"
    assert response.data["period"] == "custom"

@pytest.mark.django_db
def test_income_wallet_not_found(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"XYZ",
        "period":"month"
    })
    assert response.status_code == 404
    assert response.data["detail"] == "Wallet not found."

@pytest.mark.django_db
def test_income_currency_not_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
            "period":"month"
        })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_income_custom_range_with_period(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"USDT",
        "period":"month",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Use either period or start_date/end_date, not both."

@pytest.mark.django_db
def test_income_only_start_date_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"USDT",
        "start_date": "2026-09-01",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_income_only_end_date_sent(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:income"),
        {
            "currency": "USDT",
            "end_date": "2026-09-30",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_income_invalid_date_format(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:income"),{
        "currency":"USDT",
        "start_date":"09-01-2026",
        "end_date":"09-30-2026"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Dates must be in YYYY-MM-DD format."

@pytest.mark.django_db
def test_income_invalid_date_range(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:income"),
        {
            "currency": "USDT",
            "start_date": "2026-09-30",
            "end_date": "2026-09-01",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "start_date cannot be after end_date."

@pytest.mark.django_db
def test_expense_invalid_date_range(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:expense"),
        {
            "currency": "USDT",
            "start_date": "2026-09-30",
            "end_date": "2026-09-01",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "start_date cannot be after end_date."

@pytest.mark.django_db
def test_expense_custom_date_range(api_client,ledger_entries,current_month):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"USDT",
            "start_date": current_month["start_date"].isoformat(),
            "end_date": current_month["end_date"].isoformat(),
    })
    assert response.status_code == 200
    assert response.data["expense"] == Decimal("50")
    assert response.data["currency"] == "USDT"
    assert response.data["period"] == "custom"

@pytest.mark.django_db
def test_expense_wallet_not_found(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"XYZ",
        "period":"month"
    })
    assert response.status_code == 404
    assert response.data["detail"] == "Wallet not found."

@pytest.mark.django_db
def test_expense_currency_not_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
            "period":"month"
        })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_expense_custom_range_with_period(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"USDT",
        "period":"month",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Use either period or start_date/end_date, not both."

@pytest.mark.django_db
def test_expense_only_start_date_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"USDT",
        "start_date": "2026-09-01",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_expense_only_end_date_sent(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:expense"),
        {
            "currency": "USDT",
            "end_date": "2026-09-30",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_expense_invalid_date_format(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:expense"),{
        "currency":"USDT",
        "start_date":"09-01-2026",
        "end_date":"09-30-2026"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Dates must be in YYYY-MM-DD format."


@pytest.mark.django_db
def test_summary_custom_date_range(api_client,ledger_entries,current_month):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"USDT",
            "start_date": current_month["start_date"].isoformat(),
            "end_date": current_month["end_date"].isoformat(),
    })
    assert response.status_code == 200
    assert response.data["summary"] == {
    "income": Decimal("100.00000000"),
    "expense": Decimal("50.00000000"),
    }
    assert response.data["currency"] == "USDT"
    assert response.data["period"] == "custom"

@pytest.mark.django_db
def test_summary_wallet_not_found(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"XYZ",
        "period":"month"
    })
    assert response.status_code == 404
    assert response.data["detail"] == "Wallet not found."

@pytest.mark.django_db
def test_summary_currency_not_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
            "period":"month"
        })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_summary_custom_range_with_period(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"USDT",
        "period":"month",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Use either period or start_date/end_date, not both."

@pytest.mark.django_db
def test_summary_only_start_date_sent(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"USDT",
        "start_date": "2026-09-01",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_summary_only_end_date_sent(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:summary"),
        {
            "currency": "USDT",
            "end_date": "2026-09-30",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_summary_invalid_date_format(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:summary"),{
        "currency":"USDT",
        "start_date":"09-01-2026",
        "end_date":"09-30-2026"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Dates must be in YYYY-MM-DD format."

@pytest.mark.django_db
def test_summary_invalid_date_range(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:summary"),
        {
            "currency": "USDT",
            "start_date": "2026-09-30",
            "end_date": "2026-09-01",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "start_date cannot be after end_date."

@pytest.mark.django_db
def test_monthly_report(api_client,ledger_entries,wallets,current_month):
    response=api_client.get(reverse("analytics:monthly-report"),{
        "currency":"USDT", 
        "month":current_month["month"]
    })
    assert response.status_code == 200
    assert response.data["expense"] == Decimal("50")
    assert response.data["income"] == Decimal("100")
    assert response.data["expenses_by_category"] == {"OTHER":Decimal("50")}
    assert response.data["month"] == current_month["month"]

@pytest.mark.django_db
def test_monthly_report_currency_is_required(api_client,ledger_entries,wallets):
    response=api_client.get(reverse("analytics:monthly-report"),{
        "month":"2026-09"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_monthly_report_default_current_month(api_client,ledger_entries,wallets,current_month):
    response=api_client.get(reverse("analytics:monthly-report"),{
        "currency":"USDT", 
    })
    assert response.status_code == 200
    assert response.data["expense"] == Decimal("50")
    assert response.data["income"] == Decimal("100")
    assert response.data["expenses_by_category"] == {"OTHER":Decimal("50")}
    assert response.data["month"] == current_month["month"]
    assert response.data["month"] == timezone.now().strftime("%Y-%m")


@pytest.mark.django_db
def test_monthly_report_invalid_month(api_client,ledger_entries):
    response=api_client.get(reverse("analytics:monthly-report"),{
        "currency":"USDT", 
        "month":"XYZ"
    }) 
    assert response.status_code == 400
    assert response.data["detail"] == "Invalid month format. Use YYYY-MM."

@pytest.mark.django_db
def test_monthly_report_wallet_not_found(api_client):
    response=api_client.get(reverse("analytics:monthly-report"),{
        "currency":"INVALID", 
        "month":"2026-09"
    })
    assert response.data["detail"] == "Wallet not found."
    assert response.status_code == 404    


@pytest.mark.django_db
def test_get_balance_history(api_client,user,wallets,create_ledger_entry):
    wallet=wallets[Wallet.Currency.USDT]
    create_ledger_entry(
        wallet=wallet,
        user=user,
        amount="300",
        entry_type=LedgerEntry.EntryType.CREDIT,
        created_at=timezone.make_aware(
        datetime(2026, 5, 30, 12, 0)  # noqa: DTZ001
    ))
    create_ledger_entry(
            wallet=wallet,
            user=user,
            amount="100",
            entry_type=LedgerEntry.EntryType.DEBIT,
            created_at=timezone.make_aware(
            datetime(2026, 6, 3, 12, 0) # noqa: DTZ001
        ))
    create_ledger_entry(
            wallet=wallet,
            user=user,
            amount="200",
            entry_type=LedgerEntry.EntryType.CREDIT,
            created_at=timezone.make_aware(
            datetime(2026, 6, 3, 15, 0) # noqa: DTZ001
        ))
    response=api_client.get(reverse("analytics:balance-history"),{
        "currency":Wallet.Currency.USDT,
        "start_date":"2026-06-01",
        "end_date":"2026-06-05"
    })
    assert response.status_code == 200
    assert response.data == [
        {
            "date": date(2026, 6, 1),
            "balance": Decimal("300"),
        },
        {
            "date":date(2026,6,3),
            "balance":Decimal("400")
        }
    ]

@pytest.mark.django_db
def test_balance_history_currency_is_required(api_client,wallets):
    response=api_client.get(reverse("analytics:balance-history"),{
        "start_date":"2026-06-01",
        "end_date":"2026-06-05"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_balance_history_date_format(api_client):
    response=api_client.get(reverse("analytics:balance-history"),{
        "currency":"USDT",
        "start_date":"09-01-2026",
        "end_date":"09-30-2026"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Dates must be in YYYY-MM-DD format."

@pytest.mark.django_db
def test_balance_history_start_date_sent(api_client):
    response=api_client.get(reverse("analytics:balance-history"),{
        "currency":"USDT",
        "start_date": "2026-09-01",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_balance_history_end_date_sent(api_client):
    response=api_client.get(reverse("analytics:balance-history"),{
        "currency":"USDT",
        "end_date": "2026-09-01",
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Both start_date and end_date are required."

@pytest.mark.django_db
def test_balance_history_invalid_date_range(api_client, ledger_entries):
    response = api_client.get(
        reverse("analytics:balance-history"),
        {
            "currency": "USDT",
            "start_date": "2026-09-30",
            "end_date": "2026-09-01",
        },
    )

    assert response.status_code == 400
    assert response.data["detail"] == "start_date cannot be after end_date."

@pytest.mark.django_db
def test_balance_history_wallet_not_found(api_client):
    response=api_client.get(reverse("analytics:balance-history"),{
        "currency":"XYZ",
        "start_date": "2026-09-30",
        "end_date": "2026-10-01",
    })
    assert response.status_code == 404
    assert response.data["detail"] == "Wallet not found."

@pytest.mark.django_db
def test_ai_summary_view(financial_summary_data,api_client):

    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "period":"week"
    })
    assert response.status_code == 200
    assert response.data["currency"] == "USDT"
    assert response.data["period"] == "week"
    assert response.data["income"] == "3000.00000000"
    assert response.data["expense"] == "1050.00000000"
    assert response.data["net"] == "1950.00000000"
    assert "start_date" in response.data
    assert "end_date" in response.data
    assert "expenses_by_category" in response.data

    assert isinstance(response.data["expenses_by_category"], dict)
    assert isinstance(response.data["summary"], str)
    assert isinstance(response.data["insights"], list)
    assert isinstance(response.data["recommendations"], list)

@pytest.mark.django_db
def test_ai_summary_view_with_custom_dates(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "start_date":"2026-01-05",
        "end_date":"2026-11-08",
    })
    assert response.status_code == 200
    assert response.data["currency"] == "USDT"
    assert response.data["start_date"].startswith("2026-01-05")
    assert response.data["end_date"].startswith("2026-11-09")
    assert "income" in response.data
    assert "expense" in response.data
    assert "expenses_by_category" in response.data
    assert isinstance(response.data["expenses_by_category"], dict)
    assert isinstance(response.data["summary"], str)
    assert isinstance(response.data["insights"], list)
    assert isinstance(response.data["recommendations"], list)

@pytest.mark.django_db
def test_ai_summary_view_currency_required(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "period":"year"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "currency is required."

@pytest.mark.django_db
def test_ai_summary_view_with_custom_range_and_period(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "period":"month",
        "start_date":"2026-01-01",
        "end_date":"2026-01-30",
        "currency":"USDT"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Use either period or start_date/end_date, not both."

@pytest.mark.django_db
def test_ai_summary_view_invalid_date_format(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "start_date":"20-01-2026",
        "end_date":"2026-01-30"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Dates must be in YYYY-MM-DD format."

@pytest.mark.django_db
def test_ai_summary_view_end_date_before_start_date(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "start_date":"2026-02-01",
        "end_date":"2026-01-20"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "start_date cannot be after end_date."

@pytest.mark.django_db
def test_ai_summary_view_wallet_not_found(api_client,financial_summary_data):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"XYZ",
        "period":"month"
    })
    assert response.status_code == 404
    assert response.data["detail"] == "Wallet not found."

@pytest.mark.django_db
def test_ai_summary_view_only_start_date_sent(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "start_date":"2026-01-30"
    })
    assert response.status_code == 400
    assert response.data["detail"] =="Both start_date and end_date are required."

@pytest.mark.django_db
def test_ai_summary_view_only_end_date_sent(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "end_date":"2026-01-30"
    })
    assert response.status_code == 400
    assert response.data["detail"] =="Both start_date and end_date are required."

@pytest.mark.django_db
def test_ai_summay_view_authentication_error(financial_summary_data):
    client=APIClient()
    response=client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "start_date":"2026-01-05",
        "end_date":"2026-11-08",
    })
    assert response.status_code == 401 # type: ignore

@pytest.mark.django_db
def test_ai_summary_view_invalid_period(financial_summary_data,api_client):
    response=api_client.get(reverse("analytics:ai-summary"),{
        "currency":"USDT",
        "period":"invalid"
    })
    assert response.status_code == 400
    assert response.data["detail"] == "Invalid period"

@pytest.mark.django_db
def test_ai_summary_view_without_transactions(
    user,
    wallets,
    api_client,
):
    with patch(
        "apps.analytics.views.generate_financial_summary",
    ) as mock_ai:
        response = api_client.get(
            reverse("analytics:ai-summary"),
            {
                "currency": "USDT",
                "period": "month",
            },
        )

    assert response.status_code == 200

    assert response.data["currency"] == "USDT"
    assert response.data["period"] == "month"

    assert response.data["income"] == "0.00000000"
    assert response.data["expense"] == "0.00000000"
    assert response.data["net"] == "0.00000000"
    assert response.data["expenses_by_category"] == {}

    assert response.data["summary"] == "No financial activity recorded."
    assert response.data["insights"] == [
        "Insufficient data for financial analysis."
    ]
    assert response.data["recommendations"] == [
        "Record transactions to enable analysis."
    ]

    mock_ai.assert_not_called()

@pytest.mark.django_db
def test_ai_summary_view_ai_service_unavailable(
    financial_summary_data,
    api_client,
):
    with patch(
        "apps.analytics.views.generate_financial_summary",
        side_effect=httpx.HTTPError("AI service unavailable")
    )as mock_ai:
        response=api_client.get(reverse("analytics:ai-summary"),{
                "currency": "USDT",
                "period": "week",
        })
        assert response.status_code  == 503
        assert response.data["detail"] == "AI financial summary is temporarily unavailable."
        mock_ai.assert_called_once()