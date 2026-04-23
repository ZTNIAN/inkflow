# 📋 项目交接文档

> 本文档用于新对话/新开发者快速理解项目上下文，继续开发或维护。

---

## 一句话定位

**InkFlow** = 公众号/头条文章的 AI 写作工作台，核心理念是「人机共创」而非「一键出稿」。

---

## 项目背景

### 为什么做这个？
原项目 [dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow) 是一个 AI 长篇小说创作系统，基于 Dramatica 叙事理论，有 5 层写作管线、因果链、伏笔系统、情感弧线等复杂机制。

用户希望将其改造为公众号/头条文章写作工具。经过讨论，确定了核心原则：
- **不要拿着锤子找钉子** — 小说系统的复杂状态机（因果链、伏笔追踪）对 2000 字的单篇文章是过度工程
- **LLM 单次上下文够用** — 不需要外部状态机追踪逻辑
- **新媒体写作的灵魂是信息源** — 需要素材输入/RAG，不是无中生写
- **人机共创** — AI 发散，人做决策

### 从原项目复用了什么？
- LLM 抽象层设计思路（OpenAI SDK 兼容，重试机制）
- FastAPI 后端框架骨架
- JSON 解析容错（`_repair` 截断修复）
- 写后验证器框架（规则引擎，但规则全部替换）
- 前端 UI 组件样式（按钮、卡片、布局配色）

### 砍掉了什么？
- 多线叙事系统（NarrativeThread, TimelineEvent）
- 伏笔生命周期管理（Hook 系统）
- 信息边界系统（KnownInfoRecord）
- 关系网络（RelationshipRecord）
- 因果链追踪（CausalLink）
- 情感弧线追踪（EmotionalSnapshot）
- 世界观配置（characters/world/events JSON）
- 大纲→章纲→细纲的三层结构
- 状态快照/回滚

---

## 技术架构

```
用户浏览器
  ↓ HTTP
FastAPI (app.py, port 8765)
  ↓ 调用
Pipeline (pipeline.py)
  ├── extract_material()   → LLM 提取素材要点
  ├── generate_outline()   → LLM 生成大纲 + 标题
  ├── generate_titles()    → LLM 单独生成标题
  ├── generate_content()   → LLM 分块写正文
  ├── format_html()        → LLM 生成排版 HTML
  ├── extract_style()      → LLM 分析写作风格
  └── run_full()           → 一键走完全部流程
  ↓ 调用
LLM (llm.py)
  └── DeepSeek / Ollama / 任意 OpenAI 兼容 API
  ↓ 返回后
Validator (validator.py)
  └── 11 项规则检测
```

### 数据存储
- **纯文件驱动**，无数据库
- `data/articles/{id}.json` — 每篇文章的完整数据
- `data/styles/{id}.json` — 风格克隆 profile
- `.env` — API 配置

### 前端
- **单文件 SPA** (`index.html`)，约 1200 行
- 暗色主题，无构建工具，无框架依赖
- 5 步流程条：选题 → 素材 → 大纲 → 正文 → 导出
- 关键交互点：
  - 标题候选点击选择
  - 大纲小节可编辑（弹窗）
  - 正文 textarea 可直接修改
  - 导出支持预览/HTML/纯文本

---

## 关键设计决策

### 1. 为什么分块生成？
一次性生成 3000 字，后半段质量会下降（LLM 的注意力衰减）。分块策略：
- 开头（150-300字）→ 各小节（按 word_budget）→ 结尾 + CTA（100-200字）
- 每块 Prompt 带入上一块最后 200 字（`prev_tail`），确保衔接

### 2. 风格克隆怎么做？
1. 用户上传 3-5 篇 .txt/.md 样本文章
2. 调用 LLM 分析：句式特征、惯用词汇、标点习惯、语调、结构风格
3. 保存为 `style_profile.json`
4. 后续生成时，将 profile 注入 Prompt 的「写作风格要求」section

### 3. 验证器规则
| 规则 | 级别 | 说明 |
|------|------|------|
| AI_MARKER | warning | "仿佛/忽然/竟然"等词，每3000字上限1次 |
| FORBIDDEN | error | "全场震惊/众所周知"等禁止句式 |
| META | warning | "核心动机/叙事节奏"等元叙事 |
| REPORT | warning | "分析了形势/综合考虑"等报告式语言 |
| COLLECTIVE | warning | "众人哗然/所有人齐声"等集体套话 |
| SENSITIVE | warning | 广告法违禁词/平台敏感词 |
| LENGTH | warning | 字数不符合平台建议 |
| LONG_PARA | warning | 段落超300字影响手机阅读 |
| CONSECUTIVE_LE | warning | 连续6句含"了"字 |

