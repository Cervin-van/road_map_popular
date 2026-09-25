from django_filters import rest_framework as filters

from apps.categories.models import Category
from apps.reviews.models import RATING_MAX, RATING_MIN

from .models import Location


class LocationFilter(filters.FilterSet):
    category = filters.ModelChoiceFilter(queryset=Category.objects.all())
    category_slug = filters.CharFilter(field_name="category__slug")
    author = filters.NumberFilter(field_name="author_id")
    # avg_rating is an annotation from selectors.locations_with_stats(), so it is
    # filterable here. Locations without reviews have NULL and never match.
    min_rating = filters.NumberFilter(
        field_name="avg_rating", lookup_expr="gte", min_value=RATING_MIN, max_value=RATING_MAX
    )
    max_rating = filters.NumberFilter(
        field_name="avg_rating", lookup_expr="lte", min_value=RATING_MIN, max_value=RATING_MAX
    )

    class Meta:
        model = Location
        fields = []  # all filters are declared explicitly above
