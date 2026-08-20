from django.contrib.auth.models import User
from django.db import transaction

from apps.wallets.models import Wallet


@transaction.atomic
def register_user(*,validated_data):
    password=validated_data.pop('password1')
    validated_data.pop('password2')
    user=User.objects.create_user(
        password=password,
        **validated_data,
    )
    for currency, _ in Wallet.Currency.choices:
        Wallet.objects.create(
            user=user,
            currency=currency,
        )
    return user