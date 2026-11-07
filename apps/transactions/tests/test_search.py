from unittest.mock import patch

import pytest

from apps.transactions.models import Tag, Transaction
from apps.transactions.search import (
    get_elasticsearch_client,
    get_transaction_document,
    index_transaction,
    search_transactions,
)
from apps.transactions.search_indexes import TRANSACTION_INDEX
from apps.wallets.models import Wallet


@pytest.mark.django_db
def test_get_transaction_document(ali,ali_wallets,wallets,create_transfer):
    source_wallet=ali_wallets[Wallet.Currency.USDT]
    destination_wallet=wallets[Wallet.Currency.USDT]
    transaction=create_transfer(
        initiated_by=ali,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount="50"
    )
    transaction.description = "Grocery shopping"
    transaction.category = "FOOD"
    transaction.save(update_fields=["description", "category"])
    grocery_tag = Tag.objects.create(name="grocery")
    food_tag = Tag.objects.create(name="food")
    transaction.tags.add(grocery_tag, food_tag)
    document=get_transaction_document(transaction)

    assert document["transaction_id"] == transaction.pk
    assert set(document["visible_to_user_ids"]) == {
        ali.id,
        source_wallet.user_id,
        destination_wallet.user_id,
    }
    assert document["description"] == "Grocery shopping"
    assert set(document["tags"]) == {"grocery","food"}
    assert document["category"] == "FOOD"
    assert document["status"] == Transaction.TransactionStatus.COMPLETED
    assert document["created_at"] == transaction.created_at
    assert document["transaction_type"] == Transaction.TransactionType.TRANSFER


@pytest.mark.django_db
def test_get_index_transaction(ali, ali_wallets, wallets, create_transfer):
    with patch(
        "apps.transactions.search_indexes.create_transaction_index",
    ), patch(
        "apps.transactions.search.get_elasticsearch_client",
    ) as mock_client:

        source_wallet = ali_wallets[Wallet.Currency.USDT]
        destination_wallet = wallets[Wallet.Currency.USDT]

        transaction = create_transfer(
            initiated_by=ali,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            amount="50",
        )

        transaction.description = "Grocery shopping"
        transaction.category = "FOOD"
        transaction.save(update_fields=["description", "category"])

        grocery_tag = Tag.objects.create(name="grocery")
        food_tag = Tag.objects.create(name="food")
        transaction.tags.add(grocery_tag, food_tag)

        mock_es = mock_client.return_value
        mock_es.index.return_value = {"result": "created"}

        result = index_transaction(transaction)

        mock_es.index.assert_called_once_with(
            index="ledgercore_transactions",
            id=transaction.id,
            document=get_transaction_document(transaction),
        )

        assert result == "created"
        mock_es.close.assert_called_once()

@pytest.mark.django_db
def test_index_transaction_in_elasticsearch(user,wallets,wallets_2,create_transfer):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    transaction=create_transfer(
        initiated_by=user,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount="50"
    )
    transaction.description = "Elasticsearch integration test"
    transaction.save(update_fields=["description"])
    es = get_elasticsearch_client()
    try:
        es.options(ignore_status=[404]).delete(
            index=TRANSACTION_INDEX,
            id=transaction.id,
        )
    finally:
        es.close()
    result=index_transaction(transaction)
    assert result == "created"
    es = get_elasticsearch_client()
    try:
        es.indices.refresh(index=TRANSACTION_INDEX)
        document=es.get(index=TRANSACTION_INDEX,id=transaction.id)
        assert document["_source"]["transaction_id"] == transaction.id
        assert document["_source"]["description"] == "Elasticsearch integration test"
    finally:
        es.options(ignore_status=[404]).delete(
            index=TRANSACTION_INDEX,
            id=transaction.id,
        )
        es.close()

