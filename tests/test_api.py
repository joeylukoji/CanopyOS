from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


def photo():
    image = Image.fromarray(
        np.random.default_rng(1).integers(40, 220, (256, 256, 3), dtype=np.uint8)
    )
    buffer = BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


class TestVision:
    __test__ = False
    status = "ready"
    model_id = "test-double-not-a-real-model"

    def segment(self, image):
        mask = np.full((image.height, image.width), 6, dtype=np.uint8)
        mask[:, : image.width // 3] = 4
        return mask, 0.9


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, vision=TestVision())) as client:
        client.get("/")
        yield client


def upload(client, data=None, mime="image/jpeg"):
    return client.post("/api/v1/scans", files={"image": ("photo.jpg", data or photo(), mime)})


def test_private_upload_analyze_report_delete(client):
    response = upload(client)
    assert response.status_code == 201
    scan_id = response.json()["scan_id"]
    response = client.post(f"/api/v1/scans/{scan_id}/analyze")
    assert response.status_code == 202
    report = client.get(f"/api/v1/scans/{scan_id}").json()
    assert report["status"] == "completed"
    assert report["report"]["decision"]["source"] == "rules_fallback"
    asset = report["report"]["assets"]["original"]
    assert client.get(asset).status_code == 200
    assert client.get(f"/scans/{scan_id}").status_code == 200
    assert len(client.get("/api/v1/scans").json()) == 1
    assert client.delete(f"/api/v1/scans/{scan_id}").status_code == 204
    assert client.get(asset).status_code == 404


def test_another_browser_cannot_read_or_delete(client):
    scan_id = upload(client).json()["scan_id"]
    with TestClient(client.app) as other:
        other.get("/")
        assert other.get("/api/v1/scans").json() == []
        assert other.get(f"/api/v1/scans/{scan_id}").status_code == 404
        assert other.get(f"/assets/{scan_id}/original.jpg").status_code == 404
        assert other.delete(f"/api/v1/scans/{scan_id}").status_code == 404


@pytest.mark.parametrize(
    "data,mime", [(b"not an image", "image/jpeg"), (b"<svg/>", "image/svg+xml")]
)
def test_bad_images_rejected(client, data, mime):
    assert upload(client, data, mime).status_code == 415


def test_oversized_upload_rejected(client):
    assert upload(client, b"x" * (8 * 1024 * 1024 + 1)).status_code == 413


def test_cross_origin_mutation_rejected(client):
    response = client.post(
        "/api/v1/scans",
        headers={"Origin": "https://evil.example"},
        files={"image": ("x.jpg", photo(), "image/jpeg")},
    )
    assert response.status_code == 403


def test_dark_photo_never_produces_recommendation(client):
    buffer = BytesIO()
    Image.new("RGB", (256, 256), "black").save(buffer, "JPEG")
    scan_id = upload(client, buffer.getvalue()).json()["scan_id"]
    client.post(f"/api/v1/scans/{scan_id}/analyze")
    result = client.get(f"/api/v1/scans/{scan_id}").json()
    assert result["status"] == "rejected"
    assert result["report"] is None
    assert "wider outdoor view" in result["error"]


def test_server_busy_is_retryable_and_does_not_lose_upload(client):
    scan_id = upload(client).json()["scan_id"]
    pipeline = client.app.state.pipeline
    pipeline.slot.acquire()
    try:
        assert client.post(f"/api/v1/scans/{scan_id}/analyze").status_code == 409
        assert client.get(f"/api/v1/scans/{scan_id}").json()["status"] == "uploaded"
    finally:
        pipeline.slot.release()


def test_completed_analysis_is_idempotent(client):
    scan_id = upload(client).json()["scan_id"]
    client.post(f"/api/v1/scans/{scan_id}/analyze")
    before = client.get(f"/api/v1/scans/{scan_id}").json()
    client.post(f"/api/v1/scans/{scan_id}/analyze")
    assert client.get(f"/api/v1/scans/{scan_id}").json() == before


def test_analysis_rate_limit(client):
    store = client.app.state.store
    assert all(store.allow("test", "test-analysis", 2, 3) for _ in range(2))
    assert not store.allow("test", "test-analysis", 2, 3)
    assert store.allow("other", "test-analysis", 2, 3)
    assert not store.allow("third", "test-analysis", 2, 3)


def test_configured_providers_are_not_reported_as_verified(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GEMMA_ENDPOINT", "http://localhost:11434")
    with TestClient(create_app(tmp_path, vision=TestVision())) as test_client:
        health = test_client.get("/api/v1/health").json()
    assert health["status"] == "degraded"
    assert health["jev"] == "configured_unverified"


def test_running_scan_cannot_be_deleted_even_at_storage_boundary(client):
    from app.storage import ScanBusy

    store = client.app.state.store
    scan_id = store.create("owner", "street")
    store.update(scan_id, status="processing", stage=1)
    with pytest.raises(ScanBusy):
        store.delete(scan_id, "owner")
    assert store.get(scan_id, "owner")["status"] == "processing"
