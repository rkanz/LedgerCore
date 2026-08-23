from django.core.cache import cache

TRANSACTION_CACHE_TTL = 60


def transaction_history_cache_key(user_id,path):
    return f"transactions:user:{user_id}:{path}"

def transaction_history_detail_cache_key(user_id,transaction_id):
    return f"transactions:{user_id}:{transaction_id}"

def invalidate_transaction_history_cache(user_id):
    cache.delete_pattern(  # pyright: ignore[reportAttributeAccessIssue]
        f"transactions:user:{user_id}:*"
    )
def invalidate_transaction_history_detail_cache(user_id,transaction_id):
    cache.delete(transaction_history_detail_cache_key(user_id,transaction_id))

def invalidate_user_transaction_cache(user_id,transaction_id=None):
    invalidate_transaction_history_cache(user_id)
    if transaction_id is not None:
        invalidate_transaction_history_detail_cache(user_id,transaction_id)

