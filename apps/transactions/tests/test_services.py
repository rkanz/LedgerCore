from datetime import timedelta
import uuid
from decimal import Decimal

from django.utils import timezone
import pytest

from apps.transactions.models import LedgerEntry, Transaction
from apps.transactions.services import (
    deposit,
    get_frequent_recipients,
    get_recent_recipients,
    transfer,
    withdraw,
)
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_desposit(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    transaction=deposit(
        wallet=wallet,
        amount=Decimal("100"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("100")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED

@pytest.mark.django_db
def test_withdraw_insufficent_balance(user,wallets):

    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Insufficent wallet balance."):
        withdraw(
        wallet=wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    wallet.refresh_from_db()

    assert wallet.balance == Decimal("0")

@pytest.mark.django_db
def test_withdraw(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    transaction=withdraw(
        initiated_by=user,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        wallet=wallet
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("50")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED

@pytest.mark.django_db
def test_withdraw_create_debit_ledger_entry(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    transaction=withdraw(
        wallet= wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    ledger_entry = transaction.ledger_entries.get() # pyright: ignore[reportAttributeAccessIssue]
    assert ledger_entry.wallet == wallet
    assert ledger_entry.amount == Decimal("50")
    assert ledger_entry.entry_type == LedgerEntry.EntryType.DEBIT

@pytest.mark.django_db
def test_withdraw_idempotency(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance = Decimal("100")
    wallet.save(update_fields=["balance"])
    idempotency_key=uuid.uuid4()
    first_transaction=withdraw(
        initiated_by=user,
        wallet=wallet,
        idempotency_key=idempotency_key,
        amount=Decimal("50")
    )
    second_transaction=withdraw(
        initiated_by=user,
        wallet=wallet,
        idempotency_key=idempotency_key,
        amount=Decimal("50")
    )
    wallet.refresh_from_db()
    assert first_transaction == second_transaction
    assert wallet.balance == Decimal("50")
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.django_db
def test_deposit_idempotency(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    idempotency_key=uuid.uuid4()
    first_transaction=deposit(
        wallet=wallet,
        initiated_by=user,
        amount=Decimal("150"),
        idempotency_key=idempotency_key
    )
    second_transaction=deposit(
        wallet=wallet,
        initiated_by=user,
        amount=Decimal("150"),
        idempotency_key=idempotency_key
    )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("150")
    assert first_transaction == second_transaction
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).count() == 1

@pytest.mark.django_db
def test_deposit_zero_amount(user,wallets):
    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Deposit amount must be greater than zero",
    ):
        deposit(
            wallet=wallet,
            amount=Decimal("0"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("0")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_transfer(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    transaction=transfer(
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("50"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("100")
    assert destination_wallet.balance == Decimal("50")
    assert transaction.status == Transaction.TransactionStatus.COMPLETED
    assert transaction.transaction_type == Transaction.TransactionType.TRANSFER
    ledger_entries=LedgerEntry.objects.all()
    assert ledger_entries.count() == 2
    source_entry=ledger_entries.get(
        wallet=source_wallet,
        entry_type=LedgerEntry.EntryType.DEBIT,
    )
    destination_entry=ledger_entries.get(
            wallet=destination_wallet,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )
    assert source_entry.amount == Decimal("50")
    assert destination_entry.amount == Decimal("50") 

@pytest.mark.django_db
def test_transfer_insufficent_balance(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Insufficent wallet balance.",):
        transfer(
                source_wallet=source_wallet,
                destination_wallet=destination_wallet,
                amount=Decimal("50"),
                idempotency_key=uuid.uuid4(),
                initiated_by=user
            )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert destination_wallet.balance==Decimal("0")
    assert Transaction.objects.count() == 0

@pytest.mark.django_db
def test_transfer_idempotency(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    idempotency_key=uuid.uuid4()
    first_transaction=transfer(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("100"),
        initiated_by=user,
    )
    second_transaction=transfer(
        idempotency_key=idempotency_key,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount=Decimal("100"),
        initiated_by=user,
    )
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert Transaction.objects.filter(
        idempotency_key=idempotency_key).count() == 1
    assert source_wallet.balance == Decimal("50")
    assert destination_wallet.balance == Decimal("100")
    assert first_transaction== second_transaction

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_transfer_invalid_amount(wallets,wallets_2,user,amount):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    with pytest.raises(
        ValueError,
        match="Transfer amount must be greater than zero.",
    ): 
        transfer(
            amount=amount,
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            idempotency_key=uuid.uuid4()
    )
    destination_wallet.refresh_from_db()
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("0")
    assert destination_wallet.balance == Decimal("0")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_transfer_diffrenct_currency(user,wallets,wallets_2):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    destination_wallet=wallets_2[Wallet.Currency.BTC]
    with pytest.raises(ValueError,match="Wallet currencies must match."):
        transfer(
            amount=Decimal("100"),
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            idempotency_key=uuid.uuid4()
    )
    destination_wallet.refresh_from_db()
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance==Decimal("0")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_same_wallet(user,wallets):
    source_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance=Decimal("150")
    source_wallet.save(update_fields=["balance"])
    with pytest.raises(ValueError,match="Cannot transfer to the same wallet."):
        transfer(
            source_wallet=source_wallet,
            destination_wallet=source_wallet,
            amount=Decimal("50"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    source_wallet.refresh_from_db()
    assert source_wallet.balance == Decimal("150")
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0 

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_deposit_invalid_amount(user,wallets,amount):
    wallet=wallets[Wallet.Currency.USDT]
    with pytest.raises(ValueError,match="Deposit amount must be greater than zero."):
        deposit(
            wallet=wallet,
            amount=amount,
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.parametrize(
    "amount",
    [Decimal("0"),Decimal("-50")]
)
@pytest.mark.django_db
def test_withdraw_invalid_amount(user,wallets,amount):
    wallet=wallets[Wallet.Currency.USDT]
    wallet.balance=Decimal("150")
    wallet.save(update_fields=["balance"])
    with pytest.raises(ValueError,match="Withdraw amount must be greater than zero."):
        withdraw(
            wallet=wallet,
            amount=amount,
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0

@pytest.mark.django_db
def test_get_frequent_recipients(create_transfer,user,ali_wallets,mina_wallets,wallets):
    user_wallet=wallets[Wallet.Currency.USDT]
    ali_wallet=ali_wallets[Wallet.Currency.USDT]
    mina_wallet=mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    recipients=get_frequent_recipients(
        currency=Wallet.Currency.USDT,
        user=user,
    )
    assert list(recipients) == [mina_wallet, ali_wallet]

@pytest.mark.django_db
def test_frequent_recipients_excludes_failed_transfers(create_transfer,user,ali_wallets,mina_wallets,wallets):
    user_wallet=wallets[Wallet.Currency.USDT]
    ali_wallet=ali_wallets[Wallet.Currency.USDT]
    mina_wallet=mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=mina_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
        status=Transaction.TransactionStatus.FAILED
    )   
    create_transfer(
        initiated_by=user,
        source_wallet=user_wallet,
        destination_wallet=ali_wallet,
        status=Transaction.TransactionStatus.FAILED
    )
    recipients=get_frequent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    ) 
    assert list(recipients) == [mina_wallet]
    assert recipients[0].transfer_count == 1       # type: ignore


@pytest.mark.django_db
def test_get_frequent_recipients_different_currencies(wallets,mina_wallets,create_transfer,user):
    user_usdt_wallet=wallets[Wallet.Currency.USDT]
    user_btc_wallet=wallets[Wallet.Currency.BTC]

    mina_usdt_wallet=mina_wallets[Wallet.Currency.USDT]
    mina_btc_wallet=mina_wallets[Wallet.Currency.BTC]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    create_transfer(
        initiated_by=user,
        source_wallet=user_btc_wallet,
        destination_wallet=mina_btc_wallet,
    )
    recipients=get_frequent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert recipients[0].transfer_count == 2 # type: ignore

@pytest.mark.django_db
def test_get_frequent_recipients_only_counts_current_user_transfers(
    user,
    ali,
    wallets,
    ali_wallets,
    mina_wallets,
    create_transfer,
):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    mina_usdt_wallet = mina_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet
    )
    create_transfer(
        initiated_by=ali,
        source_wallet=ali_usdt_wallet,
        destination_wallet=mina_usdt_wallet
    )
    recipients=get_frequent_recipients(
        user=ali,
        currency=Wallet.Currency.USDT
    )
    assert list(recipients) == [mina_usdt_wallet]
    assert len(recipients) == 1
    assert recipients[0].transfer_count == 1 # type: ignore

@pytest.mark.django_db
def test_get_recent_recipients(create_transfer,wallets,user,ali_wallets,mina_wallets):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    mina_usdt_wallet = mina_wallets[Wallet.Currency.USDT]
    old_mina=create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    old_ali = create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet,
    )

    recent_mina = create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=mina_usdt_wallet,
    )
    old_mina.created_at =timezone.now() - timedelta(days=3)
    old_mina.save(update_fields=["created_at"])

    old_ali.created_at =timezone.now() - timedelta(days=2)
    old_ali.save(update_fields=["created_at"])

    recent_mina.created_at = timezone.now() - timedelta(days=1)
    recent_mina.save(update_fields=["created_at"])
    recent_recipients=get_recent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert list(recent_recipients) == [mina_usdt_wallet,ali_usdt_wallet]

@pytest.mark.django_db
def test_get_recent_recipients_excludes_failed_transfers(create_transfer,wallets,user,ali_wallets):
    user_usdt_wallet = wallets[Wallet.Currency.USDT]
    ali_usdt_wallet = ali_wallets[Wallet.Currency.USDT]
    create_transfer(
        initiated_by=user,
        source_wallet=user_usdt_wallet,
        destination_wallet=ali_usdt_wallet,
        status=Transaction.TransactionStatus.FAILED
    )
    recent_recipients=get_recent_recipients(
        user=user,
        currency=Wallet.Currency.USDT
    )
    assert list(recent_recipients) == []