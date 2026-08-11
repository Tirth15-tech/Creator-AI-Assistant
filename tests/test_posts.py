from io import BytesIO


class TestHistory:
    def test_empty_history(self, auth_client):
        resp = auth_client.get("/api/posts/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_pagination_params(self, auth_client):
        resp = auth_client.get("/api/posts/history?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_pagination_invalid_page(self, auth_client):
        resp = auth_client.get("/api/posts/history?page=0")
        assert resp.status_code == 422

    def test_pagination_invalid_page_size(self, auth_client):
        resp = auth_client.get("/api/posts/history?page_size=200")
        assert resp.status_code == 422


class TestUpload:
    def test_upload_no_file_no_text(self, auth_client):
        resp = auth_client.post("/api/posts/upload", data={"text": ""})
        assert resp.status_code == 400

    def test_upload_text_only(self, auth_client):
        resp = auth_client.post(
            "/api/posts/upload",
            data={"text": "Hello world, this is test content for social media"},
        )
        assert resp.status_code in (200, 201, 503)

    def test_upload_unauthorized(self, client):
        resp = client.post("/api/posts/upload", data={"text": "Hello"})
        assert resp.status_code == 401

    def test_upload_image_jpeg(self, auth_client):
        img_bytes = BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        resp = auth_client.post(
            "/api/posts/upload",
            data={"text": "test image"},
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert resp.status_code in (200, 201, 500, 503)


class TestExport:
    def test_export_txt_nonexistent(self, auth_client):
        resp = auth_client.get("/api/posts/99999/export/txt")
        assert resp.status_code == 404

    def test_export_invalid_format(self, auth_client):
        resp = auth_client.get("/api/posts/1/export/pdf")
        assert resp.status_code in (400, 404)

    def test_export_all_csv(self, auth_client):
        resp = auth_client.get("/api/posts/export-all/csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"


class TestQuality:
    def test_quality_no_media(self, auth_client):
        resp = auth_client.get("/api/posts/99999/quality")
        assert resp.status_code == 404
