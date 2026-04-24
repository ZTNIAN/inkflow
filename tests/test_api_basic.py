class TestHealthCheck:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "configured" in data

    def test_health_configured_true(self, client):
        resp = client.get("/api/health")
        assert resp.json()["configured"] is True


class TestSettings:
    def test_get_settings(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert data["configured"] is True

    def test_save_settings(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr("app.ENV_PATH", tmp_path / ".env")
        resp = client.post("/api/settings", json={
            "deepseek_api_key": "sk-new-key-12345",
            "deepseek_base_url": "https://api.deepseek.com/v1",
            "deepseek_model": "deepseek-chat",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestListEndpoints:
    def test_list_articles_empty(self, client):
        resp = client.get("/api/articles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_tags_empty(self, client):
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_stats_empty(self, client, temp_data_dir, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        monkeypatch.setattr("app.BASE_DIR", temp_data_dir.parent)
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["total_words"] == 0

    def test_format_templates(self, client):
        resp = client.get("/api/format/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)
        ids = [t["id"] for t in templates]
        assert "minimal" in ids
        assert "vibrant" in ids
        assert "business" in ids

    def test_article_templates(self, client):
        resp = client.get("/api/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert isinstance(templates, list)
        ids = [t["id"] for t in templates]
        assert "listicle" in ids or "story" in ids


class TestArticleOperations:
    def test_get_article_not_found(self, client):
        resp = client.get("/api/articles/nonexistent")
        assert resp.status_code == 404

    def test_delete_article_not_found(self, client):
        resp = client.delete("/api/articles/nonexistent")
        assert resp.status_code == 200

    def test_copy_article_not_found(self, client):
        resp = client.post("/api/articles/nonexistent/copy")
        assert resp.status_code == 404

    def test_save_and_get_article(self, client, temp_data_dir, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        monkeypatch.setattr("app.BASE_DIR", temp_data_dir.parent)
        resp = client.post("/api/articles/save", json={
            "topic": "测试保存",
            "content": "这是测试内容",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        article_id = data["id"]

        resp = client.get(f"/api/articles/{article_id}")
        assert resp.status_code == 200
        assert resp.json()["topic"] == "测试保存"


class TestTagFilter:
    def test_list_articles_by_tag_empty(self, client):
        resp = client.get("/api/articles/tag/test")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestVersionHistory:
    def test_list_versions_empty(self, client):
        resp = client.get("/api/articles/nonexistent/versions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_version_not_found(self, client):
        resp = client.get("/api/articles/nonexistent/versions/ver1.json")
        assert resp.status_code == 404


class TestStyles:
    def test_list_styles_empty(self, client):
        resp = client.get("/api/styles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_style_not_found(self, client):
        resp = client.get("/api/styles/nonexistent")
        assert resp.status_code == 404

    def test_delete_style_not_found(self, client):
        resp = client.delete("/api/styles/nonexistent")
        assert resp.status_code == 200
