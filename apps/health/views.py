from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views import View
from elasticsearch import Elasticsearch


class HealthCheckView(View):
   
    def get(self,request):
        health_status={
            "database":"ok",
            "status":"ok",
            "redis":"ok",
            "elasticsearch": "ok"
        }
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception: # noqa: BLE001
            health_status["status"] = "error"
            health_status ["database"] = "error"
        try:
            cache.set("health_check","ok",timeout=10)
            if cache.get("health_check") != "ok":
                raise RuntimeError("Redis health check failed.")
        except Exception:  # noqa: BLE001
            health_status["status"] = "error"
            health_status ["redis"] = "error"
        es = Elasticsearch(
            settings.ELASTICSEARCH_URL,
            request_timeout=2,
        )

        try:
            if not es.ping():
                health_status["elasticsearch"] = "error"
        except Exception:  # noqa: BLE001
            health_status["elasticsearch"] = "error"
        finally:
            es.close()
        status_code = 200 if health_status["status"] == "ok" else 503

        return JsonResponse(health_status, status=status_code)

