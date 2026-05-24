# QuantA-Share —— AI驱动的A股量化分析平台

面向A股市场的智能量化选股与交易辅助系统，提供波段策略、短线情绪分析、持仓风控、AI对话复盘等功能。

## 项目结构

```
QuantA_Share/
├── backend/             # Python FastAPI 后端
│   ├── app/
│   │   ├── api/         # REST API 路由 (12个模块)
│   │   ├── core/        # 配置、数据库、安全
│   │   ├── models/      # SQLAlchemy 数据模型 (15个)
│   │   ├── schemas/     # Pydantic 校验模型 (13个)
│   │   └── services/    # 业务逻辑层 (数据/策略/AI/邮件/账单/风控)
│   ├── requirements.txt
│   └── .env.example     # 环境变量模板
├── 前端/                 # 前端页面 (纯静态HTML + ES模块)
│   ├── 选股看板.html
│   ├── AI对话.html
│   ├── 持仓风险.html
│   ├── 复盘日志.html
│   ├── 策略参数.html
│   ├── 付费中心.html
│   ├── 系统设置.html
│   ├── 登录.html
│   ├── 注册.html
│   └── js/              # JavaScript 模块
├── supabase/
│   └── migrations/      # PostgreSQL 迁移SQL (7个)
├── cloud_function/       # 云函数支付回调中转
│   ├── aliyun_relay.py  # 阿里云FC版本
│   └── tencent_relay.py # 腾讯云SCF版本
├── docs/                 # 文档
├── LICENSE
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 15+
- (可选) Docker + Docker Compose

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/你的账号/QuantA_Share.git
cd QuantA_Share

# 2. 安装后端依赖
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写必要配置（见下方配置说明）

# 4. 创建 PostgreSQL 数据库
psql -U postgres -c "CREATE DATABASE quanta_share;"

# 5. 运行数据库迁移
python run_sql_migrations.py

# 6. 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. 打开前端
# 方式一：后端直接托管 (后端启动后访问 http://localhost:8000)
# 方式二：用 VS Code Live Server 打开 前端/ 目录，访问 http://127.0.0.1:5500
```

### Docker 部署（生产环境）

```bash
# 1. 创建 docker-compose.yml（参考 DEPLOY.md）
# 2. 配置 .env
# 3. 启动
docker compose up -d --build
```

详见 [DEPLOY.md](./DEPLOY.md)

## 配置说明

编辑 `backend/.env` 文件，以下按重要程度排列：

### 必填配置

```env
# ── 数据库 ──
DATABASE_URL=postgresql+asyncpg://postgres:你的密码@127.0.0.1:5432/quanta_share

# ── JWT 鉴权 ──
JWT_SECRET=换一个随机字符串
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── 邮件验证码 ──
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=你的QQ邮箱@qq.com
SMTP_PASSWORD=你的QQ邮箱SMTP授权码
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=你的QQ邮箱@qq.com
```

### AI 模型配置（至少配置一个）

```env
# ── 主 AI（Nuwax Agent） ──
NUWAX_API_KEY=你的Nuwax密钥
NUWAX_BASE_URL=https://nuwax.com
NUWAX_AGENT_ID=/space/你的空间ID/agent/你的AgentID

# ── 备用 AI（DeepSeek） ──
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=60

# ── 第二备用 AI（GitHub Models） ──
GITHUB_MODELS_API_KEY=你的GitHub Token
GITHUB_MODELS_BASE_URL=https://models.github.ai/inference
GITHUB_MODELS_MODEL=openai/gpt-4o

# ── 联网搜索（可选） ──
TAVILY_API_KEY=你的Tavily密钥
BRAVE_API_KEY=你的Brave密钥
```

### 支付FM配置（可选，如需付费功能）

```env
ZHIFUFM_API_URL=https://你的接口根地址
ZHIFUFM_MERCHANT_NUM=你的商户号
ZHIFUFM_SECRET=你的接入密钥
ZHIFUFM_PAY_TYPE=aloop
ZHIFUFM_NOTIFY_URL=https://你的云函数地址/notify
BILLING_PUBLIC_BASE_URL=https://你的公网域名
ADMIN_SECRET=换一个管理员密钥
```

### 其他配置

```env
# CORS 跨域白名单（本地开发）
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500,null

# 前端页面基础地址（支付完成后跳转用）
FRONTEND_BASE_URL=http://127.0.0.1:5500
```

## API 接口

| 路径 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /api/v1/auth/email/send-code` | 发送邮箱验证码 |
| `POST /api/v1/auth/email/register` | 邮箱注册 |
| `POST /api/v1/auth/login` | 登录 |
| `GET /api/v1/stock-board/*` | 选股看板 |
| `GET /api/v1/market/*` | 市场行情数据 |
| `POST /api/v1/ai/chat` | AI 对话 |
| `GET /api/v1/portfolio/*` | 持仓管理 |
| `GET /api/v1/review/*` | 复盘日志 |
| `GET /api/v1/system/*` | 系统设置/状态 |
| `GET /api/v1/billing/plans` | 付费套餐 |
| `POST /api/v1/billing/orders` | 创建订单 |
| `POST /api/v1/billing/notify` | 支付回调 |

## 数据源

本项目使用 [BaoStock](http://baostock.com) 作为A股数据源，支持：

- 历史日/周/月/分钟K线数据
- 除权除息信息
- 季频财务数据（盈利/营运/成长/偿债/现金流）
- 宏观经济数据（利率/准备金率/货币供应）
- 指数成分股（上证50/沪深300/中证500）

详见 [数据集参考文档.md](./数据集参考文档.md)

## 策略说明

包含两套交易策略的量化规则：

- **波段策略**：依托均线趋势（5日线上穿所有均线）+ 7%放量突破信号，30%止盈/20日线止损
- **短线策略**：抓情绪龙头，分歧日介入，连板晋级率>30%，5%无条件止损

详见 [策略.md](./策略.md)

## 云函数部署（支付回调中转）

本项目使用 支付FM 作为支付网关，由于 支付FM 的回调IP限制，需要在国内云函数上部署中转服务：

```bash
# 将 cloud_function/aliyun_relay.py 部署到阿里云函数计算(FC)
# 或 cloud_function/tencent_relay.py 部署到腾讯云函数(SCF)
# 环境变量：
#   OVERSEAS_SERVER_URL = https://你的服务器/api/v1/billing/notify
#   ALLOWED_IPS = 47.94.194.102,39.107.193.170
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 数据库 | PostgreSQL + SQLAlchemy |
| AI引擎 | Nuwax / DeepSeek / GitHub Models |
| 前端 | 原生 HTML + ES Modules + Tailwind CSS CDN |
| 数据源 | BaoStock |
| 部署 | Docker + Nginx + Systemd |

## 许可证

MIT License - 详见 [LICENSE](./LICENSE) 文件
