import pytest

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
