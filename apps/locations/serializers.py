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


class LocationListSerializer(serializers.ModelSerializer):
    # Nested data comes from select_related in selectors.alive_locations(): no N+1
    category = CategoryShortSerializer(read_only=True)
    author = AuthorShortSerializer(read_only=True)
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
            "created_at",
        ]

    def get_short_description(self, obj) -> str:
        return Truncator(obj.description).chars(SHORT_DESCRIPTION_LENGTH)


class LocationDetailSerializer(serializers.ModelSerializer):
    category = CategoryShortSerializer(read_only=True)
    author = AuthorShortSerializer(read_only=True)

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
