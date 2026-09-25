from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db.models import ProtectedError
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.common.exceptions import Conflict, custom_exception_handler
from apps.common.permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from apps.common.utils import viewer_key

rf = APIRequestFactory()


def _req(method, user):
    request = getattr(rf, method)("/")
    request.user = user
    return request


# --- infrastructure -------------------------------------------------------


@pytest.mark.django_db
def test_swagger_docs_available(api_client):
    assert api_client.get("/api/docs/").status_code == 200


@pytest.mark.django_db
def test_openapi_schema_available(api_client):
    response = api_client.get("/api/schema/")
    assert response.status_code == 200
    assert b"openapi" in response.content


def test_cache_is_locmem_in_tests(settings):
    assert settings.CACHES["default"]["BACKEND"].endswith("LocMemCache")
    assert cache.add("k", 1, timeout=60) is True
    assert cache.add("k", 1, timeout=60) is False  # SET NX semantics


def test_only_session_authentication(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "rest_framework.authentication.SessionAuthentication"
    ]


# --- exception handler ----------------------------------------------------


def test_conflict_returns_409_with_code():
    response = custom_exception_handler(Conflict("dup", code="already_voted"), {})
    assert response.status_code == 409
    assert response.data == {"detail": "dup", "code": "already_voted"}


def test_protected_error_mapped_to_409():
    response = custom_exception_handler(ProtectedError("in use", set()), {})
    assert response.status_code == 409
    assert response.data["code"] == "protected"


def test_validation_error_unchanged():
    response = custom_exception_handler(ValidationError({"title": ["required"]}), {})
    assert response.status_code == 400
    assert "title" in response.data


# --- permissions ----------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_write(user):
    obj = SimpleNamespace(author_id=user.pk)
    assert IsOwnerOrAdmin().has_object_permission(_req("patch", user), None, obj)


@pytest.mark.django_db
def test_non_owner_cannot_write_but_admin_can(user, admin):
    obj = SimpleNamespace(author_id=user.pk + 1000)
    assert not IsOwnerOrAdmin().has_object_permission(_req("patch", user), None, obj)
    assert IsOwnerOrAdmin().has_object_permission(_req("delete", admin), None, obj)


def test_anonymous_can_only_read_objects():
    obj = SimpleNamespace(author_id=1)
    perm = IsOwnerOrAdmin()
    assert perm.has_object_permission(_req("get", AnonymousUser()), None, obj)
    assert not perm.has_object_permission(_req("delete", AnonymousUser()), None, obj)


@pytest.mark.django_db
def test_admin_or_read_only(user, admin):
    perm = IsAdminOrReadOnly()
    assert perm.has_permission(_req("get", AnonymousUser()), None)
    assert not perm.has_permission(_req("post", user), None)
    assert perm.has_permission(_req("post", admin), None)


# --- viewer key -----------------------------------------------------------


@pytest.mark.django_db
def test_viewer_key_for_user(user):
    assert viewer_key(_req("get", user)) == f"user:{user.pk}"


def test_viewer_key_for_anonymous_depends_on_ip_and_ua():
    a = rf.get("/", REMOTE_ADDR="1.1.1.1", HTTP_USER_AGENT="ua")
    b = rf.get("/", REMOTE_ADDR="2.2.2.2", HTTP_USER_AGENT="ua")
    a.user = b.user = AnonymousUser()
    key_a = viewer_key(a)
    assert key_a.startswith("anon:") and len(key_a) == 69
    assert key_a != viewer_key(b)


def test_x_forwarded_for_ignored_by_default(settings):
    settings.USE_X_FORWARDED_FOR = False
    a = rf.get("/", REMOTE_ADDR="1.1.1.1", HTTP_X_FORWARDED_FOR="9.9.9.9")
    b = rf.get("/", REMOTE_ADDR="1.1.1.1", HTTP_X_FORWARDED_FOR="8.8.8.8")
    a.user = b.user = AnonymousUser()
    assert viewer_key(a) == viewer_key(b)
