from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    # No single-column index: a boolean with two values is not selective; concrete
    # models add composite indexes that start with is_deleted instead.
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()  # alive only; used by the API
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()  # everything; admin only

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        update_fields = ["is_deleted", "deleted_at"]
        # auto_now is applied on save() only when the field is listed in update_fields
        if any(f.name == "updated_at" for f in self._meta.concrete_fields):
            update_fields.append("updated_at")
        self.save(update_fields=update_fields)
