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
