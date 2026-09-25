from django.contrib import admin

from .models import LocationSubscription


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "created_at")
    raw_id_fields = ("user", "location")
    search_fields = ("user__username", "location__title")
