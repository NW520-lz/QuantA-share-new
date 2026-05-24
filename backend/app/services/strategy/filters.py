from typing import Any

DEFAULT_NEW_STOCK_DAYS = 60

# 市值过滤：单位亿元
# 低于此值的个股流动性差、易被操控，不纳入波段策略
MIN_MARKET_CAP_BILLION = 30.0

# 排除行业（波段策略不适合的行业）
EXCLUDED_INDUSTRIES = {
    "银行",
    "保险",
    "证券",
    "房地产",
    "综合",
}


def is_st_stock(name: str | None, tags: list[str] | None = None) -> bool:
    if tags:
        for tag in tags:
            if "st" in tag.lower() or "退" in tag:
                return True
    if not name:
        return False
    lowered = name.lower()
    return lowered.startswith("st") or "*st" in lowered or "退" in name


def is_new_stock(listing_days: int | None, threshold: int = DEFAULT_NEW_STOCK_DAYS) -> bool:
    if listing_days is None:
        return False
    return listing_days < threshold


def is_suspended(is_suspended_flag: bool | None) -> bool:
    return bool(is_suspended_flag)


def is_below_min_market_cap(market_cap_billion: float | None) -> bool:
    """市值低于阈值则过滤（None 表示未知，放行）。"""
    if market_cap_billion is None:
        return False
    return market_cap_billion < MIN_MARKET_CAP_BILLION


def is_excluded_industry(industry: str | None) -> bool:
    """属于排除行业则过滤（None 表示未知，放行）。"""
    if not industry:
        return False
    for excluded in EXCLUDED_INDUSTRIES:
        if excluded in industry:
            return True
    return False


def passes_base_filters(meta: dict[str, Any]) -> bool:
    name = meta.get("name")
    tags = meta.get("tags")
    listing_days = meta.get("listing_days")
    suspended = meta.get("is_suspended")
    market_cap = meta.get("market_cap_billion")   # 单位：亿元
    industry = meta.get("industry")

    if is_st_stock(name, tags):
        return False
    if is_new_stock(listing_days):
        return False
    if is_suspended(suspended):
        return False
    if is_below_min_market_cap(market_cap):
        return False
    if is_excluded_industry(industry):
        return False

    return True
