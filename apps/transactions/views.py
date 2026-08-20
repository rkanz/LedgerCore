import uuid

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.transactions.models import Transaction
from apps.wallets.models import Wallet

from .serializers import (
    DepositSerializer,
    TransactionHistorySerializer,
    TransferSerializer,
    WithdrawSerializer,
)
from .services import deposit, transfer, withdraw


# Create your views here.
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
          ).distinct().order_by("-created_at")
transaction_history_view=TransactionHistoryAPIView.as_view()


class TransactionHistoryDetailAPIView(generics.RetrieveAPIView):
    serializer_class=TransactionHistorySerializer
    def get_queryset(self):
        return Transaction.objects.filter(
                    Q(initiated_by=self.request.user)
                    |Q(source_wallet__user=self.request.user)
                    |Q(destination_wallet__user=self.request.user)
                  ).distinct()

transaction_detail_view=TransactionHistoryDetailAPIView.as_view()

