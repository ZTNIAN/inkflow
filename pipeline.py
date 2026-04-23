"""核心管线 — 公众号/头条文章生成"""
from __future__ import annotations
import json, uuid, re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from llm import LLM, Message, parse_json, parse_json_list, with_retry
from validator import Validator, ValidationResult

DATA_DIR = Path(__file__).parent / "data"


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StyleProfile:
    """从用户样本文章中提取的风格特征"""
    id: str = ""
    name: str = ""
    sentence_patterns: list[str] = field(default_factory=list)   # 句式特征
    vocabulary: list[str] = field(default_factory=list)          # 惯用词汇
    punctuation_habits: str = ""                                 # 标点习惯
    tone: str = ""                                               # 整体语调
    structure_style: str = ""                                    # 结构风格
    sample_summary: str = ""                                     # 样本摘要
    raw_profile: str = ""                                        # 完整分析文本


@dataclass
class Outline:
    """文章大纲"""
    title_candidates: list[str] = field(default_factory=list)
    selected_title: str = ""
    hook: str = ""                    # 开头钩子
    sections: list[dict] = field(default_factory=list)  # [{title, key_points, word_budget}]
    cta: str = ""                     # 结尾行动号召
    tags: list[str] = field(default_factory=list)


@dataclass
class Article:
    """完整文章"""
    id: str = ""
    topic: str = ""
    platform: str = "wechat"          # wechat | toutiao
    mode: str = "干货型"              # 干货型 | 争议型 | 故事型 | 测评型
    status: str = "draft"             # draft | outlined | writing | done
    outline: Outline = field(default_factory=Outline)
    content: str = ""
    html: str = ""
    style_profile_id: str = ""
    source_text: str = ""             # 对标素材
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(True))
    created_at: str = ""
    word_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 管线
# ═══════════════════════════════════════════════════════════════════════════════

class Pipeline:

    def __init__(self, llm: LLM, validator: Validator | None = None):
        self.llm = llm
        self.validator = validator or Validator()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 0: 风格提取（从样本文章克隆用户写作风格）
    # ─────────────────────────────────────────────────────────────────────────

    def extract_style(self, samples: list[str], name: str = "我的风格") -> StyleProfile:
        combined = "\n\n---\n\n".join(s[:3000] for s in samples[:5])

        prompt = f"""你是一位资深的写作教练。请分析以下 {len(samples)} 篇文章样本，提取作者的写作风格特征。

## 样本文章
{combined}

请输出 JSON：
{{
  "sentence_patterns": ["句式特征1", "句式特征2", ...],
  "vocabulary": ["惯用词1", "惯用词2", ...],
  "punctuation_habits": "标点使用习惯描述",
  "tone": "整体语调描述（如：犀利理性、温暖治愈、幽默毒舌）",
  "structure_style": "结构风格描述（如：总分总、故事开头+金句结尾）",
  "sample_summary": "200字以内的风格总结"
}}

要求：
1. 从实际文本中提取，不要臆测
2. vocabulary 至少列出 10 个高频词
3. sentence_patterns 列出 3-5 个典型的句式模式"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是写作风格分析师，只输出合法 JSON。"),
            Message("user", prompt),
        ], temperature=0.3))

        data = parse_json(resp.content)
        profile = StyleProfile(
            id=f"style_{uuid.uuid4().hex[:8]}",
            name=name,
            sentence_patterns=data.get("sentence_patterns", []),
            vocabulary=data.get("vocabulary", []),
            punctuation_habits=data.get("punctuation_habits", ""),
            tone=data.get("tone", ""),
            structure_style=data.get("structure_style", ""),
            sample_summary=data.get("sample_summary", ""),
            raw_profile=json.dumps(data, ensure_ascii=False, indent=2),
        )

        # 保存到文件
        style_dir = DATA_DIR / "styles"
        style_dir.mkdir(parents=True, exist_ok=True)
        path = style_dir / f"{profile.id}.json"
        path.write_text(json.dumps(_to_dict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: 素材清洗（从对标文章/参考资料中提取核心信息）
    # ─────────────────────────────────────────────────────────────────────────

    def extract_material(self, source_text: str, topic: str) -> dict:
        """从对标素材中提取核心事实、观点、金句"""
        text = source_text[:8000]  # 截断防超 token

        prompt = f"""你是一位新媒体内容分析师。请从以下素材中提取可用于写作的核心信息。

