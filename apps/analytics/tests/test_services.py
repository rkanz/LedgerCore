from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.analytics.services import (
    get_balance_history,
    get_date_range,
    get_expense,
    get_income,
    get_month_date_range,
    get_monthly_report,
    get_summary,
    resolve_date_range,
)
from apps.transactions.models import LedgerEntry
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_get_income(wallets,ledger_entries):
    wallet=wallets[Wallet.Currency.USDT]
    start_date,end_date=resolve_date_range(period="month")
    income=get_income(
        wallet=wallet,
        start_date=start_date,
        end_date=end_date
    )
    assert income == Decimal("100")

@pytest.mark.django_db
def test_get_expense(wallets,ledger_entries):
    wallet=wallets[Wallet.Currency.USDT]
    start_date,end_date=resolve_date_range(period="month")
    expense=get_expense(
        wallet=wallet,
        start_date=start_date,
        end_date=end_date
    )
    assert expense == Decimal("50")

@pytest.mark.django_db
def test_get_summary(wallets,ledger_entries):
    wallet=wallets[Wallet.Currency.USDT]
    start_date,end_date=resolve_date_range(period="month")
    summary=get_summary(
        wallet=wallet,
        start_date=start_date,
        end_date=end_date
    )
    assert summary["income"] == Decimal("100")
    assert summary["expense"] == Decimal("50")
    assert summary == {
    "income": Decimal("100"),
    "expense": Decimal("50"),
    }
@pytest.mark.django_db
def test_get_date_range_week():
    start_date,end_date=get_date_range("week")
    assert end_date - start_date == timedelta(days=7)

@pytest.mark.django_db
def test_get_date_range_month():
    start_date,end_date=get_date_range("month") # noqa: RUF059
    assert start_date.day == 1
    assert start_date.hour == 0
    assert start_date.minute == 0
    assert start_date.second == 0

@pytest.mark.django_db
def test_get_date_range_year():
    start_date,end_date=get_date_range("year")  # noqa: RUF059
    assert start_date.month == 1
    assert start_date.day == 1
    assert start_date.hour == 0
    assert start_date.minute == 0
    assert start_date.second == 0

def test_resolve_date_range_custom():
    start_date=date(2026,6,1)
    end_date=date(2026,11,15)
    start_datetime,end_datetime=resolve_date_range(
        start_date=start_date,
        end_date=end_date
    )
    assert start_datetime.date() == date(2026,6,1)
    assert start_datetime.hour == 0
    assert start_datetime.minute == 0
    assert end_datetime.date() == date(2026,11,16)
    assert end_datetime.hour == 0
    assert end_datetime.minute == 0

@pytest.mark.django_db
def test_resolve_date_range_invalid():
    start_date=date(2027,1,1)
    end_date=date(2026,1,15)
    with pytest.raises(
        ValueError,
        match="start_date cant be after end_date ."
    ):
        resolve_date_range(
            start_date=start_date,
            end_date=end_date
        )

@pytest.mark.django_db
def test_resolve_date_range_missing_date():
    with pytest.raises(
        ValueError,
        match="Both start_date and end_date are required."
    ):
        resolve_date_range(
            start_date=date(2026,1,1)
        )
    with pytest.raises(
        ValueError,
        match="Both start_date and end_date are required."
    ):
        resolve_date_range(
            end_date=date(2026,1,1)
        )
        
@pytest.mark.django_db
def test_resolve_date_range_invalid_start_date():
    start_date=date(2026,1,1)
    end_date=date(2025,2,3)
    with pytest.raises(
        ValueError,
        match="start_date cant be after end_date ."
    ):
        resolve_date_range(
            start_date=start_date,
            end_date=end_date
        )
            

@pytest.mark.django_db
def test_get_range_invalid_period():
    with pytest.raises(
        ValueError,
        match="Invalid period"
    ):
        get_date_range("invalid")

