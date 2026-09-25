from django.db import IntegrityError, transaction

from apps.common.exceptions import Conflict

from .models import Review, ReviewVote

REVIEW_UNIQUE = "uniq_review_per_user_location"
VOTE_UNIQUE = "uniq_vote_per_user_review"
UPDATABLE_FIELDS = frozenset({"rating", "text"})


def _violates(exc: IntegrityError, constraint: str) -> bool:
    # psycopg exposes the violated constraint name; stabler than parsing the message
    diag = getattr(exc.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None) == constraint


def create_review(*, location, author, rating: int, text: str) -> Review:
    duplicate = Conflict("You have already reviewed this location.", code="review_already_exists")
    if Review.objects.filter(location=location, author=author).exists():
        raise duplicate
    try:
        # Savepoint: a failed INSERT must not break an enclosing transaction
        with transaction.atomic():
            return Review.objects.create(location=location, author=author, rating=rating, text=text)
    except IntegrityError as exc:
        if _violates(exc, REVIEW_UNIQUE):  # lost a race with a concurrent request
            raise duplicate from exc
        raise


def update_review(review: Review, **fields) -> Review:
    forbidden = fields.keys() - UPDATABLE_FIELDS
    if forbidden:
        raise ValueError(f"Fields cannot be updated: {', '.join(sorted(forbidden))}")
    if not fields:
        return review

    for name, value in fields.items():
        setattr(review, name, value)
    review.save(update_fields=[*fields, "updated_at"])
    return review


def delete_review(review: Review) -> None:
    review.delete()


def vote_review(*, review: Review, user, value: int) -> ReviewVote:
    duplicate = Conflict("You have already voted for this review.", code="already_voted")
    if ReviewVote.objects.filter(review=review, user=user).exists():
        raise duplicate
    try:
        with transaction.atomic():
            return ReviewVote.objects.create(review=review, user=user, value=value)
    except IntegrityError as exc:
        if _violates(exc, VOTE_UNIQUE):
            raise duplicate from exc
        raise


def remove_vote(*, review: Review, user) -> bool:
    deleted, _ = ReviewVote.objects.filter(review=review, user=user).delete()
    return deleted > 0