@pytest.mark.django_db
def test_index_multiple_transactions(user,wallets,wallets_2,create_transfer):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    food_transaction=create_transfer(
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            amount="50"
    )
    food_transaction.description = "Grocery shopping"
    food_transaction.category = "FOOD"
    food_transaction.save(update_fields=["description", "category"])
    food_tag = Tag.objects.create(name="food")
    food_transaction.tags.add(food_tag)
    transport_transaction=create_transfer(
            initiated_by=user,
            source_wallet=source_wallet,
            destination_wallet=destination_wallet,
            amount="20"
    )
    transport_transaction.description = "Taxi ride"
    transport_transaction.category = "TRANSPORT"
    transport_transaction.save(update_fields=["description", "category"])
    transport_tag = Tag.objects.create(name="transport")
    transport_transaction.tags.add(transport_tag)

    es = get_elasticsearch_client()
    try:
        for transaction in (food_transaction, transport_transaction):
            es.options(ignore_status=[404]).delete(
                index=TRANSACTION_INDEX,
                id=transaction.id,
            )
    finally:
        es.close()

    es = get_elasticsearch_client()
    try:
        assert index_transaction(food_transaction) == "created"
        assert index_transaction(transport_transaction) == "created"
        es=get_elasticsearch_client()
        try:
            es.indices.refresh(index=TRANSACTION_INDEX)
            food_document=es.get(index=TRANSACTION_INDEX,id=food_transaction.id)
            transport_document=es.get(index=TRANSACTION_INDEX,id=transport_transaction.id)
            assert food_document["_source"]["transaction_id"] == food_transaction.id
            assert food_document["_source"]["description"] == "Grocery shopping"
            assert food_document["_source"]["tags"]== ["food"]
            assert transport_document["_source"]["transaction_id"] == transport_transaction.id
            assert transport_document["_source"]["description"] == "Taxi ride"
            assert transport_document["_source"]["tags"] == ["transport"]
        finally:
            es.close()
    finally:
        es = get_elasticsearch_client()
        try:
            for transaction in (food_transaction, transport_transaction):
                es.options(ignore_status=[404]).delete(
                    index=TRANSACTION_INDEX,
                    id=transaction.id,)
        finally:
            es.close()

@pytest.mark.django_db
def test_search_transactions(user,wallets,wallets_2,create_transfer):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    transaction=create_transfer(
        initiated_by=user,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount="50"
    )
    transaction.description = "Grocery shopping"
    transaction.save(update_fields=["description"])

    tag = Tag.objects.create(name="food")
    transaction.tags.add(tag)
    es = get_elasticsearch_client()

    try:
        es.options(ignore_status=[404]).delete(
            index=TRANSACTION_INDEX,
            id=transaction.id,
        )
    finally:
        es.close()

    assert index_transaction(transaction) == "created"

    es = get_elasticsearch_client()
    try:
        es.indices.refresh(index=TRANSACTION_INDEX)
    finally:
        es.close()

    description_results = search_transactions(
        query="Grocery",
        user_id=user.id
    )
    tag_results=search_transactions(
        query="food",
        user_id=user.id
    )
    assert transaction.id in description_results
    assert transaction.id in tag_results

@pytest.mark.django_db
def test_index_transaction_creates_index(user,wallets,wallets_2,create_transfer):
    source_wallet=wallets[Wallet.Currency.USDT]
    destination_wallet=wallets_2[Wallet.Currency.USDT]
    transaction=create_transfer(
        initiated_by=user,
        source_wallet=source_wallet,
        destination_wallet=destination_wallet,
        amount="50"
    )
    from apps.transactions.search import (
        get_elasticsearch_client,
        index_transaction,
    )
    from apps.transactions.search_indexes import TRANSACTION_INDEX

    es = get_elasticsearch_client()
    try:
        es.indices.delete(
            index=TRANSACTION_INDEX,
            ignore_unavailable=True,
        )
    finally:
        es.close()

    index_transaction(transaction)

    es = get_elasticsearch_client()
    try:
        assert es.indices.exists(index=TRANSACTION_INDEX)

        mapping = es.indices.get_mapping(index=TRANSACTION_INDEX)
        properties = mapping[TRANSACTION_INDEX]["mappings"]["properties"]

        assert properties["tags"]["analyzer"] == "transaction_index_analyzer"
    finally:
        es.close()