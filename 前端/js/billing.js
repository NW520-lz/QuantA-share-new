import { apiFetch, getToken } from "./api.js";

const errorEl = document.getElementById("billing-error");
const statusEl = document.getElementById("current-status");
const notLoggedInEl = document.getElementById("not-logged-in");

const setError = (msg) => {
    if (!errorEl) return;
    if (!msg) { errorEl.classList.add("hidden"); return; }
    errorEl.classList.remove("hidden");
    errorEl.textContent = msg;
};

// 检查登录态，未登录显示提示而不是静默跳转
function checkLogin() {
    if (!getToken()) {
        notLoggedInEl?.classList.remove("hidden");
        // 禁用所有付费按钮
        document.querySelectorAll(".plan-btn, #donate-btn").forEach(btn => {
            btn.disabled = true;
            btn.title = "请先登录";
        });
        return false;
    }
    return true;
}

const handlePlanClick = async (btn, planCode) => {
    if (!checkLogin()) return;
    setError("");
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "正在创建订单...";
    try {
        const order = await apiFetch("/billing/orders", {
            method: "POST",
            body: JSON.stringify({ plan_code: planCode }),
        });
        if (order.pay_url) {
            window.location.href = order.pay_url;
        } else {
            setError("未获取到支付链接，请重试");
            btn.disabled = false;
            btn.textContent = origText;
        }
    } catch (e) {
        setError(e.message || "创建订单失败，请重试");
        btn.disabled = false;
        btn.textContent = origText;
    }
};

const handleDonate = async () => {
    if (!checkLogin()) return;
    const amountEl = document.getElementById("donate-amount");
    const msgEl = document.getElementById("donate-message");
    const btn = document.getElementById("donate-btn");
    const yuan = parseFloat(amountEl?.value);
    if (!yuan || yuan < 1) { setError("请输入有效的打赏金额（最低1元）"); return; }
    setError("");
    btn.disabled = true;
    btn.textContent = "处理中...";
    try {
        const order = await apiFetch("/billing/donate", {
            method: "POST",
            body: JSON.stringify({
                amount_cny: Math.round(yuan * 100),
                message: msgEl?.value.trim() || "",
            }),
        });
        if (order.pay_url) {
            window.location.href = order.pay_url;
        } else {
            setError("未获取到支付链接，请重试");
        }
    } catch (e) {
        setError(e.message || "创建打赏失败，请检查金额后重试");
    } finally {
        btn.disabled = false;
        btn.textContent = "打赏";
    }
};

const loadStatus = async () => {
    if (!getToken()) return;
    try {
        const sub = await apiFetch("/billing/subscription");
        if (sub?.is_subscribed && sub.tier && sub.tier !== "lüyi") {
            const tierName = { daoyou: "道友期", qianbei: "前辈期", trial: "试用期" }[sub.tier] || sub.tier;
            const ends = sub.ends_at ? new Date(sub.ends_at).toLocaleDateString("zh-CN") : "永久";
            statusEl.textContent = `当前状态：${tierName} · 有效期至 ${ends}`;
            statusEl.classList.remove("hidden");
        }
    } catch (_) { /* ignore */ }
};

// 绑定套餐按钮
document.querySelectorAll(".plan-btn").forEach((btn) => {
    btn.addEventListener("click", () => handlePlanClick(btn, btn.dataset.plan));
});
document.getElementById("donate-btn")?.addEventListener("click", handleDonate);

// 初始化
checkLogin();
loadStatus();
