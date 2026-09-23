from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.exchange.serializers import ExchangeTransactionSerializer
from apps.wallets.models import Wallet

from .models import Tag, Transaction


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

class TagNamesField(serializers.ListField):
    def to_representation(self, value):
        return list(
            value.values_list("name", flat=True)
        )
    
class TransactionHistorySerializer(serializers.ModelSerializer):
    exchange_details=ExchangeTransactionSerializer(read_only=True)
    tags = TagNamesField(
    child=serializers.CharField(max_length=20),
    required=False,)
    class Meta:
        model=Transaction
        fields=["id","source_wallet","destination_wallet","transaction_type","status","amount","currency",
                "idempotency_key","created_at","completed_at","initiated_by","exchange_details","tags","category"]
        read_only_fields = [
     "id",
    "source_wallet",
    "destination_wallet",
    "transaction_type",
    "status",
    "amount",
    "currency",
    "idempotency_key",
    "created_at",
    "completed_at",
    "initiated_by",
    "exchange_details",
]
    def update(self,instance,validated_data):
        tags=validated_data.pop("tags",None)
        instance=super().update(instance,validated_data)
        if tags is not None:
            tags_objects=[
                Tag.objects.get_or_create(name=tag)[0]
                for tag in tags
            ]
            instance.tags.set(tags_objects)
        return instance

User=get_user_model()

class RecipientUserSerializer(serializers.ModelSerializer):
    name=serializers.SerializerMethodField()
    class Meta:
        model=User
        fields=["id","name"]
        read_only_fields=fields
    def get_name(self,obj)-> str:
        return obj.get_full_name()


class RecipientSerializer(serializers.ModelSerializer):
    user=RecipientUserSerializer(read_only=True)
    class Meta:
        model=Wallet
        fields=["id","user","currency"]
        read_only_fields=fields