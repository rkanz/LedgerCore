import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_exchange_rate(exchange_rate):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)( # type: ignore
        "exchange_rates",
        {
            "type":"exchange_rate_update",
            "data":{
                "base_currency":exchange_rate.base_currency,
                "quote_currency":exchange_rate.quote_currency,
                "rate":str(exchange_rate.rate)
            },
        },
    )
def send_notification(*,user_id:int,data:dict):
    
    channel_layer=get_channel_layer()
    group_name = f"notifications_user_{user_id}"
    try:
        async_to_sync(channel_layer.group_send)( # type: ignore
            group_name,
            {
                "type":"notification",
                "data":data
            }
        )
        logger.info(
            "Notification sent: user_id=%s type=%s transaction_id=%s",
            user_id,
            data.get("type"),
            data.get("transaction_id"),
        )        
    except Exception:
        logger.exception(
            "Failed to send notification:"
            "user_id=%s type=%s transaction_id=%s",
            user_id,
            data.get("type"),
            data.get("transaction_id")
        )
        raise