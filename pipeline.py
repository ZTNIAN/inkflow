"""核心管线 — 公众号/头条文章生成 v3（参考链接抓取+图片建议+批量生成+排版模板）"""
from __future__ import annotations
import json, uuid, re, html2text
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from typing import Generator

from llm import LLM, Message, parse_json, parse_json_list, with_retry
from validator import Validator, ValidationResult

DATA_DIR = Path(__file__).parent / "data"


# ═══════════════════════════════════════════════════════════════════════════════
# 排版模板
# ═══════════════════════════════════════════════════════════════════════════════

FORMAT_TEMPLATES = {
    "minimal": {
        "name": "简约白",
        "desc": "干净清爽，适合干货/知识类",
        "p_style": "margin:16px 0;line-height:1.8;font-size:15px;color:#333;",
        "h3_style": "margin:24px 0 12px;font-size:17px;font-weight:bold;color:#1a1a1a;",
        "strong_style": "color:#1a1a1a;",
        "quote_style": "border-left:3px solid #e74c3c;padding:8px 16px;margin:16px 0;background:#f9f9f9;color:#555;font-size:14px;",
        "tag_style": "display:inline-block;padding:2px 8px;margin:2px 4px;background:#f0f0f0;color:#666;border-radius:3px;font-size:12px;",
    },
    "vibrant": {
        "name": "活泼彩",
        "desc": "色彩丰富，适合情感/故事类",
        "p_style": "margin:16px 0;line-height:1.8;font-size:15px;color:#333;",
        "h3_style": "margin:24px 0 12px;font-size:18px;font-weight:bold;color:#e74c3c;",
        "strong_style": "color:#e74c3c;",
        "quote_style": "border-left:3px solid #f39c12;padding:10px 16px;margin:16px 0;background:#fef9e7;color:#7d6608;font-size:14px;border-radius:0 8px 8px 0;",
        "tag_style": "display:inline-block;padding:3px 10px;margin:2px 4px;background:#fdebd0;color:#e67e22;border-radius:12px;font-size:12px;",
    },
    "business": {
        "name": "商务灰",
        "desc": "专业稳重，适合商业/测评类",
        "p_style": "margin:16px 0;line-height:1.8;font-size:15px;color:#2c3e50;",
        "h3_style": "margin:24px 0 12px;font-size:17px;font-weight:bold;color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:6px;",
        "strong_style": "color:#2c3e50;",
        "quote_style": "border-left:3px solid #3498db;padding:10px 16px;margin:16px 0;background:#ebf5fb;color:#5d6d7e;font-size:14px;",
        "tag_style": "display:inline-block;padding:3px 10px;margin:2px 4px;background:#ebf5fb;color:#3498db;border-radius:4px;font-size:12px;font-weight:500;",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 文章结构模板
# ═══════════════════════════════════════════════════════════════════════════════

ARTICLE_TEMPLATES = {
    "listicle": {
        "name": "清单体",
        "desc": "N个方法/技巧/建议，结构清晰，完读率高",
        "mode": "干货型",
        "outline_hint": "围绕一个核心主题，列出 3-7 个具体方法/技巧/建议，每个方法独立成节，带案例或数据支撑",
        "section_guide": "每节：标题→痛点→方法→案例→小结",
    },
    "comparison": {
        "name": "对比测评",
        "desc": "A vs B，帮读者做决策",
        "mode": "测评型",
        "outline_hint": "选取两个或多个对象进行对比，从多个维度分析优劣，给出明确推荐",
        "section_guide": "每节：维度→A的表现→B的表现→结论",
    },
    "story": {
        "name": "情感故事",
        "desc": "真实案例切入，以小见大",
        "mode": "故事型",
        "outline_hint": "用一个真实或虚构的故事开头，引出核心观点，通过多个案例层层递进，结尾升华主题",
        "section_guide": "每节：场景→冲突→转折→启示",
    },
    "hot_take": {
        "name": "争议观点",
        "desc": "反常识，引发讨论和传播",
        "mode": "争议型",
        "outline_hint": "抛出一个反常识的核心观点，用 3-5 个论据支撑，预判反驳并回应，结尾引导讨论",
        "section_guide": "每节：论点→论据→案例→反驳预判",
    },
    "tutorial": {
        "name": "教程指南",
        "desc": "手把手教，步骤明确",
        "mode": "干货型",
        "outline_hint": "针对一个具体问题，给出完整的解决方案，按步骤拆解，每步配图或案例",
        "section_guide": "每节：步骤编号→具体操作→注意事项→常见错误",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StyleProfile:
    id: str = ""
    name: str = ""
    sentence_patterns: list[str] = field(default_factory=list)
    vocabulary: list[str] = field(default_factory=list)
    punctuation_habits: str = ""
    tone: str = ""
    structure_style: str = ""
    sample_summary: str = ""
    raw_profile: str = ""


@dataclass
class Outline:
    title_candidates: list[str] = field(default_factory=list)
    selected_title: str = ""
    hook: str = ""
    sections: list[dict] = field(default_factory=list)
    cta: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class RevisionRecord:
    instruction: str = ""
    section_title: str = ""
    before: str = ""
    after: str = ""
    timestamp: str = ""


@dataclass
class Article:
    id: str = ""
    topic: str = ""
    platform: str = "wechat"
    mode: str = "干货型"
    status: str = "draft"
    outline: Outline = field(default_factory=Outline)
    content: str = ""
    html: str = ""
    style_profile_id: str = ""
    source_text: str = ""
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(True))
    created_at: str = ""
    word_count: int = 0
    revision_history: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 管线
# ═══════════════════════════════════════════════════════════════════════════════

class Pipeline:

    def __init__(self, llm: LLM, validator: Validator | None = None):
        self.llm = llm
        self.validator = validator or Validator()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 0: 风格提取
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

        style_dir = DATA_DIR / "styles"
        style_dir.mkdir(parents=True, exist_ok=True)
        path = style_dir / f"{profile.id}.json"
        path.write_text(json.dumps(_to_dict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: 素材清洗
    # ─────────────────────────────────────────────────────────────────────────

    def extract_material(self, source_text: str, topic: str) -> dict:
        text = source_text[:8000]

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
    # Step 2: 大纲生成
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

## 叙事弧线要求（核心）
爆款文章不是信息罗列，而是「带节奏」。你的大纲必须包含这条情绪曲线：
1. **钩子（开头）**：用一个反常识的数据/场景/提问制造「停顿感」，让读者产生「这跟我有关」的感觉
2. **痛点放大（前半段）**：把读者模糊的焦虑具象化，用案例和数据让他们点头——"对，就是这样"
3. **转折/方案（中段）**：给出读者没想到的角度或解决方案，制造「原来如此」的顿悟感
4. **实操落地（后半段）**：具体的工具/步骤/清单，让读者觉得「看完就能用」
5. **情绪收尾（结尾）**：用金句或开放性问题收尾，制造转发欲

请严格按以下 JSON 格式输出（注意：title_candidates 必须是字符串数组，不是对象）：

JSON 格式示例：
{{
  "title_candidates": ["标题文本1", "标题文本2", "标题文本3", "标题文本4", "标题文本5"],
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
1. title_candidates 是字符串数组，每个元素就是一个完整的标题文本，不要加"标题方案1"之类的前缀
2. 标题必须风格各异，覆盖不同吸引策略：爆款型（带数字/悬念）、共鸣型（击中痛点）、反常识型（制造好奇）、实用型（明确价值）、情感型（引发转发）
3. sections 数量 {section_count} 个，每个 section 的 word_budget 总和 ≈ {word_target} 字
4. hook 必须具体到「怎么写」，不要只说「用一个故事开头」
5. 整体结构要有节奏感：紧→松→紧，或低→高→更高
6. 每个 section 的 writing_guide 必须说明「这个位置读者应该有什么情绪」"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是顶尖新媒体内容策划师，擅长设计爆款文章结构。只输出合法 JSON，title_candidates 必须是字符串数组。"),
            Message("user", prompt),
        ], temperature=0.8))

        data = parse_json(resp.content)

        titles = data.get("title_candidates", [])
        # 清理标题：去掉可能残留的前缀
        cleaned = []
        for t in titles:
            if not isinstance(t, str):
                t = str(t)
            t = re.sub(r'^标题方案\d+[（(][^）)]*[）)][:：]?\s*', '', t)
            t = re.sub(r'^\d+[.、]\s*', '', t)
            cleaned.append(t.strip() if t.strip() else t)
        titles = cleaned
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
    # Step 3: 标题优化
    # ─────────────────────────────────────────────────────────────────────────

    def generate_titles(self, topic: str, outline_summary: str,
                        platform: str = "wechat", count: int = 10) -> list[dict]:
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
    # Step 4: 正文生成（普通模式）
    # ─────────────────────────────────────────────────────────────────────────

    def generate_content(
        self,
        topic: str,
        outline: Outline,
        platform: str = "wechat",
        material: dict | None = None,
        style_profile: StyleProfile | None = None,
    ) -> str:
        title = outline.selected_title or outline.title_candidates[0]
        all_sections = outline.sections
        chunks: list[str] = []

        style_instruction = self._build_style_instruction(style_profile)

        # 开头
        print(f"  [1/{len(all_sections)+2}] 生成开头...")
        chunks.append(self._generate_hook(topic, title, outline.hook, platform, style_instruction))

        # 各小节
        for i, section in enumerate(all_sections):
            print(f"  [{i+2}/{len(all_sections)+2}] 生成「{section.get('title', '')}」...")
            prev_tail = chunks[-1][-200:] if chunks else ""
            material_hint = self._get_material_hint(material, i)
            chunks.append(self._generate_section(
                topic, title, section, prev_tail, all_sections,
                platform, style_instruction, material_hint
            ))

        # 结尾
        print(f"  [{len(all_sections)+2}/{len(all_sections)+2}] 生成结尾...")
        prev_tail = chunks[-1][-200:] if chunks else ""
        chunks.append(self._generate_ending(topic, title, outline.cta, outline.tags, prev_tail, platform, style_instruction))

        return "\n\n".join(chunks)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4b: 正文生成（流式模式 — 通过 SSE 推送进度）
    # ─────────────────────────────────────────────────────────────────────────

    def generate_content_stream(
        self,
        topic: str,
        outline: Outline,
        platform: str = "wechat",
        material: dict | None = None,
        style_profile: StyleProfile | None = None,
    ) -> Generator[dict, None, None]:
        """流式生成正文，yield 进度事件供 SSE 推送"""
        title = outline.selected_title or outline.title_candidates[0]
        all_sections = outline.sections
        chunks: list[str] = []

        style_instruction = self._build_style_instruction(style_profile)

        # 开头
        yield {"type": "progress", "step": 1, "total": len(all_sections)+2, "label": "生成开头..."}
        hook_text = self._generate_hook(topic, title, outline.hook, platform, style_instruction)
        chunks.append(hook_text)
        yield {"type": "chunk", "index": 0, "content": hook_text}

        # 各小节
        for i, section in enumerate(all_sections):
            yield {"type": "progress", "step": i+2, "total": len(all_sections)+2,
                   "label": f"生成「{section.get('title', '')}」..."}
            prev_tail = chunks[-1][-200:] if chunks else ""
            material_hint = self._get_material_hint(material, i)
            sec_text = self._generate_section(
                topic, title, section, prev_tail, all_sections,
                platform, style_instruction, material_hint
            )
            chunks.append(sec_text)
            yield {"type": "chunk", "index": i+1, "content": sec_text}

        # 结尾
        yield {"type": "progress", "step": len(all_sections)+2, "total": len(all_sections)+2,
               "label": "生成结尾..."}
        prev_tail = chunks[-1][-200:] if chunks else ""
        end_text = self._generate_ending(topic, title, outline.cta, outline.tags, prev_tail, platform, style_instruction)
        chunks.append(end_text)
        yield {"type": "chunk", "index": len(all_sections)+1, "content": end_text}

        # 完成
        full_content = "\n\n".join(chunks)
        validation = self.validator.validate(full_content, platform)
        yield {"type": "done", "content": full_content, "word_count": len(full_content),
               "score": validation.score, "passed": validation.passed,
               "issue_count": len(validation.issues)}

    # ─────────────────────────────────────────────────────────────────────────
    # 内部方法：构建风格指令
    # ─────────────────────────────────────────────────────────────────────────

    def _build_style_instruction(self, style_profile: StyleProfile | None) -> str:
        if not style_profile:
            return ""
        return f"""
## 写作风格（必须严格模仿）
- 语调：{style_profile.tone}
- 惯用词：{'、'.join(style_profile.vocabulary[:10])}
- 句式：{'；'.join(style_profile.sentence_patterns[:3])}
- 标点：{style_profile.punctuation_habits}
"""

    def _get_material_hint(self, material: dict | None, index: int) -> str:
        if not material:
            return ""
        gold = material.get("golden_sentences", [])
        facts = material.get("core_facts", [])
        relevant = (gold[index] if index < len(gold) else "") or (facts[index] if index < len(facts) else "")
        if relevant:
            return f"\n本节可用素材：{relevant}"
        return ""

    def _generate_hook(self, topic: str, title: str, hook_design: str,
                       platform: str, style_instruction: str) -> str:
        prompt = f"""你是一位顶尖的{platform}写手，粉丝50万+，以「说人话」著称。请为以下文章写一个抓人的开头。

## 标题
{title}

## 开头设计方向
{hook_design}

## 主题
{topic}
{style_instruction}
## 写作要求（这是爆款文章，不是公文）
1. 用「你」开头或第二人称视角，像跟朋友聊天一样
2. 第一句话就要制造「停顿感」——可以是反常识的数据、一个扎心的提问、或一个让人共鸣的场景
3. 禁止使用以下开头套路：
   - "今天我们来聊聊..." / "在这个时代..." / "随着...的发展"
   - "你有没有想过..."（太老套）
   - 任何以"首先"、"其次"开头的句子
4. 好的开头示例：
   - 直接甩一个反常识的数据："2023年，683万对——这是中国近十年最低的结婚登记数。"
   - 用一个具体场景切入："上周五，我妈第27次在饭桌上问我：你到底什么时候结婚？我放下筷子，说了句让她沉默的话。"
   - 抛一个尖锐的问题："如果结婚是一笔投资，年化收益是多少？"
5. 字数 150-300 字，只输出正文，不要任何标注或解释"""

        resp = self.llm.complete([
            Message("system", f"你是一位{platform}爆款写手，50万粉丝，风格犀利、真诚、接地气。你写的东西不像AI，像一个有阅历的朋友在跟你掏心窝子。直接输出正文，不要任何标注。"),
            Message("user", prompt),
        ], temperature=0.85)
        return resp.content.strip()

    def _generate_section(self, topic: str, title: str, section: dict,
                          prev_tail: str, all_sections: list, platform: str,
                          style_instruction: str, material_hint: str) -> str:
        prompt = f"""继续写文章的下一部分。你是一位有50万粉丝的{platform}写手，风格真诚、接地气、有观点。

## 标题
{title}

## 当前小节
标题：{section.get('title', '')}
要点：{'；'.join(section.get('key_points', []))}
字数预算：约 {section.get('word_budget', 500)} 字（严格控制，不要超出太多）
写作指导：{section.get('writing_guide', '')}

## 上文结尾（必须平滑衔接）
...{prev_tail}

## 全文大纲（了解全局位置）
{' → '.join(s.get('title', '') for s in all_sections)}
{material_hint}
{style_instruction}
## 写作要求（爆款标准，不是写报告）
1. 像朋友聊天一样写，用「你」称呼读者，偶尔用「我」带入自己的视角
2. 每个观点必须配一个具体的案例或数据——不要泛泛而谈
3. 案例要「不完美」才真实——不要每个案例都刚好切中论点。可以用"我朋友小X，情况其实挺复杂的"、"这个方法不一定适合所有人"、"说实话我当时也犹豫了很久"这种带瑕疵的叙述
4. 段落之间用口语化过渡，不要用"接下来"、"另外"、"此外"这种连接词
5. 金句自然融入正文，不要用「金句：」标签标注——读者看得出来你在刻意造句
6. 本节标题用加粗显示（**标题**），但标题本身要有吸引力，不要用"第一点"、"第二点"
7. 禁止出现：「在当今社会」「众所周知」「不可否认」「值得一提的是」「不禁」「仿佛」「宛如」「霎时」「金句：」
8. 严格控制在 {section.get('word_budget', 500)} 字左右（±10%），不要写太多
9. 只输出正文，不要任何标注"""

        resp = self.llm.complete([
            Message("system", f"你是一位{platform}爆款写手，50万粉丝。你的文章特点是：说人话、有故事、有观点、不啰嗦。读者看完会转发给朋友说「这篇写得太对了」。严格控制字数，不要写多了。直接输出正文。"),
            Message("user", prompt),
        ], temperature=0.85, max_tokens=min(4096, int(section.get('word_budget', 500)) * 3))
        return resp.content.strip()

    def _generate_ending(self, topic: str, title: str, cta: str,
                         tags: list, prev_tail: str, platform: str,
                         style_instruction: str) -> str:
        prompt = f"""写文章的结尾部分。你是一位有50万粉丝的{platform}写手。

## 标题
{title}

## 结尾设计方向
{cta}

## 上文结尾
...{prev_tail}

## 标签
{' '.join('#' + t for t in tags)}
{style_instruction}
## 写作要求
1. 不要"总而言之"、"综上所述"、"最后"这种总结式开头
2. 用一个短句或金句收尾，要有力量感——让人读完想转发
3. 互动引导要自然，像朋友之间的对话：
   - 差："欢迎点赞转发评论关注"（机器人语气）
   - 好："你身边有不结婚的朋友吗？把这篇转给ta，看看ta怎么说。"
4. 可以用反问、选择题、或一个开放性的思考来引导讨论
5. 严格控制在 100-150 字，不要写太长，结尾要干脆利落
6. 只输出正文，不要任何标注"""

        resp = self.llm.complete([
            Message("system", f"你是{platform}爆款写手，擅长写出让人想转发的结尾。你的结尾不煽情、不说教，但就是让人忍不住想分享。结尾要短、有力、干脆。直接输出正文。"),
            Message("user", prompt),
        ], temperature=0.85, max_tokens=1024)
        return resp.content.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4.5: 多轮修订
    # ─────────────────────────────────────────────────────────────────────────

    def revise_content(
        self,
        current_content: str,
        instruction: str,
        topic: str = "",
        outline: Outline | None = None,
        platform: str = "wechat",
        style_profile: StyleProfile | None = None,
        section_title: str = "",
    ) -> str:
        style_instruction = self._build_style_instruction(style_profile)

        outline_context = ""
        if outline:
            outline_context = f"""
## 文章大纲（修订时保持结构一致）
- 标题：{outline.selected_title}
- 结构：{' → '.join(s.get('title', '') for s in outline.sections)}
"""

        if section_title:
            prompt = f"""你是一位资深的{platform}编辑。用户对文章的某个小节不满意，请根据反馈修改该小节，保持其他部分不变。

## 文章主题
{topic}
{outline_context}
## 当前全文
{current_content}

## 用户反馈
{instruction}

## 要求修订的小节
「{section_title}」

{style_instruction}
## 修订规则
1. 只修改「{section_title}」小节的内容，其他小节保持原样
2. 保持与上文和下文的衔接自然
3. 保持整体字数大致不变（±20%）
4. 直接输出修订后的完整全文，不要加任何标注或说明"""
        else:
            prompt = f"""你是一位资深的{platform}编辑。用户对文章不满意，请根据反馈修改全文。

## 文章主题
{topic}
{outline_context}
## 当前全文
{current_content}

## 用户修改意见
{instruction}

{style_instruction}
## 修订规则
1. 认真理解用户的修改意见，针对性修改
2. 保持文章整体结构和风格一致
3. 如果修改意见要求精简字数，必须严格执行——删掉重复段落、压缩冗余案例、砍掉多余客套话
4. 结尾部分必须干脆利落：一句金句收尾 + 一个互动引导，不要超过 150 字
5. 不要出现多个"最后一句"或重复收尾
6. 直接输出修订后的完整全文，不要加任何标注或说明"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", f"你是{platform}资深编辑，擅长根据反馈精准修改文章。直接输出修订后的全文。"),
            Message("user", prompt),
        ], temperature=0.5))

        return resp.content.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: 排版输出
    # ─────────────────────────────────────────────────────────────────────────

    def format_html(self, content: str, title: str, tags: list[str],
                    template: str = "minimal") -> str:
        """将 Markdown 正文转为公众号适配的 HTML 片段，支持模板选择"""
        tpl = FORMAT_TEMPLATES.get(template, FORMAT_TEMPLATES["minimal"])

        prompt = f"""将以下文章正文转换为微信公众号编辑器兼容的 HTML 片段。

## 标题
{title}

## 正文
{content}

## 标签
{', '.join(tags)}

## 排版风格
{tpl['name']}（{tpl['desc']}）

## 转换规则
1. 段落用 <p style="{tpl['p_style']}"> 包裹
2. 加粗文本用 <strong style="{tpl['strong_style']}"> 包裹
3. 小节标题用 <h3 style="{tpl['h3_style']}"> 包裹
4. 段落之间留白确保手机阅读舒适
5. 重要金句用 <blockquote style="{tpl['quote_style']}"> 包裹
6. 标签用 <span style="{tpl['tag_style']}"> 包裹
7. 只输出 HTML 片段，不要 <html><body> 等外层标签"""

        resp = self.llm.complete([
            Message("system", "你是公众号排版专家，只输出 HTML 片段，不要任何说明。"),
            Message("user", prompt),
        ], temperature=0.3)

        return resp.content.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：参考链接抓取
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def fetch_reference(url: str) -> dict:
        """抓取参考链接内容，提取正文"""
        import urllib.request
        from readability import Document

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        doc = Document(html)
        title = doc.title()
        readable = doc.summary()

        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0
        text = h.handle(readable).strip()

        return {"url": url, "title": title, "text": text[:6000]}

    def extract_material_from_urls(self, urls: list[str], topic: str) -> dict:
        """从多个参考链接抓取内容并提取素材"""
        combined = ""
        for url in urls[:5]:
            try:
                ref = self.fetch_reference(url.strip())
                combined += f"\n\n## 来源：{ref['title']}\n{ref['text']}"
            except Exception as e:
                combined += f"\n\n## 来源：{url}（抓取失败：{e}）"

        if not combined.strip():
            return {"core_facts": [], "key_opinions": [], "golden_sentences": [],
                    "data_points": [], "controversial_angles": [], "hook_ideas": []}

        return self.extract_material(combined, topic)

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：图片建议
    # ─────────────────────────────────────────────────────────────────────────

    def suggest_images(self, content: str, outline: Outline) -> list[dict]:
        """在文章合适位置建议配图，附带 AI 绘图 prompt"""
        sections = outline.sections
        topic = outline.selected_title or ""

        prompt = f"""为以下公众号文章生成配图建议，每个位置给出 Midjourney 风格的绘图 prompt。

## 文章标题
{topic}

## 文章结构
开头 → {' → '.join(s.get('title', '') for s in sections)} → 结尾

请输出 JSON 数组：
[
  {{
    "position": "位置描述",
    "suggestion": "配图类型",
    "description": "中文描述",
    "ai_prompt": "Midjourney style English prompt, cinematic, high quality, --ar 16:9"
  }}
]

要求：
1. 开头一张封面图，每个小节一张配图
2. ai_prompt 用英文，包含风格、构图、色调描述
3. 图片风格统一，适合公众号阅读场景"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是配图策划师，擅长为新媒体文章设计视觉方案。只输出合法 JSON 数组。"),
            Message("user", prompt),
        ], temperature=0.7))

        return parse_json_list(resp.content)

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：批量生成
    # ─────────────────────────────────────────────────────────────────────────

    def generate_batch(
        self,
        topics: list[str],
        platform: str = "wechat",
        mode: str = "干货型",
        style_profile: StyleProfile | None = None,
    ) -> list[dict]:
        """批量生成多篇文章的大纲+标题"""
        results = []
        for topic in topics[:10]:
            try:
                outline = self.generate_outline(
                    topic=topic, platform=platform, mode=mode,
                    style_profile=style_profile,
                )
                results.append({
                    "topic": topic,
                    "ok": True,
                    "outline": _to_dict(outline),
                })
            except Exception as e:
                results.append({
                    "topic": topic,
                    "ok": False,
                    "error": str(e),
                })
        return results

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：SEO 关键词优化（头条专用）
    # ─────────────────────────────────────────────────────────────────────────

    def optimize_seo(self, content: str, topic: str) -> dict:
        """针对头条搜索推荐算法优化关键词"""
        prompt = f"""分析以下文章，提供 SEO 优化建议（针对头条/百度搜索推荐）。

## 主题
{topic}

## 文章内容（前2000字）
{content[:2000]}

请输出 JSON：
{{
  "primary_keyword": "核心关键词",
  "secondary_keywords": ["相关词1", "相关词2", ...],
  "suggested_title": "SEO 优化后的标题",
  "keyword_density": "当前关键词密度评估",
  "suggestions": ["优化建议1", "优化建议2", ...]
}}"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是 SEO 优化专家，擅长新媒体内容的搜索优化。只输出合法 JSON。"),
            Message("user", prompt),
        ], temperature=0.3))

        return parse_json(resp.content)

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：单节重新生成
    # ─────────────────────────────────────────────────────────────────────────

    def regenerate_section(
        self,
        topic: str,
        outline: Outline,
        section_index: int,
        current_content: str,
        platform: str = "wechat",
        style_profile: StyleProfile | None = None,
        material: dict | None = None,
    ) -> str:
        """重新生成指定小节，保持其他部分不变"""
        sections = outline.sections
        if section_index < 0 or section_index >= len(sections):
            raise ValueError(f"无效的小节索引：{section_index}")

        section = sections[section_index]
        style_instruction = self._build_style_instruction(style_profile)
        material_hint = self._get_material_hint(material, section_index)

        # 从当前内容中提取该小节前后的文本
        # 用小节标题作为锚点
        title = section.get('title', '')
        parts = current_content.split(title)

        # 找到上文结尾
        prev_tail = ""
        if len(parts) > 1:
            prev_text = parts[0].strip()
            prev_tail = prev_text[-200:] if prev_text else ""

        # 找到下文开头
        next_head = ""
        if len(parts) > 2:
            next_text = title.join(parts[1:]).strip()
            next_head = next_text[:200] if next_text else ""
        elif len(parts) == 2:
            next_text = parts[1].strip()
            next_head = next_text[:200] if next_text else ""

        prompt = f"""重新写文章的一个小节，替换原来的内容。

