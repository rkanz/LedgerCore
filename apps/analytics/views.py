from datetime import datetime

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,  # type: ignore
    extend_schema,
)
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.wallets.models import Wallet

from .services import (
    get_balance_history,
    get_expense,
    get_income,
    get_monthly_report,
    get_summary,
    resolve_date_range,
)


@extend_schema(
    summary="Get income report",
    description="""
    Returns the income report for the user's wallet in the selected currency
    and date range. The date range can be selected using a predefined period
    (week, month, or year) or a custom start_date and end_date.
    """,
    tags=["Analytics"],
    responses={
        200:OpenApiResponse(
            description="Income report returned successfully."
        ),
        400:OpenApiResponse(
            description="Invalid request parameters, including missing currency, "
                "missing start_date or end_date, conflicting period and "
                "custom date range, or invalid date format."
        ),404:OpenApiResponse(
            description="Wallet not found."
        )
    },
    parameters=[
        OpenApiParameter(
            name="currency",
            description="Wallet currency e.g. USDT.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Predefined period: week, month, or year.",
            required=False
        ),
        OpenApiParameter(
            name="start_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Start date in YYYY-MM-DD format.",
            required=False
        ), OpenApiParameter(
            name="end_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="End date in YYYY-MM-DD format.",
            required=False,

        )
    ],examples=[
        OpenApiExample(
            "Successful income response",
            summary="Get income",
            value={
            "currency":"USDT",
            "period": "week",
            "income":"100.00000000",
            "start_date":"2026-07-01T00:00:00Z",
            "end_date":"2026-07-08T00:00:00Z",
            },response_only=True
        )
    ]
)
class IncomeAPIView(APIView):
    def get(self,request):
        currency=request.query_params.get("currency")
        period=request.query_params.get("period")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not currency:
            return Response(
                {"detail": "currency is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if period and (start_date or end_date):
            return Response(
                {
                    "detail": (
                        "Use either period or start_date/end_date, "
                        "not both."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start_date = None
        parsed_end_date = None
        if start_date or end_date:
            if not start_date or not end_date:
                return Response(
                    {
                        "detail": (
                            "Both start_date and end_date "
                            "are required."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                parsed_start_date = datetime.strptime(  # noqa: DTZ007
                        start_date,
                        "%Y-%m-%d",).date()

                parsed_end_date = datetime.strptime(  # noqa: DTZ007
                        end_date,
                        "%Y-%m-%d",).date()
            except ValueError:
                    return Response(
                        {
                            "detail": (
                                "Dates must be in YYYY-MM-DD format."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        wallet=Wallet.objects.filter(
            user=request.user,
            currency=currency,
            is_active=True
        ).first()
        if wallet is None:
            return Response(
                {"detail": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
        )
        try:
            start_datetime, end_datetime = resolve_date_range(
                period=period,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        income=get_income(wallet,start_datetime, end_datetime)
        return Response({
            "currency":wallet.currency,
            "period": period or ("custom" if parsed_start_date else "month"),
            "income":income,
            "start_date":start_datetime,
            "end_date":end_datetime,

        })

income_view=IncomeAPIView.as_view()

@extend_schema(
    summary="Get expense report",
    description="""
    Returns the expense report for the user's wallet in the selected currency
    and date range. The date range can be selected using a predefined period
    (week, month, or year) or a custom start_date and end_date.
    """,
    tags=["Analytics"],
    responses={
        200:OpenApiResponse(
            description="Expense report returned successfully."
        ),
        400:OpenApiResponse(
            description="Invalid request parameters, including missing currency, "
                "missing start_date or end_date, conflicting period and "
                "custom date range, or invalid date format."
        ),404:OpenApiResponse(
            description="Wallet not found."
        )
    },
    parameters=[
        OpenApiParameter(
            name="currency",
            description="Wallet currency e.g. USDT.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Predefined period: week, month, or year.",
            required=False
        ),
        OpenApiParameter(
            name="start_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Start date in YYYY-MM-DD format.",
            required=False
        ), OpenApiParameter(
            name="end_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="End date in YYYY-MM-DD format.",
            required=False,

        )
    ],examples=[
        OpenApiExample(
            "Successful expense response",
            summary="Get expense",
            value={
            "currency":"USDT",
            "period": "week",
            "expense":"100.00000000",
            "start_date":"2026-07-01T00:00:00Z",
            "end_date":"2026-07-08T00:00:00Z",
            },response_only=True
        )
    ]
)
class ExpenseAPIView(APIView):
    def get(self,request):
        currency=request.query_params.get("currency")
        period = request.query_params.get("period")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not currency:
            return Response(
                {"detail": "currency is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if period and (start_date or end_date):
            return Response(
                {
                    "detail": (
                        "Use either period or start_date/end_date, "
                        "not both."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start_date = None
        parsed_end_date = None
        if start_date or end_date:
            if not start_date or not end_date:
                return Response(
                    {
                        "detail": (
                            "Both start_date and end_date "
                            "are required."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                parsed_start_date = datetime.strptime(  # noqa: DTZ007
                        start_date,
                        "%Y-%m-%d",).date()

                parsed_end_date = datetime.strptime(  # noqa: DTZ007
                        end_date,
                        "%Y-%m-%d",).date()
            except ValueError:
                    return Response(
                        {
                            "detail": (
                                "Dates must be in YYYY-MM-DD format."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        wallet=Wallet.objects.filter(
            user=request.user,
            currency=currency,
            is_active=True
        ).first()
        if wallet is None:
            return Response(
                {"detail": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
        )
        try:
            start_datetime, end_datetime = resolve_date_range(
                period=period,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        expense=get_expense(wallet,start_datetime, end_datetime)
        return Response({
            "currency":wallet.currency,
            "period": period or ("custom" if parsed_start_date else "month"),
            "expense":expense,
            "start_date":start_datetime,
            "end_date":end_datetime,

        })
expense_view=ExpenseAPIView.as_view()

@extend_schema(
    summary="Get Summary report",
    description="""
    Returns the summary report of income & expense for the user's wallet in the selected currency
    and date range. The date range can be selected using a predefined period
    (week, month, or year) or a custom start_date and end_date.
    """,
    tags=["Analytics"],
    responses={
        200:OpenApiResponse(
            description="Summary report returned successfully."
        ),
        400:OpenApiResponse(
            description="Invalid request parameters, including missing currency, "
                "missing start_date or end_date, conflicting period and "
                "custom date range, or invalid date format."
        ),404:OpenApiResponse(
            description="Wallet not found."
        )
    },
    parameters=[
        OpenApiParameter(
            name="currency",
            description="Wallet currency e.g. USDT.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Predefined period: week, month, or year.",
            required=False
        ),
        OpenApiParameter(
            name="start_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Start date in YYYY-MM-DD format.",
            required=False
        ), OpenApiParameter(
            name="end_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="End date in YYYY-MM-DD format.",
            required=False,

        )
    ],examples=[
        OpenApiExample(
            "Successful summary response",
            summary="Get summary",
            value={
            "currency":"USDT",
            "period": "week",
            "summary":{
                "income":"100.00000000",
                "expense":"50.00000000"
            },
            "start_date":"2026-07-01T00:00:00Z",
            "end_date":"2026-07-08T00:00:00Z",
            },response_only=True
        )
    ]
)
class SummaryAPIView(APIView):
    def get(self,request):
        currency=request.query_params.get("currency")
        period=request.query_params.get("period")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not currency:
            return Response(
                {"detail": "currency is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if period and (start_date or end_date):
            return Response(
                {
                    "detail": (
                        "Use either period or start_date/end_date, "
                        "not both."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        parsed_start_date = None
        parsed_end_date = None
        if start_date or end_date:
            if not start_date or not end_date:
                return Response(
                    {
                        "detail": (
                            "Both start_date and end_date "
                            "are required."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                parsed_start_date = datetime.strptime(  # noqa: DTZ007
                        start_date,
                        "%Y-%m-%d",).date()

                parsed_end_date = datetime.strptime(  # noqa: DTZ007
                        end_date,
                        "%Y-%m-%d",).date()
            except ValueError:
                    return Response(
                        {
                            "detail": (
                                "Dates must be in YYYY-MM-DD format."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        wallet=Wallet.objects.filter(
            user=request.user,
            currency=currency,
            is_active=True
        ).first()
        if wallet is None:
            return Response(
                {"detail": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
        )
        try:
            start_datetime, end_datetime = resolve_date_range(
                period=period,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        summary=get_summary(wallet,start_datetime,end_datetime)
        return Response(
            {
                "currency":wallet.currency,
                "start_date":start_datetime,
                "end_date":end_datetime,
                "summary":summary,
                "period":period or ("custom" if parsed_start_date else "month"),
            }
        )
summary_view=SummaryAPIView.as_view()

@extend_schema(
    summary="Get monthly report",
    description="Returns monthly report for user's wallet in the selected currency and month.",
    tags=["Analytics"],
    responses={
        200:OpenApiResponse(
            description="Monthly report returned successfully."
        ),400:OpenApiResponse(
            description="Invalid request parameters, including missing currency," 
                "missing month or invalid date format. "
        ),404:OpenApiResponse(
            description="Wallet not found."
        )
    },parameters=[
        OpenApiParameter(
            name="currency",
            description="Wallet currency e.g. USDT.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),OpenApiParameter(
            name="month",
            description="Month in YYYY-MM Format e.g. 2026-07.",
            type=OpenApiTypes.STR,
            required=False
        )
    ],examples=[
        OpenApiExample(
            "Successful monthly report response",
            summary="Get monthly report",
            value={                            
            "currency":"USDT",
            "month":"2026-07",
            "income":"1000.00000000",
            "expense":"800.00000000",
            "expenses_by_category":{
                "FOOD":"150.00000000",
                "HEALTH":"250.00000000",
                "OTHER":"400.00000000"
            }
        },response_only=True
        )
    ]
)
class MonthlyReportAPIView(APIView):
    def get(self,request):
        currency=request.query_params.get("currency")
        month=request.query_params.get("month")
        if not currency:
            return Response({
                "detail":"currency is required."
            },status=status.HTTP_400_BAD_REQUEST)
        wallet=Wallet.objects.filter(
            user=request.user,
            is_active=True,
            currency=currency,
        ).first()
        if wallet is None:
            return Response({
                "detail":"Wallet not found."
            },status=status.HTTP_404_NOT_FOUND)
        if month is None:
            month = timezone.now().strftime("%Y-%m")
        try:
            report=get_monthly_report(wallet,month)
        except ValueError as exc:
            return Response({
                "detail":str(exc)
            },status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "currency":wallet.currency,
            "month":month,
            "income":report["income"],
            "expense":report["expense"],
            "expenses_by_category":report["expenses_by_category"]
        })

monthly_report_view=MonthlyReportAPIView.as_view()

@extend_schema(
    summary="Get balance history",
    description="""
    Returns the balance history report for the user's wallet in the selected currency
    and date range. The date range can be selected using start_date and end_date.
    """,
    tags=["Analytics"],
    responses={
        200:OpenApiResponse(
            description="Balance history report returned successfully."
        ),400:OpenApiResponse("Invalid request parameters, including missing currency, "
                "missing start_date or end_date or invalid date format. "
        ),404:OpenApiResponse(
            "Wallet not found."
        )
    },
    parameters=[
        OpenApiParameter(
            name="currency",
            description="Wallet currency e.g. USDT.",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            required=True,
        ),
        OpenApiParameter(
            name="start_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="Start date in YYYY-MM-DD format.",
            required=True
        ), OpenApiParameter(
            name="end_date",
            type=OpenApiTypes.DATE,
            location=OpenApiParameter.QUERY,
            description="End date in YYYY-MM-DD format.",
            required=True,
        )        
    ],examples=[
        OpenApiExample(
            "Successful balance history response",
            summary="Get balance history",
            value=[
        {
            "date": "2026-06-01",
            "balance": "300.00000000",
        },
        {
            "date":"2026-06-03",
            "balance":"400.00000000"
        }
    ],response_only=True,           
        )
    ]
)
class BalanceHistoryAPIView(APIView):
    def get(self, request):
        currency = request.query_params.get("currency")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not currency:
            return Response(
                {"detail": "currency is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not start_date or not end_date:
            return Response(
                {"detail": "Both start_date and end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed_start_date = datetime.strptime(  # noqa: DTZ007
                start_date,
                "%Y-%m-%d",
            ).date()

            parsed_end_date = datetime.strptime(  # noqa: DTZ007
                end_date,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return Response(
                {"detail": "Dates must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed_start_date > parsed_end_date:
            return Response(
                {"detail": "start_date cannot be after end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            history = get_balance_history(
                user=request.user,
                currency=currency,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
            )
        except Wallet.DoesNotExist:
            return Response(
                {"detail": "Wallet not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            history,
            status=status.HTTP_200_OK,
        )
balance_history_view=BalanceHistoryAPIView.as_view()