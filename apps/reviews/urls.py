from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import LocationReviewViewSet, ReviewViewSet

router = SimpleRouter()
router.register("reviews", ReviewViewSet, basename="review")

# Nested route declared by hand: no drf-nested-routers dependency
urlpatterns = [
    path(
        "locations/<int:location_pk>/reviews/",
        LocationReviewViewSet.as_view({"get": "list"}),
        name="location-reviews",
    ),
    *router.urls,
]
