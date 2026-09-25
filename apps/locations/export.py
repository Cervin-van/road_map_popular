"""Export of (filtered) locations to CSV / JSON with pandas."""

import pandas as pd
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone

COLUMNS = {
    # queryset field -> output column
    "id": "id",
    "title": "title",
    "description": "description",
    "category__name": "category",
    "author__username": "author",
    "address": "address",
    "latitude": "latitude",
    "longitude": "longitude",
    "avg_rating": "avg_rating",
    "reviews_count": "reviews_count",
    "views_count": "views_count",
    "views_7d": "views_7d",
    "popularity": "popularity",
    "created_at": "created_at",
}

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
}


def locations_dataframe(queryset: QuerySet) -> pd.DataFrame:
    # values() keeps the annotations and ordering and avoids model instances
    rows = list(queryset.values(*COLUMNS))
    frame = pd.DataFrame.from_records(rows, columns=list(COLUMNS)).rename(columns=COLUMNS)
    frame["latitude"] = frame["latitude"].astype(float)
    frame["longitude"] = frame["longitude"].astype(float)
    frame["avg_rating"] = frame["avg_rating"].astype(float).round(2)  # NULL -> NaN -> empty/null
    frame["popularity"] = frame["popularity"].astype(float).round(2)
    # values() yields UTC; match the API, which renders in TIME_ZONE
    frame["created_at"] = [timezone.localtime(value).isoformat() for value in frame["created_at"]]
    return frame


def render(frame: pd.DataFrame, export_format: str) -> bytes:
    if export_format == "csv":
        # BOM so Excel detects UTF-8 and shows Cyrillic correctly
        return frame.to_csv(index=False).encode("utf-8-sig")
    return frame.to_json(orient="records", force_ascii=False).encode("utf-8")


def export_response(queryset: QuerySet, export_format: str) -> HttpResponse:
    content = render(locations_dataframe(queryset), export_format)
    filename = f"locations_{timezone.localdate():%Y-%m-%d}.{export_format}"
    response = HttpResponse(content, content_type=CONTENT_TYPES[export_format])
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
