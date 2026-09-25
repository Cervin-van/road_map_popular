import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

CSRF_URL = "/api/auth/csrf/"
REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"

REGISTER_PAYLOAD = {
    "username": "newbie",
    "email": "newbie@example.com",
    "password": "Str0ng-pass-42",
    "password2": "Str0ng-pass-42",
}


# --- csrf -----------------------------------------------------------------


def test_csrf_endpoint_sets_cookie(api_client):
    response = api_client.get(CSRF_URL)
    assert response.status_code == 200
    assert "csrftoken" in response.cookies
    assert response.data["csrfToken"]


def test_anonymous_post_without_csrf_token_is_rejected():
    user = UserFactory()
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(
        LOGIN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 403
    assert "CSRF" in response.data["detail"]


def test_anonymous_post_with_csrf_token_is_accepted():
    user = UserFactory()
    client = APIClient(enforce_csrf_checks=True)
    token = client.get(CSRF_URL).cookies["csrftoken"].value
    response = client.post(
        LOGIN_URL,
        {"username": user.username, "password": DEFAULT_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


# --- register -------------------------------------------------------------


def test_register_creates_user_and_logs_in(api_client):
    response = api_client.post(REGISTER_URL, REGISTER_PAYLOAD, format="json")
    assert response.status_code == 201
    assert response.data["username"] == "newbie"
    assert "password" not in response.data
    assert User.objects.get(username="newbie").check_password("Str0ng-pass-42")
    assert api_client.get(ME_URL).status_code == 200


@pytest.mark.parametrize(
    "field, value",
    [("username", "NEWBIE"), ("email", "NEWBIE@Example.com")],
)
def test_register_duplicate_is_case_insensitive(api_client, field, value):
    UserFactory(username="newbie", email="newbie@example.com")
    payload = {**REGISTER_PAYLOAD, "username": "other", "email": "other@example.com"}
    payload[field] = value
    response = api_client.post(REGISTER_URL, payload, format="json")
    assert response.status_code == 400
    assert field in response.data


def test_register_password_mismatch(api_client):
    payload = {**REGISTER_PAYLOAD, "password2": "Different-pass-42"}
    response = api_client.post(REGISTER_URL, payload, format="json")
    assert response.status_code == 400
    assert "password2" in response.data


def test_register_weak_password(api_client):
    payload = {**REGISTER_PAYLOAD, "password": "12345", "password2": "12345"}
    response = api_client.post(REGISTER_URL, payload, format="json")
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.filter(username="newbie").exists()


def test_register_forbidden_for_authenticated(auth_client):
    response = auth_client.post(REGISTER_URL, REGISTER_PAYLOAD, format="json")
    assert response.status_code == 403


# --- login / logout / me --------------------------------------------------


def test_login_sets_session_cookie(api_client, user):
    response = api_client.post(
        LOGIN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 200
    assert response.data["id"] == user.id
    assert "sessionid" in response.cookies


def test_login_wrong_password(api_client, user):
    response = api_client.post(
        LOGIN_URL, {"username": user.username, "password": "wrong"}, format="json"
    )
    assert response.status_code == 400
    assert response.data["non_field_errors"][0].code == "invalid_credentials"
    assert "sessionid" not in response.cookies


def test_login_inactive_user_rejected(api_client):
    user = UserFactory(is_active=False)
    response = api_client.post(
        LOGIN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 400


def test_logout_ends_session(auth_client):
    assert auth_client.post(LOGOUT_URL).status_code == 204
    assert auth_client.get(ME_URL).status_code == 403


def test_logout_anonymous_forbidden(api_client):
    assert api_client.post(LOGOUT_URL).status_code == 403


def test_me_returns_current_user(auth_client, user):
    response = auth_client.get(ME_URL)
    assert response.status_code == 200
    assert response.data == {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": False,
        "date_joined": response.data["date_joined"],
    }


def test_me_anonymous_forbidden(api_client):
    assert api_client.get(ME_URL).status_code == 403
