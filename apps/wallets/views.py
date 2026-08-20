from rest_framework import generics

from .models import Wallet
from .serializers import WalletSerializer


class WalletListAPIView(generics.ListAPIView):
    serializer_class=WalletSerializer
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user,is_active=True).order_by('id')
    
wallet_list_view = WalletListAPIView.as_view()

class WalletDetailAPIView(generics.RetrieveAPIView):
    serializer_class=WalletSerializer
    def get_queryset(self):
        return Wallet.objects.filter(
            user=self.request.user,
            is_active=True,
        ) 

wallet_detail_view = WalletDetailAPIView.as_view()