## 主题方向
{topic}

## 素材内容
{text}

请输出 JSON：
{{
  "core_facts": ["核心事实1", "核心事实2", ...],
  "key_opinions": ["关键观点1", "关键观点2", ...],
  "golden_sentences": ["金句1", "金句2", ...],
  "data_points": ["数据/案例1", "数据/案例2", ...],
  "controversial_angles": ["争议角度1", "争议角度2", ...],
  "hook_ideas": ["开头钩子创意1", "创意2", ...]
}}

要求：
1. 只提取素材中确实存在的信息，不要编造
2. 金句保留原文，不要改写
3. 争议角度是从素材中能推导出的不同立场"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是新媒体内容分析师，擅长提炼素材中的核心信息。只输出合法 JSON。"),
            Message("user", prompt),
        ], temperature=0.3))

        return parse_json(resp.content)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: 大纲生成（人机共创 — 返回候选，用户选择/修改后再继续）
    # ─────────────────────────────────────────────────────────────────────────

    def generate_outline(
        self,
        topic: str,
        platform: str = "wechat",
        mode: str = "干货型",
        material: dict | None = None,
        style_profile: StyleProfile | None = None,
        extra_requirements: str = "",
    ) -> Outline:
        """生成文章大纲 + 多个标题候选"""

        platform_desc = {
            "wechat": "公众号（社交分发，读者注重深度、共鸣、排版留白，1500-3000字）",
            "toutiao": "头条（算法推荐，读者注重信息增量、争议点、接地气，800-2000字）",
        }[platform]

        mode_desc = {
            "干货型": "提供实用方法论、步骤清单、工具推荐，读者看完能直接用",
            "争议型": "抛出反常识观点、制造对立、引发讨论，核心是「信息增量+情绪触发」",
            "故事型": "用真实案例/个人经历切入，以小见大，核心是「情感共鸣+认知升级」",
            "测评型": "对比分析、数据说话、给出明确推荐，核心是「帮读者做决策」",
        }[mode]

        material_section = ""
        if material:
            facts = "\n".join(f"  - {f}" for f in material.get("core_facts", [])[:5])
            opinions = "\n".join(f"  - {o}" for o in material.get("key_opinions", [])[:5])
            gold = "\n".join(f"  - {g}" for g in material.get("golden_sentences", [])[:5])
            data = "\n".join(f"  - {d}" for d in material.get("data_points", [])[:5])
            material_section = f"""
## 可用素材（从对标文章提取）
### 核心事实
{facts}
### 关键观点
{opinions}
### 金句（可直接引用）
{gold}
### 数据/案例
{data}
"""

        style_section = ""
        if style_profile:
            style_section = f"""
## 写作风格要求（必须严格遵循）
- 语调：{style_profile.tone}
- 结构风格：{style_profile.structure_style}
- 惯用词汇：{'、'.join(style_profile.vocabulary[:15])}
- 句式特征：{'；'.join(style_profile.sentence_patterns[:5])}
- 标点习惯：{style_profile.punctuation_habits}
"""

        word_target = "1500-3000" if platform == "wechat" else "800-2000"
        section_count = "4-6" if platform == "wechat" else "3-5"

        prompt = f"""你是一位顶尖的新媒体内容策划师。请为以下主题生成文章大纲。

## 主题
{topic}

## 平台
{platform_desc}

## 文章类型
{mode_desc}

## 字数目标
{word_target} 字
{material_section}{style_section}
{f'## 额外要求{chr(10)}{extra_requirements}' if extra_requirements else ''}

请输出 JSON：
{{
  "title_candidates": [
    "标题方案1（爆款型，带数字/悬念）",
    "标题方案2（共鸣型，击中痛点）",
    "标题方案3（反常识型，制造好奇）",
    "标题方案4（实用型，明确价值）",
    "标题方案5（情感型，引发转发）"
  ],
  "hook": "开头前3句的内容设计（必须在10秒内抓住读者，说明具体怎么写）",
  "sections": [
    {{
      "title": "小节标题",
      "key_points": ["要点1", "要点2"],
      "word_budget": 500,
      "writing_guide": "本节写作指导（语气、角度、注意事项）"
    }}
  ],
  "cta": "结尾行动号召的设计（引导点赞/转发/评论/关注的具体话术）",
  "tags": ["标签1", "标签2", "标签3"]
}}

要求：
1. 标题候选必须风格各异，覆盖不同吸引策略
2. sections 数量 {section_count} 个，每个 section 的 word_budget 总和 ≈ {word_target} 字
3. hook 必须具体到「怎么写」，不要只说「用一个故事开头」
4. 整体结构要有节奏感：紧→松→紧，或低→高→更高"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是顶尖新媒体内容策划师，擅长设计爆款文章结构。只输出合法 JSON。"),
            Message("user", prompt),
        ], temperature=0.8))

        data = parse_json(resp.content)

        titles = data.get("title_candidates", [])
        # 清理标题：去掉"标题方案1（爆款型）："这种前缀
        cleaned = []
        for t in titles:
            t = re.sub(r'^标题方案\d+[（(][^）)]*[）)][:：]?\s*', '', t)
            t = re.sub(r'^\d+[.、]\s*', '', t)
            cleaned.append(t.strip() if t.strip() else t)
        titles = cleaned
        # 确保有 5 个标题
        while len(titles) < 5:
            titles.append(f"关于{topic}的第{len(titles)+1}个角度")

        return Outline(
            title_candidates=titles,
            selected_title=titles[0] if titles else topic,
            hook=data.get("hook", ""),
            sections=data.get("sections", []),
            cta=data.get("cta", ""),
            tags=data.get("tags", []),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: 标题优化（单独生成更多标题候选 + 评分）
    # ─────────────────────────────────────────────────────────────────────────

    def generate_titles(self, topic: str, outline_summary: str,
                        platform: str = "wechat", count: int = 10) -> list[dict]:
        """生成标题候选并评分"""

        prompt = f"""为以下主题的{platform}文章生成 {count} 个标题候选，并为每个标题评分。

