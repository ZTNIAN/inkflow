"""写后验证器 — 去AI味 + 敏感词 + 平台规范检测 v2"""
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

# ── AI 常用连接词/套话 ──
AI_FILLER = [
    "首先，", "其次，", "最后，", "另外，", "此外，",
    "值得注意的是", "需要指出的是", "不可否认",
    "在这个过程中", "在当今社会", "随着...的发展",
    "让我们一起来看看", "接下来让我们",
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

# ── 常见敏感词（广告法违禁词 + 平台敏感词 + 医疗/金融）──
SENSITIVE_WORDS = [
    # 广告法极限词
    "最好", "第一", "唯一", "首个", "首选", "最佳", "最优", "最高", "最低", "最大", "最小",
    "绝对", "100%", "保证", "永远", "万能", "顶级", "极致", "国家级", "世界级", "全网最",
    "史上最", "独一无二", "无与伦比", "前无古人", "绝无仅有", "史无前例", "遥遥领先",
    # 医疗/健康
    "治愈", "根治", "特效", "神药", "偏方", "秘方", "祖传", "包治", "药到病除",
    "癌症", "肿瘤", "艾滋病", "性病", "不孕不育",
    # 金融/理财
    "暴富", "躺赚", "零风险", "稳赚", "割韭菜", "庞氏", "资金盘", "传销",
    "保本保息", "年化收益", "日赚", "月入百万", "财务自由",
    # 色情/低俗
    "约炮", "一夜情", "裸聊", "色情", "淫秽", "成人用品",
    # 政治敏感
    "六四", "天安门", "法轮功", "藏独", "疆独", "台独", "港独",
    # 歧视/仇恨
    "穷逼", "屌丝", "死胖子", "娘炮", "直男癌", "女拳",
    # 平台违禁
    "加微信", "加QQ", "私聊", "扫码", "点击链接", "免费领",
    "转发有奖", "关注抽奖", "限时特价", "最后一天", "错过再等一年",
]

# ── 重复表达检测 ──
REPETITIVE_PATTERNS = [
    (r"重要(?:的)?(?:是|事情|事情是)", "重复表达"),
    (r"不得不说", "AI 套话"),
    (r"说白了", "过度口语化"),
    (r"说到底", "AI 套话"),
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

        # 10. AI 填充词密度过高
        filler_count = sum(1 for f in AI_FILLER if f in content)
        if filler_count >= 3:
            issues.append(Issue("AI_FILLER", "warning",
                f"AI 套话/连接词过多（{filler_count}处），建议精简"))

        # 11. 重复表达
        for pat, label in REPETITIVE_PATTERNS:
            m = re.findall(pat, content)
            if len(m) >= 2:
                issues.append(Issue("REPETITIVE", "warning",
                    f"{label}：「{m[0]}」出现 {len(m)} 次"))

        # 12. 感叹号过多
        excl_count = content.count("！") + content.count("!")
        if excl_count > 5:
            issues.append(Issue("EXCLAMATION", "warning",
                f"感叹号过多（{excl_count}个），公众号读者不喜欢大喊大叫"))

        # 13. 段落缺少变化（全是短段或全是长段）
        if paras and len(paras) >= 4:
            lengths = [len(p) for p in paras]
            avg = sum(lengths) / len(lengths)
            short_count = sum(1 for l in lengths if l < avg * 0.4)
            long_count = sum(1 for l in lengths if l > avg * 2.5)
            if short_count == 0 and long_count == 0 and len(set(lengths)) <= 2:
                issues.append(Issue("MONOTONE", "warning",
                    "段落长度过于单调，建议长短交替增加节奏感"))

        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        score = max(0, 100 - error_count * 15 - warning_count * 5)

        return ValidationResult(
            passed=error_count == 0,
            issues=issues,
            score=score,
        )
