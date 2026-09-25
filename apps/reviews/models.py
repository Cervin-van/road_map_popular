from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel
from apps.locations.models import Location

RATING_MIN, RATING_MAX = 1, 5


class Review(TimeStampedModel):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(RATING_MIN), MaxValueValidator(RATING_MAX)]
    )
    text = models.TextField()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "author"], name="uniq_review_per_user_location"
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=RATING_MIN, rating__lte=RATING_MAX),
                name="review_rating_range",
            ),
        ]

    def __str__(self):
        return f"{self.author} → {self.location}: {self.rating}"


class ReviewVote(models.Model):
    class Value(models.IntegerChoices):
        LIKE = 1, "like"
        DISLIKE = -1, "dislike"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    value = models.SmallIntegerField(choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="uniq_vote_per_user_review"),
            models.CheckConstraint(condition=Q(value__in=[1, -1]), name="review_vote_value_valid"),
        ]

    def __str__(self):
        return f"{self.user} {self.get_value_display()} review #{self.review_id}"
