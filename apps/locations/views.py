from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.common.permissions import IsOwnerOrAdmin

from . import cache as list_cache
from . import export, selectors, services
from .filters import LocationFilter
from .models import Location
from .serializers import (
    ExportQuerySerializer,
    LocationDetailSerializer,
    LocationListSerializer,
    LocationMapSerializer,
    LocationWriteSerializer,
    MapQuerySerializer,
)

_write_schema = extend_schema(request=LocationWriteSerializer, responses=LocationDetailSerializer)


@extend_schema_view(create=_write_schema, update=_write_schema, partial_update=_write_schema)
class LocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]
    filterset_class = LocationFilter
    search_fields = ["title", "description"]  # ?search=, case-insensitive icontains
    ordering_fields = ["created_at", "avg_rating", "popularity"]  # annotations are orderable
    ordering = ["-created_at"]

    def get_queryset(self):
        return selectors.locations_with_stats()

    def get_serializer_class(self):
        if self.action == "list":
            return LocationListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return LocationWriteSerializer
        return LocationDetailSerializer

    def list(self, request, *args, **kwargs):
        # Shared across users: the list payload must never depend on request.user
        cached = list_cache.get("list", request.query_params)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            list_cache.set("list", request.query_params, response.data)
        return response

    @extend_schema(
        parameters=[MapQuerySerializer],
        responses={200: OpenApiTypes.OBJECT},
        description="GeoJSON FeatureCollection of the most popular locations. "
        "Accepts the same filters, search and ordering as the list (default -popularity).",
    )
    @action(detail=False, methods=["get"], pagination_class=None)
    def map(self, request):
        cached = list_cache.get("map", request.query_params)
        if cached is not None:
            return Response(cached)

        params = MapQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        self.ordering = ["-popularity"]  # default for the map; ?ordering= still wins
        queryset = self.filter_queryset(self.get_queryset())
        if bbox := params.validated_data.get("bbox"):
            min_lng, min_lat, max_lng, max_lat = bbox
            queryset = queryset.filter(
                longitude__gte=min_lng,
                longitude__lte=max_lng,
                latitude__gte=min_lat,
                latitude__lte=max_lat,
            )
        locations = queryset[: params.validated_data["limit"]]
        data = {
            "type": "FeatureCollection",
            "features": LocationMapSerializer(locations, many=True).data,
        }
        list_cache.set("map", request.query_params, data)
        return Response(data)

    @extend_schema(
        parameters=[ExportQuerySerializer],
        responses={
            (200, "text/csv"): OpenApiTypes.BINARY,
            (200, "application/json"): OpenApiTypes.BINARY,
        },
        description="Download locations as CSV or JSON. Accepts the same filters, search "
        "and ordering as the list; not paginated.",
    )
    @action(detail=False, methods=["get"], pagination_class=None)
    def export(self, request):
        params = ExportQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        queryset = self.filter_queryset(self.get_queryset())
        return export.export_response(queryset, params.validated_data["export_format"])

    def retrieve(self, request, *args, **kwargs):
        # Cheap lookup first: the stats query runs once, after the view is registered,
        # so views_7d in this response already includes the current view.
        # Never cached: it has a side effect and must show fresh numbers.
        location = get_object_or_404(Location.objects, pk=kwargs["pk"])  # soft-deleted -> 404
        self.check_object_permissions(request, location)
        services.register_view(location, request)
        return Response(self._detail(location.pk))

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
