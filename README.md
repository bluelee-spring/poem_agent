# 诗千家智能体 (Poem Agent)

LLM 驱动的古典诗歌创作 Agent —— 基于 [诗千家](https://poem.pkudh.org) API + [搜韵网](https://cnkgraph.com) 格律校验，由 DeepSeek V4 作为决策核心，接入飞书 Bot 实现「热点采集 → 批量创作 → 自动入库 → 工作群推送」全流程闭环。

## 快速开始

```bash
pip install -e .                    # 安装依赖
cp .env.template .env               # 复制配置模板
# 编辑 .env 填入 API Key（至少需要 LLM_API_KEY）
```

```bash
# 飞书 Bot（最常用）
python -m src.main feishu --mode both    # 接收消息 + 每天定时批量创作

# 终端交互模式
python -m src.main agent                 # 对话写诗
python -m src.main hot -n 20             # 看热搜
```

## 核心能力

| 能力 | 说明 |
|------|------|
| 🔥 热搜采集 | 百度热搜（含新闻摘要）+ 微博热搜，双源去重 |
| 🤖 LLM 决策 | DeepSeek V4 自主筛选话题、规划参数、评鉴作品 |
| ✍️ 诗歌生成 | 调用诗千家 API，支持 8 大类 43 种体裁 |
| 📐 格律校验 | 搜韵网 API，逐字平仄标注、韵脚检测、对仗检查 |
| 📊 飞书入库 | 6 项结构化数据写入 Wiki 多维表格 |
| ⏰ 定时推送 | 每天定时自动批量创作 20 首 → 转发工作群 |
| 💬 飞书 Bot | 私聊/群聊 @机器人，发「创作」立即触发 |

## 架构

```
用户（飞书 App / CLI 终端 / 定时任务）
              │
              ▼
     ┌─────────────────┐
     │  Agent Controller│  ← LLM 大脑（DeepSeek V4）
     └────────┬────────┘
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
热搜采集    诗千家 API   搜韵网 API
(百度+微博)  (生成诗歌)   (格律校验)
   │          │          │
   └──────────┼──────────┘
              ▼
     ┌─────────────────┐
     │  飞书多维表格     │  ← 6 项数据写入
     │  (Wiki Bitable)  │
     └─────────────────┘
```

## 项目结构

```
src/
├── agent/          Agent 控制器 + Skill 加载
├── llm/            LLM Provider 抽象层（DeepSeek / OpenAI）
├── tools/          Tool 层（7 个工具，schema + registry + handlers）
├── api/            诗千家 API 封装（生成/认证/韵部查询）
├── skills/         可插拔技能包（hot_topic_poem）
├── feishu/         飞书 Bot 全套
│   ├── bot.py           双模式 Bot（WebSocket/HTTP + 消息路由）
│   ├── client.py        飞书 API（消息/Wiki/Bitable）
│   ├── batch_creator.py 批量创作（搜热点→筛选→生成→校验→评鉴→入库）
│   └── scheduler.py     定时任务调度器
├── memory/         本地历史 + 偏好统计
├── config/         配置 + Prompt 模板 + 日志
└── main.py         CLI 入口
```



## 配置 (.env)

```bash
# 飞书
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_WIKI_TOKEN=xxx               #飞书知识库
FEISHU_TABLE_ID=xxxxx               #飞书多维表格
FEISHU_FORWARD_CHAT_ID=oc_xxx       # 转发到工作群（可选）
FEISHU_SCHEDULE_ENABLED=true
FEISHU_SCHEDULE_TIME=10:00          #定时事件

# 诗千家 + LLM
POEM_ACCESS_TOKEN=xxx               # python -m src.main auth 获取
LLM_API_KEY=sk-xxx                  # https://platform.deepseek.com/api_keys
LLM_PROVIDER=deepseek
```

## 技术栈

- Python 3.10+
- DeepSeek V4 / OpenAI API
- httpx + aiohttp (HTTP)
- BeautifulSoup4 + lxml (热搜 HTML 解析)
- lark-oapi (飞书 SDK)
- Rich (终端美化)
- Pydantic (数据校验)

## License

MIT
