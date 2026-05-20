# Step2API

将 [阶跃星辰 (stepfun.com)](https://www.stepfun.com/) Web 对话能力转换为 OpenAI 兼容 API。

**重要免责声明**

本仓库仅供学习、研究、个人实验和内部验证使用，不提供任何形式的商业授权、适用性保证或结果保证。作者不对因使用、修改、分发、部署或依赖本项目而产生的任何直接或间接损失、账号封禁、数据丢失、法律风险或第三方索赔负责。请勿将本项目用于违反服务条款、协议、法律法规或平台规则的场景。

---

## 架构概览

```
Client (OpenAI SDK / 兼容客户端)
        │
        ▼
   Step2API (FastAPI)
        │
   ┌────┴────┐
   │ Account │  ← 多账号轮询 + 并发控制
   │  Pool   │
   └────┬────┘
        │
   ┌────┴────┐
   │ StepFun │  ← SMS 登录 / Token 刷新
   │  Auth   │
   └────┬────┘
        │
   ┌────┴────┐
   │  Chat   │  ← 会话管理 / 流式响应
   │ Session │
   └────┬────┘
        │
   ┌────┴────┐
   │StepFun  │  Connect/gRPC-Web API
   │Web Chat │
   └─────────┘
```

## 核心能力

| 能力 | 说明 |
|------|------|
| OpenAI 兼容 | `GET /v1/models`, `POST /v1/chat/completions` (流式 + 非流式) |
| 多账号轮询 | 自动 token 刷新、并发槽位 + 等待队列 |
| 鉴权模式 | API Key 托管模式 / 直通 Token 模式 |
| 模型别名 | 支持 gpt-4、claude-sonnet-4-6 等别名映射 |
| CORS 支持 | 统一允许跨域请求 |
| SMS 登录 | 支持 Admin API 触发短信验证码登录 |

## 快速开始

### 方式一：本地源码运行

```bash
# 1. 克隆仓库
git clone <repo_url> step2api
cd step2api

# 2. 安装依赖
pip install -e .

# 3. 配置
cp config.example.json config.json
# 编辑 config.json，填入你的 StepFun 账号信息

# 4. 启动
python -m step2api.main
# 或
step2api
```

默认访问地址：`http://127.0.0.1:5001`

### 方式二：uvicorn 直接启动

```bash
pip install -r requirements.txt
uvicorn step2api.main:app --host 127.0.0.1 --port 5001
```

## 配置说明

```jsonc
{
  "host": "127.0.0.1",
  "port": 5001,

  // API 密钥（客户端请求时使用）
  "keys": ["sk-step2api-your-secret-key"],
  "api_keys": [
    {"key": "sk-step2api-your-secret-key", "name": "default"}
  ],

  // 账号列表（StepFun 手机号）
  "accounts": [
    {"phone": "+86 13800138000", "name": "account1"}
  ],

  // 模型别名映射
  "model_aliases": {
    "gpt-4": "step-3.5-flash",
    "gpt-4o": "step-3.5-flash",
    "claude-sonnet-4-6": "step-3.5-flash",
    "claude-opus-4-6": "step-3.5-flash"
  },

  // 运行时配置
  "runtime": {
    "account_max_inflight": 2,  // 每账号最大并发数
    "account_max_queue": 4,     // 等待队列上限
    "token_refresh_interval": 600
  },

  // 对话自动清理
  "auto_delete": {
    "mode": "none"  // none / single / all
  },

  // 思考提示注入
  "thinking_injection": {
    "enabled": true,
    "prompt": ""
  }
}
```

## 鉴权模式

| 模式 | 说明 |
|------|------|
| 托管账号模式 | Bearer / x-api-key 传入 config.keys 中的 key，由服务自动轮询选择账号 |
| 直通 Token 模式 | 传入 token 不在 config.keys 中时，直接作为 StepFun token 透传 |

可选请求头 `X-Step2-Target-Account`：指定使用某个账号（值为 phone 或 name）。

## 使用示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-step2api-your-secret-key",
    base_url="http://127.0.0.1:5001/v1"
)

# 非流式
response = client.chat.completions.create(
    model="step-3.5-flash",
    messages=[
        {"role": "user", "content": "你好，请介绍一下阶跃星辰"}
    ]
)
print(response.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="step-3.5-flash",
    messages=[
        {"role": "user", "content": "写一首关于AI的诗"}
    ],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

```bash
# curl 非流式
curl http://127.0.0.1:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-step2api-your-secret-key" \
  -d '{
    "model": "step-3.5-flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# curl 流式
curl http://127.0.0.1:5001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-step2api-your-secret-key" \
  -d '{
    "model": "step-3.5-flash",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

## Admin API

| 端点 | 说明 |
|------|------|
| `GET /admin/queue/status` | 查看账号池并发状态 |
| `GET /admin/accounts` | 列出所有配置的账号 |
| `POST /admin/accounts/send-sms` | 为指定账号发送短信验证码 |
| `POST /admin/accounts/login` | 使用验证码完成登录 |

## 运行状况探测

| 端点 | 说明 |
|------|------|
| `GET /healthz` | 存活探针 |
| `GET /readyz` | 就绪探针 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `STEP2API_CONFIG_PATH` | 配置文件路径 | `config.json` |
| `STEP2API_CONFIG_JSON` | Base64编码的JSON配置 | - |
| `STEP2API_ADMIN_KEY` | Admin API Key | - |
| `STEP2API_HOST` | 监听地址 | `127.0.0.1` |
| `STEP2API_PORT` | 监听端口 | `5001` |
| `STEP2API_ACCOUNTS` | JSON格式的账号列表 | - |
| `STEP2API_ACCOUNT_MAX_INFLIGHT` | 每账号最大并发 | `2` |
| `STEP2API_ACCOUNT_MAX_QUEUE` | 等待队列上限 | `4` |

## 许可证

AGPL-3.0

本项目参考了 [ds2api](https://github.com/CJackHwang/ds2api) 的架构思路。
