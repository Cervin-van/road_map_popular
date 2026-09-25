from decimal import Decimal

import pytest

from apps.locations import services
from apps.locations.models import Location
from tests.factories import CategoryFactory, LocationFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_location_sets_author():
    author = UserFactory()
    category = CategoryFactory()

    location = services.create_location(
        author=author,
        title="Park",
        description="Green",
        category=category,
        address="Main st. 1",
        latitude=Decimal("50.45"),
        longitude=Decimal("30.52"),
    )

    location.refresh_from_db()
    assert location.author == author
    assert location.category == category
    assert location.is_deleted is False


def test_update_location_changes_only_given_fields():
    location = LocationFactory(title="Old", address="Old address")
    old_updated_at = location.updated_at

    services.update_location(location, title="New")

    location.refresh_from_db()
    assert location.title == "New"
    assert location.address == "Old address"
    assert location.updated_at > old_updated_at


def test_update_location_without_fields_is_noop(django_assert_num_queries):
    location = LocationFactory()
    with django_assert_num_queries(0):
        services.update_location(location)


@pytest.mark.parametrize("field", ["author", "is_deleted"])
def test_update_location_rejects_protected_fields(field):
    location = LocationFactory()
    with pytest.raises(ValueError, match=field):
        services.update_location(location, **{field: None})


def test_soft_delete_location():
    location = LocationFactory()

    services.soft_delete_location(location)

    assert not Location.objects.filter(pk=location.pk).exists()
    assert Location.all_objects.get(pk=location.pk).is_deleted is True
