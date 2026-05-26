import { apiFetch, sanitize } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { showTierBadge } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
showTierBadge();

// 支付完成后跳转回来，轮询订单状态并提示
(async () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("paid") === "1") {
        const toast = document.createElement("div");
        toast.className = "fixed top-4 right-4 z-50 bg-green-600 text-white text-sm px-4 py-3 rounded-lg shadow-lg transition-all";
        toast.textContent = "支付成功！正在确认订单...";
        document.body.appendChild(toast);
        for (let i = 0; i < 5; i++) {
            await new Promise((r) => setTimeout(r, 3000));
            try {
                const sub = await apiFetch("/billing/subscription");
                if (sub?.is_subscribed && sub.tier && sub.tier !== "lüyi") {
                    const name = { daoyou: "道友期", qianbei: "前辈期" }[sub.tier] || sub.tier;
                    toast.textContent = `${name}已开通，享受全部功能！`;
                    showTierBadge();
                    setTimeout(() => toast.remove(), 4000);
                    return;
                }
            } catch (_) { /* ignore */ }
        }
        toast.className = toast.className.replace("bg-green-600", "bg-zinc-700");
        toast.textContent = "订单确认中，稍后刷新页面查看状态";
        setTimeout(() => toast.remove(), 5000);
        window.history.replaceState({}, "", window.location.pathname);
    }
    if (params.get("donated") === "1") {
        const toast = document.createElement("div");
        toast.className = "fixed top-4 right-4 z-50 bg-amber-600 text-white text-sm px-4 py-3 rounded-lg shadow-lg";
        toast.textContent = "感谢打赏！管理员将在24小时内审核。";
        document.body.appendChild(toast);
        setTimeout(() => { toast.remove(); window.history.replaceState({}, "", window.location.pathname); }, 5000);
    }
})();

const progressLabel = document.getElementById("scan-progress-text");
const progressBar = document.getElementById("scan-progress-bar");
const sentimentLabel = document.getElementById("market-sentiment-label");
const updateTime = document.getElementById("market-update-time");
const tableBody = document.getElementById("candidate-table-body");
const gaugeLabel = document.getElementById("sentiment-gauge-label");
const gaugeScore = document.getElementById("sentiment-gauge-score");
const watchlistContainer = document.getElementById("watchlist-container");
const scanTimeEl = document.getElementById("scan-time-text");

const formatNumber = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    return Number(value).toFixed(digits);
};

const formatPercent = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    return `${(Number(value) * 100).toFixed(digits)}%`;
};

const statusColorMap = {
    green: "bg-green-500",
    yellow: "bg-yellow-500",
    red: "bg-red-500",
};

const signalTypeLabels = {
    limitup_breakout: "涨停回调突破",
    pullback: "回踩止跌",
    breakout: "低位突破",
    trend: "趋势确认",
};

const renderRow = (item) => {
    const riskClass = statusColorMap[item.status] || "bg-yellow-500";
    const rowClass = item.should_buy ? "heat-map-green" : item.status === "red" ? "heat-map-red" : "";
    const signalLabel = signalTypeLabels[item.signal_type] || null;
    const signalBadge = signalLabel
        ? `<span class="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded border border-green-500/30">${sanitize(signalLabel)}</span>`
        : "";

    return `
        <tr class="h-table-row-height ${rowClass} hover:bg-white/5">
            <td class="px-4 font-label-xs font-bold text-on-surface">${sanitize(item.symbol)}</td>
            <td class="px-4 font-body-md text-on-surface">${sanitize(item.name)}</td>
            <td class="px-4 font-label-xs text-right text-on-surface">${formatNumber(item.price)}</td>
            <td class="px-4 font-label-xs text-right text-error">${formatNumber(item.stop_loss)}</td>
            <td class="px-4 font-label-xs text-right text-primary font-bold">${formatNumber(item.r_value, 2)}</td>
            <td class="px-4 font-label-xs text-right text-on-surface">${formatNumber(item.volume_ratio, 2)}</td>
            <td class="px-4 text-center">
                <div class="flex items-center justify-center gap-1.5">
                    ${signalBadge}
                    <div class="inline-block w-2 h-2 rounded-full ${riskClass}"></div>
                </div>
            </td>
        </tr>
    `;
};

const renderWatchItem = (item) => {
    const rise = item.change_pct >= 0;
    const txtClass = rise ? "text-green-500" : "text-error";
    const barBg = rise ? "bg-green-500/20 border-green-500" : "bg-error-container/20 border-error";
    const pct = `${item.change_pct >= 0 ? "+" : ""}${formatNumber(item.change_pct)}%`;
    const bars = item.bars
        .map((h) => `<div class="flex-1 ${barBg} rounded-t border-t" style="height: ${h}%"></div>`)
        .join("");
    return `
        <div class="p-2 border border-outline-variant bg-surface rounded ${rise ? "" : "opacity-80"}">
            <div class="flex justify-between items-center mb-2">
                <span class="font-label-xs text-on-surface">${sanitize(item.title)}</span>
                <span class="text-[10px] ${txtClass}">${sanitize(pct)}</span>
            </div>
            <div class="h-16 flex items-end gap-1">${bars}</div>
        </div>
    `;
};

const loadCandidates = async () => {
    if (!tableBody) return;
    const data = await apiFetch("/market/candidates", { method: "GET" });

    if (!data.candidates.length) {
        tableBody.innerHTML = `
            <tr class="h-table-row-height">
                <td class="px-4 text-on-surface-variant" colspan="8">暂无标的数据，扫描进行中...</td>
            </tr>`;
        if (progressLabel) progressLabel.textContent = "后台扫描中...";
        if (sentimentLabel) sentimentLabel.textContent = "等待首次扫描";
        return;
    }

    tableBody.innerHTML = data.candidates.map((item) => renderRow(item)).join("");
    if (watchlistContainer) {
        watchlistContainer.innerHTML = data.watchlist.map((item) => renderWatchItem(item)).join("");
    }

    if (progressLabel) progressLabel.textContent = `${data.progress_pct}% 已完成`;
    if (progressBar) progressBar.style.width = `${data.progress_pct}%`;
    if (sentimentLabel) sentimentLabel.textContent = data.sentiment_label;
    if (gaugeLabel) gaugeLabel.textContent = data.sentiment_label;
    if (gaugeScore) gaugeScore.textContent = `信心指数: ${formatNumber(data.sentiment_score, 1)}`;
    if (updateTime) updateTime.textContent = `更新时间: ${new Date().toLocaleTimeString()}`;

    try {
        const status = await apiFetch("/market/scan-status", { method: "GET" });
        if (scanTimeEl && status.last_scan_at) {
            const dt = new Date(status.last_scan_at);
            scanTimeEl.textContent = `上次扫描: ${dt.toLocaleString()} | ${status.total_scanned} 只标的`;
        } else if (scanTimeEl) {
            scanTimeEl.textContent = "后台扫描中...";
        }
    } catch (e) {
        /* ignore */
    }
};

initStatus();
initNavigation();
initAvatarMenu();
loadCandidates().catch((error) => {
    if (tableBody) {
        tableBody.innerHTML = `
            <tr class="h-table-row-height">
                <td class="px-4 text-on-surface-variant" colspan="7">加载失败: ${sanitize(error.message)}</td>
            </tr>
        `;
    }
});