## 主题
{topic}

## 大纲摘要
{outline_summary[:500]}

请输出 JSON 数组：
[
  {{
    "title": "标题文本",
    "style": "爆款型/共鸣型/反常识型/实用型/情感型/悬念型",
    "score": 85,
    "reason": "评分理由（一句话）"
  }}
]

评分标准（0-100）：
- 点击欲望（40分）：是否让人忍不住想点？
- 信息增量（30分）：是否暗示了「看完能得到什么」？
- 平台适配（30分）：是否符合{platform}的阅读场景？"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是标题优化专家，只输出合法 JSON 数组。"),
            Message("user", prompt),
        ], temperature=0.9))

        return parse_json_list(resp.content)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: 正文生成（分块 + 全局上下文视窗）
    # ─────────────────────────────────────────────────────────────────────────

    def generate_content(
        self,
        topic: str,
        outline: Outline,
        platform: str = "wechat",
        material: dict | None = None,
        style_profile: StyleProfile | None = None,
    ) -> str:
        """分块生成正文，带上下文衔接"""

        title = outline.selected_title or outline.title_candidates[0]
        all_sections = outline.sections
        chunks: list[str] = []

        style_instruction = ""
        if style_profile:
            style_instruction = f"""
## 写作风格（必须严格模仿）
- 语调：{style_profile.tone}
- 惯用词：{'、'.join(style_profile.vocabulary[:10])}
- 句式：{'；'.join(style_profile.sentence_patterns[:3])}
- 标点：{style_profile.punctuation_habits}
"""

        # ── 开头 ──
        print(f"  [1/{len(all_sections)+2}] 生成开头...")
        hook_prompt = f"""你是一位顶尖的{platform}写手。请为以下文章写一个抓人的开头。

## 标题
{title}

## 开头设计
{outline.hook}

## 主题
{topic}
{style_instruction}
## 要求
- 直接进入，不要"今天我们来聊聊"这种废话
- 开头3句内必须让读者产生「这篇文章跟我有关」的感觉
- 字数 150-300 字
- 只输出正文，不要任何标注"""

        resp = self.llm.complete([
            Message("system", f"你是{platform}爆款写手，文笔流畅，开头必抓人。直接输出正文。"),
            Message("user", hook_prompt),
        ], temperature=0.8)
        chunks.append(resp.content.strip())

        # ── 各小节 ──
        for i, section in enumerate(all_sections):
            print(f"  [{i+2}/{len(all_sections)+2}] 生成「{section.get('title', '')}」...")
            prev_tail = chunks[-1][-200:] if chunks else ""

            material_hint = ""
            if material:
                gold = material.get("golden_sentences", [])
                facts = material.get("core_facts", [])
                relevant = (gold[i] if i < len(gold) else "") or (facts[i] if i < len(facts) else "")
                if relevant:
                    material_hint = f"\n本节可用素材：{relevant}"

            section_prompt = f"""继续写文章的下一部分。

## 标题
{title}

## 当前小节
标题：{section.get('title', '')}
要点：{'；'.join(section.get('key_points', []))}
字数预算：约 {section.get('word_budget', 500)} 字
写作指导：{section.get('writing_guide', '')}

## 上文结尾（必须平滑衔接）
...{prev_tail}

## 全文大纲（了解全局位置）
{' → '.join(s.get('title', '') for s in all_sections)}
{material_hint}
{style_instruction}
## 要求
- 承接上文语气，不要突兀跳转
- 本节标题用加粗显示（**标题**）
- 只输出正文，不要任何标注"""

            resp = self.llm.complete([
                Message("system", f"你是{platform}写手，擅长让段落之间自然过渡。直接输出正文。"),
                Message("user", section_prompt),
            ], temperature=0.8)
            chunks.append(resp.content.strip())

        # ── 结尾 + CTA ──
        print(f"  [{len(all_sections)+2}/{len(all_sections)+2}] 生成结尾...")
        prev_tail = chunks[-1][-200:] if chunks else ""

        ending_prompt = f"""写文章的结尾部分。

## 标题
{title}

## 结尾设计
{outline.cta}

## 上文结尾
...{prev_tail}

## 标签
{' '.join('#' + t for t in outline.tags)}
{style_instruction}
## 要求
- 总结全文核心观点（1-2句）
- 自然引导互动（点赞/转发/评论），不要生硬
- 字数 100-200 字
- 只输出正文，不要任何标注"""

        resp = self.llm.complete([
            Message("system", f"你是{platform}写手，擅长写出让人想转发的结尾。直接输出正文。"),
            Message("user", ending_prompt),
        ], temperature=0.8)
        chunks.append(resp.content.strip())

        return "\n\n".join(chunks)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: 排版输出（生成适配公众号编辑器的 HTML）
    # ─────────────────────────────────────────────────────────────────────────

    def format_html(self, content: str, title: str, tags: list[str]) -> str:
        """将 Markdown 正文转为公众号适配的 HTML 片段"""

        prompt = f"""将以下文章正文转换为微信公众号编辑器兼容的 HTML 片段。

## 标题
{title}

## 正文
{content}

## 标签
{', '.join(tags)}

## 转换规则
1. 段落用 <p style="margin:16px 0;line-height:1.8;font-size:15px;color:#333;"> 包裹
2. 加粗文本用 <strong style="color:#1a1a1a;"> 包裹
3. 小节标题用 <h3 style="margin:24px 0 12px;font-size:17px;font-weight:bold;color:#1a1a1a;"> 包裹
4. 段落之间留白（margin）确保手机阅读舒适
5. 重要金句可以用 <blockquote style="border-left:3px solid #e74c3c;padding:8px 16px;margin:16px 0;background:#f9f9f9;color:#555;font-size:14px;"> 包裹
6. 最后加上标签区域
7. 只输出 HTML 片段，不要 <html><body> 等外层标签"""

        resp = self.llm.complete([
            Message("system", "你是公众号排版专家，只输出 HTML 片段，不要任何说明。"),
            Message("user", prompt),
        ], temperature=0.3)

        return resp.content.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # 完整流程（一键走完，用于测试）
    # ─────────────────────────────────────────────────────────────────────────

    def run_full(
        self,
        topic: str,
        platform: str = "wechat",
        mode: str = "干货型",
        source_text: str = "",
        style_profile: StyleProfile | None = None,
        extra_requirements: str = "",
    ) -> Article:
        """完整管线：素材→大纲→正文→验证→排版"""

        article_id = f"art_{uuid.uuid4().hex[:8]}"
        print(f"\n{'='*60}")
        print(f"📝 开始生成：{topic}")
        print(f"   平台：{platform} | 类型：{mode}")
        print(f"{'='*60}")

        # Step 1: 素材清洗
        material = None
        if source_text.strip():
            print("\n🔍 Step 1: 提取素材...")
            material = self.extract_material(source_text, topic)
            print(f"   提取到 {len(material.get('core_facts', []))} 个事实, "
                  f"{len(material.get('golden_sentences', []))} 条金句")

        # Step 2: 大纲生成
        print("\n📋 Step 2: 生成大纲...")
        outline = self.generate_outline(
            topic=topic, platform=platform, mode=mode,
            material=material, style_profile=style_profile,
            extra_requirements=extra_requirements,
        )
        print(f"   标题：{outline.selected_title}")
        print(f"   结构：{' → '.join(s.get('title', '') for s in outline.sections)}")

        # Step 3: 正文生成
        print("\n✍️  Step 3: 分块生成正文...")
        content = self.generate_content(
            topic=topic, outline=outline, platform=platform,
            material=material, style_profile=style_profile,
        )
        word_count = len(content)
        print(f"   生成完成：{word_count} 字")

        # Step 4: 写后验证
        print("\n🔍 Step 4: 写后验证...")
        validation = self.validator.validate(content, platform)
        print(f"   得分：{validation.score}/100 | "
              f"{'✅ 通过' if validation.passed else '⚠️ 有问题'}")
        if validation.issues:
            for issue in validation.issues[:5]:
                print(f"   [{issue.severity}] {issue.description}")

        # Step 5: 排版
        print("\n📐 Step 5: 生成排版...")
        html = self.format_html(content, outline.selected_title, outline.tags)

        article = Article(
            id=article_id,
            topic=topic,
            platform=platform,
            mode=mode,
            status="done",
            outline=outline,
            content=content,
            html=html,
            style_profile_id=style_profile.id if style_profile else "",
            source_text=source_text[:2000] if source_text else "",
            validation=validation,
            created_at=datetime.now(timezone.utc).isoformat(),
            word_count=word_count,
        )

        # 保存
        self._save_article(article)

        print(f"\n{'='*60}")
        print(f"✅ 完成！文章 ID: {article_id}")
        print(f"   字数: {word_count} | 验证得分: {validation.score}/100")
        print(f"{'='*60}\n")

        return article

    # ─────────────────────────────────────────────────────────────────────────
    # 持久化
    # ─────────────────────────────────────────────────────────────────────────

    def _save_article(self, article: Article):
        art_dir = DATA_DIR / "articles"
        art_dir.mkdir(parents=True, exist_ok=True)
        path = art_dir / f"{article.id}.json"
        path.write_text(json.dumps(_to_dict(article), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def load_article(article_id: str) -> dict:
        path = DATA_DIR / "articles" / f"{article_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"文章不存在：{article_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def list_articles() -> list[dict]:
        art_dir = DATA_DIR / "articles"
        if not art_dir.exists():
            return []
        articles = []
        for f in sorted(art_dir.glob("*.json"), reverse=True):
            data = json.loads(f.read_text(encoding="utf-8"))
            articles.append({
                "id": data.get("id"),
                "topic": data.get("topic"),
                "platform": data.get("platform"),
                "mode": data.get("mode"),
                "status": data.get("status"),
                "word_count": data.get("word_count"),
                "score": data.get("validation", {}).get("score"),
                "title": data.get("outline", {}).get("selected_title"),
                "created_at": data.get("created_at"),
            })
        return articles

    @staticmethod
    def list_styles() -> list[dict]:
        style_dir = DATA_DIR / "styles"
        if not style_dir.exists():
            return []
        styles = []
        for f in sorted(style_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            styles.append({
                "id": data.get("id"),
                "name": data.get("name"),
                "tone": data.get("tone"),
                "sample_summary": data.get("sample_summary"),
            })
        return styles

    @staticmethod
    def load_style(style_id: str) -> StyleProfile:
        path = DATA_DIR / "styles" / f"{style_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"风格不存在：{style_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return StyleProfile(**{k: v for k, v in data.items() if k in StyleProfile.__dataclass_fields__})


# ── 工具函数 ──

def _to_dict(obj):
    """递归 dataclass → dict"""
    if hasattr(obj, '__dataclass_fields__'):
        return {k: _to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj
