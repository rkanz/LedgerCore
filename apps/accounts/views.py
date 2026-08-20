from rest_framework import generics
from rest_framework.permissions import AllowAny

from .serializers import RegisterSerializer
from .services import register_user


class RegisterAPIView(generics.CreateAPIView):
    permission_classes=[AllowAny]
    serializer_class=RegisterSerializer

    def perform_create(self, serializer):
        user = register_user(
        validated_data=serializer.validated_data
    )
        serializer.instance = user
register_view=RegisterAPIView.as_view()