---

## 开发进度

### ✅ 已完成（2026-04-23）
- **多轮修订** — 人机共创核心能力
  - `Pipeline.revise_content()` — 全局/局部修订（指定小节只改那一段）
  - `POST /api/revise` — 执行修订
  - `POST /api/revise/suggest` — 根据验证结果智能推荐修改方向
  - 前端 Step 4 修订面板：快捷建议按钮、自定义意见、小节选择、修订历史+撤销
  - 修订历史持久化（保存/加载文章时一并存储）
- **JSON 解析修复** — DeepSeek 弯引号（`""`）导致 `json.loads` 崩溃
  - `llm.py` 新增 `_fix_smart_quotes()` 状态机，按字符串边界精准替换

### 🔜 下一步计划（按优先级）

#### P0：手动参考链接抓取（信息源）
> 新媒体写作的灵魂是信息源。当前 AI 凭空编，写出来没有信息增量。

**方案（最简版）：**
- 前端增加「参考链接」输入框（支持粘贴 1-3 个 URL）
- 后端新增 `POST /api/fetch-references` 端点
  - 用 `httpx` 抓取网页 → 提取正文（`readability` 或 `trafilatura`）
  - 调用 LLM 从抓取内容中提取核心事实、数据、金句
  - 返回结构化的参考素材，注入后续大纲/正文生成的 prompt
- 比全自动 RAG 简单得多，但已经能让文章有信息增量

**关键文件：** `app.py`（新端点）、`pipeline.py`（新方法）、`index.html`（Step 2 素材区改造）

#### P1：排版模板（交付质量）
> 公众号读者在手机上看，排版直接影响完读率。当前只有暗色预览，实际发公众号需要亮色清爽样式。

**方案：**
- 新增 `templates/` 目录，存放不同排版风格的 HTML/CSS 模板
- 至少 3 种风格：简约白、活泼彩、商务灰
- `pipeline.py` 的 `format_html()` 改为接收模板参数
- 前端导出步骤增加「排版风格」选择器
- 模板用内联 CSS（公众号编辑器不支持外部样式表）

**关键文件：** `templates/`（新目录）、`pipeline.py`（`format_html` 改造）、`app.py`（模板列表端点）、`index.html`（Step 5 模板选择）

---

## 已知问题 & 待优化

### 已知问题
1. **标题候选前缀混入** — AI 有时输出"标题方案1（爆款型）：xxx"，Pipeline 已加清理逻辑但可能不完美
2. **风格提取样本格式** — 目前只支持 .txt/.md，不支持 .docx/.pdf
3. **无持久化用户系统** — 所有数据本地文件存储，无登录/多用户

### 其他待做方向
- **敏感词库扩充** — 当前只有基础库，可接入平台官方违禁词列表
- **图片建议** — 在合适位置建议配图，甚至生成配图描述
- **批量生成** — 输入多个主题，批量出稿
- **SEO 优化** — 针对头条的搜索推荐算法优化关键词密度
- **查重预警** — 检测生成内容是否与网上已有文章过于相似

---

## 快速上手（给接班人）

```bash
# 1. 克隆
git clone https://github.com/ZTNIAN/inkflow.git
cd inkflow

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 启动
python3 app.py

# 5. 打开浏览器
# http://localhost:8765
```

---

## 代码入口速查

| 想改什么 | 看哪个文件 | 关键函数/类 |
|----------|-----------|-------------|
| API 端点 | `app.py` | `@app.post("/api/...")` |
| 管线流程 | `pipeline.py` | `Pipeline.run_full()` |
| 大纲生成逻辑 | `pipeline.py` | `Pipeline.generate_outline()` |
| 正文生成逻辑 | `pipeline.py` | `Pipeline.generate_content()` |
| **多轮修订** | `pipeline.py` | `Pipeline.revise_content()` |
| **修订建议** | `app.py` | `POST /api/revise/suggest` |
| LLM 调用 | `llm.py` | `LLM.complete()` |
| **JSON 解析/弯引号修复** | `llm.py` | `parse_json()` / `_fix_smart_quotes()` |
| 验证规则 | `validator.py` | `Validator.validate()` |
| 前端界面 | `index.html` | `<script>` 部分的 JS 函数 |
| **前端修订面板** | `index.html` | `doRevise()` / `quickRevise()` / `loadSuggestions()` |
| 配置 | `.env` | `DEEPSEEK_*` 变量 |

---

## 联系 & 背景

- 基于 [dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow) 改造
- 使用 DeepSeek API 作为默认 LLM 后端
- 项目创建时间：2026-04-23
