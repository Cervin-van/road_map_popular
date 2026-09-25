from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models import ProtectedError

from apps.locations.models import Location
from tests.factories import CategoryFactory, LocationFactory, UserFactory

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


# --- write API ------------------------------------------------------------


@pytest.fixture
def payload():
    category = CategoryFactory()
    return {
        "title": "Mariinsky Park",
        "description": "Old park near the parliament",
        "category": category.id,
        "address": "Hrushevskoho st.",
        "latitude": "50.446900",
        "longitude": "30.537600",
    }


def test_anonymous_cannot_create(api_client, payload):
    assert api_client.post(LIST_URL, payload, format="json").status_code == 403


def test_user_creates_location_as_author(auth_client, user, payload):
    other = UserFactory()
    response = auth_client.post(LIST_URL, {**payload, "author": other.id}, format="json")

    assert response.status_code == 201
    assert response.data["author"]["id"] == user.id  # payload author is ignored
    assert response.data["category"]["id"] == payload["category"]
    assert Location.objects.get(pk=response.data["id"]).author == user


def test_create_rounds_extra_coordinate_decimals(auth_client, payload):
    response = auth_client.post(
        LIST_URL, {**payload, "latitude": "50.4469005", "longitude": 30.53760049}, format="json"
    )
    assert response.status_code == 201
    assert response.data["latitude"] == "50.446901"
    assert response.data["longitude"] == "30.537600"


@pytest.mark.parametrize(
    "field, value",
    [("latitude", "90.5"), ("longitude", "-181"), ("latitude", "1e10"), ("longitude", "abc")],
)
def test_create_rejects_out_of_range_coordinates(auth_client, payload, field, value):
    response = auth_client.post(LIST_URL, {**payload, field: value}, format="json")
    assert response.status_code == 400
    assert field in response.data


def test_create_rejects_unknown_category(auth_client, payload):
    response = auth_client.post(LIST_URL, {**payload, "category": 999_999}, format="json")
    assert response.status_code == 400
    assert "category" in response.data


def test_create_requires_fields(auth_client):
    response = auth_client.post(LIST_URL, {}, format="json")
    assert response.status_code == 400
    assert {"title", "description", "category", "address", "latitude", "longitude"} <= set(
        response.data
    )


def test_owner_can_patch(auth_client, user):
    location = LocationFactory(author=user)
    response = auth_client.patch(detail_url(location.pk), {"title": "Renamed"}, format="json")
    assert response.status_code == 200
    assert response.data["title"] == "Renamed"
    assert response.data["author"]["id"] == user.id


def test_owner_can_put(auth_client, user, payload):
    location = LocationFactory(author=user)
    response = auth_client.put(detail_url(location.pk), payload, format="json")
    assert response.status_code == 200
    assert response.data["title"] == payload["title"]


def test_non_owner_cannot_patch_or_delete(auth_client):
    location = LocationFactory()
    assert (
        auth_client.patch(detail_url(location.pk), {"title": "X"}, format="json").status_code == 403
    )
    assert auth_client.delete(detail_url(location.pk)).status_code == 403
    location.refresh_from_db()
    assert location.is_deleted is False


def test_admin_can_patch_foreign_location(admin_client):
    location = LocationFactory()
    response = admin_client.patch(detail_url(location.pk), {"title": "By admin"}, format="json")
    assert response.status_code == 200


def test_owner_delete_is_soft(auth_client, user):
    location = LocationFactory(author=user)

    assert auth_client.delete(detail_url(location.pk)).status_code == 204

    assert Location.all_objects.get(pk=location.pk).is_deleted is True
    assert auth_client.get(detail_url(location.pk)).status_code == 404
    assert auth_client.get(LIST_URL).data["count"] == 0
    assert auth_client.delete(detail_url(location.pk)).status_code == 404


def test_patch_soft_deleted_location_returns_404(auth_client, user):
    location = LocationFactory(author=user)
    location.soft_delete()
    response = auth_client.patch(detail_url(location.pk), {"title": "X"}, format="json")
    assert response.status_code == 404


def test_delete_category_in_use_returns_409(admin_client):
    location = LocationFactory()
    response = admin_client.delete(f"/api/categories/{location.category_id}/")
    assert response.status_code == 409
    assert response.data["code"] == "protected"
