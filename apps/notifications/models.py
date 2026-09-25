from django.conf import settings
from django.db import models

from apps.locations.models import Location


class LocationSubscription(models.Model):
    """A user wants an email about every new review of the location."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_subscriptions"
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "location"], name="uniq_subscription_per_user_location"
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.location}"
