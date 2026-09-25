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


# --- API ------------------------------------------------------------------


def subscribe_url(location):
    return f"/api/locations/{location.pk}/subscribe/"


def test_subscribe_and_list(auth_client, user):
    location = LocationFactory()

    response = auth_client.post(subscribe_url(location))

    assert response.status_code == 201
    assert response.data["location"] == {"id": location.id, "title": location.title}
    listed = auth_client.get("/api/subscriptions/").data["results"]
    assert [s["location"]["id"] for s in listed] == [location.id]


def test_subscribe_twice_returns_409(auth_client, user):
    location = LocationSubscriptionFactory(user=user).location
    response = auth_client.post(subscribe_url(location))
    assert response.status_code == 409
    assert response.data["code"] == "already_subscribed"


def test_unsubscribe(auth_client, user):
    location = LocationSubscriptionFactory(user=user).location
    assert auth_client.delete(subscribe_url(location)).status_code == 204
    assert auth_client.delete(subscribe_url(location)).status_code == 404


def test_anonymous_cannot_subscribe_or_list(api_client):
    assert api_client.post(subscribe_url(LocationFactory())).status_code == 403
    assert api_client.get("/api/subscriptions/").status_code == 403


def test_subscribe_to_soft_deleted_location_returns_404(auth_client):
    location = LocationFactory()
    location.soft_delete()
    assert auth_client.post(subscribe_url(location)).status_code == 404


def test_my_subscriptions_only_mine_and_alive(auth_client, user):
    mine = LocationSubscriptionFactory(user=user)
    LocationSubscriptionFactory(user=user).location.soft_delete()
    LocationSubscriptionFactory()  # someone else's

    listed = auth_client.get("/api/subscriptions/").data["results"]

    assert [s["id"] for s in listed] == [mine.id]
