from django.urls import path

from . import views

urlpatterns=[
    path("rates/",views.exchange_rate_list_view,name='exchange-rate-list'),
    path("",views.exchange_transaction_view,name='exchange-transaction')
]