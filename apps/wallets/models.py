from decimal import Decimal

from django.conf import settings
from django.db import models

# Create your models here.


class Wallet(models.Model):
    class Currency(models.TextChoices):
        IRR = "IRR", "Iranian Rial"
        USDT = "USDT", "Tether"
        BTC = "BTC", "Bitcoin"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallets",
    )
    currency = models.CharField(max_length=10, choices=Currency.choices)
    balance = models.DecimalField(
        max_digits=20, decimal_places=8, default=Decimal("0.00000000")
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "currency"], name="unique_user_currency_wallet"
            )
        ]

    def __str__(self):
        return f"{self.user.username}-{self.currency}"



