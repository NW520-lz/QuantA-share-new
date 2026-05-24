create table if not exists system_event_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    channel text not null default 'system',
    level text not null default 'INFO',
    source text not null default 'backend',
    message text not null,
    context jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_system_event_logs_user_created_at
    on system_event_logs(user_id, created_at desc);

create index if not exists idx_system_event_logs_channel_created_at
    on system_event_logs(channel, created_at desc);
