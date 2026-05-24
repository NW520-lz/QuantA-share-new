import { apiFetch } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
await requireTier("daoyou");

const tableBody = document.getElementById("positions-table-body");
const updatedAt = document.getElementById("positions-updated-at");
const candidatesEl = document.getElementById("dashboard-candidates");
const totalPositionPctEl = document.getElementById("total-position-pct");
const allocationEl = document.getElementById("allocation-list");
const riskMaxSingleEl = document.getElementById("risk-max-single");
const riskMaxSingleBar = document.getElementById("risk-max-single-bar");
const riskBetaEl = document.getElementById("risk-beta");
const riskBetaBar = document.getElementById("risk-beta-bar");
const riskDrawdownEl = document.getElementById("risk-drawdown");
const riskDrawdownBar = document.getElementById("risk-drawdown-bar");
const riskHintEl = document.getElementById("risk-hint");
const posSymbolEl = document.getElementById("pos-symbol");
const posNameEl = document.getElementById("pos-name");
const posQtyEl = document.getElementById("pos-quantity");
const posAvgPriceEl = document.getElementById("pos-avg-price");
const posLastPriceEl = document.getElementById("pos-last-price");
const posSaveBtn = document.getElementById("pos-save-btn");
const posSaveMsg = document.getElementById("pos-save-msg");

const formatNumber = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    return Number(value).toFixed(digits);
};

const formatPercent = (value, digits = 2) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "--";
    return `${Number(value).toFixed(digits)}%`;
};

const renderRow = (position) => {
    const pnlPct = Number(position.pnl_pct ?? 0);
    const pnlClass = pnlPct >= 0 ? "text-green-400" : "text-error";
    const statusClass = pnlPct >= 0 ? "bg-green-500" : "bg-red-500";
    const quantity = Number(position.quantity ?? 0);
    const avgPrice = Number(position.avg_price ?? 0);
    const buyAmount = quantity * avgPrice;

    return `
        <tr class="border-b border-outline-variant hover:bg-surface-container-highest transition-colors">
            <td class="px-4 py-2">
                <div class="font-bold text-on-surface">${position.name || "--"}</div>
                <div class="text-[10px] text-on-surface-variant">${position.symbol}</div>
            </td>
            <td class="px-4 py-2 text-right">${formatNumber(quantity, 0)}</td>
            <td class="px-4 py-2 text-right">${formatNumber(position.avg_price)}</td>
            <td class="px-4 py-2 text-right">${formatNumber(buyAmount)}</td>
            <td class="px-4 py-2 text-right">${formatNumber(position.last_price)}</td>
            <td class="px-4 py-2 text-right ${pnlClass}">${formatPercent(position.pnl_pct)}</td>
            <td class="px-4 py-2 text-right ${pnlClass}">${formatNumber(position.pnl)}</td>
            <td class="px-4 py-2 text-right">${position.risk_level || "--"}</td>
            <td class="px-4 py-2 text-center"><span class="inline-block w-2 h-2 ${statusClass} rounded-full"></span></td>
        </tr>
    `;
};

const renderCandidateCard = (item) => {
    const riskClass = item.risk_pct >= 4 ? "text-error" : "text-on-surface";
    return `
        <div class="bg-surface-container-low border border-outline-variant p-4 hover:border-primary transition-colors cursor-pointer group relative overflow-hidden">
            <div class="flex justify-between items-start mb-2">
                <div>
                    <h3 class="font-bold text-on-surface">${item.name}</h3>
                    <p class="text-label-xs font-label-xs text-on-surface-variant">${item.symbol}</p>
                </div>
                <span class="text-xs px-2 py-0.5 bg-primary-container text-primary rounded">${item.tag}</span>
            </div>
            <div class="grid grid-cols-2 gap-y-2 mt-4 text-sm">
                <div class="text-on-surface-variant">买入参考</div><div class="text-right font-data-tabular">${formatNumber(item.price)}</div>
                <div class="text-on-surface-variant">止损价</div><div class="text-right text-error font-data-tabular">${formatNumber(item.stop_loss)}</div>
                <div class="text-on-surface-variant">目标止盈</div><div class="text-right text-green-400 font-data-tabular">${formatNumber(item.take_profit)}</div>
                <div class="text-on-surface-variant">R 值(风险)</div><div class="text-right font-label-xs ${riskClass}">${formatPercent(item.risk_pct, 1)}</div>
            </div>
        </div>
    `;
};

const renderAllocationItem = (name, valuePct, colorClass) => {
    return `
        <div class="flex items-center">
            <span class="w-3 h-3 ${colorClass} mr-2"></span>
            <span class="text-on-surface-variant flex-1">${name}</span>
            <span class="font-data-tabular">${formatPercent(valuePct, 1)}</span>
        </div>
    `;
};

