import pytest
from django.db import IntegrityError

from tests.factories import LocationFactory, ReviewFactory, ReviewVoteFactory

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


# --- read API -------------------------------------------------------------


def location_reviews_url(location_id):
    return f"/api/locations/{location_id}/reviews/"


def review_url(review_id):
    return f"/api/reviews/{review_id}/"


def test_list_location_reviews_with_counters(api_client):
    review = ReviewFactory()
    ReviewVoteFactory.create_batch(2, review=review, value=1)
    ReviewVoteFactory(review=review, value=-1)
    ReviewFactory()  # another location: not listed

    response = api_client.get(location_reviews_url(review.location_id))

    assert response.status_code == 200
    assert response.data["count"] == 1
    item = response.data["results"][0]
    assert item["location"] == review.location_id
    assert item["author"] == {"id": review.author_id, "username": review.author.username}
    assert (item["likes_count"], item["dislikes_count"]) == (2, 1)
    assert item["my_vote"] is None


@pytest.mark.parametrize("value, label", [(1, "like"), (-1, "dislike")])
def test_my_vote_for_authenticated_user(auth_client, user, value, label):
    review = ReviewFactory()
    ReviewVoteFactory(review=review, user=user, value=value)
    ReviewVoteFactory(review=review, value=-value)  # someone else's vote is not "mine"

    response = auth_client.get(review_url(review.pk))

    assert response.status_code == 200
    assert response.data["my_vote"] == label


def test_my_vote_null_when_user_did_not_vote(auth_client):
    review = ReviewVoteFactory().review
    assert auth_client.get(review_url(review.pk)).data["my_vote"] is None


def test_order_by_likes(api_client):
    location = LocationFactory()
    popular = ReviewFactory(location=location)
    ReviewVoteFactory.create_batch(3, review=popular)
    quiet = ReviewFactory(location=location)

    response = api_client.get(location_reviews_url(location.pk), {"ordering": "-likes_count"})

    assert [r["id"] for r in response.data["results"]] == [popular.id, quiet.id]


def test_reviews_of_soft_deleted_location_are_hidden(api_client):
    review = ReviewFactory()
    review.location.soft_delete()

    assert api_client.get(location_reviews_url(review.location_id)).status_code == 404
    assert api_client.get(review_url(review.pk)).status_code == 404


def test_unknown_location_returns_404(api_client):
    assert api_client.get(location_reviews_url(999_999)).status_code == 404


def test_list_reviews_has_no_n_plus_one(auth_client, django_assert_num_queries):
    location = LocationFactory()
    for review in ReviewFactory.create_batch(5, location=location):
        ReviewVoteFactory(review=review)
    # session + user (auth) + location lookup + COUNT + one SELECT with annotations;
    # constant regardless of the number of reviews/votes
    with django_assert_num_queries(5):
        response = auth_client.get(location_reviews_url(location.pk))
    assert response.data["count"] == 5
