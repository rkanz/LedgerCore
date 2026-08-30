import uuid

from django.core.cache import cache
from django.db.models import Q
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

from apps.transactions.models import Transaction
from apps.wallets.models import Wallet

from .cache import (
    TRANSACTION_CACHE_TTL,
    transaction_history_cache_key,
    transaction_history_detail_cache_key,
)
from .serializers import (
    DepositSerializer,
    TransactionHistorySerializer,
    TransferSerializer,
    WithdrawSerializer,
)
from .services import deposit, transfer, withdraw


@extend_schema(
    summary="Withdraw funds",
     description="""
    Withdraw funds from the authenticated user's wallet.

    The operation is idempotent and will not process the same
    Idempotency-Key more than once.

    The wallet must have sufficient balance to complete the withdrawal.
    """,tags=["Transactions"],
    request=WithdrawSerializer,
    responses={
         201:WithdrawSerializer,
         400:OpenApiResponse(
              description="Invalid request or insufficient balance ."
         ),401:OpenApiResponse(
              description="Authentication credentials were not provided."
         ),404:OpenApiResponse(
              description="Wallet not found ."
         )
    },parameters=[
         OpenApiParameter(
              name="Idempotency-Key",
              type=OpenApiTypes.UUID,
              location=OpenApiParameter.HEADER,
              required=True,
              description="Unique key used to prevent duplicate withdrawals."
         )
    ],examples=[
         OpenApiExample(
         "Withdraw USDT",
         summary="Withdraw 50USDT",
         description="Example request for withdrawing USDT",
         value={
              "amount":"50",
              "currency":"USDT"
         },request_only=True
         )
    ]
)
class WithdrawAPIView(APIView):
    def post(self,request):
        serializer=WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key_raw=request.headers.get('Idempotency-key')
        if not idempotency_key_raw:
            return Response(
                {'detail':'Idempotency-key header is required.'},status=status.HTTP_400_BAD_REQUEST
            )
        try:
            idempotency_key=uuid.UUID(idempotency_key_raw)
        except ValueError:
            return Response({
                'detail':'Idempotency-key must be a valid UUID.'
            },status=status.HTTP_400_BAD_REQUEST)
        currency = serializer.validated_data['currency'] # type: ignore
        wallet = Wallet.objects.filter(
        user=request.user,
        currency=currency,
        is_active=True).first()
        if wallet is None:
            return Response({
                'detail':'Wallet not found.'
            },status=status.HTTP_404_NOT_FOUND)
        try:
            new_transaction=withdraw(
                wallet=wallet,
                initiated_by=request.user,
                amount=serializer.validated_data['amount'], # type: ignore
                idempotency_key=idempotency_key,
            )
        except ValueError as e:
            return Response({
                'detail':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
        response_serializer=WithdrawSerializer(new_transaction)
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED)
withdraw_view=WithdrawAPIView.as_view()

@extend_schema(
    summary="Deposit funds",
    description="""
    Deposit funds into the authenticated user's wallet.

    The operation is idempotent. Reusing the same Idempotency-Key
    will not create another transaction or modify the wallet balance
    more than once.
    """ ,
    tags=["Transactions"],
    request=DepositSerializer,
    responses={
         201:DepositSerializer,
         400:OpenApiResponse(
              description="Invalid deposit request."
         ),401:OpenApiResponse(
              description="Authentication credentials were not provided."
         ),404:OpenApiResponse(
              description="Wallet not found."
         )
    },parameters=[
         OpenApiParameter(
              name="Idempotency-key",
              type=OpenApiTypes.UUID,
              location=OpenApiParameter.HEADER,
              required=True,
              description= "Unique key used to safely retry the same deposit "
                "without creating duplicate transactions."
         )
    ],examples=[
         OpenApiExample(
              "DepositUSDT",
              summary="Deposit 250 USDT",
              description="Example request for depositing 250USDT",
              value={
                   "currency":"USDT",
                   "amount":"250",
              },
              request_only=True
         )
    ]
)
class DepositAPIView(APIView):
    def post(self,request):
       
        serializer=DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key_raw=request.headers.get('Idempotency-key')
        if not idempotency_key_raw:
            return Response({
                'detail':'Idempotency-key header is required.'},status=status.HTTP_400_BAD_REQUEST
            )
        try:
            idempotency_key=uuid.UUID(idempotency_key_raw)
        except ValueError:
            return Response({
                            'detail':'Idempotency-key must be a valid UUID.'
                        },status=status.HTTP_400_BAD_REQUEST)
        currency = serializer.validated_data['currency'] # type: ignore
        wallet = Wallet.objects.filter(
        user=request.user,
        currency=currency,
        is_active=True).first()
        if wallet is None:
            return Response({
                'detail':'Wallet cannot be found.'
            },status=status.HTTP_404_NOT_FOUND)
        try:
            new_transaction=deposit(
                amount=serializer.validated_data['amount'], # type: ignore
                initiated_by=request.user,
                wallet=wallet,
                idempotency_key=idempotency_key
            )
        except ValueError as e:
                    return Response({
                        'detail':str(e)
                    },status=status.HTTP_400_BAD_REQUEST)
            
        response_serializer=DepositSerializer(new_transaction)
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED)
deposit_view=DepositAPIView.as_view()


