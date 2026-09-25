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
