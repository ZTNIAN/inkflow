import json, pytest
from llm import parse_json, parse_json_list, _extract_json_text, _fix_smart_quotes, _fix_trailing_commas, _fix_object_as_array, _repair, with_retry
from llm import Response, Message, LLM


class TestExtractJsonText:
    def test_extract_normal(self):
        assert _extract_json_text('{"a":1}') == '{"a":1}'

    def test_extract_markdown_wrapped(self):
        text = '```json\n{"a": 1}\n```'
        assert _extract_json_text(text) == '{"a": 1}'

    def test_extract_with_before_after_text(self):
        text = '前面的话{"a": 1}后面的话'
        assert _extract_json_text(text) == '{"a": 1}'

    def test_extract_array(self):
        text = '前面[1, 2, 3]后面'
        assert _extract_json_text(text) == '[1, 2, 3]'

    def test_extract_no_json(self):
        assert _extract_json_text("纯文本没有JSON") == "纯文本没有JSON"


class TestFixSmartQuotes:
    def test_normal_string_unchanged(self):
        text = '{"key": "value"}'
        assert _fix_smart_quotes(text) == '{"key": "value"}'

    def test_curly_quotes_fixed(self):
        text = '{"key": "\u201cvalue\u201d"}'
        result = _fix_smart_quotes(text)
        assert '"\\"value\\""' in result or '\\"value\\"' in result

    def test_nested_quotes(self):
        text = '{"key": "他说\u201c你好\u201d"}'
        result = _fix_smart_quotes(text)
        assert result is not None

    def test_book_title_marks(self):
        text = '{"key": "\u300a书名\u300b"}'
        result = _fix_smart_quotes(text)
        assert "\\u300a" in result or "\\" in result


class TestFixTrailingCommas:
    def test_trailing_comma_in_object(self):
        text = '{"a": 1, "b": 2,}'
        assert _fix_trailing_commas(text) == '{"a": 1, "b": 2}'

    def test_trailing_comma_in_array(self):
        text = '["a", "b",]'
        assert _fix_trailing_commas(text) == '["a", "b"]'

    def test_no_trailing_comma(self):
        text = '{"a": 1}'
        assert _fix_trailing_commas(text) == '{"a": 1}'


class TestFixObjectAsArray:
    def test_object_with_chinese_keys(self):
        text = '{"title_candidates": {"方案1（爆款型）": "标题内容1", "方案2（共鸣型）": "标题内容2"}}'
        result = _fix_object_as_array(text)
        data = json.loads(result)
        assert isinstance(data["title_candidates"], list)
        assert "标题内容1" in data["title_candidates"]

    def test_normal_object_unchanged(self):
        text = '{"config": {"key1": "value1", "key2": "value2"}}'
        result = _fix_object_as_array(text)
        assert '"config"' in result and '"key1"' in result

    def test_single_item_object(self):
        text = '{"tags": {"一个标签": "标签值"}}'
        result = _fix_object_as_array(text)
        data = json.loads(result)
        assert isinstance(data["tags"], list)


class TestRepair:
    def test_truncated_object(self):
        text = '{"a": 1, "b": 2'
        result = _repair(text)
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_truncated_array(self):
        text = '["a", "b"'
        result = _repair(text)
        assert json.loads(result) == ["a", "b"]

    def test_truncated_nested(self):
        text = '{"a": [1, 2'
        result = _repair(text)
        data = json.loads(result)
        assert data["a"] == [1, 2]

    def test_truncated_trailing_comma(self):
        text = '{"a": 1,'
        result = _repair(text)
        assert json.loads(result) == {"a": 1}


class TestParseJson:
    def test_normal_json(self):
        result = parse_json('{"a": 1, "b": 2}')
        assert result == {"a": 1, "b": 2}

    def test_markdown_wrapped(self):
        result = parse_json('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_smart_quotes(self):
        text = '{"title": "\u201c测试标题\u201d"}'
        result = parse_json(text)
        assert "title" in result

    def test_trailing_comma(self):
        result = parse_json('{"a": 1, "b": 2,}')
        assert result == {"a": 1, "b": 2}

    def test_full_pipeline(self):
        text = '```json\n{"title_candidates": {"方案1": "标题A", "方案2": "标题B"}, "sections": [{"title": "测试", "key_points": ["点1", "点2"], "word_budget": 500, "writing_guide": "指导"}],}\n```'
        result = parse_json(text)
        assert "title_candidates" in result
        assert isinstance(result["sections"], list)

    def test_truncated_object(self):
        raw = '{"title_candidates": ["标题1", "标题2"], "sections": [{"title": "测试", "key_points": ["点1"]'
        result = parse_json(raw)
        assert "title_candidates" in result

    def test_parse_failure(self):
        with pytest.raises(Exception):
            parse_json("完全不是JSON")

    def test_pydantic_validation_error(self):
        with pytest.raises(Exception):
            BadSchema = type("BadSchema", (), {"model_validate": staticmethod(lambda x: (_ for _ in ()).throw(ValueError("bad")))})
            parse_json('{"a": 1}', schema=BadSchema())


class TestParseJsonList:
    def test_normal_array(self):
        result = parse_json_list('[{"a": 1}, {"a": 2}]')
        assert len(result) == 2

    def test_single_object_fallback(self):
        result = parse_json_list('{"a": 1}')
        assert isinstance(result, list)
        assert len(result) == 1

    def test_markdown_wrapped_array(self):
        result = parse_json_list('```json\n[{"a": 1}]\n```')
        assert len(result) == 1

    def test_trailing_comma_array(self):
        result = parse_json_list('[{"a": 1}, {"b": 2},]')
        assert len(result) == 2


class TestWithRetry:
    def test_success_first_try(self):
        assert with_retry(lambda: 42) == 42

    def test_success_after_retry(self):
        calls = [0]
        def fn():
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("try again")
            return 42
        assert with_retry(fn, max_attempts=3, delay=0.01) == 42
        assert calls[0] == 2

    def test_all_fail(self):
        def fn():
            raise ValueError("always fail")
        with pytest.raises(ValueError):
            with_retry(fn, max_attempts=2, delay=0.01)


class TestLLMMock:
    def test_mock_complete(self, mock_llm):
        resp = mock_llm.complete([Message("user", "test")])
        assert isinstance(resp, Response)
        data = json.loads(resp.content)
        assert "title_candidates" in data

    def test_mock_stream(self, mock_llm):
        results = list(mock_llm.stream([Message("user", "test")]))
        assert results == ["mock stream"]
