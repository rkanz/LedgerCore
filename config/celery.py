import os

from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"

)
app=Celery("config")

app.config_from_object('django.conf:settings',namespace='CELERY')

app.conf.beat_schedule={
    "update-eur-usd-every-15-minutes":{
        "task":"apps.exchange.tasks.update_exchange_rate",
        "schedule":900.0,
        "args":("EUR","USD"),
    },
    "update-usd-eur-every-15minutes":{
        "task":"apps.exchange.tasks.update_exchange_rate",
        "schedule":900.0,
        "args":("USD","EUR"),
    },

}

app.autodiscover_tasks()
