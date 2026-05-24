alter table users
    add column if not exists email_verified boolean not null default false;

alter table users
    add column if not exists trial_ends_at timestamptz;

create table if not exists email_verification_codes (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    purpose text not null default 'register',
    code_hash text not null,
    expires_at timestamptz not null,
    attempts integer not null default 0,
    consumed_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_email_verify_email_purpose_created
    on email_verification_codes(email, purpose, created_at desc);

create table if not exists billing_plans (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    price_cny integer not null,
    period_days integer not null default 30,
    features jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists user_subscriptions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    plan_code text not null references billing_plans(code),
    status text not null default 'pending',
    starts_at timestamptz not null default now(),
    ends_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_user_subscriptions_user_id
    on user_subscriptions(user_id);

create table if not exists payment_orders (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    plan_code text not null references billing_plans(code),
    amount_cny integer not null,
    status text not null default 'pending',
    gateway text not null default 'manual',
    payment_url text,
    extra jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    paid_at timestamptz
);

create index if not exists idx_payment_orders_user_id_created
    on payment_orders(user_id, created_at desc);

insert into billing_plans (code, name, price_cny, period_days, features, is_active)
values
    ('starter_monthly', 'Starter 月付', 99, 30, '{"daily_scan_limit": 100, "ai_calls": 200, "backtest_symbols": 20}'::jsonb, true),
    ('pro_monthly', 'Pro 月付', 199, 30, '{"daily_scan_limit": 500, "ai_calls": 1000, "backtest_symbols": 100}'::jsonb, true),
    ('pro_yearly', 'Pro 年付', 1990, 365, '{"daily_scan_limit": 500, "ai_calls": 12000, "backtest_symbols": 100}'::jsonb, true)
on conflict (code) do update set
    name = excluded.name,
    price_cny = excluded.price_cny,
    period_days = excluded.period_days,
    features = excluded.features,
    is_active = excluded.is_active;
