from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from freezegun import freeze_time
from rest_framework.test import APIRequestFactory

from apps.locations import services
from apps.locations.models import Location, LocationView
from tests.factories import LocationFactory, LocationViewFactory, UserFactory

pytestmark = pytest.mark.django_db


# --- model ----------------------------------------------------------------


def test_anonymous_viewer_key_fits():
    view = LocationViewFactory(viewer_key="anon:" + "f" * 64)
    view.refresh_from_db()
    assert len(view.viewer_key) == 69


def test_views_survive_user_deletion():
    user = UserFactory()
    view = LocationViewFactory(user=user, viewer_key=f"user:{user.pk}")

    user.delete()

    view.refresh_from_db()
    assert view.user is None


def test_views_removed_with_location_hard_delete():
    view = LocationViewFactory()
    Location.all_objects.filter(pk=view.location_id).delete()
    assert not LocationView.objects.exists()


# --- register_view service ------------------------------------------------

rf = APIRequestFactory()


def make_request(user=None, ip="10.0.0.1", ua="pytest"):
    request = rf.get("/", REMOTE_ADDR=ip, HTTP_USER_AGENT=ua)
    request.user = user or AnonymousUser()
    return request


def test_first_view_is_counted_with_user():
    location, user = LocationFactory(), UserFactory()

    assert services.register_view(location, make_request(user)) is True

    view = LocationView.objects.get()
    assert (view.location, view.user, view.viewer_key) == (location, user, f"user:{user.pk}")


def test_repeat_view_within_hour_not_counted():
    location, user = LocationFactory(), UserFactory()
    services.register_view(location, make_request(user))
    assert services.register_view(location, make_request(user)) is False
    assert LocationView.objects.count() == 1


def test_view_counted_again_after_an_hour():
    location = LocationFactory()
    with freeze_time("2026-01-01 10:00") as frozen:
        services.register_view(location, make_request())
        frozen.tick(timedelta(minutes=59))
        assert services.register_view(location, make_request()) is False
        frozen.tick(timedelta(minutes=2))
        assert services.register_view(location, make_request()) is True
    assert LocationView.objects.count() == 2


def test_different_viewers_counted_separately():
    location = LocationFactory()
    services.register_view(location, make_request(ip="1.1.1.1"))
    services.register_view(location, make_request(ip="2.2.2.2"))
    services.register_view(location, make_request(ip="1.1.1.1", ua="other browser"))
    services.register_view(location, make_request(UserFactory()))
    assert LocationView.objects.count() == 4
    assert LocationView.objects.filter(user__isnull=True).count() == 3


def test_same_viewer_different_locations_counted():
    user = UserFactory()
    services.register_view(LocationFactory(), make_request(user))
    services.register_view(LocationFactory(), make_request(user))
    assert LocationView.objects.count() == 2


def test_cache_failure_does_not_count_or_raise(caplog):
    location = LocationFactory()
    with patch.object(services.cache, "add", side_effect=ConnectionError("redis down")):
        assert services.register_view(location, make_request()) is False
    assert not LocationView.objects.exists()
    assert "view not counted" in caplog.text
