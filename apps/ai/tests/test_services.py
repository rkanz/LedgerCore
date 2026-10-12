import uuid
from unittest.mock import patch

import pytest

from apps.ai.services import (
    categorize_transaction,
    generate_financial_summary,
    safe_categorize_transaction,
)
from apps.analytics.services import get_financial_summary
from apps.transactions.models import Category, Transaction
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_categorize_transaction(user,wallets):
    transaction=Transaction.objects.create(
        source_wallet=wallets["USDT"],
        transaction_type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount="50",
        currency="USDT",
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
        description="خرید نان و شیر از فروشگاه"
    )
    result=categorize_transaction(transaction)
    transaction.refresh_from_db()

    print("SAVED CATEGORY:", transaction.category)
    print(
        "SAVED TAGS:",
        list(transaction.tags.values_list("name", flat=True))
    )
    print("AI RESULT:", result)
    assert result is not None
    assert result.category.value == "FOOD"
    assert 0 <= result.confidence <= 1
    assert 1 <= len(result.tags) <= 3
    assert list(transaction.tags.values_list("name", flat=True)) == ["groceries"]


@pytest.mark.django_db
def test_safe_categorize_transaction_handles_ai_failure(user,wallets,caplog):
    transaction=Transaction.objects.create(
        source_wallet=wallets["USDT"],
        transaction_type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount="50",
        currency="USDT",
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
        description="خرید نان و شیر از فروشگاه"
    )
    with patch(
        "apps.ai.services.categorize_transaction",
        side_effect=Exception("AI service unavailable")
    ):
        safe_categorize_transaction(transaction.id) # type: ignore
    transaction.refresh_from_db()

    assert transaction.status == Transaction.TransactionStatus.COMPLETED
    assert "AI transaction categorization failed:" in caplog.text
    assert str(transaction.id) in caplog.text # type: ignore

@pytest.mark.django_db
def test_safe_categorize_transaction_description_is_empty(user,wallets):
    transaction=Transaction.objects.create(
        source_wallet=wallets["USDT"],
        transaction_type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount="50",
        currency="USDT",
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
        description= " "
    )
    with patch("apps.ai.services.CloudflareAIClient") as mock_client:
        result = categorize_transaction(transaction)
    transaction.refresh_from_db()
    assert result is None
    assert transaction.category == Category.OTHER
    assert not transaction.tags.exists()
    mock_client.assert_not_called()

@pytest.mark.django_db
def test_categorize_transaction_random_description(user, wallets):
    transaction = Transaction.objects.create(
        source_wallet=wallets["USDT"],
        transaction_type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount="50",
        currency="USDT",
        idempotency_key=uuid.uuid4(),
        initiated_by=user,
        description="sdnasndjasnd 12328380",
    )
    result=categorize_transaction(transaction)
    transaction.refresh_from_db()
    
    print("DESCRIPTION:", transaction.description)
    print("CATEGORY:", transaction.category)
    print("CONFIDENCE:", result.confidence) # type: ignore
    print("TAGS:", list(transaction.tags.values_list("name", flat=True)))

@pytest.mark.django_db
def test_generate_financial_summary(wallets,user,financial_summary_data):
    wallet=wallets[Wallet.Currency.USDT]
    financial_data = get_financial_summary(
        wallet=wallet,
        period="month",
    )
    result=generate_financial_summary(financial_data)
    print(result)
    assert result.summary
    assert 1 <= len(result.insights) <= 4
    assert 1 <= len(result.recommendations) <= 3