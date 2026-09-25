from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "created_at", "updated_at"]
        read_only_fields = ["slug", "created_at", "updated_at"]

    def validate_name(self, value):
        slug = Category.make_slug(value)
        if not slug:
            raise serializers.ValidationError("Name must contain letters or digits.")
        # Uniqueness is slug uniqueness: catches "Музеї" vs "МУЗЕЇ" vs "Музеї!".
        # A concurrent duplicate still hits the DB unique constraint (500, admin-only, rare).
        duplicates = Category.objects.filter(slug=slug)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value
