import uuid

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
     OpenApiExample,
     OpenApiParameter,
     OpenApiResponse,
     OpenApiTypes,  # type: ignore
     extend_schema,
)
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.exchange.cache import EXCHANGE_RATE_TTL, exchange_rate_list_cache_key
from apps.exchange.models import ExchangeRate
from apps.exchange.serializers import (
     ExchangeRateSerializer,
     ExchangeSerializer,
     ExchangeTransactionSerializer,
)
from apps.exchange.services import exchange
from apps.wallets.models import Wallet


class ExchangeRatePagination(PageNumberPagination):
     page_size=10

@extend_schema(
    summary="Get exchange rates",
    description="""
    Returns available exchange rate snapshots.
    Supports filtering by base and quote currency,
    ordering by rate or fetched time, and pagination.
    Authentication is required.
    Results are cached using Redis.
    """,
    tags=["Exchange"],
    responses={
        200:ExchangeRateSerializer(many=True),
        401:OpenApiResponse(
            description="Authentication credentials were not provided."
        )
    }
)
class ExchangeRateListAPIView(generics.ListAPIView):
    serializer_class=ExchangeRateSerializer
    pagination_class=ExchangeRatePagination
    filter_backends=[DjangoFilterBackend,OrderingFilter]
    filterset_fields=["base_currency","quote_currency"]
    ordering_fields=["rate","fetched_at"]
    def get_queryset(self):
        return ExchangeRate.objects.all().order_by("-fetched_at")
    def list(self,request,*args,**kwargs):
        cache_key=exchange_rate_list_cache_key(request.get_full_path())
        cached_data=cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        queryset=self.filter_queryset(self.get_queryset())
        page=self.paginate_queryset(queryset)
        if page is not None:
            serializer=self.get_serializer(page,many=True)
            response=self.get_paginated_response(serializer.data)
            cache.set(cache_key,response.data,timeout=EXCHANGE_RATE_TTL)
            return response
        serializer=self.get_serializer(queryset,many=True)
        cache.set(cache_key,serializer.data,timeout=EXCHANGE_RATE_TTL)
        return Response(serializer.data)
exchange_rate_list_view=ExchangeRateListAPIView.as_view()

@extend_schema(
    summary="Exchange different currencies",
    description="""
    Exchange an amount from one currency wallet to another
    currency wallet belonging to the authenticated user.

    The exchange rate and fee are calculated server-side.
    The Idempotency-Key header is required to prevent duplicate
    exchange transaction
    """,
    tags=["Exchange"],
    request=ExchangeSerializer,
    responses={
        201:ExchangeTransactionSerializer,
        400:OpenApiResponse(
            description='Invalid idempotency-key,insufficient wallet balance,invalid request,' 
            'unavailable exchange rate.'
        ),
        404:OpenApiResponse(
            description="Wallet not found."
        ),
        401:OpenApiResponse(
            description="Authentication credentials were not provided."
        )
    },
    parameters=[
         OpenApiParameter(
         name="Idempotency-Key",
         type=OpenApiTypes.UUID,
         location=OpenApiParameter.HEADER,
         description="Unique key used to prevent duplicate exchange.",
         required=True
        )],
    examples=[
        OpenApiExample(
            "Exchange EUR To USD",
            summary="Exchange 100 EUR to USD",
            description="Example request for exchanging 100 EUR from EUR wallet "
            "to USD wallet.",
            value={
                "source_currency": "EUR",
                "destination_currency": "USD",
                "amount": "100"
            },request_only=True
        )
    ]
)
class ExchangeTransactionAPIView(APIView):
    def post(self,request):

        idempotency_key_raw=request.headers.get(
            'Idempotency-key'
        )
        if not idempotency_key_raw:
            return Response(
            {'detail':'Idempotency-Key header is required.'},status=status.HTTP_400_BAD_REQUEST)
        try:
            idempotency_key=uuid.UUID(idempotency_key_raw)
        except ValueError:
            return Response({
            'detail':'Idempotency-Key must be a valid UUID.'
            },status=status.HTTP_400_BAD_REQUEST)
        serializer=ExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_currency=serializer.validated_data["source_currency"] # type: ignore
        destination_currency=serializer.validated_data["destination_currency"] # type: ignore
        amount=serializer.validated_data["amount"] # type: ignore
        source_wallet=get_object_or_404(
            Wallet,
            user=request.user,
            currency=source_currency,
            is_active=True
        )
        destination_wallet = get_object_or_404(
            Wallet,
            user=request.user,
            currency=destination_currency,
            is_active=True,
        )
        try:
            transaction = exchange(
                idempotency_key=idempotency_key,
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                amount=serializer.validated_data["amount"], # type: ignore
                initiated_by=request.user,
        )   
        except ValueError as e:
            return Response(
        {
            "detail": str(e)
        },
        status=status.HTTP_400_BAD_REQUEST,
        )
        exchange_transaction=transaction.exchange_details # pyright: ignore[reportAttributeAccessIssue]
        response_serializer=ExchangeTransactionSerializer(
            exchange_transaction
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )
exchange_transaction_view=ExchangeTransactionAPIView.as_view()
