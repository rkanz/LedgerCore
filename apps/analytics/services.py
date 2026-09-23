from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.transactions.models import LedgerEntry
from apps.wallets.models import Wallet


def get_income(
    wallet:Wallet,
    start_date,
    end_date,
)-> Decimal:
    result=LedgerEntry.objects.filter(
        wallet=wallet,
        entry_type=LedgerEntry.EntryType.CREDIT,
        created_at__gte=start_date,
        created_at__lt=end_date,
    ).aggregate(income=Sum("amount"))
    return result["income"] or Decimal("0")

def get_date_range(period:str) -> tuple[datetime, datetime]:
    now=timezone.now()
    if period == "week":
        start_date=now-timedelta(days=7)
    elif period == "month":
        start_date=now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    elif period == "year":
        start_date = now.replace(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    else:
        raise ValueError("Invalid period")
    return start_date,now

def resolve_date_range(
    period: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[datetime, datetime]:
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError(
                "Both start_date and end_date are required."
            )
        if start_date > end_date :
            raise ValueError("start_date cant be after end_date .")
        tz=timezone.get_current_timezone()
        start_datetime = timezone.make_aware(
            datetime.combine(
                start_date,
                time.min,
            ),
            timezone=tz,
        )
        end_datetime=timezone.make_aware(
        datetime.combine(
            end_date + timedelta(days=1),
            time.min
        ),
        timezone=tz
    )
        return start_datetime,end_datetime
    return get_date_range(period or "month")

def get_expense(
    wallet:Wallet,
    start_date,
    end_date,
)-> Decimal:
    result=LedgerEntry.objects.filter(
        wallet=wallet,
        entry_type=LedgerEntry.EntryType.DEBIT,
        created_at__gte=start_date,
        created_at__lt=end_date,
    ).aggregate(expense=Sum("amount"))
    return result["expense"] or Decimal("0")

def get_summary(
        wallet:Wallet,
        start_date:datetime,
        end_date:datetime,
)-> dict[str, Decimal]:
    result=LedgerEntry.objects.filter(
            wallet=wallet,
            created_at__gte=start_date,
            created_at__lte=end_date
    ).aggregate(income=Sum(Case(When(
        entry_type=LedgerEntry.EntryType.CREDIT,
        then="amount"
    ),default=Decimal("0"),
    output_field=DecimalField(
        max_digits=20,decimal_places=8
                ),
            ),
        ),
    expense=Sum(Case(When(
        entry_type=LedgerEntry.EntryType.DEBIT,
        then="amount"
    ),
        default=Decimal("0"),
        output_field=DecimalField(
            max_digits=20,decimal_places=8)
                  ),
        ),
    )
    return {
        "income": result["income"] or Decimal("0"),
        "expense": result["expense"] or Decimal("0"),
    }

def get_month_date_range(month) -> tuple[datetime, datetime]:
    try:
        year,month_number=map(int,month.split("-"))
        tz=timezone.get_current_timezone()
        start_date=datetime(year,month_number,1, tzinfo=tz)
    except (ValueError,TypeError):
        raise ValueError("Invalid month format. Use YYYY-MM.")
    if month_number == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_date=datetime(year,month_number+1,1,tzinfo=tz)

    return start_date,end_date

def get_monthly_report(wallet,month):
    start_date,end_date=get_month_date_range(month)
    income=get_income(
        wallet=wallet,
        start_date=start_date,
        end_date=end_date
    )
    expense=get_expense(
        wallet=wallet,
        start_date=start_date,
        end_date=end_date
    )
    expenses_by_category=(
        LedgerEntry.objects.filter(
            wallet=wallet,
            entry_type=LedgerEntry.EntryType.DEBIT,
            created_at__gte=start_date,
            created_at__lt=end_date,
        ).values("transaction__category").annotate(total=Sum("amount"))
    )
    expenses_by_category={
        item["transaction__category"]:item["total"]
        for item in expenses_by_category
    }
    return {
        "income":income,
        "expense":expense,
        "expenses_by_category":expenses_by_category
    }

def get_balance_history(user,currency,start_date,end_date):
    wallet=Wallet.objects.get(
        user=user,currency=currency
    )
    opening_balance=(
        LedgerEntry.objects.filter(
            wallet=wallet,
            created_at__date__lt=start_date
        ).aggregate(
            balance=Sum(
                Case(
                    When(
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        then=F("amount")
                    ),
                    When(
                        entry_type=LedgerEntry.EntryType.DEBIT,
                        then=-F("amount")
                    ),
                    default=Value(0),
                    output_field=DecimalField(
                        max_digits=20,decimal_places=8
                    ),
                )
            )
        )["balance"]
    )or 0
    daily_changes=(
        LedgerEntry.objects.filter(
            wallet=wallet,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).annotate(date=TruncDate("created_at")).values("date").annotate(
            change=Sum(
                Case(
                    When(
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        then=F("amount")
                    ),When(
                        entry_type=LedgerEntry.EntryType.DEBIT,
                        then=-F("amount")
                    ),default=Value(0),
                    output_field=DecimalField(
                        decimal_places=8,max_digits=20
                    )
                )
            )
        ).order_by("date")
    )
    history=[
        {
            "date":start_date,
            "balance":opening_balance
        }
    ]
    current_balance=opening_balance
    for daily_change in daily_changes:
        current_balance+=daily_change["change"]
        if current_balance != history[-1]["balance"]:
            history.append(
                {
                    "date":daily_change["date"],
                    "balance":current_balance
                }
            )
    return history