const loadDashboard = async () => {
    const data = await apiFetch("/portfolio/dashboard");

    if (updatedAt) {
        const dt = new Date(data.updated_at);
        updatedAt.textContent = `更新时间: ${Number.isNaN(dt.getTime()) ? new Date().toLocaleString() : dt.toLocaleString()}`;
    }

    if (candidatesEl) {
        const onlyHighWin = (data.candidates || []).filter((item) => item.tag === "高胜率");
        if (!onlyHighWin.length) {
            candidatesEl.innerHTML = `<div class="col-span-full text-on-surface-variant text-sm border border-outline-variant p-4 rounded">今日无高胜率标的</div>`;
        } else {
            candidatesEl.innerHTML = onlyHighWin.slice(0, 5).map(renderCandidateCard).join("");
        }
    }

    if (tableBody) {
        const positions = data.positions || [];
        if (!positions.length) {
            tableBody.innerHTML = `
                <tr class="border-b border-outline-variant">
                    <td class="px-4 py-3 text-on-surface-variant" colspan="9">暂无持仓记录，请先录入买入股数和买入均价</td>
                </tr>
            `;
        } else {
            tableBody.innerHTML = positions.map(renderRow).join("");
        }
    }

    if (totalPositionPctEl) totalPositionPctEl.textContent = formatPercent(data.total_position_pct, 1);

    if (allocationEl) {
        const colors = ["bg-primary", "bg-tertiary", "bg-error", "bg-outline-variant"];
        allocationEl.innerHTML = (data.allocation || [])
            .slice(0, 4)
            .map((item, idx) => renderAllocationItem(item.name, item.value_pct, colors[idx] || "bg-outline-variant"))
            .join("");
    }

    if (riskMaxSingleEl) riskMaxSingleEl.textContent = formatPercent(data.max_single_position_pct, 1);
    if (riskMaxSingleBar) riskMaxSingleBar.style.width = `${Math.min(100, Math.max(0, data.max_single_position_pct * 5))}%`;

    if (riskBetaEl) riskBetaEl.textContent = formatNumber(data.beta, 2);
    if (riskBetaBar) riskBetaBar.style.width = `${Math.min(100, Math.max(0, data.beta * 50))}%`;

    if (riskDrawdownEl) riskDrawdownEl.textContent = formatPercent(data.max_drawdown_pct, 2);
    if (riskDrawdownBar) riskDrawdownBar.style.width = `${Math.min(100, Math.max(0, data.max_drawdown_pct * 10))}%`;

    if (riskHintEl) riskHintEl.textContent = data.risk_hint || "";
};

const savePosition = async () => {
    const symbol = posSymbolEl?.value?.trim();
    const quantity = Number(posQtyEl?.value);
    const avgPrice = Number(posAvgPriceEl?.value);
    const lastPrice = posLastPriceEl?.value ? Number(posLastPriceEl.value) : null;

    if (!symbol || !quantity || !avgPrice) {
        if (posSaveMsg) posSaveMsg.textContent = "请填写代码、买入股数、买入均价";
        return;
    }

    if (posSaveBtn) posSaveBtn.disabled = true;
    if (posSaveMsg) posSaveMsg.textContent = "保存中...";

    try {
        const result = await apiFetch("/portfolio/positions", {
            method: "POST",
            body: JSON.stringify({
                symbol,
                name: posNameEl?.value?.trim() || null,
                quantity,
                avg_price: avgPrice,
                last_price: Number.isFinite(lastPrice) ? lastPrice : null,
            }),
        });
        if (posSaveMsg) posSaveMsg.textContent = "持仓已保存 ✓";
        if (posSymbolEl) posSymbolEl.value = "";
        if (posNameEl) posNameEl.value = "";
        if (posQtyEl) posQtyEl.value = "";
        if (posAvgPriceEl) posAvgPriceEl.value = "";
        if (posLastPriceEl) posLastPriceEl.value = "";
        await loadDashboard();
    } catch (error) {
        const msg = error.message || String(error);
        if (posSaveMsg) posSaveMsg.innerHTML = `<span class="text-error">保存失败: ${msg}</span>`;
    } finally {
        if (posSaveBtn) posSaveBtn.disabled = false;
    }
};

const clearAllPositions = async () => {
    if (!confirm("确定清空所有持仓记录？此操作不可撤销。")) return;
    try {
        const result = await apiFetch("/portfolio/clear-all", { method: "POST" });
        alert(`已清仓 ${result.cleared} 只持仓`);
        await loadDashboard();
    } catch (error) {
        alert(`清仓失败: ${error.message}`);
    }
};

const exportPositions = () => {
    const token = localStorage.getItem("token");
    if (!token) {
        alert("未登录");
        return;
    }
    const a = document.createElement("a");
    a.href = `/api/v1/portfolio/export?token=${encodeURIComponent(token)}`;
    a.download = "positions.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

const loadWalletBalance = async () => {
    try {
        const data = await apiFetch("/portfolio/balance");
        const walletBtn = document.querySelector('[data-action="balance-wallet"]');
        if (walletBtn) {
            const pnlSign = data.total_pnl >= 0 ? "+" : "";
            walletBtn.title = `总市值: ${data.total_market_value.toFixed(2)} | 总盈亏: ${pnlSign}${data.total_pnl.toFixed(2)}`;
        }
    } catch (e) {
        // ignore balance errors silently
    }
};

posSaveBtn?.addEventListener("click", savePosition);
document.querySelector('[data-action="clear-all"]')?.addEventListener("click", clearAllPositions);
document.querySelector('[data-action="export-report"]')?.addEventListener("click", exportPositions);
document.querySelector('[data-action="balance-wallet"]')?.addEventListener("click", loadWalletBalance);

initStatus();
initNavigation();
initAvatarMenu();
Promise.all([loadDashboard(), loadWalletBalance()]).catch((error) => {
    console.error(error);
    if (tableBody) {
        tableBody.innerHTML = `
            <tr class="border-b border-outline-variant">
                <td class="px-4 py-3 text-on-surface-variant" colspan="9">加载失败: ${error.message}</td>
            </tr>
        `;
    }
});
