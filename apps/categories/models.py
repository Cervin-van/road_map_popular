from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=100)
    # allow_unicode: plain slugify() strips Cyrillic entirely and yields "".
    # slugify() lowercases, so a unique slug also makes names unique case-insensitively.
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True, editable=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    @staticmethod
    def make_slug(name: str) -> str:
        return slugify(name, allow_unicode=True)

    def save(self, *args, **kwargs):
        # Here rather than in a service: the admin bypasses services
        self.slug = self.make_slug(self.name)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "name" in update_fields:
            kwargs["update_fields"] = {*update_fields, "slug"}
        super().save(*args, **kwargs)
