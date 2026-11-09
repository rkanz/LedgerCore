from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_check_success():
    client=APIClient()
    response=client.get(reverse("health-check"))
    assert response.status_code == 200 # type: ignore
    assert response.json() == { # type: ignore
        "database": "ok",
        "status": "ok",
        "redis": "ok",
        "elasticsearch": "ok"
    }

@pytest.mark.django_db
@patch("apps.health.views.cache.set")
def test_health_check_redis_failure(mock_cache_set):
    mock_cache_set.side_effect=Exception("Redis unavailable")
    client=APIClient()
    response=client.get(reverse("health-check"))
    assert response.status_code == 503 # type: ignore
    assert response.json() == { # type: ignore
        "database":"ok",
        "status":"error",
        "redis":"error",
        "elasticsearch": "ok"
    }

@pytest.mark.django_db
@patch("apps.health.views.connection.cursor")
def test_health_check_data_base_failure(mock_cursor):
    mock_cursor.side_effect=Exception("Database unavailable")
    client=APIClient()
    response=client.get(reverse("health-check"))
    assert response.status_code == 503 # type: ignore
    assert response.json() == { # type: ignore
        "database":"error",
        "status":"error",
        "redis":"ok",
        "elasticsearch": "ok"
    }

@pytest.mark.django_db
@patch("apps.health.views.Elasticsearch")
def test_health_check_elasticsearch_failure(mock_elasticsearch):
    mock_es = mock_elasticsearch.return_value
    mock_es.ping.return_value = False

    client = APIClient()
    response = client.get(reverse("health-check"))

    assert response.status_code == 200  # type: ignore
    assert response.json() == {  # type: ignore
        "database": "ok",
        "status": "ok",
        "redis": "ok",
        "elasticsearch": "error"
    }

    mock_es.close.assert_called_once()