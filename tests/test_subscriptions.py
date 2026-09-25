from unittest.mock import patch

import pytest
from django.db.models import QuerySet

from apps.common.exceptions import Conflict
from apps.notifications import services
from apps.notifications.models import LocationSubscription
from tests.factories import (
    LocationFactory,
    LocationSubscriptionFactory,
    ReviewFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --- services -------------------------------------------------------------


def test_subscribe_and_unsubscribe():
    user, location = UserFactory(), LocationFactory()

    services.subscribe(user=user, location=location)
    assert LocationSubscription.objects.filter(user=user, location=location).exists()

    assert services.unsubscribe(user=user, location=location) is True
    assert services.unsubscribe(user=user, location=location) is False


def test_duplicate_subscription_raises_conflict():
    subscription = LocationSubscriptionFactory()
    with pytest.raises(Conflict) as exc_info:
        services.subscribe(user=subscription.user, location=subscription.location)
    assert exc_info.value.detail.code == "already_subscribed"


def test_duplicate_subscription_race_raises_conflict():
    subscription = LocationSubscriptionFactory()
    with patch.object(QuerySet, "exists", return_value=False), pytest.raises(Conflict):
        services.subscribe(user=subscription.user, location=subscription.location)


def test_recipients_are_location_author_and_subscribers_without_review_author():
    location = LocationFactory()
    subscriber = LocationSubscriptionFactory(location=location).user
    reviewer = UserFactory()
    LocationSubscriptionFactory(location=location, user=reviewer)  # subscribed reviewer
    LocationSubscriptionFactory(location=location, user=location.author)  # author twice
    review = ReviewFactory(location=location, author=reviewer)

    recipients = services.recipients_for_review(review)

    assert sorted(u.pk for u in recipients) == sorted([location.author.pk, subscriber.pk])


def test_recipients_skip_users_without_email_or_inactive():
    location = LocationFactory(author=UserFactory(email=""))
    LocationSubscriptionFactory(location=location, user=UserFactory(is_active=False))
    active = LocationSubscriptionFactory(location=location).user

    recipients = services.recipients_for_review(ReviewFactory(location=location))

    assert recipients == [active]


def test_author_reviewing_own_location_gets_no_email():
    location = LocationFactory()
    review = ReviewFactory(location=location, author=location.author)
    assert services.recipients_for_review(review) == []
