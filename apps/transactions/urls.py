from django.urls import path

from . import views

app_name='transactions'

urlpatterns=[

    path('deposit/',views.deposit_view,name='deposit'),
    path('withdraw/',views.withdraw_view,name='withdraw'),
    path('transfer/', views.transfer_view, name='transfer'),
    path("", views.transaction_history_view, name="transaction-history"),
    path("<int:pk>/", views.transaction_detail_view, name="transaction-detail"),

]