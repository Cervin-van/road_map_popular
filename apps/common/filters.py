from django.db.models import F
from rest_framework.filters import OrderingFilter


class StableOrderingFilter(OrderingFilter):
    """OrderingFilter with NULLS LAST and a pk tie-break.

    - Postgres puts NULLs first on DESC, so `-avg_rating` would list locations
      without reviews on top; NULLS LAST in both directions keeps them at the end.
    - Many rows share a value (e.g. popularity of new locations). Without a
      unique tie-break the order of equal rows is undefined and pages may
      overlap or skip rows.
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset

        expressions = [
            F(field[1:]).desc(nulls_last=True)
            if field.startswith("-")
            else F(field).asc(nulls_last=True)
            for field in ordering
        ]
        if not {field.lstrip("-") for field in ordering} & {"pk", "id"}:
            expressions.append(F("pk").desc())
        return queryset.order_by(*expressions)
