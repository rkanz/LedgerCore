
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/transactions/', include('apps.transactions.urls')),
    path('api/token/',TokenObtainPairView.as_view(),name='token-obtain'),
    path('api/token/refresh/',TokenRefreshView.as_view(),name='token-refresh'),

    path('api/accounts/',include('apps.accounts.urls')),

    path('api/wallets/',include('apps.wallets.urls')),

    path('api/schema/',SpectacularAPIView.as_view(),name="schema"),
    path('api/docs/',SpectacularRedocView.as_view(url_name='schema'),name="redoc"),
    path('api/swagger/',SpectacularSwaggerView.as_view(url_name='schema'),name='swagger-ui')
]
