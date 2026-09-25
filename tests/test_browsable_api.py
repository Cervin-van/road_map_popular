"""Smoke test: every endpoint renders as an HTML page in the DRF Browsable API.

JSON clients never hit this path, but the HTML renderer builds forms for the
allowed methods and needs a serializer per view/action; a view without one
crashes with 500 only in the browser.
"""

import pytest

from tests.factories import LocationSubscriptionFactory, ReviewFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def urls(user):
    review = ReviewFactory()
    location = review.location
    LocationSubscriptionFactory(user=user, location=location)
    return [
        "/api/auth/csrf/",
        "/api/auth/register/",
        "/api/auth/login/",
        "/api/auth/logout/",
        "/api/auth/me/",
        "/api/auth/password-reset/",
        "/api/auth/password-reset/confirm/",
        "/api/categories/",
        f"/api/categories/{location.category_id}/",
        "/api/locations/",
        f"/api/locations/{location.pk}/",
        "/api/locations/map/",
        f"/api/locations/{location.pk}/reviews/",
        f"/api/locations/{location.pk}/subscribe/",
        f"/api/reviews/{review.pk}/",
        f"/api/reviews/{review.pk}/vote/",
        "/api/subscriptions/",
    ]


@pytest.mark.parametrize("client_fixture", ["api_client", "auth_client", "admin_client"])
def test_every_endpoint_renders_as_html(request, urls, client_fixture):
    client = request.getfixturevalue(client_fixture)
    failures = {}
    for url in urls:
        response = client.get(url, HTTP_ACCEPT="text/html")
        if response.status_code >= 500:
            failures[url] = response.status_code
    assert failures == {}
