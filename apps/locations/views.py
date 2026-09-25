from rest_framework import viewsets

from . import selectors
from .serializers import LocationDetailSerializer, LocationListSerializer


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return selectors.alive_locations()

    def get_serializer_class(self):
        if self.action == "list":
            return LocationListSerializer
        return LocationDetailSerializer
