<div align="center">

# ✍️ InkFlow

### AI 公众号 / 头条文章生成器

**从选题到排版的一站式写作工具**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[快速开始](#-快速开始5分钟跑起来) · [工作原理](#-工作原理) · [功能特性](#-功能特性) · [操作手册](#-小白操作手册) · [项目结构](#-项目结构)

</div>

---

## InkFlow 是什么？

InkFlow 是一款 **AI 驱动的新媒体文章生成工具**，专注于公众号和头条图文的创作。

它不是简单的"AI 帮你写文章"，而是一个**人机共创的工作台**：AI 负责发散和干脏活（生成候选标题、写初稿），人类负责做核心决策（选标题、调大纲、改正文）。

### 与普通 AI 写作工具的区别

| | 普通 AI 写作工具 | **InkFlow** |
|---|---|---|
| 工作模式 | 输入主题 → 一键出稿（黑盒） | **5 步流程，每步可干预** |
| 标题 | AI 给一个标题 | **5-10 个候选 + 爆款评分，你来选** |
| 大纲 | 不可见或不可改 | **可视化编辑，可增删改拖拽** |
| 素材 | 无中生有 | **支持粘贴对标文章，AI 提取核心信息** |
| 风格 | "请用幽默风格"（没用） | **上传你的文章样本，克隆真实写作风格** |
| 去 AI 味 | 无 | **11 项规则检测 + 敏感词过滤** |
| 平台适配 | 公众号/头条不分 | **双模式：公众号深度文 / 头条信息流** |

---

## 🏗️ 工作原理

### 整体架构

```
┌─────────────────────────────────────────────────┐
│                  Web UI (SPA)                    │
│   5 步流程 · 人机共创 · 实时预览 · 排版导出       │
├─────────────────────────────────────────────────┤
│                REST API (FastAPI)                 │
│   20+ 端点 · 选题/大纲/正文/验证/排版/风格        │
├─────────────────────────────────────────────────┤
│                 核心管线 (Pipeline)                │
│   素材清洗 → 大纲生成 → 分块写作 → 验证 → 排版    │
├─────────────────────────────────────────────────┤
│                 LLM 抽象层                        │
│   DeepSeek / Ollama / 任意 OpenAI 兼容接口        │
├─────────────────────────────────────────────────┤
│                 写后验证器                         │
│   AI 标记词 · 禁止句式 · 敏感词 · 平台规范         │
└─────────────────────────────────────────────────┘
```

### 5 步创作流程

```
Step 1: 选题输入
  └─ 输入主题 → 选择平台(公众号/头条) → 选择类型(干货/争议/故事/测评)
       ↓
Step 2: 素材注入（可选）
  └─ 粘贴对标文章 → AI 提取核心事实/观点/金句/数据
       ↓
Step 3: 大纲生成（人机共创 ⭐）
  └─ AI 生成大纲 + 5-10 个标题候选
  └─ 用户选择标题 → 编辑/增删小节 → 确认后继续
       ↓
Step 4: 正文生成
  └─ 分块生成（开头 → 各小节 → 结尾）
  └─ 每块带入上一块最后 200 字做衔接（全局上下文视窗）
  └─ 自动生成后立即验证（去 AI 味 + 敏感词）
       ↓
Step 5: 排版导出
  └─ 生成公众号适配 HTML → 预览/复制 HTML/复制纯文本
```

### 关键设计决策

**Q: 为什么不用 RAG / 向量数据库？**
A: 公众号文章 1500-3000 字，DeepSeek 单次上下文完全 hold 得住。用 JSON 状态机追踪一篇短文是过度工程。在 Prompt 里写"确保起承转合"比写 1000 行代码追踪情绪曲线有效得多。

**Q: 为什么要分块生成？**
A: 一次性生成 3000 字，后半段质量会下降。分块 + 上下文衔接既保证质量，又保持连贯。

**Q: 风格克隆是怎么做的？**
A: 用户上传 3-5 篇自己写的文章 → AI 分析句式特征、惯用词汇、标点习惯 → 保存为 style_profile.json → 后续生成时注入 Prompt。

---

## ✨ 功能特性

### 核心功能
- 🎯 **智能选题** — 输入主题，AI 自动生成 5-10 个爆款标题候选
- 📚 **素材清洗** — 粘贴对标文章，AI 提取事实、观点、金句
- 📋 **人机共创大纲** — AI 生成结构，你来选择和修改
- ✍️ **分块正文生成** — 带上下文衔接，避免割裂感
- 🔍 **写后验证** — 11 项规则检测（去 AI 味 + 敏感词 + 平台规范）
- 📐 **一键排版** — 生成公众号编辑器兼容的 HTML
- 🎨 **风格克隆** — 上传样本文章，克隆你的写作风格

### 平台适配
- 📱 **公众号模式** — 1500-3000 字深度文，情绪共鸣 + 排版留白
- 📰 **头条模式** — 800-2000 字信息流，争议点 + 接地气语言

### 文章类型
- 💡 **干货型** — 方法论 / 步骤清单 / 工具推荐
- 🔥 **争议型** — 反常识观点 / 引发讨论
- 📖 **故事型** — 真实案例 / 情感共鸣
- ⚖️ **测评型** — 对比分析 / 帮读者做决策

---

## 🚀 快速开始（5分钟跑起来）

### 环境要求
- Python 3.10+
- DeepSeek API Key（[去申请](https://platform.deepseek.com)）

### 安装

```bash
# 克隆项目
git clone https://github.com/ZTNIAN/inkflow.git
cd inkflow

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

### 启动

```bash
python3 app.py
```

然后打开浏览器访问 **http://localhost:8765**

### 使用 Ollama（免费本地模型）

```bash
# 安装 Ollama: https://ollama.ai
ollama pull qwen2.5

# 修改 .env
DEEPSEEK_API_KEY=ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
DEEPSEEK_MODEL=qwen2.5
```

---

## 📖 小白操作手册

### 第一步：创建文章
1. 打开网页，点击右上角 **「+ 新文章」**
2. 在「主题」框输入你想写的选题，例如：`为什么恋爱中的女生越来越「作」？`
3. 选择平台：**公众号**（长文）或 **头条**（短文）
4. 选择类型：**干货型 / 争议型 / 故事型 / 测评型**

### 第二步：添加素材（可选但推荐）
1. 如果你有对标文章（别人写的爆款），把正文粘贴到素材框
2. 点击 **「🔍 提取素材要点」**
3. AI 会提取核心事实、观点、金句供后续使用

### 第三步：调整大纲（最重要的一步！）
1. AI 会自动生成文章结构和 5 个标题候选
2. **点击选择你喜欢的标题**（或点「自定义标题」自己写）
3. 查看文章结构，点击 **「✏️ 编辑」** 可修改每个小节
4. 确认无误后点击 **「✍️ 确认大纲，开始写正文」**

> ⚠️ **这一步是人机共创的核心！** 不要跳过。花 2 分钟调整大纲，能大幅提升最终质量。

### 第四步：查看正文
1. AI 分块生成正文，自动衔接
2. 生成后会自动验证（去 AI 味 + 敏感词检测）
3. 你可以直接在编辑框里修改文字
4. 不满意可以点 **「🔄 重新生成正文」**

### 第五步：导出使用
1. 点击 **「📐 生成排版」** 生成公众号适配 HTML
2. 切换到「📱 预览」查看手机端效果
3. 点击 **「📋 复制 HTML」**
4. 打开公众号后台 → 新建图文 → 切换到 HTML 模式 → 粘贴

---

## 📁 项目结构

```
inkflow/
├── app.py              # FastAPI 服务（20+ API 端点）
├── pipeline.py         # 核心管线（素材→大纲→正文→验证→排版）
├── llm.py              # LLM 抽象层（DeepSeek/Ollama/OpenAI兼容）
├── validator.py        # 写后验证器（11项规则检测）
├── index.html          # 前端 SPA（单文件，暗色主题）
├── requirements.txt    # Python 依赖
├── .env.example        # 配置模板
├── .gitignore
├── README.md           # 本文件
├── HANDOFF.md          # 项目交接文档
└── data/               # 运行时数据（git 不追踪）
    ├── articles/       # 已生成的文章 JSON
    └── styles/         # 风格克隆 profile JSON
```

### API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取配置 |
| POST | `/api/settings` | 保存配置 |
| GET | `/api/articles` | 文章列表 |
| GET | `/api/articles/{id}` | 文章详情 |
| POST | `/api/articles/save` | 保存文章 |
| DELETE | `/api/articles/{id}` | 删除文章 |
| GET | `/api/styles` | 风格列表 |
| POST | `/api/styles/extract` | 上传样本提取风格 |
| POST | `/api/extract-material` | 从素材提取要点 |
| POST | `/api/generate/outline` | 生成大纲 |
| POST | `/api/generate/titles` | 生成标题候选 |
| POST | `/api/generate/content` | 生成正文 |
| POST | `/api/generate/full` | 一键完整生成 |
| POST | `/api/format` | 排版生成 HTML |
| POST | `/api/validate` | 写后验证 |

---

## 🔧 配置说明

编辑 `.env` 文件：

```env
# DeepSeek 配置（推荐）
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-你的密钥

# Ollama 配置（免费，本地运行）
# DEEPSEEK_API_KEY=ollama
# DEEPSEEK_BASE_URL=http://localhost:11434/v1
# DEEPSEEK_MODEL=qwen2.5
```

---

## 📄 License

MIT License

---

## 🙏 致谢

- [DeepSeek](https://platform.deepseek.com) — 大模型 API
- [FastAPI](https://fastapi.tiangolo.com) — Web 框架
- [Ollama](https://ollama.ai) — 本地模型运行时
