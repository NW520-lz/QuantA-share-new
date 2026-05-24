# QuantA-Share Backend

## Requirements
- Python 3.10+
- PostgreSQL (local or Supabase)

## Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Environment
Copy `.env.example` to `.env` and set values.

Local DB default:
`DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/quanta_share`

Email verification requires SMTP:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

AI fallback (optional, when Nuwax is unavailable):
- `GITHUB_MODELS_API_KEY`
- `GITHUB_MODELS_BASE_URL`
- `GITHUB_MODELS_MODEL`

Cloud deploy: keep code unchanged, override only env vars in your cloud platform.

## Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Migrations
Apply SQL files in `supabase/migrations/` in order.
For this feature, include:
- `20260524_000004_auth_billing.sql`

Local one-click:
```bash
cd backend
python run_sql_migrations.py
```

## New APIs
- `POST /api/v1/auth/email/send-code`
- `POST /api/v1/auth/email/register`
- `GET /api/v1/billing/plans`
- `POST /api/v1/billing/orders`
- `POST /api/v1/billing/orders/{order_id}/confirm`
- `GET /api/v1/billing/subscription`

## Health Check
```bash
curl http://localhost:8000/health
```
