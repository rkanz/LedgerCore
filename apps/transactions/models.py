from django.conf import settings
from django.db import models

from apps.wallets.models import Wallet


# Create your models here.
class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT="DEPOSIT","Deposit"
        WITHDRAW="WITHDRAW","Withdraw"
        TRANSFER="TRANSFER","Transfer"
    class TransactionStatus(models.TextChoices):
        PENDING="PENDING","Pending"
        COMPLETED="COMPLETED","Completed"
        FAILED="FAILED","Failed"
    source_wallet=models.ForeignKey(
        Wallet,on_delete=models.PROTECT,
        related_name="transactions",null=True,blank=True
    )
    destination_wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT,
                                         related_name="incoming_transactions",null=True,blank=True)
    transaction_type=models.CharField(max_length=20,choices=TransactionType.choices)
    status=models.CharField(max_length=20,choices=TransactionStatus.choices,default=TransactionStatus.PENDING)
    amount=models.DecimalField(max_digits=20,decimal_places=8)
    currency=models.CharField(max_length=10,choices=Wallet.Currency.choices)
    idempotency_key=models.UUIDField(unique=True)
    created_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    initiated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="initiated_transactions")

class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        DEBIT="DEBIT","Debit"
        CREDIT="CREDIT","Credit"
    transaction=models.ForeignKey(Transaction,on_delete=models.PROTECT,related_name="ledger_entries") 
    created_at=models.DateTimeField(auto_now_add=True)  
    amount=models.DecimalField(max_digits=20,decimal_places=8)
    entry_type=models.CharField(max_length=6,choices=EntryType.choices)
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT,related_name="ledger_entries")
