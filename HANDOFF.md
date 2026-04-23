# HANDOFF.md — 项目交接文档

本文档用于新对话/新开发者快速理解项目上下文，继续开发或维护。

## 项目概述

InkFlow = 公众号/头条文章的 AI 写作工作台，核心理念是「人机共创」而非「一键出稿」。

### 起源

原项目 [dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow) 是一个 AI 长篇小说创作系统，基于 Dramatica 叙事理论，有 5 层写作管线、因果链、伏笔系统、情感弧线等复杂机制。

用户希望将其改造为公众号/头条文章写作工具。经过讨论，确定了核心原则：

- 不要拿着锤子找钉子 — 小说系统的复杂状态机对 2000 字的单篇文章是过度工程
- LLM 单次上下文够用 — 不需要外部状态机追踪逻辑
- 新媒体写作的灵魂是信息源 — 需要素材输入/RAG，不是无中生写
- 人机共创 — AI 发散，人做决策

## 架构

```
用户浏览器
 ↓ HTTP
FastAPI (app.py, port 8765)
 ↓ 调用
Pipeline (pipeline.py)
 ├── extract_material()       → LLM 提取素材要点
 ├── extract_material_from_urls() → 抓取参考链接 + 提取素材
 ├── generate_outline()       → LLM 生成大纲 + 标题
 ├── generate_titles()        → LLM 单独生成标题
 ├── generate_content()       → LLM 分块写正文
 ├── generate_content_stream() → LLM 流式分块写正文（SSE）
 ├── regenerate_section()     → LLM 重写单个小节
 ├── revise_content()         → LLM 多轮修订
 ├── suggest_images()         → LLM 配图建议 + AI 绘图 prompt
 ├── format_html()            → LLM 生成排版 HTML（3 种模板）
 ├── audit_article()          → LLM 六维度审计
 ├── optimize_seo()           → LLM SEO 优化建议
 ├── extract_style()          → LLM 分析写作风格
 ├── generate_batch()         → 批量生成大纲
 └── run_full()               → 一键走完全部流程
 ↓ 调用
LLM (llm.py)
 └── DeepSeek / Ollama / 任意 OpenAI 兼容 API
 ↓ 返回后
Validator (validator.py)
 └── 13 项规则检测
```

## 数据模型

### 存储

- 纯文件驱动，无数据库
- `data/articles/{id}.json` — 每篇文章的完整数据
- `data/articles/{id}/versions/*.json` — 版本历史
- `data/styles/{id}.json` — 风格克隆 profile
- `.env` — API 配置

### 核心数据结构

```python
@dataclass
class Article:
    id: str
    topic: str
    platform: str          # wechat | toutiao
    mode: str              # 干货型 | 争议型 | 故事型 | 测评型
    status: str            # draft | outlined | writing | done
    outline: Outline
    content: str
    html: str
    style_profile_id: str
    source_text: str
    validation: ValidationResult
    created_at: str
    word_count: int
    revision_history: list

@dataclass
class Outline:
    title_candidates: list[str]
    selected_title: str
    hook: str              # 开头钩子
    sections: list[dict]   # [{title, key_points, word_budget, writing_guide}]
    cta: str               # 结尾行动号召
    tags: list[str]

@dataclass
class StyleProfile:
    id: str
    name: str
    sentence_patterns: list[str]
    vocabulary: list[str]
    punctuation_habits: str
    tone: str
    structure_style: str
    sample_summary: str
```

## 前端

- 单文件 SPA (index.html)，约 1600 行
- 暗/亮双主题，localStorage 持久化
- 无构建工具，无框架依赖
- 5 步流程条：选题 → 素材 → 大纲 → 正文 → 导出
- 导出页 6 个 tab：预览 / HTML / 纯文本 / 配图 / SEO / 审计

### 关键交互

- 标题候选点击选择
- 大纲小节可编辑（弹窗）+ 拖拽排序
- 正文 textarea 可直接编辑
- 单节重新生成
- 多轮修订（全局/局部）+ 修订历史 + 撤销
- 侧边栏标签筛选 + 复制/删除
- 写作统计面板
- 快捷键：Ctrl+S / Ctrl+Enter / N / Esc

## 核心设计决策

### 分块生成

一次性生成 3000 字，后半段质量会下降（LLM 的注意力衰减）。分块策略：

- 开头（150-300字）→ 各小节（按 word_budget）→ 结尾 + CTA（100-200字）
- 每块 Prompt 带入上一块最后 200 字（prev_tail），确保衔接
- 支持 SSE 流式输出，前端实时显示进度

### 风格克隆

- 用户上传 3-5 篇 .txt/.md 样本文章
- 调用 LLM 分析：句式特征、惯用词汇、标点习惯、语调、结构风格
- 保存为 style_profile.json
- 后续生成时，将 profile 注入 Prompt 的「写作风格要求」section

### 写后验证（13 项规则）

| 规则 | 级别 | 说明 |
|------|------|------|
| AI_MARKER | warning | "仿佛/忽然/竟然"等词，每3000字上限1次 |
| FORBIDDEN | error | "全场震惊/众所周知"等禁止句式 |
| META | warning | "核心动机/叙事节奏"等元叙事 |
| REPORT | warning | "分析了形势/综合考虑"等报告式语言 |
| COLLECTIVE | warning | "众人哗然/所有人齐声"等集体套话 |
| SENSITIVE | warning | 广告法违禁词/平台敏感词（70+ 词） |
| LENGTH | warning | 字数不符合平台建议 |
| LONG_PARA | warning | 段落超300字影响手机阅读 |
| CONSECUTIVE_LE | warning | 连续6句含"了"字 |
| AI_FILLER | warning | AI 套话/连接词过多（≥3处） |
| REPETITIVE | warning | 重复表达出现≥2次 |
| EXCLAMATION | warning | 感叹号过多（>5个） |
| MONOTONE | warning | 段落长度过于单调 |

### 文章审计（六维度）

LLM 当「资深内容审计师」，从 6 个维度打分：

1. **AI 味** — 有没有明显的 AI 写作痕迹
2. **敏感词** — 广告法/平台违禁词风险等级
3. **内容质量** — 信息增量、逻辑流、论据强度
4. **可读性** — 段落均衡、句式变化、手机友好
5. **互动性** — 开头钩子强度、CTA 效果、转发欲
6. **平台适配** — 字数是否达标、语调是否匹配

最后合并验证器结果，给出综合评分 + 最重要的 3 个修改建议。

**验证 vs 审计的区别**：验证是规则引擎（机械检查），审计是 LLM 评估（主观判断）。验证 90 分不代表写得好，只是没触发规则；审计 65 分说明内容质量需要提升。两者互补。

### JSON 解析容错

DeepSeek 等模型输出 JSON 时常见问题：
- 包裹在 ```json ``` 中
- 弯引号（""）替代直引号
- JSON 被截断（不完整）

解决方案（llm.py）：
- `_repair()` — 修复被截断的 JSON（补全括号）
- `_fix_smart_quotes()` — 状态机按字符串边界精准替换弯引号
- `with_retry()` — 失败自动重试 3 次

### 排版模板系统

3 种内联 CSS 模板（公众号不支持外部样式表）：
- **minimal（简约白）**— 干净清爽，适合干货/知识类
- **vibrant（活泼彩）**— 色彩丰富，适合情感/故事类
- **business（商务灰）**— 专业稳重，适合商业/测评类

### 文章结构模板

5 种预设大纲结构：
- **listicle（清单体）**— N 个方法/技巧/建议
- **comparison（对比测评）**— A vs B
- **story（情感故事）**— 真实案例切入
- **hot_take（争议观点）**— 反常识，引发讨论
- **tutorial（教程指南）**— 手把手教