## 标题
{outline.selected_title}

## 要重写的小节
标题：{title}
要点：{'；'.join(section.get('key_points', []))}
字数预算：约 {section.get('word_budget', 500)} 字
写作指导：{section.get('writing_guide', '')}

## 上文结尾（必须平滑衔接）
...{prev_tail}

## 下文开头（新内容必须能与此衔接）
{next_head}...

## 全文大纲（了解全局位置）
{' → '.join(s.get('title', '') for s in sections)}
{material_hint}
{style_instruction}
## 要求
1. 承接上文语气，不要突兀跳转
2. 结尾要能与下文自然衔接
3. 本节标题用加粗显示（**标题**）
4. 只输出本节正文，不要输出其他小节
5. 不要输出任何标注或说明"""

        resp = self.llm.complete([
            Message("system", f"你是{platform}写手，擅长重写单个小节并保持全文连贯。直接输出正文。"),
            Message("user", prompt),
        ], temperature=0.8)

        new_section = resp.content.strip()

        # 拼接：上文 + 新小节 + 下文
        result_parts = []
        if len(parts) >= 2:
            result_parts.append(parts[0])  # 上文（含原标题）
            result_parts.append(new_section)  # 新小节
            if len(parts) > 2:
                result_parts.append(title.join(parts[2:]))  # 下文
            elif len(parts) == 2 and parts[1]:
                # 找到下一个section的标题作为分割点
                remaining = parts[1]
                for next_sec in sections[section_index+1:]:
                    next_title = next_sec.get('title', '')
                    if next_title and next_title in remaining:
                        idx = remaining.index(next_title)
                        result_parts.append(remaining[idx:])
                        remaining = ""
                        break
                if remaining:
                    result_parts.append(remaining)
            return "".join(result_parts)
        else:
            return new_section

    # ─────────────────────────────────────────────────────────────────────────
    # 新功能：文章综合审计
    # ─────────────────────────────────────────────────────────────────────────

    def audit_article(self, content: str, topic: str, platform: str = "wechat") -> dict:
        """对文章进行全方位审计：AI味、敏感词、内容质量、结构、SEO"""
        validation = self.validator.validate(content, platform)

        prompt = f"""你是一位资深的新媒体内容审计师。请对以下文章进行全方位质量审计。

