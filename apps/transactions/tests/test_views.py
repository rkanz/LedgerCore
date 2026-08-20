import uuid
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.transactions.models import Transaction
from apps.transactions.services import deposit, withdraw
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_withdraw_api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    wallet=Wallet.objects.get(
        user=user,
        currency=Wallet.Currency.USDT,
    )
    wallet.balance=Decimal("200")
    wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:withdraw"),{  # pyright: ignore[reportAttributeAccessIssue]
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50")
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    wallet.refresh_from_db()
    assert response.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["currency"] == Wallet.Currency.USDT # pyright: ignore[reportAttributeAccessIssue]
    assert wallet.balance == Decimal("150") # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["status"] == Transaction.TransactionStatus.COMPLETED # pyright: ignore[reportAttributeAccessIssue]
    assert Transaction.objects.filter(
    initiated_by=user,
    transaction_type=Transaction.TransactionType.WITHDRAW,).count() == 1 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_withdraw_authentication_error(user):
    client=APIClient()
    response=client.post(reverse("transactions:withdraw"),{
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50")
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_withdraw_insufficient_balance(user):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet=Wallet.objects.get(
        user=user,
        currency=Wallet.Currency.USDT,
    )
    wallet.balance=Decimal("200")
    wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:withdraw"),{  # pyright: ignore[reportAttributeAccessIssue]
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("250")
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    wallet.refresh_from_db()
    assert response.status_code == 400 # pyright: ignore[reportAttributeAccessIssue]
    assert Transaction.objects.filter(
        initiated_by=user,
        transaction_type=Transaction.TransactionType.WITHDRAW,).count() == 0
    assert wallet.balance == Decimal("200")


@pytest.mark.django_db
def test_withdraw_idempotency(user):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet=Wallet.objects.get(
            user=user,
            currency=Wallet.Currency.USDT,
        )
    wallet.balance=Decimal("200")
    wallet.save(update_fields=["balance"])
    idempotency_key = str(uuid.uuid4())
    response1=client.post(reverse("transactions:withdraw"),{  # pyright: ignore[reportAttributeAccessIssue]
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50")
    },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    response2=client.post(reverse("transactions:withdraw"),{  # pyright: ignore[reportAttributeAccessIssue]
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50")
    },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    wallet.refresh_from_db()
    assert wallet.balance == Decimal("150")
    assert Transaction.objects.filter(
    initiated_by=user,
    transaction_type=Transaction.TransactionType.WITHDRAW,).count() == 1
    assert response1.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert response2.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert response1.data["id"] == response2.data["id"] # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_deposit_api(user):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet=Wallet.objects.get(
            user=user,
            currency=Wallet.Currency.USDT,
        )
    response=client.post(reverse("transactions:deposit"),{
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("250"),
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    wallet.refresh_from_db()
    assert response.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert wallet.balance == Decimal("250")
    assert response.data["status"] == Transaction.TransactionStatus.COMPLETED# pyright: ignore[reportAttributeAccessIssue]
    assert response.data["currency"] == Wallet.Currency.USDT # pyright: ignore[reportAttributeAccessIssue]
    assert Transaction.objects.filter(
    initiated_by=user,
    transaction_type=Transaction.TransactionType.DEPOSIT,).count() == 1 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["amount"] == "250.00000000" # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["initiated_by"] == user.id # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_deposit_authentication_error():
    client=APIClient()
    response=client.post(reverse("transactions:deposit"),{
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50")
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_deposit_idempotency(user):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet=Wallet.objects.get(
        currency=Wallet.Currency.USDT,
        user=user
    )
    idempotency_key=str(uuid.uuid4())
    response1=client.post(reverse("transactions:deposit"),{
        "amount":Decimal("100"),
        "currency":Wallet.Currency.USDT
    },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    response2=client.post(reverse("transactions:deposit"),{
        "amount":Decimal("100"),
        "currency":Wallet.Currency.USDT
    },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    wallet.refresh_from_db()
    assert response1.data["id"] == response2.data["id"] # pyright: ignore[reportAttributeAccessIssue]
    assert response1.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert response2.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert wallet.balance == Decimal("100")
    assert Transaction.objects.filter(
    initiated_by=user,
    transaction_type=Transaction.TransactionType.DEPOSIT,).count() == 1


@pytest.mark.django_db
def test_transfer_api(user,wallets,wallets_2):
    client=APIClient()
    client.force_authenticate(user=user)
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("200")
    source_wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:transfer"),{
        "currency":"USDT",
        "amount":Decimal("50"),
        "destination_wallet":destination_wallet.id
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert response.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["status"] == Transaction.TransactionStatus.COMPLETED # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["currency"] == Wallet.Currency.USDT # pyright: ignore[reportAttributeAccessIssue]
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance == Decimal("50")
    assert response.data["amount"] == "50.00000000" # pyright: ignore[reportAttributeAccessIssue]
    assert Transaction.objects.filter(
        initiated_by=user,transaction_type=Transaction.TransactionType.TRANSFER
    ).count() == 1

@pytest.mark.django_db
def test_transfer_authentication_error(wallets_2):
    client=APIClient()
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    response=client.post(reverse("transactions:transfer"),{
        "currency":Wallet.Currency.USDT,
        "amount":Decimal("50"),
        "destination_wallet":destination_wallet.id
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    
    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transfer_insufficient_balance(user,wallets,wallets_2):
    client=APIClient()
    client.force_authenticate(user=user)
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("200")
    source_wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:transfer"),{
        "currency":"USDT",
        "amount":Decimal("250"),
        "destination_wallet":destination_wallet.id
    },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert response.status_code == 400 # pyright: ignore[reportAttributeAccessIssue]
    assert destination_wallet.balance == Decimal("0")
    assert source_wallet.balance == Decimal("200")
    assert Transaction.objects.filter(initiated_by=user,
        transaction_type=Transaction.TransactionType.TRANSFER).count() == 0
    
@pytest.mark.django_db
def test_transfer_same_wallet(user,wallets):
    client=APIClient()
    client.force_authenticate(user=user)
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("200")
    source_wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:transfer"),{
            "currency":"USDT",
            "amount":Decimal("150"),
            "destination_wallet":destination_wallet.id
        },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert response.status_code == 400  # pyright: ignore[reportAttributeAccessIssue]
    assert source_wallet.balance == Decimal("200")
    assert Transaction.objects.filter(initiated_by=user,
            transaction_type=Transaction.TransactionType.TRANSFER).count() == 0 
    assert response.data["detail"] == "Cannot transfer to the same wallet."  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.django_db
def test_transfer_different_currency(wallets,wallets_2,user):
    client=APIClient()
    client.force_authenticate(user=user)
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.BTC]
    source_wallet.balance = Decimal("200")
    source_wallet.save(update_fields=["balance"])
    response=client.post(reverse("transactions:transfer"),{
            "currency":"USDT",
            "amount":Decimal("50"),
            "destination_wallet":destination_wallet.id
        },HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert response.status_code == 400  # pyright: ignore[reportAttributeAccessIssue]
    assert destination_wallet.balance == Decimal("0")
    assert source_wallet.balance == Decimal("200")
    assert Transaction.objects.filter(initiated_by=user,
        transaction_type=Transaction.TransactionType.TRANSFER).count() == 0 
    assert response.data["detail"] == "Wallet currencies must match."  # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transfer_idempotency(user,wallets,wallets_2):
    idempotency_key=str(uuid.uuid4())
    client=APIClient()
    client.force_authenticate(user=user)
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    source_wallet.balance = Decimal("200")
    source_wallet.save(update_fields=["balance"])
    response1=client.post(reverse("transactions:transfer"),{
                "currency":"USDT",
                "amount":Decimal("50"),
                "destination_wallet":destination_wallet.id
            },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    response2=client.post(reverse("transactions:transfer"),{
                "currency":"USDT",
                "amount":Decimal("50"),
                "destination_wallet":destination_wallet.id
    },HTTP_IDEMPOTENCY_KEY=idempotency_key)
    source_wallet.refresh_from_db()
    destination_wallet.refresh_from_db()
    assert response1.status_code == 201  # pyright: ignore[reportAttributeAccessIssue]
    assert response2.status_code == 201  # pyright: ignore[reportAttributeAccessIssue]
    assert response1.data["id"] == response2.data["id"]  # pyright: ignore[reportAttributeAccessIssue]
    assert source_wallet.balance == Decimal("150")
    assert destination_wallet.balance == Decimal("50")
    assert Transaction.objects.filter(
        initiated_by=user,transaction_type=Transaction.TransactionType.TRANSFER
    ).count() == 1

@pytest.mark.django_db
def test_transaction_history(user,user_2,wallets,wallets_2):
    wallet1 = wallets[Wallet.Currency.USDT]
    wallet2 = wallets_2[Wallet.Currency.USDT]
    transaction1 = deposit(
        wallet=wallet1,
        amount=Decimal("250"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    transaction2 = deposit(
        wallet=wallet2,
        amount=Decimal("150"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user_2,
    )

    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-history"))
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    results= response.data["results"] # pyright: ignore[reportAttributeAccessIssue]
    assert len(results) == 1
    assert results[0]["id"] == transaction1.id # pyright: ignore[reportAttributeAccessIssue] 
    assert results[0]["initiated_by"] == user.id
    assert results[0]["id"] != transaction2.id # pyright: ignore[reportAttributeAccessIssue]
    assert results [0]["initiated_by"] != user_2.id

@pytest.mark.django_db
def test_transaction_history_detail(user,wallets):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet1 = wallets[Wallet.Currency.USDT]
    transaction1 = deposit(
        wallet=wallet1,
        amount=Decimal("250"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-detail",
                        kwargs={"pk": transaction1.id},) # pyright: ignore[reportAttributeAccessIssue]
    ) 
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["id"] == transaction1.id # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["initiated_by"] == user.id # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transaction_history_detail_fail(user,wallets,wallets_2,user_2):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet1 = wallets[Wallet.Currency.USDT]
    wallet2 = wallets_2[Wallet.Currency.USDT]
    deposit(
        wallet=wallet1,
        amount=Decimal("250"),
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
    )
    transaction2 = deposit(
            wallet=wallet2,
            amount=Decimal("150"),
            idempotency_key=uuid.uuid4(),
            initiated_by=user_2,
    )
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-detail",
                        kwargs={"pk": transaction2.id},) # pyright: ignore[reportAttributeAccessIssue]
    ) 
    assert response.status_code == 404 # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.django_db
def test_transaction_history_pagination(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    for _ in range(12):
        deposit(
            wallet=wallet,
            amount=Decimal("10"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    wallet.refresh_from_db()
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-history"))
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["count"]== 12 # pyright: ignore[reportAttributeAccessIssue]
    assert len(response.data["results"]) == 10 # pyright: ignore[reportAttributeAccessIssue]
    assert wallet.balance == Decimal("120")
    response1=client.get(reverse("transactions:transaction-history")+"?page=2")
    assert response1.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert len(response1.data["results"]) == 2 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transaction_history_filter(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    for _ in range(5):
        deposit(
            wallet=wallet,
            amount=Decimal("40"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
        )
    for _ in range(3):
            withdraw(
                wallet=wallet,
                amount=Decimal("10"),
                initiated_by=user,
                idempotency_key=uuid.uuid4()
            )
    wallet.refresh_from_db()
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-history"))
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["count"]== 8 # pyright: ignore[reportAttributeAccessIssue]
    response2=client.get(reverse("transactions:transaction-history")+"?transaction_type=WITHDRAW")
    assert response2.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert response2.data["count"] == 3 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transaction_history_ordering(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    deposit(
            wallet=wallet,
            amount=Decimal("40"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
)   
    deposit(
            wallet=wallet,
            amount=Decimal("90"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
)   
    transaction2=deposit(
            wallet=wallet,
            amount=Decimal("220"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
)   
    wallet.refresh_from_db()
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("transactions:transaction-history"))
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert wallet.balance == Decimal("350")
    assert Transaction.objects.filter(
        initiated_by=user,transaction_type=Transaction.TransactionType.DEPOSIT
    ).count()==3
    response2=client.get(reverse("transactions:transaction-history")+"?ordering=-amount")
    assert response2.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    results= response2.data["results"] # pyright: ignore[reportAttributeAccessIssue]
    assert Decimal(results[0]["amount"]) == Decimal("220")
    assert results[0]["id"] == transaction2.id # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transaction_history_authentication():
    client = APIClient()

    response = client.get(
        reverse("transactions:transaction-history")
    )

    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_transaction_history_detail_authentication(wallets,user):
    wallet=wallets[Wallet.Currency.USDT]
    transaction=deposit(
            wallet=wallet,
            amount=Decimal("40"),
            initiated_by=user,
            idempotency_key=uuid.uuid4()
)   
    client=APIClient()
    response = client.get(
            reverse("transactions:transaction-detail",
                    kwargs={"pk": transaction.id}) # pyright: ignore[reportAttributeAccessIssue]
        )
    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]