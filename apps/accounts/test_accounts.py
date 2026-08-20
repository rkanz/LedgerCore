import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_register_api():
    client=APIClient()
    response=client.post(reverse("register"),
        {
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "email": "newuser@example.com",
            "password1": "StrongPass123",
            "password2": "StrongPass123",
        },)
    assert response.status_code == 201 # pyright: ignore[reportAttributeAccessIssue]
    user=User.objects.get(username="newuser")
    assert user.email == "newuser@example.com" # pyright: ignore[reportIndexIssue]
    assert user.check_password("StrongPass123")
    assert Wallet.objects.filter(user=user).count() == 3
    assert set(
        Wallet.objects.filter(user=user).values_list("currency", flat=True)
    ) == {
        Wallet.Currency.IRR,
        Wallet.Currency.USDT,
        Wallet.Currency.BTC,
    }

@pytest.mark.django_db
def test_password_mismatch():
    client=APIClient()
    response=client.post(reverse("register"),
        {
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "email": "newuser@example.com",
            "password1": "StrongPass123",
            "password2": "StrongPass1234",
        },)
    assert response.status_code == 400  # pyright: ignore[reportAttributeAccessIssue]
    assert "password2" in response.data  # pyright: ignore[reportAttributeAccessIssue]
    assert response.data["password2"][0]== "Password does not match." # pyright: ignore[reportAttributeAccessIssue]
    assert not User.objects.filter(username="newuser").exists()

@pytest.mark.django_db
def test_short_password():
    client=APIClient()
    response=client.post(reverse("register"),
        {
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "email": "newuser@example.com",
            "password1": "Pass123",
            "password2": "Pass123",
        },)
    assert response.status_code == 400  # pyright: ignore[reportAttributeAccessIssue]
    assert not User.objects.filter(username="newuser").exists()
    assert "password1" in response.data # pyright: ignore[reportAttributeAccessIssue]
    assert "password2" in response.data # pyright: ignore[reportAttributeAccessIssue]