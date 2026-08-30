from django.db import transaction
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer
from .services import register_user
from .tasks import send_welcome_email


@extend_schema(
    summary="Register a new user.",
    description="Creates a new user account and initializes wallets for all supported currencies.",
    request=RegisterSerializer,
    tags=["Authentication"],
    responses={
        201:RegisterSerializer,
        404:OpenApiResponse(
            description="Invalid Registration data."
        )
    },examples=[
    OpenApiExample(
        "Register user",
        summary="Create a new account",
        value={
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "password1": "StrongPassword123!",
            "password2": "StrongPassword123!",
        },
        request_only=True,
    ),
]

)

class RegisterAPIView(generics.CreateAPIView):
    permission_classes=[AllowAny]
    serializer_class=RegisterSerializer

    def perform_create(self, serializer):
        user = register_user(
        validated_data=serializer.validated_data
    )
        serializer.instance = user
        transaction.on_commit(
        lambda:send_welcome_email.delay(user.id)   # type: ignore
        )
register_view=RegisterAPIView.as_view()

@extend_schema(
    summary="User Login",
    description="Authenticates the user and return JWT access and refresh tokens.",
    tags=["Authentication"],
    examples=[
        OpenApiExample(
            "Login Request",
            value={
                "username":"testuser",
                "password":"StrongPassword123"
            },request_only=True
        ),OpenApiExample(
            "Successful Response",
            value={
                "refresh":"eyJhbGc...",
                "access":"eyJhbGc..."
            },response_only=True
        ),
    ],
)
class LoginAPIView(TokenObtainPairView):
    pass
login_view=LoginAPIView.as_view()
