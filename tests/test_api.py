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

    def test_missing_course_id(self):
        r = client.post("/api/v1/ask", json={"question": "卷积定理"})
        assert r.status_code == 422


class TestCatalogAPI:
    def test_list_colleges_and_courses(self):
        r = client.get("/api/v1/colleges")
        assert r.status_code == 200
        assert len(r.json()["data"]["items"]) >= 1
        assert any(c["id"] == "college-default" for c in r.json()["data"]["items"])

        r2 = client.get("/api/v1/courses")
        assert r2.status_code == 200
        courses = r2.json()["data"]["items"]
        assert any(c["id"] == "course-default" for c in courses)

        r3 = client.get("/api/v1/courses", params={"college_id": "college-default"})
        assert r3.status_code == 200
        assert all(
            c["college_id"] == "college-default" for c in r3.json()["data"]["items"]
        )


class TestDocumentsAPI:
    def test_scan_requires_course_id(self):
        r = client.post("/api/v1/documents/scan")
        assert r.status_code == 422

    def test_scan_response_shape(self):
        r = client.post(
            "/api/v1/documents/scan",
            data={"course_id": "course-default"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 200
        assert "message" in body["data"]

    def test_scan_unknown_course_404(self):
        r = client.post(
            "/api/v1/documents/scan",
            data={"course_id": "course-nonexistent"},
        )
        assert r.status_code == 404


class TestRootRedirect:
    def test_root_goes_to_docs_without_www(self):
        r = client.get("/", follow_redirects=False)
        assert r.status_code in (307, 302)
        assert r.headers["location"].endswith("/docs")

    def test_root_redirect_helpers(self, tmp_path):
        from src.main import _ui_ready, _root_redirect_url

        assert _root_redirect_url(tmp_path) == "/docs"
        (tmp_path / "sz").mkdir()
        (tmp_path / "sz" / "index.html").write_text("x", encoding="utf-8")
        assert _ui_ready(tmp_path) is True
        assert _root_redirect_url(tmp_path) == "/sz/"
