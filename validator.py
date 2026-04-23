"""写后验证器 — 去AI味 + 敏感词 + 平台规范检测"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class Issue:
    rule: str
    severity: str   # error | warning
    description: str
    excerpt: str = ""


@dataclass
class ValidationResult:
    passed: bool
    issues: list[Issue] = field(default_factory=list)
    score: int = 100   # 0-100, 越高越好


# ── AI 标记词（每 3000 字最多 1 次）──
AI_MARKERS = [
    "仿佛", "忽然", "竟然", "不禁", "宛如", "猛地", "顿时", "霎时",
    "不由得", "赫然", "蓦然", "恍若", "犹如", "恰似",
]

# ── 禁止句式 ──
FORBIDDEN_PHRASES = [
    "不是……而是……", "全场震惊", "众人哗然", "所有人都",
    "不言而喻", "毫无疑问", "显而易见", "众所周知",
    "综上所述", "总而言之", "由此可见", "不难发现",
]

# ── 元叙事 / 说教 ──
META_PATTERNS = [
    (r"核心动机", "元叙事"), (r"叙事节奏", "元叙事"),
    (r"人物弧线", "元叙事"), (r"情节推进", "元叙事"),
    (r"显然[，,。]", "作者说教"), (r"毋庸置疑", "作者说教"),
]

# ── 报告式语言 ──
REPORT_PATTERNS = [
    r"分析了.*?(?:情况|局势|形势)", r"从.*?(?:角度|层面)(?:来|而言|看)",
    r"综合考虑", r"经过.*?(?:研究|分析|调查)",
]

# ── 集体反应套话 ──
COLLECTIVE_PATTERNS = [
    r"(?:在场|全场)(?:之人|人|众人)(?:皆|都|全)",
    r"(?:众人|所有人)(?:齐声|异口同声)",
    r"一时间.*?(?:哗然|震动|沸腾)",
]

# ── 常见敏感词（基础库，实际运营需扩充）──
SENSITIVE_WORDS = [
    "最好", "第一", "绝对", "100%", "保证", "永远", "万能",
    "治愈", "根治", "特效", "神药", "偏方",
    "暴富", "躺赚", "零风险", "稳赚", "割韭菜",
]


class Validator:

    def __init__(self, custom_sensitive: list[str] | None = None):
        self.extra_sensitive = custom_sensitive or []

    def validate(self, content: str, platform: str = "wechat") -> ValidationResult:
        issues: list[Issue] = []
        word_count = len(content)

        # 1. AI 标记词密度
        for w in AI_MARKERS:
            count = len(re.findall(w, content))
            if count == 0: continue
            per_3k = (count / word_count) * 3000 if word_count > 0 else 0
            if per_3k > 1:
                issues.append(Issue("AI_MARKER", "warning",
                    f"「{w}」出现 {count} 次（每3000字 {per_3k:.1f}，上限1）", w))

        # 2. 禁止句式
        for p in FORBIDDEN_PHRASES:
            if p in content:
                issues.append(Issue("FORBIDDEN", "error", f"禁止句式：「{p}」", p))

        # 3. 元叙事 / 说教
        for pat, label in META_PATTERNS:
            m = re.findall(pat, content)
            if m:
                issues.append(Issue("META", "warning", f"{label}：「{m[0]}」", m[0]))

        # 4. 报告式语言
        for pat in REPORT_PATTERNS:
            m = re.findall(pat, content)
            if m:
                issues.append(Issue("REPORT", "warning", f"报告式语言：「{m[0]}」", m[0]))

        # 5. 集体反应套话
        for pat in COLLECTIVE_PATTERNS:
            m = re.findall(pat, content)
            if m:
                issues.append(Issue("COLLECTIVE", "warning", f"集体套话：「{m[0]}」", m[0]))

        # 6. 敏感词
        all_sensitive = SENSITIVE_WORDS + self.extra_sensitive
        for w in all_sensitive:
            if w in content:
                issues.append(Issue("SENSITIVE", "warning", f"敏感词/广告法违禁词：「{w}」", w))

        # 7. 字数检查
        if platform == "wechat":
            if word_count < 800:
                issues.append(Issue("LENGTH", "warning", f"公众号文章偏短（{word_count}字，建议1500+）"))
            elif word_count > 5000:
                issues.append(Issue("LENGTH", "warning", f"公众号文章偏长（{word_count}字，建议3000以内）"))
        elif platform == "toutiao":
            if word_count < 500:
                issues.append(Issue("LENGTH", "warning", f"头条文章偏短（{word_count}字，建议800+）"))

        # 8. 段落过长
        paras = [p for p in re.split(r"\n{2,}", content) if p.strip()]
        long = [p for p in paras if len(p) > 300]
        if len(long) >= 2:
            issues.append(Issue("LONG_PARA", "warning", f"{len(long)}个段落超300字，影响手机阅读"))

        # 9. 连续"了"字
        sentences = re.split(r"[。！？!?]", content)
        consecutive = 0
        max_consecutive = 0
        for s in sentences:
            if "了" in s:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0
        if max_consecutive >= 6:
            issues.append(Issue("CONSECUTIVE_LE", "warning", f"连续{max_consecutive}句含「了」字"))

        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        score = max(0, 100 - error_count * 15 - warning_count * 5)

        return ValidationResult(
            passed=error_count == 0,
            issues=issues,
            score=score,
        )
