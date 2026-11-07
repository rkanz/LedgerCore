
TRANSACTION_INDEX = "ledgercore_transactions"

TRANSACTION_SETTINGS = {
    "analysis": {
        "filter": {
            "transaction_edge_ngram": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 30,
            }
        },
        "analyzer": {
            "transaction_index_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                    "transaction_edge_ngram",
                ],
            },
            "transaction_search_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": [
                    "lowercase",
                ],
            },
        },
    }
}

TRANSACTION_MAPPING = {
    "properties": {
        "transaction_id": {
            "type": "integer",
        },
        "visible_to_user_ids": {
            "type": "integer",
        },
        "description": {
            "type": "text",
            "analyzer": "transaction_index_analyzer",
            "search_analyzer": "transaction_search_analyzer",
        },
        "tags": {
            "type": "text",
            "analyzer": "transaction_index_analyzer",
            "search_analyzer": "transaction_search_analyzer",
        },
        "category": {
            "type": "keyword",
        },
        "status": {
            "type": "keyword",
        },
        "created_at": {
            "type": "date",
        },
        "transaction_type": {
            "type": "keyword",
        },
    }
}


def create_transaction_index():
    from .search import get_elasticsearch_client

    es = get_elasticsearch_client()

    try:
        if es.indices.exists(index=TRANSACTION_INDEX):
            return False

        es.indices.create(
            index=TRANSACTION_INDEX,
            settings=TRANSACTION_SETTINGS,
            mappings=TRANSACTION_MAPPING,
        )
        return True
    finally:
        es.close()


def reindex_all_transactions():
    from apps.transactions.models import Transaction
    from apps.transactions.search import index_transaction

    transactions = Transaction.objects.select_related(
        "initiated_by",
        "source_wallet",
        "destination_wallet",
    ).prefetch_related("tags")

    for transaction in transactions.iterator(chunk_size=500):
        index_transaction(transaction)
