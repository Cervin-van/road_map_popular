from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.locations.models import Location

from . import services
from .models import LocationSubscription
from .serializers import SubscriptionSerializer


class LocationSubscribeView(generics.GenericAPIView):
    """/locations/{location_pk}/subscribe/ — emails about new reviews of the location."""

    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get_location(self) -> Location:
        return get_object_or_404(Location.objects, pk=self.kwargs["location_pk"])  # alive only

    @extend_schema(request=None, responses={201: SubscriptionSerializer})
    def post(self, request, location_pk):
        subscription = services.subscribe(user=request.user, location=self.get_location())
        return Response(self.get_serializer(subscription).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, location_pk):
        if not services.unsubscribe(user=request.user, location=self.get_location()):
            raise NotFound("You are not subscribed to this location.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MySubscriptionsView(generics.ListAPIView):
    """/subscriptions/ — the current user's subscriptions."""

    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer
    ordering = ["-created_at"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation: anonymous user
            return LocationSubscription.objects.none()
        return LocationSubscription.objects.filter(
            user=self.request.user, location__is_deleted=False
        ).select_related("location")
