"""M0 smoke tests: the app serves a page and the disclaimer is present."""
import pytest


@pytest.mark.django_db
def test_index_serves_page(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_index_carries_disclaimer(client):
    """Acceptance for M0: the not-a-QMS disclaimer is visible on the page."""
    response = client.get("/")
    body = response.content.decode()
    assert "not a quality system of record" in body
    assert "signs every disposition" in body


def test_healthz_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
