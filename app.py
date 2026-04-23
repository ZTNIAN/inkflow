"""FastAPI 服务 — 公众号/头条文章生成器"""
from __future__ import annotations
import asyncio, json, os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm import LLM
from pipeline import Pipeline, StyleProfile
from validator import Validator

# ── 初始化 ────────────────────────────────────────────────────────────────────

app = FastAPI(title="Article Writer", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"

def _load_env():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

def _create_llm(temperature: float = 0.7) -> LLM:
    _load_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise HTTPException(400, "请先配置 DEEPSEEK_API_KEY")
    return LLM(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=temperature,
    )

def _pipeline(temperature: float = 0.7) -> Pipeline:
    return Pipeline(_create_llm(temperature))

# ── 请求模型 ──────────────────────────────────────────────────────────────────

class GenerateReq(BaseModel):
    topic: str
    platform: Literal["wechat", "toutiao"] = "wechat"
    mode: Literal["干货型", "争议型", "故事型", "测评型"] = "干货型"
    source_text: str = ""
    style_profile_id: str = ""
    extra_requirements: str = ""

class GenerateOutlineReq(BaseModel):
    topic: str
    platform: Literal["wechat", "toutiao"] = "wechat"
    mode: Literal["干货型", "争议型", "故事型", "测评型"] = "干货型"
    source_text: str = ""
    style_profile_id: str = ""
    extra_requirements: str = ""

class GenerateContentReq(BaseModel):
    outline: dict
    topic: str = ""
    platform: str = "wechat"
    source_text: str = ""
    style_profile_id: str = ""

class GenerateTitlesReq(BaseModel):
    topic: str
    outline_summary: str = ""
    platform: str = "wechat"
    count: int = 10

class UpdateOutlineReq(BaseModel):
    outline: dict

class ExtractStyleReq(BaseModel):
    name: str = "我的风格"

class SaveSettingsReq(BaseModel):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

# ── 页面路由 ──────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "index.html"))

# ── 设置 ──────────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    _load_env()
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return {
        "deepseek_api_key": key[:8] + "***" if key and len(key) > 8 else key,
        "deepseek_base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "deepseek_model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "configured": bool(key),
    }

@app.post("/api/settings")
def save_settings(req: SaveSettingsReq):
    lines = [
        "# Article Writer 配置",
        f"DEEPSEEK_BASE_URL={req.deepseek_base_url}",
        f"DEEPSEEK_MODEL={req.deepseek_model}",
    ]
    if req.deepseek_api_key and not req.deepseek_api_key.endswith("***"):
        lines.append(f"DEEPSEEK_API_KEY={req.deepseek_api_key}")
    else:
        # 保留原值
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DEEPSEEK_API_KEY="):
                    lines.append(line.strip())
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True}

# ── 文章列表 ──────────────────────────────────────────────────────────────────

@app.get("/api/articles")
def list_articles():
    return Pipeline.list_articles()

@app.get("/api/articles/{article_id}")
def get_article(article_id: str):
    try:
        return Pipeline.load_article(article_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

@app.delete("/api/articles/{article_id}")
def delete_article(article_id: str):
    path = BASE_DIR / "data" / "articles" / f"{article_id}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}

# ── 风格管理 ──────────────────────────────────────────────────────────────────

@app.get("/api/styles")
def list_styles():
    return Pipeline.list_styles()

@app.get("/api/styles/{style_id}")
def get_style(style_id: str):
    try:
        profile = Pipeline.load_style(style_id)
        return {
            "id": profile.id, "name": profile.name,
            "tone": profile.tone, "structure_style": profile.structure_style,
            "vocabulary": profile.vocabulary, "sentence_patterns": profile.sentence_patterns,
            "punctuation_habits": profile.punctuation_habits,
            "sample_summary": profile.sample_summary,
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))

@app.delete("/api/styles/{style_id}")
def delete_style(style_id: str):
    path = BASE_DIR / "data" / "styles" / f"{style_id}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}

@app.post("/api/styles/extract")
async def extract_style(
    name: str = Form("我的风格"),
    files: list[UploadFile] = File(...),
):
    """从上传的样本文章中提取写作风格"""
    samples = []
    for f in files[:5]:
        content = await f.read()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk", errors="replace")
        samples.append(text)

    if not samples:
        raise HTTPException(400, "请上传至少 1 个样本文件")

    try:
        profile = await asyncio.to_thread(
            _pipeline(0.3).extract_style, samples, name,
        )
        return {
            "ok": True,
            "profile": {
                "id": profile.id, "name": profile.name,
                "tone": profile.tone, "structure_style": profile.structure_style,
                "vocabulary": profile.vocabulary, "sentence_patterns": profile.sentence_patterns,
                "punctuation_habits": profile.punctuation_habits,
                "sample_summary": profile.sample_summary,
            },
        }
    except Exception as e:
        raise HTTPException(500, f"风格提取失败：{e}")

# ── 素材提取 ──────────────────────────────────────────────────────────────────

class ExtractMaterialReq(BaseModel):
    source_text: str
    topic: str

@app.post("/api/extract-material")
async def extract_material(req: ExtractMaterialReq):
    try:
        material = await asyncio.to_thread(
            _pipeline(0.3).extract_material, req.source_text, req.topic,
        )
        return {"ok": True, "material": material}
    except Exception as e:
        raise HTTPException(500, f"素材提取失败：{e}")

