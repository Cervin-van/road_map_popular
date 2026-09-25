from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_patterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("auth/", include("apps.users.urls")),
    path("", include("apps.categories.urls")),
    path("", include("apps.locations.urls")),
    path("", include("apps.reviews.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]
