from rest_framework import serializers

from apps.exchange.serializers import ExchangeTransactionSerializer

from .models import Transaction


class WithdrawSerializer(serializers.ModelSerializer):
    
    class Meta:
        model=Transaction
        fields=['id','currency','amount','status','created_at','completed_at','initiated_by']
        read_only_fields=['id','status','created_at','completed_at','initiated_by']


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model=Transaction
        fields=['id','currency','amount','status','created_at','completed_at','initiated_by']
        read_only_fields=['id','status','created_at','completed_at','initiated_by']

class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model=Transaction
        fields=['id','currency','amount','destination_wallet','status','created_at','completed_at','initiated_by']
        read_only_fields=['id','status','created_at','completed_at','initiated_by']

class TransactionHistorySerializer(serializers.ModelSerializer):
    exchange_details=ExchangeTransactionSerializer(read_only=True)
    class Meta:
        model=Transaction
        fields=["id","source_wallet","destination_wallet","transaction_type","status","amount","currency",
                "idempotency_key","created_at","completed_at","initiated_by","exchange_details"]
        read_only_fields=fields

