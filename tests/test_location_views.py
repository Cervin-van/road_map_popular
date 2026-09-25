import pytest

from apps.locations.models import Location, LocationView
from tests.factories import LocationViewFactory, UserFactory

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
