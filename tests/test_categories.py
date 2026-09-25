import pytest
from django.db import IntegrityError

from apps.categories.models import Category
from tests.factories import CategoryFactory

pytestmark = pytest.mark.django_db


# --- model ----------------------------------------------------------------


def test_slug_generated_from_cyrillic_name():
    category = CategoryFactory(name="Кав'ярні та ресторани")
    assert category.slug == "кавярні-та-ресторани"


def test_slug_follows_rename():
    category = CategoryFactory(name="Парки")
    category.name = "Сквери"
    category.save(update_fields=["name"])
    category.refresh_from_db()
    assert category.slug == "сквери"


@pytest.mark.parametrize("duplicate", ["МУЗЕЇ", "Музеї!"])
def test_duplicate_slug_rejected_by_db(duplicate):
    Category.objects.create(name="Музеї")
    with pytest.raises(IntegrityError, match="slug"):
        Category.objects.create(name=duplicate)
