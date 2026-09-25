from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.categories.models import Category
from apps.common.models import SoftDeleteModel, TimeStampedModel


class Location(TimeStampedModel, SoftDeleteModel):
    """A place on the map.

    Rating and popularity are never stored here: they are ORM annotations
    in selectors (see ARCHITECTURE.md §4).
    """

    title = models.CharField(max_length=200)
    description = models.TextField()
    # PROTECT also counts soft-deleted locations: their rows still exist
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="locations")
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90, latitude__lte=90),
                name="location_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180, longitude__lte=180),
                name="location_longitude_range",
            ),
        ]
        indexes = [
            models.Index(fields=["is_deleted", "created_at"], name="location_alive_created_idx"),
        ]

    def __str__(self):
        return self.title