@pytest.mark.django_db
def test_get_month_date_range():
    start_date,end_date=get_month_date_range("2026-07")
    tz = timezone.get_current_timezone()
    assert start_date == datetime(2026, 7, 1, 0, 0, tzinfo=tz)
    assert end_date == datetime(2026, 8, 1, 0, 0, tzinfo=tz)

@pytest.mark.django_db
def test_get_month_date_range_invalid_format():
    with pytest.raises(
        ValueError,
        match="Invalid month format. Use YYYY-MM."
    ):
        get_month_date_range("2026-13")

@pytest.mark.django_db
def test_get_month_date_range_december():
    start_date,end_date=get_month_date_range("2026-12")
    tz = timezone.get_current_timezone()
    assert start_date == datetime(2026, 12, 1, 0, 0, tzinfo=tz)
    assert end_date == datetime(2027, 1, 1, 0, 0, tzinfo=tz)

@pytest.mark.django_db
def test_get_month_date_range_invalid_month():
    with pytest.raises(
        ValueError,
        match="Invalid month format. Use YYYY-MM."
    ):
        get_month_date_range("2026/7")


@pytest.mark.django_db
def test_get_monthly_report(wallets,user,ledger_entries):
    wallet=wallets[Wallet.Currency.USDT]
    current_month = timezone.localdate().strftime("%Y-%m")
    result = get_monthly_report(wallet, current_month)
    assert result["income"] == Decimal("100")
    assert result["expense"] == Decimal("50")
    assert result["expenses_by_category"] == {"OTHER":Decimal("50")}

@pytest.mark.django_db
def test_get_monthly_report_multiple_categories(wallets,user,ledger_entries_multiple_categories):
    wallet=wallets[Wallet.Currency.USDT]
    current_month = timezone.localdate().strftime("%Y-%m")
    result = get_monthly_report(wallet, current_month)
    assert result["expense"] == Decimal("80")
    assert result["expenses_by_category"] == {"FOOD":Decimal("50"),"HEALTH":Decimal("30")}
    assert result["income"] == Decimal("0")

@pytest.mark.django_db
def test_get_monthly_report_no_transaction(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    result=get_monthly_report(wallet,"2025-05")
    assert result["expense"] == Decimal("0")
    assert result["income"] == Decimal("0")
    assert result["expenses_by_category"] == {}


@pytest.mark.django_db
def test_get_balance_history(user,wallets,create_ledger_entry,):
    wallet=wallets[Wallet.Currency.USDT]
    create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="1000",
        entry_type=LedgerEntry.EntryType.CREDIT,
        created_at=timezone.make_aware(
            datetime(2026, 5, 30, 12, 0) # noqa: DTZ001
        )
    )
    create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="200",
        entry_type=LedgerEntry.EntryType.CREDIT,
        created_at=timezone.make_aware(
            datetime(2026, 6, 2, 12, 0) # noqa: DTZ001
        ),
    )
    create_ledger_entry(
        user=user,
        wallet=wallet,
        amount="300",
        entry_type=LedgerEntry.EntryType.DEBIT,
        created_at=timezone.make_aware(
            datetime(2026, 6, 4, 12, 0) # noqa: DTZ001
        ),
    )
    history = get_balance_history(
        user=user,
        currency=Wallet.Currency.USDT,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 5),
    )
    assert history == [
        {
            "date": date(2026, 6, 1),
            "balance": Decimal("1000"),
        },
        {
            "date": date(2026, 6, 2),
            "balance": Decimal("1200"),
        },
        {
            "date": date(2026, 6, 4),
            "balance": Decimal("900"),
        },
    ]

@pytest.mark.django_db
def test_get_balance_history_combines_entries_from_same_day(user,wallets,create_ledger_entry,):
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
    history=get_balance_history(
        user=user,
        currency=Wallet.Currency.USDT,
        start_date=date(2026,6,1),
        end_date=date(2026,6,4)
    )
    assert history ==  [
        {
            "date": date(2026, 6, 1),
            "balance": Decimal("300"),
        },
        {
            "date":date(2026,6,3),
            "balance":Decimal("400")
        }
    ]
  