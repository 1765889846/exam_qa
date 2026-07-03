"""API 契约单元测试。"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


class TestAskAPI:
    def test_validation_error_format(self):
        r = client.post("/api/v1/ask", json={"question": ""})
        assert r.status_code == 422
        body = r.json()
        assert body["code"] == 422
        assert "message" in body
        assert isinstance(body["message"], str)


class TestDocumentsAPI:
    def test_scan_response_shape(self):
        r = client.post("/api/v1/documents/scan")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 200
        assert "data" in body
        assert "message" in body["data"]
