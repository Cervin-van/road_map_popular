import math
from datetime import timedelta

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from freezegun import freeze_time

from apps.locations.selectors import locations_with_stats
from tests.factories import LocationFactory, LocationViewFactory, ReviewFactory

pytestmark = pytest.mark.django_db


def stats(location):
    return locations_with_stats().get(pk=location.pk)


def expected_popularity(avg, count, views, m=3.0, c=5.0, w_r=50.0, w_c=20.0, w_v=10.0):
    bayes = (c * m + (avg or 0) * count) / (c + count)
    return w_r * bayes / 5 + w_c * math.log(1 + count) + w_v * math.log(1 + views)


# --- selector -------------------------------------------------------------


def test_location_without_reviews_or_views():
    location = stats(LocationFactory())

    assert location.avg_rating is None  # "no ratings", not a zero rating
    assert (location.reviews_count, location.views_count, location.views_7d) == (0, 0, 0)
    assert location.bayes_rating == pytest.approx(3.0)  # the prior mean
    assert location.popularity == pytest.approx(expected_popularity(None, 0, 0))


def test_avg_rating_and_reviews_count():
    location = LocationFactory()
    for rating in (5, 4, 3):
        ReviewFactory(location=location, rating=rating)
    ReviewFactory(rating=1)  # another location

    location = stats(location)

    assert location.avg_rating == pytest.approx(4.0)
    assert location.reviews_count == 3


def test_reviews_and_views_do_not_multiply():
    # A JOIN of reviews × views would report 12 reviews and 12 views here
    location = LocationFactory()
    ReviewFactory.create_batch(3, location=location, rating=5)
    LocationViewFactory.create_batch(4, location=location)

    location = stats(location)

    assert (location.reviews_count, location.views_7d) == (3, 4)
    assert location.avg_rating == pytest.approx(5.0)


def test_views_outside_window_are_ignored():
    location = LocationFactory()
    now = timezone.now()
    for days_ago in (8, 7.5, 6, 0):
        with freeze_time(now - timedelta(days=days_ago)):
            LocationViewFactory(location=location)

    with freeze_time(now):
        location = stats(location)
        assert location.views_7d == 2
        assert location.views_count == 4  # the total keeps older views


def test_popularity_matches_formula():
    location = LocationFactory()
    ReviewFactory(location=location, rating=5)
    ReviewFactory(location=location, rating=2)
    LocationViewFactory.create_batch(9, location=location)

    assert stats(location).popularity == pytest.approx(expected_popularity(3.5, 2, 9))


def test_bayesian_rating_prefers_many_good_reviews_over_one_perfect():
    one_perfect = LocationFactory()
    ReviewFactory(location=one_perfect, rating=5)
    many_good = LocationFactory()
    for _ in range(10):
        ReviewFactory(location=many_good, rating=4)

    ranked = list(locations_with_stats().order_by("-bayes_rating"))

    assert ranked == [many_good, one_perfect]


def test_order_by_popularity():
    quiet = LocationFactory()
    viewed = LocationFactory()
    LocationViewFactory.create_batch(5, location=viewed)
    reviewed = LocationFactory()
    ReviewFactory.create_batch(3, location=reviewed, rating=5)

    ranked = list(locations_with_stats().order_by("-popularity"))

    assert ranked == [reviewed, viewed, quiet]


def test_coefficients_come_from_settings(settings):
    location = LocationFactory()
    LocationViewFactory(location=location)
    settings.POPULARITY_WEIGHT_VIEWS = 100.0

    expected = expected_popularity(None, 0, 1, w_v=100.0)
    assert stats(location).popularity == pytest.approx(expected)


def test_zero_prior_weight_is_rejected(settings):
    settings.POPULARITY_PRIOR_WEIGHT = 0
    with pytest.raises(ImproperlyConfigured):
        locations_with_stats()


def test_soft_deleted_locations_excluded():
    location = LocationFactory()
    location.soft_delete()
    assert not locations_with_stats().exists()


# --- API ------------------------------------------------------------------


def test_list_and_detail_expose_rounded_stats(api_client):
    location = LocationFactory()
    for rating in (5, 4, 4):
        ReviewFactory(location=location, rating=rating)

    item = api_client.get("/api/locations/").data["results"][0]
    detail = api_client.get(f"/api/locations/{location.pk}/").data

    for data in (item, detail):
        assert data["avg_rating"] == 4.33
        assert data["reviews_count"] == 3
    # Checked on the list only: the detail request registers a view of its own
    assert item["popularity"] == round(expected_popularity(13 / 3, 3, 0), 2)


def test_avg_rating_null_in_api_without_reviews(api_client):
    LocationFactory()
    assert api_client.get("/api/locations/").data["results"][0]["avg_rating"] is None


def test_list_with_stats_has_no_n_plus_one(api_client, django_assert_num_queries):
    for location in LocationFactory.create_batch(4):
        ReviewFactory(location=location)
        LocationViewFactory(location=location)
    with django_assert_num_queries(2):  # COUNT + one SELECT with correlated subqueries
        api_client.get("/api/locations/")
