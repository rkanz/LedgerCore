import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.services import register_user
from apps.wallets.models import Wallet


@pytest.fixture
def user():
    return register_user(
        validated_data={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Test",
            "email": "alice@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )

@pytest.fixture
def wallets(user):
    return {
        wallet.currency: wallet
        for wallet in Wallet.objects.filter(user=user)
    }

@pytest.fixture
def user_2():
        return register_user(
        validated_data={
            "username": "Bob123",
            "first_name": "Bob",
            "last_name": "Test",
            "email": "bob@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )
@pytest.fixture
def wallets_2(user_2):
     return{
        wallet.currency: wallet
            for wallet in Wallet.objects.filter(user=user_2)
     }

@pytest.mark.django_db
def test_wallets_list(user):
    client=APIClient()
    client.force_authenticate(user=user)
    response=client.get(reverse("wallet-list"))
    assert response.status_code == 200 # pyright: ignore[reportAttributeAccessIssue]
    assert len(response.data) == 3 # pyright: ignore[reportAttributeAccessIssue]
    assert {wallet["currency"] for wallet in response.data} == { # pyright: ignore[reportAttributeAccessIssue]
        Wallet.Currency.IRR, 
        Wallet.Currency.USDT,
        Wallet.Currency.BTC,
    }

@pytest.mark.django_db
def test_wallet_list_authentication_error():
    client = APIClient()

    response = client.get(
        reverse("wallet-list")
    )
    assert response.status_code == 401 # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_wallet_detail(user,wallets):
    client=APIClient()
    client.force_authenticate(user=user)
    wallet = wallets[Wallet.Currency.USDT]
    response=client.get(reverse("wallet-detail",kwargs={"pk": wallet.id}))
    assert response.status_code== 200 # pyright: ignore[reportAttributeAccessIssue] 
    assert response.data["id"] == wallet.id # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["currency"] == Wallet.Currency.USDT # pyright: ignore[reportAttributeAccessIssue]قعبب
    assert response.data["is_active"] is True # pyright: ignore[reportAttributeAccessIssue]

@pytest.mark.django_db
def test_wallet_detail_other_user(user,wallets_2):
    client=APIClient()
    client.force_authenticate(user=user)
    other_wallet=wallets_2[Wallet.Currency.USDT]
    response=client.get(reverse("wallet-detail",kwargs={"pk":other_wallet.id}))
    assert response.status_code == 404 # pyright: ignore[reportAttributeAccessIssue]