## 主题
{topic}

## 平台
{"公众号" if platform == "wechat" else "头条"}

## 文章内容
{content[:4000]}

请从以下维度审计，输出 JSON：
{{
  "overall_score": 85,
  "overall_verdict": "通过/需修改/不通过",
  "dimensions": {{
    "ai_flavor": {{
      "score": 80,
      "level": "轻微/中等/严重",
      "issues": ["问题1", "问题2"],
      "suggestions": ["建议1", "建议2"]
    }},
    "sensitive_words": {{
      "score": 90,
      "issues": ["敏感词1", "敏感词2"],
      "risk_level": "低/中/高"
    }},
    "content_quality": {{
      "score": 75,
      "info_increment": "高/中/低",
      "logic_flow": "好/一般/差",
      "evidence_strength": "强/中/弱",
      "issues": ["问题1"],
      "suggestions": ["建议1"]
    }},
    "readability": {{
      "score": 85,
      "paragraph_balance": "好/一般/差",
      "sentence_variety": "好/一般/差",
      "mobile_friendly": true,
      "issues": ["问题1"],
      "suggestions": ["建议1"]
    }},
    "engagement": {{
      "score": 70,
      "hook_strength": "强/中/弱",
      "cta_effectiveness": "好/一般/差",
      "shareability": "高/中/低",
      "issues": ["问题1"],
      "suggestions": ["建议1"]
    }},
    "platform_fit": {{
      "score": 80,
      "word_count_ok": true,
      "tone_match": true,
      "issues": ["问题1"],
      "suggestions": ["建议1"]
    }}
  }},
  "top_fixes": ["最重要的修改1", "最重要的修改2", "最重要的修改3"],
  "highlight": "文章最大的亮点（一句话）"
}}"""

        resp = with_retry(lambda: self.llm.complete([
            Message("system", "你是资深新媒体内容审计师，擅长从多个维度评估文章质量。只输出合法 JSON。"),
            Message("user", prompt),
        ], temperature=0.3))

        audit = parse_json(resp.content)

        # 合并验证器结果
        audit["validator"] = {
            "score": validation.score,
            "passed": validation.passed,
            "issue_count": len(validation.issues),
            "issues": [{"rule": i.rule, "severity": i.severity, "description": i.description}
                       for i in validation.issues],
        }

        return audit

    # ─────────────────────────────────────────────────────────────────────────
    # 完整流程
    # ─────────────────────────────────────────────────────────────────────────

    def _auto_revise(
        self,
        content: str,
        outline: Outline,
        topic: str,
        platform: str,
        style_profile: StyleProfile | None = None,
        max_rounds: int = 2,
        target_words: tuple = (1500, 3000),
    ) -> tuple[str, ValidationResult]:
        """自动迭代：验证 → 发现问题 → 自动修订 → 再验证，最多 max_rounds 轮"""
        validation = self.validator.validate(content, platform)
        word_count = len(content)

        for round_num in range(1, max_rounds + 1):
            # 检查是否需要修订
            issues_to_fix = []
            for issue in validation.issues:
                if issue.severity == "error":
                    issues_to_fix.append(issue)
                elif issue.rule in ("AI_MARKER", "FORBIDDEN", "META", "REPORT",
                                    "COLLECTIVE", "AI_FILLER", "REPETITIVE",
                                    "CONSECUTIVE_LE", "EXCLAMATION"):
                    issues_to_fix.append(issue)

            # 字数检查
            too_long = word_count > target_words[1]
            too_short = word_count < target_words[0]

            if not issues_to_fix and not too_long and not too_short:
                break

            print(f"\n🔄 自动修订第 {round_num} 轮（当前 {word_count} 字，目标 {target_words[0]}-{target_words[1]}）...")

            # 构建修订指令
            fix_instructions = []
            if too_long:
                target = int((target_words[0] + target_words[1]) / 2)
                excess = word_count - target
                fix_instructions.append(
                    f"【字数超标】当前 {word_count} 字，必须精简到 {target} 字左右（需删掉约 {excess} 字）。"
                    f"具体操作：1) 删除重复论述和冗余过渡段 2) 每个案例只保留最有力的一个，删掉雷同的 3) "
                    f"去掉所有「金句：」标签，把金句自然融入正文 4) 结尾砍掉多余的客套话，只留一句收尾+一个互动引导"
                )
            if too_short:
                target = int((target_words[0] + target_words[1]) / 2)
                fix_instructions.append(
                    f"当前 {word_count} 字，太短了。请扩充到 {target} 字左右："
                    f"每个观点增加一个案例或数据支撑，增加金句密度。"
                )

            for issue in issues_to_fix[:5]:
                if issue.rule == "AI_MARKER":
                    fix_instructions.append(f"减少 AI 痕迹词：{issue.description}，用更口语化的表达替换")
                elif issue.rule == "FORBIDDEN":
                    fix_instructions.append(f"删除禁止句式：{issue.description}")
                elif issue.rule == "META":
                    fix_instructions.append(f"去掉元叙事/说教：{issue.description}")
                elif issue.rule == "REPORT":
                    fix_instructions.append(f"去掉报告腔：{issue.description}，改成口语化表达")
                elif issue.rule == "COLLECTIVE":
                    fix_instructions.append(f"删除集体套话：{issue.description}")
                elif issue.rule == "AI_FILLER":
                    fix_instructions.append(f"精简套话连接词：{issue.description}")
                elif issue.rule == "REPETITIVE":
                    fix_instructions.append(f"避免重复表达：{issue.description}")
                elif issue.rule == "CONSECUTIVE_LE":
                    fix_instructions.append(f"减少「了」字连用：{issue.description}")
                elif issue.rule == "EXCLAMATION":
                    fix_instructions.append(f"减少感叹号：{issue.description}")

            instruction = "\n".join(fix_instructions)

            try:
                content = self.revise_content(
                    current_content=content,
                    instruction=instruction,
                    topic=topic,
                    outline=outline,
                    platform=platform,
                    style_profile=style_profile,
                )
                word_count = len(content)
                validation = self.validator.validate(content, platform)
                print(f"   修订后：{word_count} 字 | 得分 {validation.score}/100")
            except Exception as e:
                print(f"   修订失败：{e}，跳过本轮")
                break

        return content, validation

    def run_full(
        self,
        topic: str,
        platform: str = "wechat",
        mode: str = "干货型",
        source_text: str = "",
        style_profile: StyleProfile | None = None,
        extra_requirements: str = "",
    ) -> Article:
        article_id = f"art_{uuid.uuid4().hex[:8]}"
        print(f"\n{'='*60}")
        print(f"📝 开始生成：{topic}")
        print(f"   平台：{platform} | 类型：{mode}")
        print(f"{'='*60}")

        material = None
        if source_text.strip():
            print("\n🔍 Step 1: 提取素材...")
            material = self.extract_material(source_text, topic)
            print(f"   提取到 {len(material.get('core_facts', []))} 个事实, "
                  f"{len(material.get('golden_sentences', []))} 条金句")

        print("\n📋 Step 2: 生成大纲...")
        outline = self.generate_outline(
            topic=topic, platform=platform, mode=mode,
            material=material, style_profile=style_profile,
            extra_requirements=extra_requirements,
        )
        print(f"   标题：{outline.selected_title}")
        print(f"   结构：{' → '.join(s.get('title', '') for s in outline.sections)}")

        print("\n✍️  Step 3: 分块生成正文...")
        content = self.generate_content(
            topic=topic, outline=outline, platform=platform,
            material=material, style_profile=style_profile,
        )
        word_count = len(content)
        print(f"   初稿完成：{word_count} 字")

        # Step 4: 自动迭代验证+修订
        print("\n🔍 Step 4: 验证 + 自动修订...")
        target_words = (1500, 3000) if platform == "wechat" else (800, 2000)
        content, validation = self._auto_revise(
            content, outline, topic, platform, style_profile,
            max_rounds=2, target_words=target_words,
        )
        word_count = len(content)
        print(f"   最终：{word_count} 字 | 得分 {validation.score}/100 | "
              f"{'✅ 通过' if validation.passed else '⚠️ 有问题'}")
        if validation.issues:
            for issue in validation.issues[:3]:
                print(f"   [{issue.severity}] {issue.description}")

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
                "tags": data.get("tags", []),
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
    if hasattr(obj, '__dataclass_fields__'):
        return {k: _to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj
