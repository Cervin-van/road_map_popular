from django.db.models import QuerySet

from .models import Location


def alive_locations() -> QuerySet[Location]:
    # Stage 5 extends this into locations_with_stats() with rating/popularity annotations
    return Location.objects.select_related("category", "author")
