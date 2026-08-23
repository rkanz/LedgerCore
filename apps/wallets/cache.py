from django.core.cache import cache

WALLET_CACHE_TTL = 60


def wallet_list_cache_key(user_id):
    return f"wallets:user:{user_id}"


def wallet_detail_cache_key(user_id, wallet_id):
    return f"wallet:{user_id}:{wallet_id}"

def invalidate_wallet_list_cache(user_id):
    cache.delete(wallet_list_cache_key(user_id))


def invalidate_wallet_detail_cache(user_id, wallet_id):
    cache.delete(wallet_detail_cache_key(user_id, wallet_id))


def invalidate_user_wallet_cache(user_id, wallet_id=None):
    invalidate_wallet_list_cache(user_id)

    if wallet_id is not None:
        invalidate_wallet_detail_cache(user_id, wallet_id)