## API 端点一览

### 文章管理
- `GET /api/articles` — 文章列表
- `GET /api/articles/{id}` — 文章详情
- `POST /api/articles/save` — 保存文章（自动版本管理）
- `DELETE /api/articles/{id}` — 删除文章
- `POST /api/articles/{id}/copy` — 复制文章
- `GET /api/articles/{id}/versions` — 版本历史
- `GET /api/articles/{id}/versions/{file}` — 版本详情
- `GET /api/articles/tag/{tag}` — 按标签筛选

### 标签 & 统计
- `GET /api/tags` — 标签列表
- `GET /api/stats` — 写作统计

### 生成
- `POST /api/generate/outline` — 生成大纲
- `POST /api/generate/titles` — 生成标题
- `POST /api/generate/content` — 生成正文（普通）
- `POST /api/generate/content/stream` — 生成正文（SSE 流式）
- `POST /api/generate/section` — 单节重新生成
- `POST /api/generate/batch` — 批量生成大纲
- `POST /api/generate/full` — 一键完整生成

### 素材 & 风格
- `POST /api/extract-material` — 提取素材要点
- `POST /api/fetch-references` — 抓取参考链接
- `GET /api/styles` — 风格列表
- `POST /api/styles/extract` — 提取写作风格

### 修订 & 审计
- `POST /api/revise` — 多轮修订
- `POST /api/revise/suggest` — 修订建议
- `POST /api/validate` — 写后验证
- `POST /api/audit` — 文章综合审计

### 导出
- `POST /api/format` — 排版生成 HTML
- `GET /api/format/templates` — 排版模板列表
- `GET /api/templates` — 文章模板列表
- `POST /api/export/docx` — 导出 Word
- `POST /api/suggest-images` — 配图建议
- `POST /api/seo` — SEO 优化建议

### 系统
- `GET /api/health` — 健康检查
- `GET /api/settings` — 获取配置
- `POST /api/settings` — 保存配置

## 开发指南

### 想改什么 → 看哪个文件

| 目标 | 文件 | 关键函数/类 |
|------|------|------------|
| API 端点 | app.py | `@app.post("/api/...")` |
| 管线流程 | pipeline.py | `Pipeline.run_full()` |
| 大纲生成 | pipeline.py | `Pipeline.generate_outline()` |
| 正文生成 | pipeline.py | `Pipeline.generate_content()` |
| 单节重写 | pipeline.py | `Pipeline.regenerate_section()` |
| 多轮修订 | pipeline.py | `Pipeline.revise_content()` |
| 文章审计 | pipeline.py | `Pipeline.audit_article()` |
| 配图建议 | pipeline.py | `Pipeline.suggest_images()` |
| 批量生成 | pipeline.py | `Pipeline.generate_batch()` |
| LLM 调用 | llm.py | `LLM.complete()` / `LLM.stream()` |
| JSON 解析 | llm.py | `parse_json()` / `_fix_smart_quotes()` |
| 验证规则 | validator.py | `Validator.validate()` |
| 敏感词库 | validator.py | `SENSITIVE_WORDS` |
| 排版模板 | pipeline.py | `FORMAT_TEMPLATES` |
| 文章模板 | pipeline.py | `ARTICLE_TEMPLATES` |
| 前端界面 | index.html | `<script>` 部分的 JS 函数 |
| 前端修订 | index.html | `doRevise()` / `quickRevise()` |
| 前端审计 | index.html | `runAudit()` |
| 前端统计 | index.html | `showStats()` |
| 配置 | .env | `DEEPSEEK_*` 变量 |

## 已知问题

- **JSON 解析偶发失败** — DeepSeek 输出带书名号《》或特殊引号时可能解析失败，with_retry 会自动重试
- **风格提取只支持 .txt/.md** — 不支持 .docx/.pdf
- **无持久化用户系统** — 所有数据本地文件存储，无登录/多用户
- **敏感词库需持续扩充** — 当前 70+ 词，可接入平台官方违禁词列表

