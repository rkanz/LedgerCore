from decimal import Decimal

from rest_framework import serializers

from apps.exchange.models import ExchangeRate, ExchangeTransaction
from apps.wallets.models import Wallet


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model=ExchangeRate
        fields=["id","base_currency","quote_currency","rate","fetched_at"]
        read_only_fields=fields


class ExchangeSerializer(serializers.Serializer):
    source_currency=serializers.ChoiceField(choices=Wallet.Currency.choices)
    destination_currency=serializers.ChoiceField(choices=Wallet.Currency.choices)
    amount=serializers.DecimalField(max_digits=20,decimal_places=8,min_value=Decimal("0.00000001"))

    def validate(self,attrs):
        if attrs["source_currency"] == attrs["destination_currency"]:
            raise serializers.ValidationError("Source and Destination currency must be different.")
        return attrs

class ExchangeTransactionSerializer(serializers.ModelSerializer):
    transaction_id=serializers.IntegerField(
        source="transaction.id",read_only=True
    )
    source_currency=serializers.SerializerMethodField()
    destination_currency=serializers.SerializerMethodField()
    exchange_rate_value=serializers.DecimalField(
        decimal_places=12,max_digits=30,source="exchange_rate.rate"
    )
    status=serializers.CharField(source="transaction.status",read_only=True)
    class Meta:
        model=ExchangeTransaction
        fields = [
            "transaction_id",
            "source_currency",
            "destination_currency",
            "source_amount",
            "exchange_rate_value",
            "fee_amount",
            "fee_currency",
            "destination_amount",
            "status",
            "created_at",
        ]
        read_only_fields=fields
    def get_source_currency(self, obj):
        return obj.transaction.source_wallet.currency

    def get_destination_currency(self, obj):
        return obj.transaction.destination_wallet.currency

