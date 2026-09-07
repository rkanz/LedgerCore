import asyncio

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import Client

from apps.accounts.services import register_user
from apps.exchange.models import ExchangeRate
from apps.realtime.realtime import broadcast_exchange_rate, send_notification
from config.asgi import application


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_exchange_rate_realtime():
    exchange_rate= await ExchangeRate.objects.acreate(
        base_currency="EUR",
        quote_currency="USD",
        rate="1.163",
    )
    communicator = WebsocketCommunicator(
        application,
        "/ws/exchange-rates/",
    )
    connected, _ = await communicator.connect()

    assert connected is True
    await sync_to_async(broadcast_exchange_rate)(
        exchange_rate
    )
    data = await communicator.receive_json_from()
    assert data == {
        "base_currency": "EUR",
        "quote_currency": "USD",
        "rate": "1.163",
    }
    await communicator.disconnect()


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
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_notification_consumer_connects(user):
    client = Client()
    logged_in=await sync_to_async(client.login)(
        username=user.username,
        password="testpassword123"
    )
    assert logged_in is True
    session_cookie = client.cookies["sessionid"].value
    communicator = WebsocketCommunicator(
        application,
        "/ws/notifications/",
        headers=[
            (
                b"cookie",
                f"sessionid={session_cookie}".encode(),
            )
        ],
    )
    connected,_=await communicator.connect()
    assert connected is True

    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_send_notification(user):
    client = Client()

    logged_in = await sync_to_async(client.login)(
        username=user.username,
        password="testpassword123",
    )

    assert logged_in is True
    session_cookie = client.cookies["sessionid"].value

    communicator = WebsocketCommunicator(
        application,
        "/ws/notifications/",
        headers=[
            (
                b"cookie",
                f"sessionid={session_cookie}".encode(),
            )
        ],
    )

    connected, _ = await communicator.connect()
    assert connected is True
    await sync_to_async(send_notification)(
        user_id=user.id,
        data={
            "type": "withdraw",
            "message": "100 USDT از کیف پول شما برداشت شد.",
            "transaction_id": 123,
        },
    ) # type: ignore
    data = await communicator.receive_json_from()
    assert data == {
        "type": "withdraw",
        "message": "100 USDT از کیف پول شما برداشت شد.",
        "transaction_id": 123,
    }
    await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_notification_user_isolation(user):
    client = Client()

    logged_in = await sync_to_async(client.login)(
        username=user.username,
        password="testpassword123",
    )

    assert logged_in is True

    session_cookie = client.cookies["sessionid"].value

    alice = WebsocketCommunicator(
        application,
        "/ws/notifications/",
        headers=[
            (
                b"cookie",
                f"sessionid={session_cookie}".encode(),
            )
        ],
    )

    connected, _ = await alice.connect()
    assert connected is True

    bob = await sync_to_async(register_user)(
        validated_data={
            "username": "bob",
            "first_name": "Bob",
            "last_name": "Test",
            "email": "bob@test.com",
            "password1": "testpassword123",
            "password2": "testpassword123",
        }
    )

    bob_client = Client()
    logged_in = await sync_to_async(bob_client.login)(
        username=bob.username,
        password="testpassword123",
    )

    assert logged_in is True
    bob_session_cookie = bob_client.cookies["sessionid"].value

    bob_communicator = WebsocketCommunicator(
        application,
        "/ws/notifications/",
        headers=[
            (
                b"cookie",
                f"sessionid={bob_session_cookie}".encode(),
            )
        ],
    )
    connected, _ = await bob_communicator.connect()
    assert connected is True
    await sync_to_async(send_notification)(
        user_id=user.id,
        data={
            "type": "withdraw",
            "message": "100 USDT از کیف پول شما برداشت شد.",
            "transaction_id": 123,
        },
    )
    data=await alice.receive_json_from()
    assert data == {
            "type": "withdraw",
            "message": "100 USDT از کیف پول شما برداشت شد.",
            "transaction_id": 123,
    }
    with pytest.raises(asyncio.TimeoutError):
        await bob_communicator.receive_json_from(timeout=0.2)
    await alice.disconnect()


@pytest.mark.asyncio
async def test_notification_consumer_rejects_anonymous():
    communicator = WebsocketCommunicator(
        application,
        "/ws/notifications/",
    )

    connected, _ = await communicator.connect()

    assert connected is False