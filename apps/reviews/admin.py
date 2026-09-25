from django.contrib import admin

from .models import Review, ReviewVote


class ReviewVoteInline(admin.TabularInline):
    model = ReviewVote
    extra = 0
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "location", "author", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("text", "location__title", "author__username")
    raw_id_fields = ("location", "author")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ReviewVoteInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("location", "author")