@extend_schema(
    summary="Transfer funds",
    description="""
    Transfer funds from the authenticated user's wallet to another wallet.

    Source and destination wallets must use the same currency.

    The source wallet must have sufficient balance.

    Transfers to the same wallet are not allowed.

    The operation is idempotent and reusing the same Idempotency-Key
    will not create a duplicate transfer.
    """,tags=["Transactions"],
    request=TransferSerializer,
    responses={
         201:TransferSerializer,
         401:OpenApiResponse(
              description="Authentication credentials were not provided."
         ),404:OpenApiResponse(
              description="Destination wallet not found ."
         ),400:OpenApiResponse(
              description="Invalid request,insufficient balance or currency mismatch."
         )
    },parameters=[
         OpenApiParameter(
         name="Idempotency-Key",
         type=OpenApiTypes.UUID,
         location=OpenApiParameter.HEADER,
         description="Unique key used to prevent duplicate transfers.",
         required=True
        )
    ],examples=[
         OpenApiExample(
              "Transfer USDT",
              summary="Transfer 100USDT",
              description="Example request for transfering 100 usdt to another wallet. ",
              value={
                   "desination_wallet":12,
                   "amount":"100",
                   "currency":"USDT"
              },request_only=True
         )
    ]
)
class TransferAPIView(APIView):
    def post(self,request):
        serializer=TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key_raw=request.headers.get('Idempotency-key')
        if not idempotency_key_raw:
                    return Response({
                        'detail':'Idempotency-key header is required.'},status=status.HTTP_400_BAD_REQUEST
                    )
        try:
            idempotency_key=uuid.UUID(idempotency_key_raw)
        except ValueError:
            return Response({
                'detail':'Idempotency-key must be a valid UUID.'
                },status=status.HTTP_400_BAD_REQUEST)
        currency = serializer.validated_data['currency'] # type: ignore
        source_wallet = Wallet.objects.filter(
        user=request.user,
        currency=currency,
        is_active=True).first()
        if source_wallet is None:
            return Response({
                 'detail':'Wallet cannot be found.'
            },status=status.HTTP_404_NOT_FOUND)
        try:
            new_transaction=transfer(
                 source_wallet=source_wallet, # type: ignore
                 destination_wallet=serializer.validated_data['destination_wallet'],# type: ignore
                 amount=serializer.validated_data['amount'],# type: ignore
                 idempotency_key=idempotency_key,
                 initiated_by=request.user,
            )
        except ValueError as e:
            return Response({
            'detail':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
        response_serializer=TransferSerializer(new_transaction)
        return Response(response_serializer.data,
                        status=status.HTTP_201_CREATED)             
transfer_view=TransferAPIView.as_view()

class TransactionPagination(PageNumberPagination):
     page_size=10

@extend_schema(
    summary="List transaction history",
    description="""
    Return a paginated list of the authenticated user's transactions.
    Supports filtering, ordering and pagination.
    Responses are cached with Redis for a short period.
    Cache is invalidated when transaction-related wallet data changes.
    """,
    tags=["Transactions"],
    responses={
        200: TransactionHistorySerializer(many=True),
    },
    parameters=[
        OpenApiParameter(
            name="transaction_type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter transactions by type.",
        ),
        OpenApiParameter(
            name="status",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter transactions by status.",
        ),
        OpenApiParameter(
            name="currency",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Filter transactions by wallet currency.",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "Order results by amount, completed_at or created_at. "
                "Prefix the field with '-' for descending order."

            ),
        ),
    ],
)
class TransactionHistoryAPIView(generics.ListAPIView):
    serializer_class=TransactionHistorySerializer
    pagination_class=TransactionPagination
    filter_backends = [DjangoFilterBackend,OrderingFilter]
    filterset_fields = ['transaction_type', "status","currency",]
    ordering_fields=['amount','completed_at',"created_at"]
    def get_queryset(self):
        return Transaction.objects.filter(
            Q(initiated_by=self.request.user)
            |Q(source_wallet__user=self.request.user)
            |Q(destination_wallet__user=self.request.user)
          ).select_related(
            "source_wallet",
            "destination_wallet",
            "initiated_by",
            "exchange_details",
            "exchange_details__exchange_rate",
        ).distinct().order_by("-created_at")
    def list(self,request,*args,**kwargs):
        cache_key=transaction_history_cache_key(request.user.id,request.get_full_path())
        cached_data=cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        queryset=self.filter_queryset(self.get_queryset())
        page=self.paginate_queryset(queryset)
        if page is not None:
            serializer=self.get_serializer(page,many=True)
            response=self.get_paginated_response(serializer.data)
            cache.set(cache_key,response.data,timeout=TRANSACTION_CACHE_TTL)
            return response
        serializer=self.get_serializer(queryset,many=True)
        cache.set(cache_key,serializer.data,timeout=TRANSACTION_CACHE_TTL)
        return Response(serializer.data)
transaction_history_view=TransactionHistoryAPIView.as_view()

@extend_schema(
    summary="Retrieve transaction details",
    description="""
    Return detailed information about a transaction that belongs
    to or involves the authenticated user.
    """,
    tags=["Transactions"],
    responses={
        200: TransactionHistorySerializer,
        404: OpenApiResponse(
            description="Transaction not found or does not belong to the user."
        ),
    },
)
class TransactionHistoryDetailAPIView(generics.RetrieveAPIView):
    serializer_class=TransactionHistorySerializer
    def get_queryset(self):
        return Transaction.objects.filter(
                    Q(initiated_by=self.request.user)
                    |Q(source_wallet__user=self.request.user)
                    |Q(destination_wallet__user=self.request.user)
                  ).select_related(
            "source_wallet",
            "destination_wallet",
            "initiated_by",
            "exchange_details",
            "exchange_details__exchange_rate",
        ).distinct()
    def retrieve(self,request,*args,**kwargs):
        cache_key=transaction_history_detail_cache_key(request.user.id,kwargs["pk"])
        cached_data=cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        instance=self.get_object()
        serializer=self.get_serializer(instance)
        cache.set(cache_key,serializer.data,timeout=TRANSACTION_CACHE_TTL)
        return Response(serializer.data)

transaction_detail_view=TransactionHistoryDetailAPIView.as_view()

