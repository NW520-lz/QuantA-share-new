from typing import Any


# 价格单位：分（fen），1元 = 100分
# 道友期：¥29.9/月 = 2990分
# 前辈期：¥199/年 = 19900分

TIER_FREE = "lüyi"       # 蝼蚁期（免费）
TIER_DAOYOU = "daoyou"   # 道友期（¥29.9/月）
TIER_QIANBEI = "qianbei" # 前辈期（¥199/年）

TIER_RANK = {TIER_FREE: 0, TIER_DAOYOU: 1, TIER_QIANBEI: 2}

# 各等级可访问的功能
TIER_FEATURES = {
    TIER_FREE: {
        "stock_board": True,       # 选股看板（只读）
        "portfolio": False,        # 持仓风控
        "review": False,           # 复盘日志
        "strategy": False,         # 策略参数
        "ai_chat": False,          # AI对话
        "system_settings": False,  # 系统设置
    },
    TIER_DAOYOU: {
        "stock_board": True,
        "portfolio": True,
        "review": True,
        "strategy": True,
        "ai_chat": True,
        "system_settings": True,
    },
    TIER_QIANBEI: {
        "stock_board": True,
        "portfolio": True,
        "review": True,
        "strategy": True,
        "ai_chat": True,
        "system_settings": True,
    },
}


def recommended_pricing() -> tuple[str, list[dict[str, Any]]]:
    note = "开通会员，解锁全部功能。支持微信/支付宝扫码付款，付款后联系管理员确认。"
    plans = [
        {
            "code": "daoyou_monthly",
            "name": "道友期",
            "price_cny": 2990,
            "period_days": 30,
            "features": {
                "tier": TIER_DAOYOU,
                "all_features": True,
                "description": "解锁全部功能，月付",
            },
        },
        {
            "code": "qianbei_yearly",
            "name": "前辈期",
            "price_cny": 19900,
            "period_days": 365,
            "features": {
                "tier": TIER_QIANBEI,
                "all_features": True,
                "description": "解锁全部功能，年付更划算（相当于¥16.6/月）",
            },
        },
    ]
    return note, plans
