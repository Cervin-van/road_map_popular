import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tests.factories import AdminFactory, UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def admin(db):
    return AdminFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_login(admin)
    return client
