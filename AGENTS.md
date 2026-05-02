# AGENTS.md

此文件为 AI 编码助手（OpenCode、Claude Code、Cursor 等）提供工作指导。

## 项目概览

InkFlow — AI 写作工坊。Python FastAPI + 原生 HTML/CSS/JS SPA。从选题到排版，人机共创。

## OpenCode Skill 集成

本仓库启用了 addyosmani/agent-skills 的全部 20 个技能 + mattpocock/skills 的 6 个技能，位于全局 `~/.config/opencode/skills/`。

### 核心规则

- 如果某个任务匹配 skill，**必须**调用它
- Skill 位于 `skills/<skill-name>/SKILL.md`（全局目录）
- 永不跳过 skill 直接实现
- 严格遵循 skill 指令（不得部分执行）

### 意图 → Skill 映射

| 用户意图 | 自动激活的 Skill |
|---------|-----------------|
| 新功能 / 新特性 | `spec-driven-development` → `incremental-implementation` + `tdd` |
| 对齐需求 / 梳理方案 | `grill-me`（mattpocock） |
| 规划 / 分解任务 | `planning-and-task-breakdown` |
| Bug / 异常行为 | `diagnose`（mattpocock）→ `debugging-and-error-recovery` |
| 代码审查 | `code-review-and-quality` |
| 重构 / 简化 | `code-simplification` |
| API 或接口设计 | `api-and-interface-design` |
| UI 工作 | `frontend-ui-engineering` |
| 安全相关 | `security-and-hardening` |
| 性能优化 | `performance-optimization` |
| Git / 版本管理 | `git-workflow-and-versioning` |
| 部署上线 | `shipping-and-launch` |
| CI/CD | `ci-cd-and-automation` |
| 弃用 / 迁移 | `deprecation-and-migration` |
| 文档 / 架构决策 | `documentation-and-adrs` |
| 省 token / 长 session | `caveman`（mattpocock，按需） |

### 生命周期映射

OpenCode 不支持 `/spec`、`/plan` 等斜杠命令。agent 必须内部遵循以下生命周期：

- **DEFINE** → `spec-driven-development`
- **PLAN** → `planning-and-task-breakdown`
- **BUILD** → `incremental-implementation` + `tdd`
- **VERIFY** → `diagnose` → `debugging-and-error-recovery`
- **REVIEW** → `code-review-and-quality`
- **SHIP** → `shipping-and-launch`

### 执行模型

对每个请求：

1. 判断是否有 skill 适用（哪怕只有 1% 可能）
2. 优先检查 mattpocock skill（grill-me/diagnose 等前置 skill），再检查 agent-skills
3. 使用 `skill` 工具调用合适的 skill
4. 严格遵循 skill 工作流
5. 只有在必需步骤完成后才进入实现

### 反合理化

以下想法是**错误的**，必须忽略：
- "这个太小了，不需要 skill"
- "我可以快速实现一下"
- "我先收集上下文"

**正确行为**：
- 始终先检查和加载 skill

## 技术栈

- 后端: Python 3.10+ / FastAPI / Uvicorn
- 前端: 原生 HTML/CSS/JS（单文件 SPA）
- LLM: DeepSeek API（兼容 Ollama / OpenAI 兼容接口）
- 存储: 纯文件驱动（JSON）
- 测试: pytest + pytest-asyncio + httpx
