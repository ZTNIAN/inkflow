# InkFlow — AI 写作工坊

> 公众号 / 头条文章的一站式 AI 写作工具。从选题到排版，人机共创。

InkFlow 不是"AI 帮你写文章"，而是一个人机共创的工作台：AI 负责发散和干脏活（生成候选标题、写初稿），人类负责做核心决策（选标题、调大纲、改正文）。

## ✨ 功能特性

### 核心流程（5 步）
- **🎯 智能选题** — 输入主题，AI 生成 5-10 个爆款标题候选（带评分）
- **📚 素材注入** — 粘贴对标文章或参考链接，AI 提取核心事实/观点/金句
- **📋 人机共创大纲** — AI 生成结构 + 标题候选，你来选择和修改（支持拖拽排序）
- **✍️ 分块正文生成** — 带上下文衔接，SSE 流式输出实时显示进度，**初次生成即包含 AI 避坑规则**，大幅减少 AI 味
- **📐 排版导出** — 3 种排版风格，一键生成公众号 HTML / Word / 纯文本

### 高级功能
- **🔍 文章审计** — 八维度评分（AI味/敏感词/内容质量/可读性/认知差/表达效率/互动性/平台适配）
- **📝 审计一键修订** — 审计结果直接驱动 AI 批量修文，所有问题打包一次 LLM 解决
- **🔄 多轮修订** — 全局修订 + 单节重写，智能建议 + 自定义修改意见
- **🎨 风格克隆 v2** — 上传样本文章，克隆写作风格（含思维指纹/论证逻辑/修辞偏好 + 量化统计 + 原文范文）
- **🔗 参考链接抓取** — 粘贴 URL，自动抓取网页内容提取素材
- **📚 对标素材/参考链接任一或全选** — 素材阶段支持对标文章粘贴、URL 抓取、或两者合并
- **🖼️ 配图建议** — 智能推荐配图位置 + Midjourney 风格 AI 绘图 prompt
- **📊 SEO 优化** — 头条搜索关键词分析 + 优化建议
- **📦 批量生成** — 输入多个主题，批量出大纲（最多 10 篇），支持风格选择
- **📄 导出 Word** — 一键导出 .docx 文档

### 平台差异化
- **公众号** — 社交分发优化，1500-3000字，注重深度/共鸣/排版留白
- **头条** — 算法推荐优化，800-2000字，注重信息增量/接地气
- 验证器/生成 prompt/审计维度全链路按平台区分

### 写后验证（17 项规则）
AI 标记词 · 禁止句式 · 元叙事 · 报告式语言 · 集体套话 · 敏感词/广告法违禁词 · 字数检查 · 段落过长 · 连续"了"字 · AI 填充词 · 重复表达 · 感叹号过多 · 段落单调 · **替读者问问题** · **祝福式结尾** · **假故事开头** · **专家腔**

### 文章模板（5 种结构）
清单体 · 对比测评 · 情感故事 · 争议观点 · 教程指南

### 排版模板（3 种风格）
简约白（干货/知识类） · 活泼彩（情感/故事类） · 商务灰（商业/测评类）

### 体验优化
- **🌓 暗/亮主题切换** — 右上角按钮，localStorage 持久化
- **⌨️ 快捷键** — `Ctrl+S` 保存、`Ctrl+Enter` 生成、`N` 新文章、`Esc` 关弹窗
- **💾 自动保存** — 编辑 5 秒后自动存草稿
- **📜 版本管理** — 每次保存内容变化自动存档旧版本，可回退
- **📋 复制文章** — 一键克隆已有文章作为新草稿
- **🏷️ 标签管理** — 文章标签 + 按标签筛选 + 写作统计面板
- **📊 字数目标指示器** — 实时进度条 + 颜色标识
- **☑️ 批量操作** — 勾选多篇文章，批量删除/复制
- **🔍 文章搜索** — 按主题/标题/标签实时过滤
- **📱 平台筛选** — 按公众号/头条筛选文章列表

### 回收站
- 删除文章移入回收站而非直接删除
- 支持逐篇恢复和清空回收站
- 侧边栏底部显示回收站计数

## 🚀 快速开始

```bash
# 1. 克隆
git clone https://github.com/ZTNIAN/inkflow.git
cd inkflow

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key（需 DeepSeek API）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 启动
python app.py

# 5. 打开浏览器
# http://localhost:8765
```

## 📡 API 端点

### 文章管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/articles` | 文章列表 |
| GET | `/api/articles/{id}` | 文章详情 |
| POST | `/api/articles/save` | 保存文章（自动版本管理） |
| DELETE | `/api/articles/{id}` | 删除文章（移入回收站） |
| POST | `/api/articles/{id}/copy` | 复制文章 |
| GET | `/api/articles/{id}/versions` | 版本历史 |
| GET | `/api/articles/{id}/versions/{file}` | 版本详情 |
| GET | `/api/articles/tag/{tag}` | 按标签筛选 |