# ── 大纲生成 ──────────────────────────────────────────────────────────────────

@app.post("/api/generate/outline")
async def generate_outline(req: GenerateOutlineReq):
    style = None
    if req.style_profile_id:
        try:
            style = Pipeline.load_style(req.style_profile_id)
        except FileNotFoundError:
            pass

    material = None
    if req.source_text.strip():
        try:
            material = await asyncio.to_thread(
                _pipeline(0.3).extract_material, req.source_text, req.topic,
            )
        except Exception:
            pass

    try:
        outline = await asyncio.to_thread(
            _pipeline(0.8).generate_outline,
            req.topic, req.platform, req.mode, material, style, req.extra_requirements,
        )
        return {
            "ok": True,
            "outline": {
                "title_candidates": outline.title_candidates,
                "selected_title": outline.selected_title,
                "hook": outline.hook,
                "sections": outline.sections,
                "cta": outline.cta,
                "tags": outline.tags,
            },
        }
    except Exception as e:
        raise HTTPException(500, f"大纲生成失败：{e}")

# ── 标题优化 ──────────────────────────────────────────────────────────────────

@app.post("/api/generate/titles")
async def generate_titles(req: GenerateTitlesReq):
    try:
        titles = await asyncio.to_thread(
            _pipeline(0.9).generate_titles,
            req.topic, req.outline_summary, req.platform, req.count,
        )
        return {"ok": True, "titles": titles}
    except Exception as e:
        raise HTTPException(500, f"标题生成失败：{e}")

# ── 正文生成 ──────────────────────────────────────────────────────────────────

@app.post("/api/generate/content")
async def generate_content(req: GenerateContentReq):
    from pipeline import Outline

    outline = Outline(
        title_candidates=req.outline.get("title_candidates", []),
        selected_title=req.outline.get("selected_title", ""),
        hook=req.outline.get("hook", ""),
        sections=req.outline.get("sections", []),
        cta=req.outline.get("cta", ""),
        tags=req.outline.get("tags", []),
    )

    style = None
    if req.style_profile_id:
        try:
            style = Pipeline.load_style(req.style_profile_id)
        except FileNotFoundError:
            pass

    material = None
    if req.source_text.strip():
        try:
            material = await asyncio.to_thread(
                _pipeline(0.3).extract_material, req.source_text, req.topic,
            )
        except Exception:
            pass

    try:
        content = await asyncio.to_thread(
            _pipeline(0.8).generate_content,
            req.topic, outline, req.platform, material, style,
        )
        return {"ok": True, "content": content, "word_count": len(content)}
    except Exception as e:
        raise HTTPException(500, f"正文生成失败：{e}")

# ── 排版 ──────────────────────────────────────────────────────────────────────

class FormatReq(BaseModel):
    content: str
    title: str = ""
    tags: list[str] = []

@app.post("/api/format")
async def format_html(req: FormatReq):
    try:
        html = await asyncio.to_thread(
            _pipeline(0.3).format_html, req.content, req.title, req.tags,
        )
        return {"ok": True, "html": html}
    except Exception as e:
        raise HTTPException(500, f"排版失败：{e}")

# ── 验证 ──────────────────────────────────────────────────────────────────────

class ValidateReq(BaseModel):
    content: str
    platform: str = "wechat"

@app.post("/api/validate")
def validate(req: ValidateReq):
    v = Validator()
    result = v.validate(req.content, req.platform)
    return {
        "passed": result.passed,
        "score": result.score,
        "issues": [{"rule": i.rule, "severity": i.severity,
                     "description": i.description, "excerpt": i.excerpt}
                    for i in result.issues],
    }

# ── 一键生成（完整管线）──

@app.post("/api/generate/full")
async def generate_full(req: GenerateReq):
    style = None
    if req.style_profile_id:
        try:
            style = Pipeline.load_style(req.style_profile_id)
        except FileNotFoundError:
            pass

    def _run():
        return _pipeline(0.8).run_full(
            topic=req.topic,
            platform=req.platform,
            mode=req.mode,
            source_text=req.source_text,
            style_profile=style,
            extra_requirements=req.extra_requirements,
        )

    try:
        article = await asyncio.to_thread(_run)
        from pipeline import _to_dict
        return {"ok": True, "article": _to_dict(article)}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"生成失败：{e}")

# ── 保存/更新文章 ─────────────────────────────────────────────────────────────

class SaveArticleReq(BaseModel):
    id: str = ""
    topic: str = ""
    platform: str = "wechat"
    mode: str = "干货型"
    outline: dict = {}
    content: str = ""
    html: str = ""

@app.post("/api/articles/save")
def save_article(req: SaveArticleReq):
    import uuid
    from datetime import datetime, timezone
    from pipeline import _to_dict

    article_id = req.id or f"art_{uuid.uuid4().hex[:8]}"
    data = {
        "id": article_id,
        "topic": req.topic,
        "platform": req.platform,
        "mode": req.mode,
        "status": "done" if req.content else "outlined",
        "outline": req.outline,
        "content": req.content,
        "html": req.html,
        "word_count": len(req.content),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    art_dir = BASE_DIR / "data" / "articles"
    art_dir.mkdir(parents=True, exist_ok=True)
    path = art_dir / f"{article_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "id": article_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
