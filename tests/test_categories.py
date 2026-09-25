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


# --- read API -------------------------------------------------------------

LIST_URL = "/api/categories/"


def detail_url(pk):
    return f"{LIST_URL}{pk}/"


def test_anonymous_can_list_categories(api_client):
    CategoryFactory.create_batch(3)
    response = api_client.get(LIST_URL)
    assert response.status_code == 200
    assert response.data["count"] == 3
    assert {"id", "name", "slug", "description"} <= response.data["results"][0].keys()


def test_list_ordered_by_name(api_client):
    for name in ["Музеї", "Кафе", "Парки"]:
        CategoryFactory(name=name)
    names = [c["name"] for c in api_client.get(LIST_URL).data["results"]]
    assert names == ["Кафе", "Музеї", "Парки"]


def test_search_by_name(api_client):
    CategoryFactory(name="Музеї")
    CategoryFactory(name="Парки")
    response = api_client.get(LIST_URL, {"search": "муз"})
    assert [c["name"] for c in response.data["results"]] == ["Музеї"]


def test_retrieve_category(api_client):
    category = CategoryFactory(name="Музеї", description="Історія")
    response = api_client.get(detail_url(category.pk))
    assert response.status_code == 200
    assert response.data["slug"] == "музеї"
    assert response.data["description"] == "Історія"


def test_retrieve_missing_category_returns_404(api_client):
    assert api_client.get(detail_url(999_999)).status_code == 404
