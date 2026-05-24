# QuantA-Share 云服务器部署指南

> 适用于将本项目部署到海外 VPS（如 Vultr、DigitalOcean、阿里云香港、腾讯云香港等）。
> 系统要求：Ubuntu 22.04 LTS，2核2G 内存起步。

---

## 方式一：Docker 部署（推荐）

### 1. 服务器初始化

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# 安装 Docker Compose
apt install -y docker-compose-plugin
docker compose version   # 验证安装
```

### 2. 上传项目代码

```bash
# 本地执行：把项目打包上传到服务器
scp -r ./QuantA_Share root@你的服务器IP:/opt/quanta

# 或者用 git（推荐）
ssh root@你的服务器IP
git clone https://github.com/你的账号/QuantA_Share.git /opt/quanta
cd /opt/quanta
```

### 3. 创建 docker-compose.yml

在项目根目录创建 `docker-compose.yml`：

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: quanta_share
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: 你的数据库密码
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    restart: always
    depends_on:
      db:
        condition: service_healthy
    env_file: ./backend/.env
    ports:
      - "8000:8000"
    volumes:
      - ./前端:/app/前端:ro

volumes:
  pgdata:
```

### 4. 创建 backend/Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5. 配置 .env

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

关键配置项：

```env
DATABASE_URL=postgresql+asyncpg://postgres:你的数据库密码@db:5432/quanta_share
BILLING_PUBLIC_BASE_URL=https://你的域名或IP
ZHIFUFM_NOTIFY_URL=https://你的域名或IP/api/v1/billing/notify
```

### 6. 启动服务

```bash
cd /opt/quanta
docker compose up -d --build

# 查看日志
docker compose logs -f backend
```

### 7. 配置 Nginx 反向代理（有域名时）

```bash
apt install -y nginx certbot python3-certbot-nginx

# 创建 Nginx 配置
cat > /etc/nginx/sites-available/quanta << 'EOF'
server {
    listen 80;
    server_name 你的域名;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # 支付FM 回调 IP 白名单（可选）
    location /api/v1/billing/notify {
        allow 47.94.194.0/24;
        allow 39.107.193.0/24;
        deny all;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/quanta /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 申请 HTTPS 证书
certbot --nginx -d 你的域名
```

---

## 方式二：裸机部署（简单直接）

### 1. 安装依赖

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx

# 启动 PostgreSQL
systemctl enable postgresql && systemctl start postgresql
```

### 2. 创建数据库

```bash
sudo -u postgres psql << 'EOF'
CREATE DATABASE quanta_share;
CREATE USER quanta WITH PASSWORD '你的数据库密码';
GRANT ALL PRIVILEGES ON DATABASE quanta_share TO quanta;
\q
EOF
```

### 3. 部署后端

```bash
cd /opt
git clone https://github.com/你的账号/QuantA_Share.git quanta
cd quanta/backend

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env
# 修改 DATABASE_URL 为：
# postgresql+asyncpg://quanta:你的数据库密码@127.0.0.1:5432/quanta_share
```

### 4. 创建 systemd 服务

```bash
cat > /etc/systemd/system/quanta.service << 'EOF'
[Unit]
Description=QuantA Share Backend
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/opt/quanta/backend
Environment="PATH=/opt/quanta/backend/venv/bin"
ExecStart=/opt/quanta/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable quanta
systemctl start quanta
systemctl status quanta   # 确认运行正常
```

### 5. 配置 Nginx（同 Docker 方式第7步）

---

## 部署后配置支付FM

服务器启动后，更新 `.env` 里的回调地址：

```env
BILLING_PUBLIC_BASE_URL=https://你的域名
ZHIFUFM_NOTIFY_URL=https://你的域名/api/v1/billing/notify
```

然后重启服务：

```bash
# Docker 方式
docker compose restart backend

# 裸机方式
systemctl restart quanta
```

---

## 验证部署

```bash
# 健康检查
curl https://你的域名/health
# 返回 {"status":"ok"} 表示正常

# 测试支付FM回调接口是否可访问
curl "https://你的域名/api/v1/billing/notify?state=0&test=1"
# 返回 success 表示接口正常（state=0 不会触发业务逻辑）
```

---

## 常见问题

**Q: 数据库连接失败**
检查 `DATABASE_URL` 里的密码和端口，Docker 方式主机名用 `db`，裸机方式用 `127.0.0.1`。

**Q: 支付FM回调收不到**
1. 确认 `ZHIFUFM_NOTIFY_URL` 填的是公网可访问地址（不能是 127.0.0.1）
2. 检查防火墙是否放行 80/443 端口：`ufw allow 80 && ufw allow 443`
3. 用 Postman 手动 GET 请求回调地址，确认返回 `success`

**Q: 前端页面 404**
确认 `前端/` 目录已上传到服务器，且 `main.py` 里的 `frontend_dir` 路径正确。
