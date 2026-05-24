-- 迁移：支付系统更新
-- 1. payment_orders 新增 pending_review / paid_donation 状态支持（无需 DDL，status 是 varchar）
-- 2. billing_plans 价格单位改为分（fen），清空旧方案，新方案由应用启动时自动写入
-- 3. user_subscriptions 无需变更

-- 清空旧的定价方案（应用启动时会重新写入新方案）
DELETE FROM billing_plans WHERE code IN ('starter_monthly', 'pro_monthly', 'pro_yearly');

-- 确保 payment_orders.extra 列存在（兼容旧版本）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'payment_orders' AND column_name = 'extra'
    ) THEN
        ALTER TABLE payment_orders ADD COLUMN extra jsonb NOT NULL DEFAULT '{}'::jsonb;
    END IF;
END $$;

-- 确保 user_subscriptions 表存在（兼容旧版本）
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    plan_code VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);
