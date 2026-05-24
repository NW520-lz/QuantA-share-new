/**
 * tier-guard.js - 会员等级访问控制
 *
 * 使用方式：
 *   import { requireTier, showTierBadge } from "./tier-guard.js";
 *   await requireTier("daoyou");  // 不满足则跳转付费中心
 */
import { apiFetch, getToken } from "./api.js";

const TIER_RANK = { "lüyi": 0, daoyou: 1, qianbei: 2, trial: 0 };

const TIER_LABEL = {
    "lüyi": "蝼蚁期",
    daoyou: "道友期",
    qianbei: "前辈期",
    trial: "试用期",
};

// 每次页面加载只请求一次，但不跨页面缓存
let _cachedTier = null;
let _cachedSub = null;
let _fetchPromise = null;

export function clearTierCache() {
    _cachedTier = null;
    _cachedSub = null;
    _fetchPromise = null;
}

export async function fetchTier() {
    if (_cachedTier !== null) return { tier: _cachedTier, sub: _cachedSub };
    if (!getToken()) return { tier: "lüyi", sub: null };
    if (!_fetchPromise) {
        _fetchPromise = Promise.all([
            apiFetch("/billing/subscription"),
            apiFetch("/auth/me").catch(() => null),
        ]).then(([sub, user]) => {
            _cachedSub = sub;
            // admin 账号直接视为最高等级
            if (user?.role === "admin") {
                _cachedTier = "qianbei";
            } else {
                _cachedTier = sub?.tier || "lüyi";
            }
        }).catch(() => {
            _cachedTier = "lüyi";
        });
    }
    await _fetchPromise;
    return { tier: _cachedTier, sub: _cachedSub };
}

/**
 * 检查当前用户是否满足最低等级要求。
 * 不满足时跳转付费中心，满足时返回当前 tier 字符串。
 */
export async function requireTier(minTier = "daoyou") {
    const { tier } = await fetchTier();
    const userRank = TIER_RANK[tier] ?? 0;
    const minRank = TIER_RANK[minTier] ?? 1;
    if (userRank < minRank) {
        // 调试：控制台打印实际 tier，方便排查
        console.warn(`[tier-guard] requireTier("${minTier}") failed: current tier="${tier}" rank=${userRank} < required=${minRank}`);
        window.location.href = "付费中心.html";
        throw new Error("需要升级会员");
    }
    return tier;
}

/**
 * 在页面上显示当前等级徽章（插入到 data-tier-badge 元素中）。
 */
export async function showTierBadge() {
    const { tier, sub } = await fetchTier();
    const badge = document.querySelector("[data-tier-badge]");
    if (!badge) return;
    const label = TIER_LABEL[tier] || tier;
    const colors = {
        "lüyi": "bg-zinc-700 text-zinc-300",
        daoyou: "bg-blue-900 text-blue-300",
        qianbei: "bg-amber-900 text-amber-300",
        trial: "bg-zinc-700 text-zinc-300",
    };
    const color = colors[tier] || "bg-zinc-700 text-zinc-300";
    let extra = "";
    if (sub?.ends_at && tier !== "lüyi") {
        const d = new Date(sub.ends_at).toLocaleDateString("zh-CN");
        extra = ` · 至${d}`;
    }
    badge.innerHTML = `<span class="text-xs ${color} px-2 py-0.5 rounded-full">${label}${extra}</span>`;
}

/**
 * 隐藏/禁用页面上标注了 data-require-tier="daoyou" 的元素（蝼蚁期用户看不到）。
 */
export async function applyTierRestrictions() {
    const { tier } = await fetchTier();
    const userRank = TIER_RANK[tier] ?? 0;
    document.querySelectorAll("[data-require-tier]").forEach((el) => {
        const needed = el.dataset.requireTier;
        const neededRank = TIER_RANK[needed] ?? 1;
        if (userRank < neededRank) {
            el.style.display = "none";
        }
    });
}
