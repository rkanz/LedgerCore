from celery import shared_task

from apps.exchange.services import save_exchange_rate


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def update_exchange_rate(
    self,base_currency:str,quote_currency:str
):
    exchange_rate=save_exchange_rate(
        base_currency=base_currency,
        quote_currency=quote_currency
    )
    return {
        "id":exchange_rate.id, # pyright: ignore[reportAttributeAccessIssue]
        "base_currency":exchange_rate.base_currency,
        "quote_currency":exchange_rate.base_currency,
        "rate":str(exchange_rate.rate)
    }