from functools import cached_property

from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets

from apps.locations.models import Location

from . import selectors
from .models import Review
from .serializers import ReviewSerializer


class LocationReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """/locations/{location_pk}/reviews/"""

    serializer_class = ReviewSerializer
    ordering_fields = ["created_at", "rating", "likes_count"]
    ordering = ["-created_at"]

    @cached_property
    def location(self) -> Location:
        # Location.objects excludes soft-deleted rows -> 404
        return get_object_or_404(Location.objects, pk=self.kwargs["location_pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation has no URL kwargs
            return Review.objects.none()
        return selectors.reviews_with_votes(self.request.user).filter(location=self.location)


class ReviewViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """/reviews/{id}/"""

    serializer_class = ReviewSerializer

    def get_queryset(self):
        return selectors.reviews_with_votes(self.request.user)
