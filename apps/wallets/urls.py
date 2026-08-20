from django.urls import path

from . import views

urlpatterns=[
    path('',views.wallet_list_view,name='wallet-list'),
    path("<int:pk>/",views.wallet_detail_view,name='wallet-detail')
]