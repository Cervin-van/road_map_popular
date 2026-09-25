from rest_framework import viewsets

from apps.common.permissions import IsAdminOrReadOnly

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
