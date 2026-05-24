create extension if not exists "pgcrypto";
create extension if not exists "vector";

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    uid text unique,
    phone text unique,
    email text unique,
    password_hash text not null,
    role text not null default 'user',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists strategies (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    name text not null,
    description text,
    mode text not null default 'swing',
    params jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_strategies_user_id on strategies(user_id);

create table if not exists positions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    symbol text not null,
    name text,
    quantity numeric(20, 4) not null default 0,
    avg_price numeric(20, 4),
    last_price numeric(20, 4),
    pnl numeric(20, 4),
    pnl_pct numeric(10, 4),
    risk_level text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_positions_user_id on positions(user_id);

create table if not exists trades (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    strategy_id uuid references strategies(id) on delete set null,
    symbol text not null,
    side text not null,
    quantity numeric(20, 4) not null,
    price numeric(20, 4) not null,
    trade_time timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_trades_user_id on trades(user_id);

create table if not exists review_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    log_date date not null,
    title text,
    content text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_review_logs_user_day on review_logs(user_id, log_date);
