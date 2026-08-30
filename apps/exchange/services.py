from decimal import Decimal, InvalidOperation

import requests
from django.db import transaction
from django.utils import timezone

from apps.exchange.models import ExchangeRate, ExchangeTransaction
from apps.transactions.cache import invalidate_user_transaction_cache
from apps.transactions.models import LedgerEntry, Transaction
from apps.wallets.cache import invalidate_user_wallet_cache
from apps.wallets.models import Wallet

from .cache import invalidate_exchange_rate_cache

FRANKFURTER_BASE_URL="https://api.frankfurter.dev/v2"

class ExchangeRateErrror(Exception):
    pass


def get_exchange_rate(*,base_currency:str,quote_currency:str)-> Decimal:
    validate_currency_pair(
        base_currency=base_currency,
        quote_currency=quote_currency,
    )
    if base_currency == quote_currency:
        raise ValueError("Base and quote currencies must be different.")
    url=(
        f"{FRANKFURTER_BASE_URL}/rate/"
        f"{base_currency}/{quote_currency}"
    )

    try:
        response=requests.get(url,timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ExchangeRateErrror(
            "Failed to fetch exchange rate ."
        ) from exc
    data = response.json()
    try:
        rate = Decimal(str(data["rate"]))    # pyright: ignore[reportIndexIssue]
    except (KeyError,InvalidOperation) as exc:
        raise ExchangeRateErrror(
            "Invalid exchange rate response."
        ) from exc
    if rate <= 0:
        raise ExchangeRateErrror(
            "Exchange rate must be greater than zero ."
        )
    return rate

def save_exchange_rate(*,base_currency:str,quote_currency:str)->ExchangeRate:
    rate=get_exchange_rate(
        base_currency=base_currency,
        quote_currency=quote_currency
    )
    exchange_rate=ExchangeRate.objects.create(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate=rate,
    )
    transaction.on_commit(
        invalidate_exchange_rate_cache
    )
    return exchange_rate


SUPPORTED_FIAT_CURRENCIES = {
    "EUR",
    "USD",
}


def validate_currency_pair(*,base_currency:str,quote_currency:str)->None:
    if base_currency == quote_currency:
        raise ValueError("Base and quote currencies must be different.")
    if base_currency not in SUPPORTED_FIAT_CURRENCIES:
        raise ValueError (f"Unsupported base currency: {base_currency}")
    if quote_currency not in SUPPORTED_FIAT_CURRENCIES:
        raise ValueError (f"Unspported quote currency: {quote_currency}")


EXCHANGE_FEE_RATE=Decimal("0.0025")

def calculate_exchange_fee(
        *,converted_amount:Decimal
)-> Decimal :
    return converted_amount * EXCHANGE_FEE_RATE


def exchange(
    *,
    idempotency_key,
    source_wallet:Wallet,
    destination_wallet:Wallet,
    amount:Decimal,
    initiated_by,

):
    if amount <= 0:
        raise ValueError("Exchange amount must be greater than zero.")
    if source_wallet.currency == destination_wallet.currency:
        raise ValueError("Source and destination currencies must be different.")
    if source_wallet.pk == destination_wallet.pk :
        raise ValueError("Source and destination wallets must be different.")    
    with transaction.atomic():
        existing_transaction = Transaction.objects.filter(
        idempotency_key=idempotency_key).first()
        if existing_transaction:
            return existing_transaction
        first_wallet,second_wallet=sorted(
            [source_wallet,destination_wallet],key=lambda wallet:wallet.pk
        )
        first_wallet = Wallet.objects.select_for_update().get(pk=first_wallet.pk)
        second_wallet = Wallet.objects.select_for_update().get(pk=second_wallet.pk)
        if source_wallet.pk == first_wallet.pk:
            source_wallet = first_wallet
            destination_wallet=second_wallet
        else:
            destination_wallet = first_wallet
            source_wallet = second_wallet
        if amount > source_wallet.balance:
            raise ValueError("Insufficent wallet balance.")
        exchange_rate=ExchangeRate.objects.filter(
            base_currency=source_wallet.currency,
            quote_currency=destination_wallet.currency
        ).first()
        if exchange_rate is None:
            raise ValueError("Exchange rate is not available.")
        converted_amount = amount * exchange_rate.rate
        fee_amount = calculate_exchange_fee(
        converted_amount=converted_amount)
        destination_amount = converted_amount - fee_amount
        new_transaction=Transaction.objects.create(
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            transaction_type=Transaction.TransactionType.EXCHANGE,
            status=Transaction.TransactionStatus.PENDING,
            amount=amount,
            currency=source_wallet.currency,
            idempotency_key=idempotency_key,
            initiated_by=initiated_by,
        )
        ExchangeTransaction.objects.create(
            transaction=new_transaction,
            exchange_rate=exchange_rate,
            source_amount=amount,
            destination_amount=destination_amount,
            fee_amount=fee_amount,
            fee_currency=destination_wallet.currency,
        )
        LedgerEntry.objects.create(
                transaction=new_transaction,
                wallet=source_wallet,
                entry_type=LedgerEntry.EntryType.DEBIT,
                amount=amount,
        )
        LedgerEntry.objects.create(
                    transaction=new_transaction,
                    wallet=destination_wallet,
                    entry_type=LedgerEntry.EntryType.CREDIT,
                    amount=destination_amount,
        )
        source_wallet.balance -= amount
        destination_wallet.balance += destination_amount
        source_wallet.save(update_fields=["balance", "updated_at"])
        destination_wallet.save(update_fields=["balance", "updated_at"])
        new_transaction.status = Transaction.TransactionStatus.COMPLETED
        new_transaction.completed_at = timezone.now()
        new_transaction.save(update_fields=["status", "completed_at"])
        transaction.on_commit(
            lambda:invalidate_user_wallet_cache(
                user_id=initiated_by.id,
                wallet_id=source_wallet.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        transaction.on_commit(
            lambda:invalidate_user_wallet_cache(
                user_id=initiated_by.id,
                wallet_id=destination_wallet.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        transaction.on_commit(
            lambda:invalidate_user_transaction_cache(
                user_id=initiated_by.id,
                transaction_id=new_transaction.id # pyright: ignore[reportAttributeAccessIssue]
            )
        )
        return new_transaction
        
