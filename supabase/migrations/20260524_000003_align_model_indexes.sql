create index if not exists idx_users_uid on users(uid);
create index if not exists idx_users_phone on users(phone);
create index if not exists idx_users_email on users(email);
create index if not exists idx_trades_strategy_id on trades(strategy_id);