### 回收站
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/trash` | 回收站列表 |
| POST | `/api/trash/{file}/restore` | 恢复文章 |
| POST | `/api/trash/empty` | 清空回收站 |

### 标签 & 统计
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tags` | 标签列表 |
| GET | `/api/stats` | 写作统计 |

### 生成
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate/outline` | 生成大纲 |
| POST | `/api/generate/titles` | 生成标题 |
| POST | `/api/generate/content` | 生成正文（普通） |
| POST | `/api/generate/content/stream` | 生成正文（SSE 流式） |
| POST | `/api/generate/section` | 单节重新生成 |
| POST | `/api/generate/batch` | 批量生成大纲 |
| POST | `/api/generate/full` | 一键完整生成 |

### 素材 & 风格
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/extract-material` | 提取素材要点 |
| POST | `/api/fetch-references` | 抓取参考链接 |
| GET | `/api/styles` | 风格列表 |
| GET | `/api/styles/{id}` | 风格详情 |
| POST | `/api/styles/extract` | 提取写作风格 |

### 修订 & 审计
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/revise` | 多轮修订 |
| POST | `/api/revise/suggest` | 修订建议 |
| POST | `/api/validate` | 写后验证（17 项规则）|
| POST | `/api/audit` | 文章综合审计（8 维度）|

### 导出
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/format` | 排版生成 HTML |
| GET | `/api/format/templates` | 排版模板列表 |
| GET | `/api/templates` | 文章模板列表 |
| POST | `/api/export/docx` | 导出 Word |
| POST | `/api/suggest-images` | 配图建议 |
| POST | `/api/seo` | SEO 优化建议 |

### 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/settings` | 获取配置 |
| POST | `/api/settings` | 保存配置 |

## 🏗️ 项目结构

```
inkflow/
├── app.py              # FastAPI 服务（40+ API 端点）
├── pipeline.py         # 核心管线（素材→大纲→正文→验证→排版→审计）
├── llm.py              # LLM 抽象层 + JSON 解析容错（10 层修复策略）
├── validator.py        # 写后验证器（17 项规则检测）
├── index.html          # 前端 SPA（单文件，暗/亮主题）
├── requirements.txt    # Python 依赖
├── pytest.ini          # pytest 配置
├── .env.example        # 配置模板
├── AGENTS.md           # AI 编码助手工作指导
├── .gitignore
├── README.md           # 本文件
├── HANDOFF.md          # 项目交接文档
├── LICENSE
├── tests/              # 自动化测试（124 个用例）
│   ├── conftest.py     # 全局 fixture + LLM mock
│   ├── test_validator.py    # 验证器 17 项规则全覆盖
│   ├── test_llm_parse.py    # JSON 解析 10 层修复策略
│   ├── test_pipeline_unit.py # Pipeline 纯逻辑/静态方法
│   ├── test_api_basic.py    # API 基础端点
│   └── test_api_generate.py # 生成管线 API（mock LLM）
└── data/               # 运行时数据（git 不追踪）
    ├── articles/       # 已生成的文章 JSON
    │   └── {id}/
    │       └── versions/  # 版本历史
    ├── styles/         # 风格克隆 profile JSON
    └── trash/          # 回收站（删除的文章）
```

## 🧪 测试

```bash
pip install -r requirements.txt
pytest tests/ -v              # 全部 124 个用例
pytest tests/test_validator.py -v  # 仅验证器
```

| 测试文件 | 用例数 | 覆盖内容 |
|---------|--------|---------|
| `test_validator.py` | 20 | 17 项规则 + 分数计算 + 误杀防护 |
| `test_llm_parse.py` | 18 | JSON 修复策略链（弯引号/截断/尾逗号等）|
| `test_pipeline_unit.py` | 18 | 序列化/静态方法/持久化/边界条件 |
| `test_api_basic.py` | 17 | 健康检查/CRUD/版本管理/标签/风格 |
| `test_api_generate.py` | 14 | 验证/修订/大纲/审计/SEO/批量/mock LLM |

所有测试无需真实 API Key — 使用 mock LLM。

## 🔧 技术栈

- **后端**: Python 3.10+ / FastAPI / Uvicorn
- **前端**: 原生 HTML/CSS/JS（单文件 SPA，约 2500 行）
- **LLM**: DeepSeek API（兼容 Ollama / 任意 OpenAI 兼容接口）
- **存储**: 纯文件驱动（JSON），无数据库依赖
- **测试**: pytest + pytest-asyncio + httpx (FastAPI TestClient)

## 📋 设计原则

1. **人机共创** — AI 发散，人做决策，每步可干预
2. **不过度工程** — 单篇文章不需要 RAG/向量数据库
3. **信息源驱动** — 素材输入 > 无中生写
4. **分块生成** — 避免长文后半段质量下降
5. **写后验证** — 17 项规则去 AI 味 + 敏感词 + 平台规范
6. **首次生成即避坑** — 生成 prompt 内置 AI 痕迹规避清单

## License

MIT
