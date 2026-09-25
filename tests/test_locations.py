from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.locations.models import Location
from tests.factories import LocationFactory

pytestmark = pytest.mark.django_db


# --- model ----------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [("latitude", Decimal("90.000001")), ("longitude", Decimal("-180.000001"))],
)
def test_coordinates_out_of_range_rejected_by_db(field, value):
    with pytest.raises(IntegrityError, match=f"location_{field}_range"):
        LocationFactory(**{field: value})


def test_soft_delete_hides_location_from_default_manager():
    location = LocationFactory()

    location.soft_delete()

    assert not Location.objects.filter(pk=location.pk).exists()
    stored = Location.all_objects.get(pk=location.pk)
    assert stored.is_deleted is True
    assert stored.deleted_at is not None


@pytest.mark.parametrize("soft_deleted", [False, True])
def test_category_with_locations_is_protected(soft_deleted):
    location = LocationFactory()
    if soft_deleted:
        location.soft_delete()
    with pytest.raises(ProtectedError):
        location.category.delete()


def test_admin_lists_soft_deleted_locations(admin_client):
    alive = LocationFactory(title="Alive place")
    deleted = LocationFactory(title="Deleted place")
    deleted.soft_delete()

    response = admin_client.get("/admin/locations/location/")

    assert response.status_code == 200
    assert alive.title in response.content.decode()
    assert deleted.title in response.content.decode()


# --- read API -------------------------------------------------------------

LIST_URL = "/api/locations/"


def detail_url(pk):
    return f"{LIST_URL}{pk}/"


def test_anonymous_can_list_locations(api_client):
    location = LocationFactory(description="x" * 500)

    response = api_client.get(LIST_URL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["category"] == {"id": location.category_id, "name": location.category.name}
    assert item["author"] == {"id": location.author_id, "username": location.author.username}
    assert len(item["short_description"]) == 200
    assert "description" not in item


def test_list_newest_first(api_client):
    older = LocationFactory()
    newer = LocationFactory()
    ids = [item["id"] for item in api_client.get(LIST_URL).data["results"]]
    assert ids == [newer.id, older.id]


def test_list_has_no_n_plus_one(api_client, django_assert_num_queries):
    LocationFactory.create_batch(5)  # each with its own category and author
    with django_assert_num_queries(2):  # COUNT for pagination + one SELECT with JOINs
        response = api_client.get(LIST_URL)
    assert response.data["count"] == 5


def test_retrieve_location(api_client):
    location = LocationFactory()

    response = api_client.get(detail_url(location.pk))

    assert response.status_code == 200
    assert response.data["description"] == location.description
    assert response.data["latitude"] == "50.450100"
    assert "updated_at" in response.data


def test_soft_deleted_location_hidden_from_api(api_client):
    alive = LocationFactory()
    deleted = LocationFactory()
    deleted.soft_delete()

    ids = [item["id"] for item in api_client.get(LIST_URL).data["results"]]

    assert ids == [alive.id]
    assert api_client.get(detail_url(deleted.pk)).status_code == 404
