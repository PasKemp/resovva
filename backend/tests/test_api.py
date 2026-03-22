"""API-Tests – Health, Workflows, Documents."""


def test_health(client):
    """Health-Endpoint liefert 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
