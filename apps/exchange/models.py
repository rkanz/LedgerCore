from django.db import models
from django.utils import timezone

from apps.transactions.models import Transaction
from apps.wallets.models import Wallet


class ExchangeRate(models.Model):
    base_currency=models.CharField(
        choices=Wallet.Currency.choices,
        max_length=4
    )
    quote_currency=models.CharField(
        choices=Wallet.Currency.choices,
        max_length=4
    )
    rate=models.DecimalField(
        max_digits=30,
        decimal_places=12
    )
    fetched_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[
            models.UniqueConstraint(
                fields=["base_currency","quote_currency","fetched_at"],
                name="unique_exchange_rate_snapshot"
            )
        ]
        ordering=["-fetched_at"]
        def __str__(self):
            return (
                f"{self.base_currency}/{self.quote_currency} " # pyright: ignore[reportAttributeAccessIssue]
                f"= {self.rate}" # pyright: ignore[reportAttributeAccessIssue]
            )

class ExchangeTransaction(models.Model):
    transaction=models.OneToOneField(
        Transaction,on_delete=models.PROTECT,
        related_name='exchange_details'
    )
    exchange_rate=models.ForeignKey(
        ExchangeRate,on_delete=models.PROTECT,
        related_name='exchange_transactions'
    )
    source_amount=models.DecimalField(
        max_digits=20,decimal_places=8
    )
    destination_amount=models.DecimalField(
        max_digits=20,decimal_places=8
    )
    fee_amount=models.DecimalField(
        max_digits=20,decimal_places=8
    )
    fee_currency=models.CharField(
        choices=Wallet.Currency.choices,max_length=10
    )
    created_at=models.DateTimeField(
        auto_now_add=True
    )