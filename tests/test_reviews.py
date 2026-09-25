import pytest
from django.db import IntegrityError

from tests.factories import ReviewFactory, ReviewVoteFactory

pytestmark = pytest.mark.django_db


# --- models ---------------------------------------------------------------


def test_one_review_per_user_per_location_in_db():
    review = ReviewFactory()
    with pytest.raises(IntegrityError, match="uniq_review_per_user_location"):
        ReviewFactory(location=review.location, author=review.author)


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_range_enforced_by_db(rating):
    with pytest.raises(IntegrityError, match="review_rating_range"):
        ReviewFactory(rating=rating)


def test_one_vote_per_user_per_review_in_db():
    vote = ReviewVoteFactory()
    with pytest.raises(IntegrityError, match="uniq_vote_per_user_review"):
        ReviewVoteFactory(review=vote.review, user=vote.user, value=-1)


def test_vote_value_enforced_by_db():
    with pytest.raises(IntegrityError, match="review_vote_value_valid"):
        ReviewVoteFactory(value=0)


def test_same_user_can_review_different_locations():
    review = ReviewFactory()
    ReviewFactory(author=review.author)  # another location: allowed
