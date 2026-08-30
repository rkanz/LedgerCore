from django.core.cache import cache

EXCHANGE_RATE_TTL=60

def exchange_rate_list_cache_key(path):
    return f"exchange:rates{path}"

def invalidate_exchange_rate_cache():
    cache.delete_pattern("exchange:rates:*") # pyright: ignore[reportAttributeAccessIssue]