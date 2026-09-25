import pytest

from tests.factories import LocationFactory, LocationViewFactory, ReviewFactory

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


# --- ordering -------------------------------------------------------------


def ordered_ids(response):
    return [item["id"] for item in response.data["results"]]


@pytest.fixture
def rated():
    """Three locations: rated 5, rated 2 and without reviews (avg_rating = null)."""
    top = LocationFactory()
    ReviewFactory(location=top, rating=5)
    low = LocationFactory()
    ReviewFactory(location=low, rating=2)
    unrated = LocationFactory()
    return top, low, unrated


def test_default_ordering_newest_first(api_client):
    older, newer = LocationFactory(), LocationFactory()
    assert ordered_ids(api_client.get(LIST_URL)) == [newer.id, older.id]


def test_order_by_created_at_ascending(api_client):
    older, newer = LocationFactory(), LocationFactory()
    assert ordered_ids(api_client.get(LIST_URL, {"ordering": "created_at"})) == [older.id, newer.id]


@pytest.mark.parametrize(
    "ordering, expected", [("-avg_rating", ["top", "low"]), ("avg_rating", ["low", "top"])]
)
def test_order_by_avg_rating_keeps_unrated_last(api_client, rated, ordering, expected):
    top, low, unrated = rated
    by_name = {"top": top.id, "low": low.id}

    result = ordered_ids(api_client.get(LIST_URL, {"ordering": ordering}))

    assert result == [by_name[n] for n in expected] + [unrated.id]


def test_order_by_popularity(api_client):
    quiet = LocationFactory()
    viewed = LocationFactory()
    LocationViewFactory.create_batch(3, location=viewed)

    assert ordered_ids(api_client.get(LIST_URL, {"ordering": "-popularity"})) == [
        viewed.id,
        quiet.id,
    ]
    assert ordered_ids(api_client.get(LIST_URL, {"ordering": "popularity"})) == [
        quiet.id,
        viewed.id,
    ]


def test_equal_values_ordered_by_pk_for_stable_pages(api_client):
    first, second, third = LocationFactory.create_batch(3)  # equal popularity

    page1 = api_client.get(LIST_URL, {"ordering": "-popularity", "page_size": 2})
    page2 = api_client.get(LIST_URL, {"ordering": "-popularity", "page_size": 2, "page": 2})

    assert ordered_ids(page1) + ordered_ids(page2) == [third.id, second.id, first.id]


def test_unknown_ordering_field_falls_back_to_default(api_client):
    older, newer = LocationFactory(), LocationFactory()
    response = api_client.get(LIST_URL, {"ordering": "author__password"})
    assert ordered_ids(response) == [newer.id, older.id]
