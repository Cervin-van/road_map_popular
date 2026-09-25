from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import (
    Avg,
    Count,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.functions import Cast, Coalesce, Ln
from django.utils import timezone

from apps.reviews.models import Review

from .models import Location, LocationView


def locations_with_stats(qs: QuerySet[Location] | None = None) -> QuerySet[Location]:
    """Alive locations annotated with rating and popularity (ARCHITECTURE.md §4).

    Nothing here is stored in the DB. Each aggregate is a correlated Subquery:
    JOINing reviews and views together would multiply rows (reviews × views)
    and corrupt both COUNTs.
    """
    qs = Location.objects.all() if qs is None else qs

    m = float(settings.POPULARITY_PRIOR_MEAN)
    c = float(settings.POPULARITY_PRIOR_WEIGHT)
    if c <= 0:  # locations without reviews would divide by zero
        raise ImproperlyConfigured("POPULARITY_PRIOR_WEIGHT must be > 0")
    w_rating = float(settings.POPULARITY_WEIGHT_RATING)
    w_reviews = float(settings.POPULARITY_WEIGHT_REVIEWS)
    w_views = float(settings.POPULARITY_WEIGHT_VIEWS)
    since = timezone.now() - timedelta(days=settings.POPULARITY_VIEWS_WINDOW_DAYS)

    # order_by() drops Review.Meta.ordering so it cannot leak into GROUP BY
    reviews = Review.objects.filter(location=OuterRef("pk")).order_by().values("location")
    avg_sq = reviews.annotate(v=Avg("rating")).values("v")
    count_sq = reviews.annotate(v=Count("id")).values("v")
    views = LocationView.objects.filter(location=OuterRef("pk")).order_by().values("location")
    views_total_sq = views.annotate(v=Count("id")).values("v")
    views_recent_sq = views.filter(created_at__gte=since).annotate(v=Count("id")).values("v")

    reviews_count = Cast("reviews_count", FloatField())
    return (
        qs.select_related("category", "author")
        .annotate(
            avg_rating=Cast(Subquery(avg_sq), FloatField()),  # NULL when there are no reviews
            reviews_count=Coalesce(Subquery(count_sq, output_field=IntegerField()), 0),
            views_count=Coalesce(Subquery(views_total_sq, output_field=IntegerField()), 0),
            views_7d=Coalesce(Subquery(views_recent_sq, output_field=IntegerField()), 0),
        )
        .annotate(
            bayes_rating=(Value(c * m) + Coalesce(F("avg_rating"), Value(0.0)) * reviews_count)
            / (Value(c) + reviews_count),
        )
        .annotate(
            popularity=Value(w_rating) * F("bayes_rating") / Value(5.0)
            + Value(w_reviews) * Ln(reviews_count + Value(1.0))
            + Value(w_views) * Ln(Cast("views_7d", FloatField()) + Value(1.0)),
        )
    )
