from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.db.models import QuerySet

from apps.common.exceptions import Conflict
from apps.reviews import services
from apps.reviews.models import Review, ReviewVote
from tests.factories import LocationFactory, ReviewFactory, ReviewVoteFactory, UserFactory

pytestmark = pytest.mark.django_db

LIKE, DISLIKE = ReviewVote.Value.LIKE, ReviewVote.Value.DISLIKE


# --- reviews --------------------------------------------------------------


def test_create_review():
    location, author = LocationFactory(), UserFactory()

    review = services.create_review(location=location, author=author, rating=5, text="Great")

    assert Review.objects.get(pk=review.pk).author == author


def test_create_duplicate_review_raises_conflict():
    review = ReviewFactory()
    with pytest.raises(Conflict) as exc_info:
        services.create_review(location=review.location, author=review.author, rating=3, text="x")
    assert exc_info.value.detail.code == "review_already_exists"


def test_create_duplicate_review_race_raises_conflict():
    review = ReviewFactory()
    # Simulate a concurrent request passing the exists() check first
    with (
        patch.object(QuerySet, "exists", return_value=False),
        pytest.raises(Conflict) as exc_info,
    ):
        services.create_review(location=review.location, author=review.author, rating=3, text="x")
    assert exc_info.value.detail.code == "review_already_exists"
    assert Review.objects.count() == 1  # the outer transaction is still usable


def test_create_review_does_not_hide_other_integrity_errors():
    with pytest.raises(IntegrityError):
        services.create_review(location=LocationFactory(), author=UserFactory(), rating=6, text="x")


def test_update_review_changes_given_fields():
    review = ReviewFactory(rating=2, text="Meh")
    old_updated_at = review.updated_at

    services.update_review(review, rating=5)

    review.refresh_from_db()
    assert (review.rating, review.text) == (5, "Meh")
    assert review.updated_at > old_updated_at


@pytest.mark.parametrize("field", ["location", "author"])
def test_update_review_rejects_protected_fields(field):
    with pytest.raises(ValueError, match=field):
        services.update_review(ReviewFactory(), **{field: None})


def test_delete_review_removes_votes():
    vote = ReviewVoteFactory()
    services.delete_review(vote.review)
    assert not ReviewVote.objects.exists()


# --- votes ----------------------------------------------------------------


def test_vote_review():
    review, user = ReviewFactory(), UserFactory()
    vote = services.vote_review(review=review, user=user, value=DISLIKE)
    assert vote.value == DISLIKE


def test_second_vote_raises_conflict_even_with_other_value():
    vote = ReviewVoteFactory(value=LIKE)
    with pytest.raises(Conflict) as exc_info:
        services.vote_review(review=vote.review, user=vote.user, value=DISLIKE)
    assert exc_info.value.detail.code == "already_voted"


def test_vote_race_raises_conflict():
    vote = ReviewVoteFactory()
    with (
        patch.object(QuerySet, "exists", return_value=False),
        pytest.raises(Conflict),
    ):
        services.vote_review(review=vote.review, user=vote.user, value=LIKE)


def test_remove_vote_then_vote_again():
    vote = ReviewVoteFactory(value=LIKE)

    assert services.remove_vote(review=vote.review, user=vote.user) is True
    assert services.remove_vote(review=vote.review, user=vote.user) is False

    services.vote_review(review=vote.review, user=vote.user, value=DISLIKE)
    assert ReviewVote.objects.get().value == DISLIKE
