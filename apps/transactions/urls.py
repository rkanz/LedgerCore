from django.urls import path

from . import views

app_name='transactions'

urlpatterns=[

    path('deposit/',views.deposit_view,name='deposit'),
    path('withdraw/',views.withdraw_view,name='withdraw'),
    path('transfer/', views.transfer_view, name='transfer'),
    path("", views.transaction_history_view, name="transaction-history"),
    path("<int:pk>/", views.transaction_detail_view, name="transaction-detail"),
    path('frequent-recipients/',views.frequent_recipients_view,name='frequent-recipients'),
    path('recent-recipients/',views.recent_recipients_view,name='recent-recipients')

]