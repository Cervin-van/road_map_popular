import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

RESET_URL = "/api/auth/password-reset/"
CONFIRM_URL = "/api/auth/password-reset/confirm/"
LOGIN_URL = "/api/auth/login/"
ME_URL = "/api/auth/me/"

NEW_PASSWORD = "Brand-new-pass-77"


@pytest.fixture
def request_reset(api_client, django_capture_on_commit_callbacks):
    def _request(email):
        with django_capture_on_commit_callbacks(execute=True):
            return api_client.post(RESET_URL, {"email": email}, format="json")

    return _request


def _link_params(message):
    uid = re.search(r"uid=([\w-]+)", message.body).group(1)
    token = re.search(r"token=([\w-]+)", message.body).group(1)
    return uid, token


def _confirm(client, uid, token, password=NEW_PASSWORD, password2=None):
    payload = {
        "uid": uid,
        "token": token,
        "new_password": password,
        "new_password2": password if password2 is None else password2,
    }
    return client.post(CONFIRM_URL, payload, format="json")


def _login(username, password):
    return APIClient().post(LOGIN_URL, {"username": username, "password": password}, format="json")


# --- request --------------------------------------------------------------


def test_reset_sends_email_with_link(request_reset, user, settings):
    response = request_reset(user.email)
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [user.email]
    assert f"{settings.FRONTEND_URL}/reset-password?" in message.body
    assert all(_link_params(message))


def test_reset_email_lookup_is_case_insensitive(request_reset, user):
    request_reset(user.email.upper())
    assert len(mail.outbox) == 1


def test_reset_unknown_email_returns_200_without_email(request_reset):
    response = request_reset("nobody@example.com")
    assert response.status_code == 200
    assert mail.outbox == []


def test_reset_inactive_user_gets_no_email(request_reset):
    user = UserFactory(is_active=False)
    assert request_reset(user.email).status_code == 200
    assert mail.outbox == []


def test_reset_invalid_email_format(request_reset):
    assert request_reset("not-an-email").status_code == 400


def test_reset_requires_csrf_token():
    client = APIClient(enforce_csrf_checks=True)
    response = client.post(RESET_URL, {"email": "a@example.com"}, format="json")
    assert response.status_code == 403


# --- confirm --------------------------------------------------------------


def test_confirm_sets_new_password(request_reset, api_client, user):
    request_reset(user.email)
    uid, token = _link_params(mail.outbox[0])

    response = _confirm(api_client, uid, token)

    assert response.status_code == 200
    assert _login(user.username, NEW_PASSWORD).status_code == 200
    assert _login(user.username, DEFAULT_PASSWORD).status_code == 400


def test_confirm_token_is_single_use(request_reset, api_client, user):
    request_reset(user.email)
    uid, token = _link_params(mail.outbox[0])
    assert _confirm(api_client, uid, token).status_code == 200

    response = _confirm(api_client, uid, token, password="Another-pass-88")
    assert response.status_code == 400
    assert "token" in response.data


@pytest.mark.parametrize("uid, token", [("MQ", "bad-token"), ("!!garbage!!", "x")])
def test_confirm_invalid_link(api_client, user, uid, token):
    response = _confirm(api_client, uid, token)
    assert response.status_code == 400
    assert "token" in response.data


def test_confirm_password_mismatch(request_reset, api_client, user):
    request_reset(user.email)
    uid, token = _link_params(mail.outbox[0])
    response = _confirm(api_client, uid, token, password2="Other-pass-99")
    assert response.status_code == 400
    assert "new_password2" in response.data


def test_confirm_weak_password(request_reset, api_client, user):
    request_reset(user.email)
    uid, token = _link_params(mail.outbox[0])
    response = _confirm(api_client, uid, token, password="12345")
    assert response.status_code == 400
    assert "new_password" in response.data


def test_confirm_invalidates_existing_sessions(request_reset, auth_client, user):
    assert auth_client.get(ME_URL).status_code == 200
    request_reset(user.email)
    uid, token = _link_params(mail.outbox[0])

    assert _confirm(APIClient(), uid, token).status_code == 200
    assert auth_client.get(ME_URL).status_code == 403


def test_email_lists_uid_and_token_for_api_only_reset(request_reset, api_client, user):
    request_reset(user.email)
    body = mail.outbox[0].body
    uid = re.search(r"^uid: ([\w-]+)$", body, re.MULTILINE).group(1)
    token = re.search(r"^token: ([\w-]+)$", body, re.MULTILINE).group(1)

    assert (uid, token) == _link_params(mail.outbox[0])
    assert "/api/auth/password-reset/confirm/" in body
    assert _confirm(api_client, uid, token).status_code == 200
