# InkFlow — AI 写作工坊

> 公众号 / 头条文章的一站式 AI 写作工具。从选题到排版，人机共创。

InkFlow 不是"AI 帮你写文章"，而是一个人机共创的工作台：AI 负责发散和干脏活（生成候选标题、写初稿），人类负责做核心决策（选标题、调大纲、改正文）。

## ✨ 功能特性

### 核心流程（5 步）
- **🎯 智能选题** — 输入主题，AI 生成 5-10 个爆款标题候选（带评分）
- **📚 素材注入** — 粘贴对标文章或参考链接，AI 提取核心事实/观点/金句
- **📋 人机共创大纲** — AI 生成结构 + 标题候选，你来选择和修改（支持拖拽排序）
- **✍️ 分块正文生成** — 带上下文衔接，SSE 流式输出实时显示进度
- **📐 排版导出** — 3 种排版风格，一键生成公众号 HTML / Word / 纯文本

### 高级功能
- **🔍 文章审计** — 六维度评分（AI 味/敏感词/内容质量/可读性/互动性/平台适配）
- **🔄 多轮修订** — 全局修订 + 单节重写，智能建议 + 自定义修改意见
- **🎨 风格克隆** — 上传样本文章，克隆你的写作风格
- **🔗 参考链接抓取** — 粘贴 URL，自动抓取网页内容提取素材
- **🖼️ 配图建议** — 智能推荐配图位置 + Midjourney 风格 AI 绘图 prompt
- **📊 SEO 优化** — 头条搜索关键词分析 + 优化建议
- **📦 批量生成** — 输入多个主题，批量出大纲（最多 10 篇）
- **📄 导出 Word** — 一键导出 .docx 文档

### 体验优化
- **🌓 暗/亮主题切换** — 右上角按钮，localStorage 持久化
- **⌨️ 快捷键** — `Ctrl+S` 保存、`Ctrl+Enter` 生成、`N` 新文章、`Esc` 关弹窗
- **💾 自动保存** — 编辑 5 秒后自动存草稿
- **📜 版本管理** — 每次保存内容变化自动存档旧版本，可回退
- **📋 复制文章** — 一键克隆已有文章作为新草稿
- **🏷️ 标签管理** — 文章标签 + 按标签筛选 + 写作统计面板
- **📊 字数目标指示器** — 实时进度条 + 颜色标识

### 写后验证（13 项规则）
AI 标记词 · 禁止句式 · 元叙事 · 报告式语言 · 集体套话 · 敏感词/广告法违禁词 · 字数检查 · 段落过长 · 连续"了"字 · AI 填充词 · 重复表达 · 感叹号过多 · 段落单调

### 文章模板（5 种结构）
清单体 · 对比测评 · 情感故事 · 争议观点 · 教程指南

### 排版模板（3 种风格）
简约白（干货/知识类） · 活泼彩（情感/故事类） · 商务灰（商业/测评类）

## 🚀 快速开始

```bash
# 1. 克隆
git clone https://github.com/ZTNIAN/inkflow.git
cd inkflow

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 启动
python3 app.py

# 5. 打开浏览器
# http://localhost:8765
```

## 📡 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/settings` | 获取配置 |
| POST | `/api/settings` | 保存配置 |
| GET | `/api/articles` | 文章列表 |
| GET | `/api/articles/{id}` | 文章详情 |
| POST | `/api/articles/save` | 保存文章 |
| DELETE | `/api/articles/{id}` | 删除文章 |
| POST | `/api/articles/{id}/copy` | 复制文章 |
| GET | `/api/articles/{id}/versions` | 版本历史 |
| GET | `/api/articles/{id}/versions/{file}` | 版本详情 |
| GET | `/api/articles/tag/{tag}` | 按标签筛选 |
| GET | `/api/tags` | 标签列表 |
| GET | `/api/stats` | 写作统计 |
| GET | `/api/templates` | 文章模板列表 |
| GET | `/api/styles` | 风格列表 |
| POST | `/api/styles/extract` | 提取写作风格 |
| POST | `/api/extract-material` | 提取素材要点 |
| POST | `/api/fetch-references` | 抓取参考链接 |
| POST | `/api/generate/outline` | 生成大纲 |
| POST | `/api/generate/titles` | 生成标题 |
| POST | `/api/generate/content` | 生成正文（普通） |
| POST | `/api/generate/content/stream` | 生成正文（SSE 流式） |
| POST | `/api/generate/section` | 单节重新生成 |
| POST | `/api/generate/batch` | 批量生成大纲 |
| POST | `/api/generate/full` | 一键完整生成 |
| POST | `/api/revise` | 多轮修订 |
| POST | `/api/revise/suggest` | 修订建议 |
| POST | `/api/validate` | 写后验证 |
| POST | `/api/audit` | 文章综合审计 |
| POST | `/api/format` | 排版生成 HTML |
| GET | `/api/format/templates` | 排版模板列表 |
| POST | `/api/export/docx` | 导出 Word |
| POST | `/api/suggest-images` | 配图建议 |
| POST | `/api/seo` | SEO 优化建议 |

## 🏗️ 项目结构

```
inkflow/
├── app.py              # FastAPI 服务（35+ API 端点）
├── pipeline.py         # 核心管线（素材→大纲→正文→验证→排版→审计）
├── llm.py              # LLM 抽象层（DeepSeek/Ollama/OpenAI 兼容）
├── validator.py        # 写后验证器（13 项规则检测）
├── index.html          # 前端 SPA（单文件，暗/亮主题）
├── requirements.txt    # Python 依赖
├── .env.example        # 配置模板
├── .gitignore
├── README.md           # 本文件
├── HANDOFF.md          # 项目交接文档
├── LICENSE
└── data/               # 运行时数据（git 不追踪）
    ├── articles/       # 已生成的文章 JSON
    │   └── {id}/
    │       └── versions/  # 版本历史
    └── styles/         # 风格克隆 profile JSON
```

## 🔧 技术栈

- **后端**: Python 3.10+ / FastAPI / Uvicorn
- **前端**: 原生 HTML/CSS/JS（单文件 SPA，无构建工具）
- **LLM**: DeepSeek API（兼容 Ollama / 任意 OpenAI 兼容接口）
- **存储**: 纯文件驱动（JSON），无数据库依赖

## 📋 设计原则

1. **人机共创** — AI 发散，人做决策，每步可干预
2. **不过度工程** — 2000 字单篇文章不需要 RAG/向量数据库
3. **信息源驱动** — 素材输入 > 无中生写
4. **分块生成** — 避免长文后半段质量下降
5. **写后验证** — 13 项规则去 AI 味 + 敏感词 + 平台规范

## License

MIT
