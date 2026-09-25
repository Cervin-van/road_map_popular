from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.http import QueryDict

from apps.locations import cache as list_cache
from apps.reviews import services as review_services
from tests.factories import LocationFactory, ReviewFactory


def qd(query: str) -> QueryDict:
    return QueryDict(query)


# --- cache module ---------------------------------------------------------


def test_key_ignores_parameter_order():
    assert list_cache.make_key("list", qd("a=1&b=2")) == list_cache.make_key("list", qd("b=2&a=1"))


def test_key_depends_on_values_kind_and_repeated_params():
    base = list_cache.make_key("list", qd("page=1"))
    assert base != list_cache.make_key("list", qd("page=2"))
    assert base != list_cache.make_key("map", qd("page=1"))
    assert list_cache.make_key("list", qd("a=1&a=2")) != list_cache.make_key("list", qd("a=1"))


def test_set_then_get():
    list_cache.set("list", qd("page=1"), {"count": 1})
    assert list_cache.get("list", qd("page=1")) == {"count": 1}
    assert list_cache.get("list", qd("page=2")) is None


def test_invalidate_makes_old_entries_unreachable():
    list_cache.set("list", qd(""), {"count": 1})
    list_cache.invalidate()
    assert list_cache.get("list", qd("")) is None


def test_invalidate_without_version_key():
    cache.delete(list_cache.VERSION_KEY)
    list_cache.invalidate()  # incr on a missing key raises ValueError internally
    assert cache.get(list_cache.VERSION_KEY) is not None


def test_version_does_not_restart_from_one_after_eviction():
    list_cache.set("list", qd(""), {"stale": True})
    cache.delete(list_cache.VERSION_KEY)  # simulate eviction of the version key only
    assert list_cache.get("list", qd("")) is None


def test_cache_outage_is_not_fatal():
    with patch.object(list_cache.cache, "get", side_effect=ConnectionError("down")):
        assert list_cache.get("list", qd("")) is None
    with patch.object(list_cache.cache, "set", side_effect=ConnectionError("down")):
        list_cache.set("list", qd(""), {"count": 1})  # no exception
    with patch.object(list_cache.cache, "incr", side_effect=ConnectionError("down")):
        list_cache.invalidate()  # no exception


# --- cached list endpoint -------------------------------------------------

LIST_URL = "/api/locations/"


@pytest.mark.django_db
def test_second_list_request_hits_cache(api_client, django_assert_num_queries):
    LocationFactory.create_batch(2)
    first = api_client.get(LIST_URL)

    with django_assert_num_queries(0):
        second = api_client.get(LIST_URL)

    assert second.status_code == 200
    assert second.data == first.data


@pytest.mark.django_db
def test_different_query_params_are_cached_separately(api_client):
    LocationFactory(title="Park")
    LocationFactory(title="Museum")
    api_client.get(LIST_URL)
    assert api_client.get(LIST_URL, {"search": "park"}).data["count"] == 1


@pytest.mark.django_db
def test_cached_list_is_shared_between_users(api_client, auth_client):
    LocationFactory()
    assert auth_client.get(LIST_URL).data == api_client.get(LIST_URL).data


@pytest.mark.django_db
def test_invalid_filters_are_not_cached(api_client):
    api_client.get(LIST_URL, {"min_rating": "abc"})
    assert list_cache.get("list", qd("min_rating=abc")) is None


@pytest.mark.django_db
def test_detail_is_not_cached(api_client):
    location = LocationFactory()
    api_client.get(f"{LIST_URL}{location.pk}/")
    assert api_client.get(f"{LIST_URL}{location.pk}/").data["title"] == location.title
    assert not list_cache.get("list", qd(""))


# --- invalidation ---------------------------------------------------------


def list_titles(client):
    return [item["title"] for item in client.get(LIST_URL).data["results"]]


@pytest.fixture
def committed(django_capture_on_commit_callbacks):
    """Run on_commit callbacks, as a real request's transaction commit would."""

    def run(action):
        with django_capture_on_commit_callbacks(execute=True):
            return action()

    return run


@pytest.mark.django_db
def test_location_create_update_and_soft_delete_invalidate(auth_client, user, committed):
    category_id = LocationFactory(author=user).category_id
    assert len(list_titles(auth_client)) == 1  # warm the cache

    payload = {
        "title": "New",
        "description": "d",
        "category": category_id,
        "address": "a",
        "latitude": "50.1",
        "longitude": "30.1",
    }
    new_id = committed(lambda: auth_client.post(LIST_URL, payload, format="json")).data["id"]
    assert "New" in list_titles(auth_client)

    committed(
        lambda: auth_client.patch(f"{LIST_URL}{new_id}/", {"title": "Renamed"}, format="json")
    )
    assert "Renamed" in list_titles(auth_client)

    committed(lambda: auth_client.delete(f"{LIST_URL}{new_id}/"))
    assert "Renamed" not in list_titles(auth_client)


@pytest.mark.django_db
def test_new_review_updates_cached_stats(api_client, auth_client, committed):
    location = LocationFactory()
    assert api_client.get(LIST_URL).data["results"][0]["reviews_count"] == 0

    committed(
        lambda: auth_client.post(
            f"/api/locations/{location.pk}/reviews/", {"rating": 5, "text": "x"}, format="json"
        )
    )

    item = api_client.get(LIST_URL).data["results"][0]
    assert (item["reviews_count"], item["avg_rating"]) == (1, 5.0)


@pytest.mark.django_db
def test_review_update_and_delete_invalidate(api_client, committed):
    review = ReviewFactory(rating=2)
    api_client.get(LIST_URL)

    committed(lambda: review_services.update_review(review, rating=4))
    assert api_client.get(LIST_URL).data["results"][0]["avg_rating"] == 4.0

    committed(review.delete)
    assert api_client.get(LIST_URL).data["results"][0]["reviews_count"] == 0


@pytest.mark.django_db
def test_category_rename_invalidates(api_client, committed):
    location = LocationFactory()
    api_client.get(LIST_URL)
    category = location.category
    category.name = "Renamed category"

    committed(category.save)

    assert api_client.get(LIST_URL).data["results"][0]["category"]["name"] == "Renamed category"


@pytest.mark.django_db
def test_invalidation_waits_for_commit(api_client, django_capture_on_commit_callbacks):
    api_client.get(LIST_URL)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        LocationFactory()
    assert api_client.get(LIST_URL).data["count"] == 0  # not committed yet: still cached
    assert callbacks


@pytest.mark.django_db
def test_views_and_votes_do_not_invalidate(
    api_client, auth_client, committed, django_assert_num_queries
):
    review = ReviewFactory()
    api_client.get(LIST_URL)

    committed(lambda: api_client.get(f"{LIST_URL}{review.location_id}/"))  # registers a view
    committed(
        lambda: auth_client.post(
            f"/api/reviews/{review.pk}/vote/", {"value": "like"}, format="json"
        )
    )

    with django_assert_num_queries(0):
        api_client.get(LIST_URL)
