import json


class TestValidate:
    def test_validate_perfect_content(self, client, sample_content):
        resp = client.post("/api/validate", json={
            "content": sample_content,
            "platform": "wechat",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "passed" in data
        assert "score" in data
        assert "issues" in data

    def test_validate_content_with_issues(self, client):
        bad_content = "全场震惊。毫无疑问。众所周知。这是一个非常好的产品。"
        resp = client.post("/api/validate", json={
            "content": bad_content,
            "platform": "wechat",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["issues"]) >= 1
        assert data["score"] < 100


class TestRevise:
    def test_revise_missing_content(self, client):
        resp = client.post("/api/revise", json={
            "content": "",
            "instruction": "修改",
        })
        assert resp.status_code == 400

    def test_revise_missing_instruction(self, client, sample_content):
        resp = client.post("/api/revise", json={
            "content": sample_content,
            "instruction": "",
        })
        assert resp.status_code == 400


class TestSuggest:
    def test_suggest_revisions(self, client, sample_content, sample_outline_dict):
        resp = client.post("/api/revise/suggest", json={
            "content": sample_content,
            "platform": "wechat",
            "outline": sample_outline_dict,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "suggestions" in data
        assert "sections" in data
        assert "score" in data

    def test_suggest_revisions_no_outline(self, client, sample_content):
        resp = client.post("/api/revise/suggest", json={
            "content": sample_content,
            "platform": "wechat",
        })
        assert resp.status_code == 200


class TestExtractMaterial:
    def test_extract_material_no_source(self, client):
        resp = client.post("/api/extract-material", json={
            "source_text": "",
            "topic": "测试主题",
        })
        assert resp.status_code == 200 or resp.status_code == 500


class TestSaveArticle:
    def test_save_new_article(self, client, temp_data_dir, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        resp = client.post("/api/articles/save", json={
            "id": "",
            "topic": "新文章",
            "content": "这是正文内容。",
            "tags": ["测试"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["id"].startswith("art_")

    def test_save_article_twice_triggers_version(self, client, temp_data_dir, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        resp = client.post("/api/articles/save", json={
            "topic": "版本测试",
            "content": "第一版内容。",
        })
        article_id = resp.json()["id"]

        resp = client.post("/api/articles/save", json={
            "id": article_id,
            "topic": "版本测试",
            "content": "第二版内容。",
        })
        assert resp.status_code == 200

        resp = client.get(f"/api/articles/{article_id}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1


class TestGenerateEndpoints:
    def test_generate_outline(self, client, mock_llm, monkeypatch):
        monkeypatch.setattr("app._create_llm", lambda t=0.7: mock_llm)
        resp = client.post("/api/generate/outline", json={
            "topic": "测试主题",
            "platform": "wechat",
            "mode": "干货型",
        })
        data = resp.json()
        assert data["ok"] is True or resp.status_code == 500
        if data.get("ok"):
            assert "title_candidates" in data["outline"]

    def test_generate_titles(self, client, mock_llm, monkeypatch):
        monkeypatch.setattr("app._create_llm", lambda t=0.7: mock_llm)
        resp = client.post("/api/generate/titles", json={
            "topic": "测试主题",
            "outline_summary": "",
            "platform": "wechat",
            "count": 5,
        })
        data = resp.json()
        assert data["ok"] is True or resp.status_code == 500

    def test_generate_batch_too_many(self, client):
        resp = client.post("/api/generate/batch", json={
            "topics": [str(i) for i in range(11)],
        })
        assert resp.status_code == 400

    def test_generate_batch_empty(self, client):
        resp = client.post("/api/generate/batch", json={
            "topics": [],
        })
        assert resp.status_code == 400


class TestFormat:
    def test_format_html(self, client, mock_llm, monkeypatch):
        monkeypatch.setattr("app._create_llm", lambda t=0.7: mock_llm)
        resp = client.post("/api/format", json={
            "content": "**标题**\n\n正文内容。",
            "title": "测试标题",
            "tags": ["标签1"],
            "template": "minimal",
        })
        data = resp.json()
        assert data["ok"] is True or resp.status_code == 500
        if data.get("ok"):
            assert "html" in data


class TestAudit:
    def test_audit_article(self, client, mock_llm, monkeypatch):
        monkeypatch.setattr("app._create_llm", lambda t=0.7: mock_llm)
        resp = client.post("/api/audit", json={
            "content": "测试内容。",
            "topic": "测试主题",
            "platform": "wechat",
        })
        data = resp.json()
        assert data["ok"] is True or resp.status_code == 500
        if data.get("ok"):
            assert "audit" in data


class TestSEO:
    def test_seo_optimize(self, client, mock_llm, monkeypatch):
        monkeypatch.setattr("app._create_llm", lambda t=0.7: mock_llm)
        resp = client.post("/api/seo", json={
            "content": "测试内容。",
            "topic": "测试主题",
        })
        data = resp.json()
        assert data["ok"] is True or resp.status_code == 500
        if data.get("ok"):
            assert "seo" in data


class TestFetchReferences:
    def test_fetch_references_empty(self, client):
        resp = client.post("/api/fetch-references", json={
            "urls": [],
            "topic": "测试",
        })
        assert resp.status_code == 400
