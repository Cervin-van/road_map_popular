from django.contrib import admin

from .models import Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "category")
    search_fields = ("title", "address")
    raw_id_fields = ("author",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")

    def get_queryset(self, request):
        # The default manager hides soft-deleted rows; the admin must see everything
        return Location.all_objects.select_related("category", "author")
