from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.permissions import IsOwnerOrAdmin

from . import selectors, services
from .serializers import (
    LocationDetailSerializer,
    LocationListSerializer,
    LocationWriteSerializer,
)

_write_schema = extend_schema(request=LocationWriteSerializer, responses=LocationDetailSerializer)


@extend_schema_view(create=_write_schema, update=_write_schema, partial_update=_write_schema)
class LocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return selectors.locations_with_stats()

    def get_serializer_class(self):
        if self.action == "list":
            return LocationListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return LocationWriteSerializer
        return LocationDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = services.create_location(author=request.user, **serializer.validated_data)
        return Response(self._detail(location.pk), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()  # runs IsOwnerOrAdmin; soft-deleted -> 404
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        services.update_location(instance, **serializer.validated_data)
        return Response(self._detail(instance.pk))

    def perform_destroy(self, instance):
        services.soft_delete_location(instance)

    def _detail(self, pk):
        # Re-read through the selector so the response carries the same
        # stats annotations as GET
        location = selectors.locations_with_stats().get(pk=pk)
        return LocationDetailSerializer(location, context=self.get_serializer_context()).data
