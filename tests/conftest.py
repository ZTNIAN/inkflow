import json, os, pytest, tempfile
from pathlib import Path
from typing import Generator
from fastapi.testclient import TestClient
from llm import LLM, Response, Message

SAMPLE_VALID_JSON = json.dumps({
    "title_candidates": ["标题1：为什么你越努力越焦虑", "标题2：三个让你醍醐灌顶的真相", "标题3：我不加班后反而升职了"],
    "hook": "用一个反常识的数据开头：2023年，683万对——这是中国近十年最低的结婚登记数。",
    "sections": [
        {"title": "你被什么困住了", "key_points": ["焦虑的真相", "停下来的力量"], "word_budget": 500, "writing_guide": "用第二人称" },
        {"title": "停下来反而更快", "key_points": ["慢即是快", "复利思维"], "word_budget": 500, "writing_guide": "讲故事" },
    ],
    "cta": "把这篇文章转给还在焦虑的朋友",
    "tags": ["成长", "效率", "认知升级"],
}, ensure_ascii=False)

def _mock_complete(self, messages, temperature=None, max_tokens=None):
    return Response(content=SAMPLE_VALID_JSON)

def _mock_stream(self, messages, temperature=None, max_tokens=None):
    yield "mock stream"

@pytest.fixture(autouse=True)
def no_env_dependency(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-fake-key-12345")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setattr(LLM, "complete", _mock_complete)
    monkeypatch.setattr(LLM, "stream", _mock_stream)
    return LLM(api_key="sk-test", base_url="http://fake", model="test-model")

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from app import app
    with TestClient(app) as c:
        yield c

@pytest.fixture
def temp_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        from pipeline import DATA_DIR as pipeline_data_dir
        monkeypatch.setattr("pipeline.DATA_DIR", data_dir)
        yield data_dir

@pytest.fixture
def sample_content() -> str:
    return """**你被什么困住了**

你有没有想过，为什么你每天忙得脚不沾地，却感觉什么都没做成？

我之前有个同事叫小林，典型的"看起来很努力"型。每天第一个到公司，最后一个走，周末还主动加班。但年底考核，他的绩效是部门倒数。

不是他不够努力，而是他陷入了"无效勤奋"的陷阱。

**停下来，才能跑得更远**

后来小林换了个组。新组长给了他一个匪夷所思的要求：每天下午4点到5点，不准干活，只能思考。

这个要求听起来很荒谬吧？但半年后，小林成了部门晋升最快的人。

道理很简单：大部分人的努力，是在用战术上的勤奋掩盖战略上的懒惰。你花80%的时间做那些"看起来很忙"的事，却只有20%的时间在做真正重要的事。

所以，试着停一下。不会更糟，只会更好。

把这篇文章转给还在焦虑的朋友，问问ta：你是在真努力，还是在假装努力？"""

@pytest.fixture
def sample_outline_dict() -> dict:
    return {
        "title_candidates": ["标题1", "标题2", "标题3"],
        "selected_title": "测试标题",
        "hook": "hook内容",
        "sections": [
            {"title": "第一节", "key_points": ["要点1"], "word_budget": 500, "writing_guide": "指南1"},
            {"title": "第二节", "key_points": ["要点2"], "word_budget": 500, "writing_guide": "指南2"},
        ],
        "cta": "cta内容",
        "tags": ["标签1"],
    }
