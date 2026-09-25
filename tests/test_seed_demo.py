from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command

from apps.categories.models import Category
from apps.locations.management.commands.seed_demo import ADMIN_USERNAME, LOCATIONS
from apps.locations.models import Location, LocationView
from apps.locations.selectors import locations_with_stats
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


def test_seed_creates_demo_data():
    output = seed()

    assert get_user_model().objects.filter(username=ADMIN_USERNAME, is_superuser=True).exists()
    assert Category.objects.count() == 5
    assert Location.objects.count() == len(LOCATIONS)
    assert Review.objects.exists()
    assert "Created" in output
    assert mail.outbox == []  # seeding writes via the ORM: no review emails


def test_seed_backdates_views_across_the_window():
    seed()
    stats = locations_with_stats()
    total_recent = sum(location.views_7d for location in stats)
    assert 0 < total_recent < LocationView.objects.count()  # some views are older than 7 days


def test_seed_is_idempotent():
    seed()
    output = seed()
    assert "already present" in output
    assert Location.objects.count() == len(LOCATIONS)


def test_seed_reset_recreates_same_amount():
    seed()
    reviews = Review.objects.count()
    seed("--reset")
    assert Location.all_objects.count() == len(LOCATIONS)
    assert Review.objects.count() == reviews  # same --seed gives the same data
