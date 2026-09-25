from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet

# SimpleRouter: DefaultRouter would add a competing API root view per app
router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = router.urls
