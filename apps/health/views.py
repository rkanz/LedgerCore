from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views import View


class HealthCheckView(View):
   
    def get(self,request):
        health_status={
            "database":"ok",
            "status":"ok",
            "redis":"ok"
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
        if health_status["status"] == "ok":
            return JsonResponse(health_status, status=200)

        return JsonResponse(health_status, status=503)

