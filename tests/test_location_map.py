from decimal import Decimal

import pytest

from tests.factories import CategoryFactory, LocationFactory, LocationViewFactory, ReviewFactory

pytestmark = pytest.mark.django_db

MAP_URL = "/api/locations/map/"


def feature_ids(response):
    return [feature["id"] for feature in response.data["features"]]


def test_map_returns_geojson_feature_collection(api_client):
    location = LocationFactory(latitude=Decimal("50.4501"), longitude=Decimal("30.5234"))
    ReviewFactory(location=location, rating=4)

    response = api_client.get(MAP_URL)

    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    feature = response.data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {"type": "Point", "coordinates": [30.5234, 50.4501]}
    assert feature["properties"]["category"] == location.category.name
    assert feature["properties"]["avg_rating"] == 4.0
    assert set(feature["properties"]) == {"id", "title", "category", "avg_rating", "popularity"}


def test_map_default_ordering_is_most_popular_first(api_client):
    quiet = LocationFactory()
    popular = LocationFactory()
    LocationViewFactory.create_batch(5, location=popular)
    assert feature_ids(api_client.get(MAP_URL)) == [popular.id, quiet.id]


def test_map_limit(api_client):
    LocationFactory.create_batch(3)
    assert len(api_client.get(MAP_URL, {"limit": 2}).data["features"]) == 2


@pytest.mark.parametrize("limit", [0, 501, "abc"])
def test_map_invalid_limit(api_client, limit):
    response = api_client.get(MAP_URL, {"limit": limit})
    assert response.status_code == 400
    assert "limit" in response.data


def test_map_bbox(api_client):
    kyiv = LocationFactory(latitude=Decimal("50.45"), longitude=Decimal("30.52"))
    LocationFactory(latitude=Decimal("49.84"), longitude=Decimal("24.03"))  # Lviv

    response = api_client.get(MAP_URL, {"bbox": "30,50,31,51"})

    assert feature_ids(response) == [kyiv.id]


@pytest.mark.parametrize("bbox", ["30,50,31", "a,b,c,d", "31,50,30,51", "30,-91,31,51"])
def test_map_invalid_bbox(api_client, bbox):
    response = api_client.get(MAP_URL, {"bbox": bbox})
    assert response.status_code == 400
    assert "bbox" in response.data


def test_map_supports_list_filters(api_client):
    park = LocationFactory(category=CategoryFactory())
    LocationFactory()
    assert feature_ids(api_client.get(MAP_URL, {"category": park.category_id})) == [park.id]


def test_map_excludes_soft_deleted(api_client):
    LocationFactory().soft_delete()
    assert api_client.get(MAP_URL).data["features"] == []


def test_map_is_cached(api_client, django_assert_num_queries):
    LocationFactory()
    first = api_client.get(MAP_URL)
    with django_assert_num_queries(0):
        second = api_client.get(MAP_URL)
    assert second.data == first.data


def test_map_cache_invalidated_on_change(api_client, django_capture_on_commit_callbacks):
    api_client.get(MAP_URL)
    with django_capture_on_commit_callbacks(execute=True):
        LocationFactory()
    assert len(api_client.get(MAP_URL).data["features"]) == 1
