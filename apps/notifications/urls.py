from django.urls import path

from . import views

urlpatterns = [
    path(
        "locations/<int:location_pk>/subscribe/",
        views.LocationSubscribeView.as_view(),
        name="location-subscribe",
    ),
    path("subscriptions/", views.MySubscriptionsView.as_view(), name="my-subscriptions"),
]
