from django.urls import path

from . import views

app_name='analytics'

urlpatterns=[
    path('income/',views.income_view,name='income'),
    path('expense/',views.expense_view,name='expense'),
    path('summary/',views.summary_view,name='summary'),
    path('monthly-report/',views.monthly_report_view,name='monthly-report'),
    path('balance-history/',views.balance_history_view,name='balance-history')
]