from functools import cached_property

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.permissions import IsOwnerOrAdmin
from apps.locations.models import Location

from . import selectors, services
from .models import Review
from .serializers import ReviewSerializer, ReviewWriteSerializer, VoteSerializer

_write_schema = extend_schema(request=ReviewWriteSerializer, responses=ReviewSerializer)


class ReviewReadMixin:
    def _read(self, pk):
        # Re-read through the selector so the response carries counters and my_vote
        review = selectors.reviews_with_votes(self.request.user).get(pk=pk)
        return ReviewSerializer(review, context=self.get_serializer_context()).data


@extend_schema_view(create=_write_schema)
class LocationReviewViewSet(ReviewReadMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """/locations/{location_pk}/reviews/"""

    permission_classes = [IsAuthenticatedOrReadOnly]
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

    def get_serializer_class(self):
        return ReviewWriteSerializer if self.action == "create" else ReviewSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = services.create_review(
            location=self.location, author=request.user, **serializer.validated_data
        )
        return Response(self._read(review.pk), status=status.HTTP_201_CREATED)


@extend_schema_view(partial_update=_write_schema)
class ReviewViewSet(
    ReviewReadMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """/reviews/{id}/"""

    lookup_value_regex = r"\d+"  # non-numeric ids -> 404 from the router
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    # No PUT; POST is only routed to the vote action (the router maps none on detail)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return selectors.reviews_with_votes(self.request.user)

    def get_serializer_class(self):
        # Also drives the Browsable API form for each action
        return {
            "partial_update": ReviewWriteSerializer,
            "vote": VoteSerializer,
        }.get(self.action, ReviewSerializer)

    def update(self, request, *args, **kwargs):
        review = self.get_object()  # runs IsOwnerOrAdmin
        serializer = self.get_serializer(review, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_review(review, **serializer.validated_data)
        return Response(self._read(review.pk))

    def perform_destroy(self, instance):
        services.delete_review(instance)

    @extend_schema(methods=["POST"], request=VoteSerializer, responses={201: ReviewSerializer})
    @extend_schema(methods=["DELETE"], request=None, responses={204: None})
    # IsOwnerOrAdmin would make get_object() reject everyone but the review author
    @action(detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        """Like or dislike a review: POST {"value": "like" | "dislike"}; DELETE cancels your vote.

        One vote per user: a second POST returns 409 already_voted.
        """
        review = self.get_object()  # soft-deleted location -> 404

        if request.method == "DELETE":
            if not services.remove_vote(review=review, user=request.user):
                raise NotFound("You have not voted for this review.")
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.vote_review(
            review=review, user=request.user, value=serializer.validated_data["value"]
        )
        return Response(self._read(review.pk), status=status.HTTP_201_CREATED)
