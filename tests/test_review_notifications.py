import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.notifications.tasks import send_new_review_emails
from tests.factories import (
    LocationFactory,
    LocationSubscriptionFactory,
    ReviewFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def post_review(client, location):
    return client.post(
        f"/api/locations/{location.pk}/reviews/", {"rating": 4, "text": "Nice"}, format="json"
    )


def test_new_review_emails_location_author_and_subscribers(
    auth_client, user, django_capture_on_commit_callbacks
):
    location = LocationFactory()
    subscriber = LocationSubscriptionFactory(location=location).user
    LocationSubscriptionFactory(location=location, user=user)  # the reviewer is subscribed too

    with django_capture_on_commit_callbacks(execute=True):
        assert post_review(auth_client, location).status_code == 201

    recipients = sorted(address for message in mail.outbox for address in message.to)
    assert recipients == sorted([location.author.email, subscriber.email])
    assert all(len(message.to) == 1 for message in mail.outbox)  # no shared To: header
    message = mail.outbox[0]
    assert location.title in message.subject
    assert "Rating: 4/5" in message.body
    assert f"/locations/{location.pk}" in message.body


def test_no_email_when_author_reviews_own_location(django_capture_on_commit_callbacks):
    location = LocationFactory()
    client = APIClient()
    client.force_login(location.author)
    with django_capture_on_commit_callbacks(execute=True):
        post_review(client, location)
    assert mail.outbox == []


def test_email_is_sent_only_after_commit(auth_client, django_capture_on_commit_callbacks):
    location = LocationFactory()
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        post_review(auth_client, location)
    assert mail.outbox == []  # transaction not committed yet
    assert len(callbacks) >= 1


def test_duplicate_review_sends_nothing(auth_client, user, django_capture_on_commit_callbacks):
    review = ReviewFactory(author=user)
    with django_capture_on_commit_callbacks(execute=True):
        assert post_review(auth_client, review.location).status_code == 409
    assert mail.outbox == []


def test_task_skips_deleted_review_or_location():
    review = ReviewFactory()
    review.location.soft_delete()
    assert send_new_review_emails(review.pk) == 0
    assert send_new_review_emails(999_999) == 0
    assert mail.outbox == []


def test_task_returns_number_of_sent_emails():
    location = LocationFactory()
    LocationSubscriptionFactory.create_batch(2, location=location)
    review = ReviewFactory(location=location, author=UserFactory())
    assert send_new_review_emails(review.pk) == 3
