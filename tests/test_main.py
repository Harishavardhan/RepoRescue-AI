from fastapi.testclient import TestClient

from backend.main import app, demo_inspection


client = TestClient(app)


def test_accepts_public_github_url_and_normalizes_trailing_slash():
    response = client.post("/api/inspect", json={"github_url": "https://github.com/octocat/Hello-World/", "demo": True})
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert body["repository"]["name"] == "reporescue-sample"
    assert {finding["severity"] for finding in body["findings"]} >= {"high", "medium"}


def test_rejects_non_github_or_private_style_urls():
    response = client.post("/api/inspect", json={"github_url": "https://gitlab.com/org/repo"})
    assert response.status_code == 422


def test_demo_inspection_has_explanations_and_fixes():
    result = demo_inspection()
    assert result.demo is True
    assert result.findings
    assert all(item.explanation and item.fix for item in result.findings)
