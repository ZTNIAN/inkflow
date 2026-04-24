import json, pytest
from pathlib import Path
from pipeline import Pipeline, _to_dict, Outline, StyleProfile, DATA_DIR


class TestToDict:
    def test_dataclass_to_dict(self):
        o = Outline(title_candidates=["a"], selected_title="b")
        d = _to_dict(o)
        assert d["title_candidates"] == ["a"]
        assert d["selected_title"] == "b"

    def test_nested_dataclass(self):
        o = Outline(title_candidates=["t1"])
        d = _to_dict(o)
        assert isinstance(d, dict)

    def test_list_of_dataclasses(self):
        outlines = [Outline(title_candidates=["a"]), Outline(title_candidates=["b"])]
        d = _to_dict(outlines)
        assert len(d) == 2
        assert d[0]["title_candidates"] == ["a"]

    def test_dict_with_dataclass_values(self):
        o = Outline(title_candidates=["x"])
        d = _to_dict({"outline": o})
        assert d["outline"]["title_candidates"] == ["x"]

    def test_primitive_values(self):
        assert _to_dict(42) == 42
        assert _to_dict("hello") == "hello"
        assert _to_dict(None) is None


class TestOutlineDefaults:
    def test_outline_defaults(self):
        o = Outline()
        assert o.title_candidates == []
        assert o.selected_title == ""
        assert o.sections == []
        assert o.tags == []

    def test_outline_custom_values(self):
        o = Outline(title_candidates=["a", "b"], selected_title="a", sections=[{"title": "s1"}], tags=["t1"])
        assert o.selected_title == "a"
        assert len(o.sections) == 1


class TestStyleProfileDefaults:
    def test_style_profile_defaults(self):
        s = StyleProfile()
        assert s.id == ""
        assert s.vocabulary == []
        assert s.sentence_patterns == []


class TestBuildStyleInstruction:
    def test_with_profile(self):
        pipeline = Pipeline.__new__(Pipeline)
        profile = StyleProfile(tone="温暖治愈", vocabulary=["确实", "其实"], sentence_patterns=["...的"], punctuation_habits="多用逗号")
        result = pipeline._build_style_instruction(profile)
        assert "温暖治愈" in result
        assert "确实" in result

    def test_without_profile(self):
        pipeline = Pipeline.__new__(Pipeline)
        result = pipeline._build_style_instruction(None)
        assert result == ""


class TestGetMaterialHint:
    def test_with_material(self):
        pipeline = Pipeline.__new__(Pipeline)
        material = {"golden_sentences": ["金句1", "金句2"], "core_facts": ["事实1"]}
        result = pipeline._get_material_hint(material, 0)
        assert "金句1" in result

    def test_index_out_of_range(self):
        pipeline = Pipeline.__new__(Pipeline)
        material = {"golden_sentences": ["金句1"], "core_facts": ["事实1"]}
        result = pipeline._get_material_hint(material, 5)
        assert result == ""

    def test_no_material(self):
        pipeline = Pipeline.__new__(Pipeline)
        result = pipeline._get_material_hint(None, 0)
        assert result == ""


class TestRegenerateSectionInvalid:
    def test_invalid_index(self):
        pipeline = Pipeline.__new__(Pipeline)
        outline = Outline(sections=[{"title": "s1"}])
        with pytest.raises(ValueError, match="无效的小节索引"):
            pipeline.regenerate_section("topic", outline, 5, "content")


class TestStaticMethods:
    def test_load_article_not_found(self):
        with pytest.raises(FileNotFoundError):
            Pipeline.load_article("nonexistent_id")

    def test_load_style_not_found(self):
        with pytest.raises(FileNotFoundError):
            Pipeline.load_style("nonexistent_style")

    def test_list_articles_empty(self, temp_data_dir):
        result = Pipeline.list_articles()
        assert result == []

    def test_list_styles_empty(self, temp_data_dir):
        result = Pipeline.list_styles()
        assert result == []


class TestArticlePersistence:
    def test_save_and_load_article(self, temp_data_dir, mock_llm, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        from pipeline import Article, ValidationResult
        art = Article(
            id="test_001",
            topic="测试主题",
            platform="wechat",
            status="done",
            content="测试内容",
        )
        pipeline = Pipeline(mock_llm)
        pipeline._save_article(art)

        loaded = Pipeline.load_article("test_001")
        assert loaded["topic"] == "测试主题"
        assert loaded["content"] == "测试内容"

    def test_list_articles_with_data(self, temp_data_dir, mock_llm, monkeypatch):
        monkeypatch.setattr("pipeline.DATA_DIR", temp_data_dir)
        from pipeline import Article
        art1 = Article(id="a001", topic="主题1")
        art2 = Article(id="a002", topic="主题2")
        pipeline = Pipeline(mock_llm)
        pipeline._save_article(art1)
        pipeline._save_article(art2)

        articles = Pipeline.list_articles()
        assert len(articles) == 2
        topics = [a["topic"] for a in articles]
        assert "主题1" in topics
        assert "主题2" in topics
