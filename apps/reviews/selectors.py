from django.db.models import Count, OuterRef, Q, QuerySet, SmallIntegerField, Subquery, Value

from .models import Review, ReviewVote

LIKE, DISLIKE = ReviewVote.Value.LIKE, ReviewVote.Value.DISLIKE


def reviews_with_votes(user=None) -> QuerySet[Review]:
    """Reviews of alive locations with like/dislike counters and the viewer's vote.

    Both counters aggregate over the same `votes` JOIN, so there is no
    cartesian product. Review lists are not cached, so a per-user
    `my_vote` annotation is fine here.
    """
    # Review.location uses the plain base manager: soft-deleted locations must be excluded here
    qs = (
        Review.objects.filter(location__is_deleted=False)
        .select_related("author")
        .annotate(
            likes_count=Count("votes", filter=Q(votes__value=LIKE)),
            dislikes_count=Count("votes", filter=Q(votes__value=DISLIKE)),
        )
    )
    if user is not None and user.is_authenticated:
        my_vote = ReviewVote.objects.filter(review=OuterRef("pk"), user=user).values("value")[:1]
        return qs.annotate(my_vote=Subquery(my_vote, output_field=SmallIntegerField()))
    return qs.annotate(my_vote=Value(None, output_field=SmallIntegerField()))
