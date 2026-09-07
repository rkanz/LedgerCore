from django.urls import path

from .consumers import ExchangeRateConsumer, NotificationConsumer

websocket_urlpatterns=[
    path("ws/exchange-rates/",ExchangeRateConsumer.as_asgi(),), # type: ignore
    path("ws/notifications/",NotificationConsumer.as_asgi(),), # type: ignore
]