## 依赖

```
fastapi>=0.100.0
uvicorn>=0.23.0
openai>=1.0.0
pydantic>=2.0.0
python-multipart>=0.0.6
python-docx>=1.0.0
readability-lxml>=0.8.0
lxml>=4.0.0
html2text>=2024.0.0
```

## 启动

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
python3 app.py
# 打开 http://localhost:8765
```

## 版本历史

- **v1.0** — 初始版本：5 步流程 + 大纲 + 正文 + 验证 + 排版
- **v2.0** — SSE 流式输出 + 并发保护 + 自动保存 + 快捷键 + 字数指示器 + 增强验证器（13 项）
- **v3.0** — 参考链接抓取 + 排版模板（3 种）+ 配图建议 + 批量生成 + SEO 优化
- **v4.0** — 文章审计（六维度）+ 单节重写 + 导出 Word + 敏感词库扩充（70+）+ 文章模板（5 种）+ 暗/亮主题
- **v5.0** — 大纲拖拽排序 + 复制文章 + 版本管理 + AI 绘图 prompt + 删除确认
- **v6.0** — 写作统计面板 + 标签管理 + 按标签筛选
- **v7.0** — JSON 解析鲁棒性 + 自动迭代修订 + Prompt 人味升级 + 验证器优化（详见下方）

### v7.0 改动详情（2026-04-23）

#### llm.py — JSON 解析重写
- `parse_json()` 从单次尝试改为 **10 层修复策略链**，按顺序尝试：
  1. 直接解析 → 2. 修弯引号 → 3. 去尾逗号 → 4. 修对象当数组 → 5. 修截断 → 6. 各种组合
- 新增 `_fix_object_as_array()`：修复 DeepSeek 把 `title_candidates` 输出成 `{key: value}` 而非 `["str"]` 的问题
- 新增 `_fix_trailing_commas()`：去掉 JSON 尾逗号
- 新增 `_extract_json_text()`：从 LLM 输出中精准提取 JSON（去 markdown 包裹、找第一个 `{` 到最后一个 `}`）
- `_fix_smart_quotes()` 增加书名号《》处理

#### pipeline.py — Prompt 全面重写
- **大纲 prompt**：加入叙事弧线 5 步要求（钩子→痛点放大→转折→实操→情绪收尾），明确要求 `title_candidates` 是字符串数组
- **正文 prompt**：禁止 AI 套路词（"在当今社会""众所周知"等），引导"不完美"案例叙述，禁止"金句："标签，加入字数硬约束 + `max_tokens` 限制
- **结尾 prompt**：收紧到 100-150 字，禁止多个"最后一句"
- **修订 prompt**：加入"结尾不超过 150 字"、"不要多个最后一句"规则

#### pipeline.py — 自动迭代修订
- 新增 `_auto_revise()` 方法：验证 → 找问题 → 生成修订指令 → 自动修订 → 再验证，最多 2 轮
- `run_full()` 集成自动迭代循环（Step 4 改为"验证 + 自动修订"）
- 修订指令针对具体问题生成（字数超标/禁止句式/AI 套话/报告腔等）

#### validator.py — 误杀修复 + 字数扣分
- 去掉高频误杀词：`"最好""第一""唯一""绝对""100%""保证""永远"` 等单字/常见词
- 短词（≤2字）加前后边界匹配，避免"一线城市"触发"第一"
- 字数超限从 warning 升为 error（扣 15 分），确保触发自动修订

#### 测试结果
- 3 个不同 topic × 2 个 platform 全部通过，验证得分 100/100
- JSON 解析：大纲生成 5/5 成功（修复前约 50%）
- 自动修订：每次都能把超限初稿修正到目标字数范围内

---

基于 [dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow) 改造。
使用 DeepSeek API 作为默认 LLM 后端。
项目创建时间：2026-04-23
