from django.conf import settings
from elasticsearch import Elasticsearch

from apps.transactions.search_indexes import TRANSACTION_INDEX


def get_elasticsearch_client():
    return Elasticsearch(settings.ELASTICSEARCH_URL)

def get_transaction_document(transaction):
    visible_to_user_ids={
        transaction.initiated_by_id
    }
    if transaction.source_wallet_id:
        visible_to_user_ids.add(
        transaction.source_wallet.user_id
    )
    if transaction.destination_wallet_id:
        visible_to_user_ids.add(
            transaction.destination_wallet.user_id
        )
    return {
        "transaction_id":transaction.id,
        "visible_to_user_ids":list(visible_to_user_ids),
        "description":transaction.description,
        "tags":list(transaction.tags.values_list("name",flat=True)),
        "category":transaction.category,
        "status":transaction.status,
        "transaction_type":transaction.transaction_type,
        "created_at":transaction.created_at,
    }

def index_transaction(transaction):
    es=get_elasticsearch_client()
    try:
        document=get_transaction_document(transaction)

        response=es.index(
            index=TRANSACTION_INDEX,
            id=transaction.id,
            document=document,
        )
        return response["result"]
    finally:
        es.close()

def search_transactions(query:str,user_id:int,size:int = 1000)->list[int]:
    if not query.strip():
        return []
    es=get_elasticsearch_client()
    try:
        response=es.search(
            index=TRANSACTION_INDEX,
            size=size,
            source_includes=["transaction_id"],
            query={
                "bool":{
                    "filter":[
                        {
                            "term":{
                                "visible_to_user_ids":user_id,
                            }
                        }
                    ],
                    "must":[
                        {
                            "multi_match":{
                                "query":query,
                                "fields":[
                                    "description^2",
                                    "tags"
                                ]
                            }
                        }
                    ]
                }
            }
        )
        return[
            hit["_source"]["transaction_id"]
            for hit in response["hits"]["hits"]
        ]
    finally:
        es.close()