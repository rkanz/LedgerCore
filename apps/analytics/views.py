import json
import logging
from datetime import datetime

import httpx
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,  # type: ignore
    extend_schema,
)
from pydantic import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.schemas import FinancialSummaryOutput
from apps.ai.services import generate_financial_summary
from apps.analytics.serializers import AISummarySerializer
from apps.wallets.models import Wallet

from .services import (
    get_balance_history,
    get_expense,
    get_financial_summary,
    get_income,
    get_monthly_report,
    get_summary,
    resolve_date_range,
)

logger = logging.getLogger(__name__)

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
        ),400:OpenApiResponse(
            description="Invalid request parameters, including missing currency, "
                "missing start_date or end_date or invalid date format. "
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


@extend_schema(
    summary="Get AI financial summary",
    description=(
        "Returns a financial summary for the authenticated user's "
        "selected wallet and date range. If both income and expense "
        "are zero, a predefined response is returned without calling "
        "the AI service."
        ),
    tags=["Analytics"],
    parameters=[
        OpenApiParameter(
            name="currency",
            type=str,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Wallet currency e.g. USDT"
        ),
        OpenApiParameter(
            name="period",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Predefined reporting period. Cannot be combined with start_date or end_date.",
            enum=["week","month","year"],
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
    ],responses={
        200:AISummarySerializer,
        400:OpenApiResponse(
            description="Invalid query parameters or date range."
        ),401:OpenApiResponse(
            description="Authentication is required."
        ),404:OpenApiResponse(
            description="Wallet not found."
        ),503:OpenApiResponse(
            description="AI financial summary service unavailable."
        )
    },
    examples=[
        OpenApiExample(
            name="Monthly financial summary",
            summary="Successful response",
            value={
                "currency": "USDT",
                "start_date": "2026-10-01T00:00:00Z",
                "end_date": "2026-11-01T00:00:00Z",
                "period": "month",
                "income": "3000.00000000",
                "expense": "1050.00000000",
                "net": "1950.00000000",
                "expenses_by_category": {
                    "FOOD": "350.00000000",
                    "TRANSPORT": "120.00000000",
                },
                "summary": "Your income exceeded your expenses during this period.",
                "insights": [
                    "Your net balance was positive."
                ],
                "recommendations": [
                    "Review your spending by category."
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            name="No financial activity",
            summary="Predefined response when income and expense are zero",
            value={
                "currency": "USDT",
                "start_date": "2026-10-01T00:00:00Z",
                "end_date": "2026-11-01T00:00:00Z",
                "period": "month",
                "income": "0.00000000",
                "expense": "0.00000000",
                "net": "0.00000000",
                "expenses_by_category": {},
                "summary": "No financial activity recorded.",
                "insights": [
                    "Insufficient data for financial analysis."
                ],
                "recommendations": [
                    "Record transactions to enable analysis."
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            name="AI service unavailable",
            value={
                "detail": "AI financial summary is temporarily unavailable."
            },
            response_only=True,
            status_codes=["503"],
        ),
    ],
)
class AISummaryAPIView(APIView):
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
            financial_data = get_financial_summary(
                wallet=wallet,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                period=period,
            )
        except (ValueError, OverflowError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
        )
        if (
            financial_data["income"] == 0
            and financial_data["expense"] == 0
        ):
            ai_summary = FinancialSummaryOutput(
                summary="No financial activity recorded.",
                insights=["Insufficient data for financial analysis."],
                recommendations=["Record transactions to enable analysis."],
            )
        else:
            try:
                ai_summary = generate_financial_summary(
                    financial_data=financial_data,
                )

            except (
                httpx.HTTPError,
                json.JSONDecodeError,
                ValidationError,
                KeyError,
                IndexError,
                TypeError,
            ):
                logger.exception(
                    "AI financial summary generation failed."
                )
                return Response(
                    {
                        "detail": (
                            "AI financial summary is temporarily unavailable."
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        if parsed_start_date is not None:
            resolved_period = "custom"
        else:
            resolved_period = period or "month"
        response_data = {
            "currency": wallet.currency,
            "start_date": financial_data["start_datetime"],
            "end_date": financial_data["end_datetime"],
            "period": resolved_period,
            "income": financial_data["income"],
            "expense": financial_data["expense"],
            "net": financial_data["net"],
            "expenses_by_category": financial_data["expenses_by_category"],
            "summary": ai_summary.summary,
            "insights": ai_summary.insights,
            "recommendations": ai_summary.recommendations,
        }
        serializer=AISummarySerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

ai_summary_view=AISummaryAPIView.as_view()