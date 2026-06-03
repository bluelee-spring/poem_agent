# 诗千家智能体 (Poem Agent)

LLM 驱动的古典诗歌创作 Agent —— 基于 [诗千家](https://poem.pkudh.org) API，由 DeepSeek V4 作为决策核心，自动完成热搜采集 → 主题提炼 → 参数规划 → 诗歌生成 → 专业评鉴的全流程。

## 架构

```
用户输入 → LLM Brain (DeepSeek V4)
              │
              ├─ search_hot_topics  微博/百度热搜
              ├─ web_search         DuckDuckGo 网页搜索
              ├─ get_references     韵部/场景参考数据
              ├─ generate_poem      调用诗千家 API 生成
              ├─ save_poem          保存到本地历史
              └─ get_history        查询创作历史
```

**三层设计:**
- **LLM Provider 层** — 统一接口，支持 DeepSeek / OpenAI 切换
- **Tool 层** — schema（JSON Schema）+ registry（注册中心）+ handlers（执行）
- **Memory 层** — 创作历史 + 用户偏好统计

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.template .env
# 编辑 .env 填入 API Key
```

必需配置：
- `POEM_ACCESS_TOKEN` — 诗千家 API Token（运行 `poem-agent auth` 获取）
- `LLM_API_KEY` — LLM API Key（[DeepSeek](https://platform.deepseek.com/api_keys) 或 OpenAI）
- `LLM_PROVIDER` — `deepseek`（默认）或 `openai`

### 3. 运行

```bash
# 交互模式（LLM 驱动的 Agent 循环）
python -m src.main agent

# 单次创作
python -m src.main agent -t "写一首关于人工智能的诗"

# 采集热点
python -m src.main hot -n 15

# 查看历史
python -m src.main history -n 5
```

## 项目结构

```
src/
├── llm/           LLM Provider 抽象层（base/deepseek/openai/factory）
├── config/        配置 + Prompt 模板 + 日志
├── tools/         Tool 层（schema + registry + handlers）
│   ├── schema/    6 个工具 JSON Schema 定义
│   └── handlers/  工具实现
├── memory/        Memory 层（历史记录 + 用户偏好）
├── agent/         Agent 控制器 + 旧 Pipeline 模块（兼容）
├── api/           诗千家 API 封装（认证/客户端/诗歌/参考数据）
└── main.py        CLI 入口

data/              运行时数据（history.json / preference.json / app.log）
scripts/           辅助脚本（认证采集、API 探测）
```

## 技术栈

- Python 3.10+
- DeepSeek V4 / OpenAI API
- httpx (HTTP), Rich (终端美化), Pydantic (数据校验)
- BeautifulSoup4 + lxml (热搜解析)
- DuckDuckGo API (网页搜索)

## License

MIT
