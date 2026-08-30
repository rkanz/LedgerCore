from django.core.cache import cache
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import generics
from rest_framework.response import Response

from .cache import WALLET_CACHE_TTL, wallet_detail_cache_key, wallet_list_cache_key
from .models import Wallet
from .serializers import WalletSerializer


@extend_schema(
    summary="List user wallets",
    description="""
    Return all active wallets belonging to the authenticated user.

    Each user has a separate wallet for every supported currency.
    """,
    tags=["Wallets"],
    responses={
        200: WalletSerializer(many=True),
    },
)
class WalletListAPIView(generics.ListAPIView):
    serializer_class=WalletSerializer
    def list(self,request,*args,**kwargs):
        cache_key=wallet_list_cache_key(request.user.id)
        cached_data=cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        queryset=self.get_queryset()
        serializer=self.get_serializer(queryset,many=True)
        cache.set(cache_key,serializer.data,timeout=WALLET_CACHE_TTL)
        return Response(serializer.data)
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user,is_active=True).order_by('id')
    
wallet_list_view = WalletListAPIView.as_view()

@extend_schema(
    summary="Retrieve wallet details",
    description="""
    Return detailed information about an active wallet belonging
    to the authenticated user.
    """,
    tags=["Wallets"],
    responses={
        200: WalletSerializer,
        404: OpenApiResponse(
            description="Wallet not found or does not belong to the user."
        ),
    },
)
class WalletDetailAPIView(generics.RetrieveAPIView):
    serializer_class=WalletSerializer
    def retrieve(self,request,*args,**kwargs):
        cache_key=wallet_detail_cache_key(request.user.id,kwargs["pk"])
        cache_data=cache.get(cache_key)
        if cache_data is not None:
            return Response(cache_data)
        instance=self.get_object()
        serializer=self.get_serializer(instance)
        cache.set(cache_key,serializer.data,timeout=WALLET_CACHE_TTL)
        return Response(serializer.data)

    def get_queryset(self):
        return Wallet.objects.filter(
            user=self.request.user,
            is_active=True,
        ) 

wallet_detail_view = WalletDetailAPIView.as_view()