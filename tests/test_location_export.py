import csv
import io
import json

import pytest
from django.utils import timezone

from tests.factories import CategoryFactory, LocationFactory, ReviewFactory

pytestmark = pytest.mark.django_db

EXPORT_URL = "/api/locations/export/"
HEADER = [
    "id",
    "title",
    "description",
    "category",
    "author",
    "address",
    "latitude",
    "longitude",
    "avg_rating",
    "reviews_count",
    "views_7d",
    "popularity",
    "created_at",
]


def read_csv(response):
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_csv_export(api_client):
    location = LocationFactory(title="Андріївський узвіз")
    ReviewFactory(location=location, rating=5)

    response = api_client.get(EXPORT_URL, {"export_format": "csv"})

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    filename = f"locations_{timezone.localdate():%Y-%m-%d}.csv"
    assert response["Content-Disposition"] == f'attachment; filename="{filename}"'
    assert response.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    rows = read_csv(response)
    assert list(rows[0]) == HEADER
    assert rows[0]["title"] == "Андріївський узвіз"
    assert rows[0]["category"] == location.category.name
    assert (rows[0]["avg_rating"], rows[0]["reviews_count"]) == ("5.0", "1")


def test_json_export(api_client):
    location = LocationFactory()

    response = api_client.get(EXPORT_URL, {"export_format": "json"})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json; charset=utf-8"
    data = json.loads(response.content)
    assert [row["id"] for row in data] == [location.id]
    assert data[0]["avg_rating"] is None  # no reviews
    assert data[0]["latitude"] == 50.4501
    assert list(data[0]) == HEADER


def test_export_applies_filters_and_excludes_soft_deleted(api_client):
    category = CategoryFactory()
    wanted = LocationFactory(category=category)
    LocationFactory(category=category).soft_delete()
    LocationFactory()  # other category

    response = api_client.get(EXPORT_URL, {"export_format": "json", "category": category.id})

    assert [row["id"] for row in json.loads(response.content)] == [wanted.id]


def test_export_is_not_paginated(api_client):
    LocationFactory.create_batch(25)  # more than one page
    response = api_client.get(EXPORT_URL, {"export_format": "csv"})
    assert len(read_csv(response)) == 25


def test_empty_csv_export_has_header(api_client):
    response = api_client.get(EXPORT_URL, {"export_format": "csv"})
    assert response.content.decode("utf-8-sig").strip().split(",") == HEADER


@pytest.mark.parametrize("params", [{}, {"export_format": "xml"}])
def test_invalid_export_format_returns_400(api_client, params):
    response = api_client.get(EXPORT_URL, params)
    assert response.status_code == 400
    assert "export_format" in response.data


def test_drf_format_param_is_not_the_export_switch(api_client):
    # DRF reserves ?format= for renderer negotiation (no "csv" renderer -> 404),
    # which is why the parameter is called export_format
    assert api_client.get(EXPORT_URL, {"format": "csv"}).status_code == 404


def test_created_at_matches_api_timezone(api_client):
    location = LocationFactory()
    exported = json.loads(api_client.get(EXPORT_URL, {"export_format": "json"}).content)
    detail = api_client.get(f"/api/locations/{location.pk}/").data
    assert exported[0]["created_at"] == detail["created_at"]
