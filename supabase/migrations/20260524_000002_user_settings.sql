create table if not exists user_settings (
    user_id uuid primary key references users(id) on delete cascade,
    settings jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);
