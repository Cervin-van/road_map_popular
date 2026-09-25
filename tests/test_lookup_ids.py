"""Non-numeric ids in detail URLs must give 404, never 500."""

import pytest

pytestmark = pytest.mark.django_db

DETAIL_URLS = [
    "/api/locations/abc/",
    "/api/locations/1.5/",
    "/api/categories/abc/",
    "/api/reviews/abc/",
]


@pytest.mark.parametrize("url", DETAIL_URLS)
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_non_numeric_detail_id_returns_404(admin_client, url, method):
    assert getattr(admin_client, method)(url, {}, format="json").status_code == 404


@pytest.mark.parametrize("method", ["post", "delete"])
def test_non_numeric_review_id_on_vote_returns_404(admin_client, method):
    response = getattr(admin_client, method)(
        "/api/reviews/abc/vote/", {"value": "like"}, format="json"
    )
    assert response.status_code == 404
