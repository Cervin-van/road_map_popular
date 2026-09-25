from rest_framework import serializers

from apps.locations.models import Location

from .models import LocationSubscription


class SubscribedLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "title"]


class SubscriptionSerializer(serializers.ModelSerializer):
    location = SubscribedLocationSerializer(read_only=True)

    class Meta:
        model = LocationSubscription
        fields = ["id", "location", "created_at"]
