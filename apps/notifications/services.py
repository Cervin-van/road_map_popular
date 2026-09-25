from django.db import IntegrityError, transaction

from apps.common.db import violates_constraint
from apps.common.exceptions import Conflict

from .models import LocationSubscription

SUBSCRIPTION_UNIQUE = "uniq_subscription_per_user_location"


def subscribe(*, user, location) -> LocationSubscription:
    duplicate = Conflict("You are already subscribed to this location.", code="already_subscribed")
    if LocationSubscription.objects.filter(user=user, location=location).exists():
        raise duplicate
    try:
        with transaction.atomic():
            return LocationSubscription.objects.create(user=user, location=location)
    except IntegrityError as exc:
        if violates_constraint(exc, SUBSCRIPTION_UNIQUE):
            raise duplicate from exc
        raise


def unsubscribe(*, user, location) -> bool:
    deleted, _ = LocationSubscription.objects.filter(user=user, location=location).delete()
    return deleted > 0


def recipients_for_review(review) -> list:
    """Location author + subscribers, without the review author, each user once.

    Only active users with an email address.
    """
    location = review.location
    candidates = [location.author] + [
        subscription.user
        for subscription in LocationSubscription.objects.filter(location=location).select_related(
            "user"
        )
    ]
    recipients, seen = [], {review.author_id}
    for user in candidates:
        if user.pk in seen or not user.is_active or not user.email:
            continue
        seen.add(user.pk)
        recipients.append(user)
    return recipients
