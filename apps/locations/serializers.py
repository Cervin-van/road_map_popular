from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.utils.text import Truncator
from rest_framework import serializers

from apps.categories.models import Category

from .models import Location

SHORT_DESCRIPTION_LENGTH = 200


class CategoryShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class AuthorShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username"]


class RoundedFloatField(serializers.FloatField):
    """Read-only float rounded for output; None (no reviews) stays null."""

    def __init__(self, digits: int = 2, **kwargs):
        self.digits = digits
        super().__init__(read_only=True, **kwargs)

    def to_representation(self, value):
        return round(float(value), self.digits)


class LocationBaseSerializer(serializers.ModelSerializer):
    # Nested objects come from select_related and stats from annotations in
    # selectors.locations_with_stats(): serializing makes no extra queries
    category = CategoryShortSerializer(read_only=True)
    author = AuthorShortSerializer(read_only=True)
    avg_rating = RoundedFloatField(allow_null=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = RoundedFloatField()


STATS_FIELDS = ["avg_rating", "reviews_count", "views_7d", "popularity"]


class LocationListSerializer(LocationBaseSerializer):
    short_description = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "title",
            "short_description",
            "category",
            "author",
            "address",
            "latitude",
            "longitude",
            *STATS_FIELDS,
            "created_at",
        ]

    def get_short_description(self, obj) -> str:
        return Truncator(obj.description).chars(SHORT_DESCRIPTION_LENGTH)


class LocationDetailSerializer(LocationBaseSerializer):
    class Meta:
        model = Location
        fields = [
            "id",
            "title",
            "description",
            "category",
            "author",
            "address",
            "latitude",
            "longitude",
            *STATS_FIELDS,
            "created_at",
            "updated_at",
        ]


class CoordinateField(serializers.DecimalField):
    """Decimal(9, 6) that rounds extra decimals instead of rejecting them.

    Map widgets send e.g. 50.450123456; DRF validates precision *before*
    quantizing even with `rounding` set, so round first, then validate.
    """

    def __init__(self, limit: int, **kwargs):
        super().__init__(
            max_digits=9,
            decimal_places=6,
            rounding=ROUND_HALF_UP,
            min_value=Decimal(-limit),
            max_value=Decimal(limit),
            **kwargs,
        )

    def validate_precision(self, value):
        try:
            value = self.quantize(value)
        except InvalidOperation:  # too many whole digits to fit the context precision
            self.fail("max_whole_digits", max_whole_digits=self.max_whole_digits)
        return super().validate_precision(value)


class LocationWriteSerializer(serializers.ModelSerializer):
    latitude = CoordinateField(limit=90)
    longitude = CoordinateField(limit=180)

    class Meta:
        model = Location
        fields = ["title", "description", "category", "address", "latitude", "longitude"]


MAP_LIMIT_DEFAULT, MAP_LIMIT_MAX = 100, 500


class MapQuerySerializer(serializers.Serializer):
    """Map-specific query params; filters/search/ordering are shared with the list."""

    bbox = serializers.CharField(
        required=False, help_text="min_lng,min_lat,max_lng,max_lat (WGS84 degrees)"
    )
    limit = serializers.IntegerField(
        required=False, default=MAP_LIMIT_DEFAULT, min_value=1, max_value=MAP_LIMIT_MAX
    )

    def validate_bbox(self, value):
        try:
            min_lng, min_lat, max_lng, max_lat = (Decimal(part) for part in value.split(","))
        except (ValueError, InvalidOperation) as exc:
            raise serializers.ValidationError(
                "Expected four numbers: min_lng,min_lat,max_lng,max_lat."
            ) from exc
        if not (-180 <= min_lng <= max_lng <= 180 and -90 <= min_lat <= max_lat <= 90):
            # A box crossing the antimeridian (min_lng > max_lng) is not supported
            raise serializers.ValidationError("Coordinates out of range or min > max.")
        return min_lng, min_lat, max_lng, max_lat


class LocationMapSerializer(serializers.BaseSerializer):
    """One GeoJSON Feature per location (RFC 7946: coordinates are [lng, lat])."""

    def to_representation(self, obj):
        return {
            "type": "Feature",
            "id": obj.id,
            "geometry": {
                "type": "Point",
                "coordinates": [float(obj.longitude), float(obj.latitude)],
            },
            "properties": {
                "id": obj.id,
                "title": obj.title,
                "category": obj.category.name,
                "avg_rating": None if obj.avg_rating is None else round(obj.avg_rating, 2),
                "popularity": round(obj.popularity, 2),
            },
        }


class ExportQuerySerializer(serializers.Serializer):
    # Not "format": DRF reserves ?format= for renderer selection
    export_format = serializers.ChoiceField(choices=["csv", "json"])
