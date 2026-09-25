import pytest

from tests.factories import LocationFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/locations/"


def ids(response):
    return {item["id"] for item in response.data["results"]}


# --- search ---------------------------------------------------------------


def test_search_by_title_and_description(api_client):
    by_title = LocationFactory(title="Андріївський узвіз", description="Вулиця")
    by_description = LocationFactory(title="Музей", description="Поруч Андріївська церква")
    LocationFactory(title="Парк", description="Зелена зона")

    response = api_client.get(LIST_URL, {"search": "андріївськ"})

    assert ids(response) == {by_title.id, by_description.id}


def test_search_is_case_insensitive(api_client):
    location = LocationFactory(title="Golden Gate")
    assert ids(api_client.get(LIST_URL, {"search": "GOLDEN"})) == {location.id}


def test_search_with_several_terms_requires_all(api_client):
    both = LocationFactory(title="Old park", description="near the river")
    LocationFactory(title="Old museum", description="city centre")

    assert ids(api_client.get(LIST_URL, {"search": "old river"})) == {both.id}


def test_search_without_matches(api_client):
    LocationFactory(title="Park")
    assert api_client.get(LIST_URL, {"search": "nothing-like-this"}).data["count"] == 0


def test_search_skips_soft_deleted(api_client):
    LocationFactory(title="Hidden park").soft_delete()
    assert api_client.get(LIST_URL, {"search": "hidden"}).data["count"] == 0
