import { apiFetch, sanitize } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
await requireTier("daoyou");

const btnRun = document.getElementById("bt-run");
const btnStatus = document.getElementById("bt-status");
const resultsContainer = document.getElementById("bt-results-container");
const resultsTbody = document.getElementById("bt-results-tbody");
const summaryCards = document.getElementById("bt-summary-cards");
const topWinTbody = document.getElementById("bt-top-win");
const topRetTbody = document.getElementById("bt-top-ret");
const topRankings = document.getElementById("bt-top-rankings");
const historyTbody = document.getElementById("history-table-body");
const totalEl = document.getElementById("review-total");
const winRateEl = document.getElementById("review-win-rate");
const totalTradesEl = document.getElementById("review-total-trades");
const avgReturnEl = document.getElementById("review-avg-return");
const winLabel = document.getElementById("review-win-label");
const historyCount = document.getElementById("history-count");
const symbolCount = document.getElementById("bt-symbol-count");
const symbolInput = document.getElementById("bt-symbols");
const modeHint = document.getElementById("bt-mode-hint");
const symbolsContainer = document.getElementById("bt-symbols-container");
const maxContainer = document.getElementById("bt-max-container");

let scanMode = false;

const formatPct = (v, d = 2) => {
    if (v == null || Number.isNaN(v)) return "--";
    return `${Number(v).toFixed(d)}%`;
};

const formatNum = (v) => {
    if (v == null || Number.isNaN(v)) return "0";
    return Number(v).toLocaleString();
};

// --- Mode toggle ---
document.getElementById("bt-mode-manual")?.addEventListener("click", () => {
    scanMode = false;
    document.getElementById("bt-mode-manual").className = "bg-primary/20 text-primary px-4 py-1.5 rounded font-label-xs border border-primary/30";
    document.getElementById("bt-mode-scan").className = "bg-surface-container text-on-surface-variant px-4 py-1.5 rounded font-label-xs border border-outline-variant hover:border-primary/50";
    symbolsContainer.classList.remove("hidden");
    maxContainer.classList.add("hidden");
    modeHint.textContent = "按逗号输入多个代码";
});

document.getElementById("bt-mode-scan")?.addEventListener("click", () => {
    scanMode = true;
    document.getElementById("bt-mode-scan").className = "bg-primary/20 text-primary px-4 py-1.5 rounded font-label-xs border border-primary/30";
    document.getElementById("bt-mode-manual").className = "bg-surface-container text-on-surface-variant px-4 py-1.5 rounded font-label-xs border border-outline-variant hover:border-primary/50";
    symbolsContainer.classList.add("hidden");
    maxContainer.classList.remove("hidden");
    modeHint.textContent = "自动拉取全A股标的，批量回测";
});

if (symbolInput && symbolCount) {
    symbolInput.addEventListener("input", () => {
        const parts = symbolInput.value.split(",").map(s => s.trim()).filter(Boolean);
        symbolCount.textContent = `当前 ${parts.length} 个标的`;
    });
}

// --- Run batch backtest ---
if (btnRun) {
    btnRun.addEventListener("click", async () => {
        let payload;

        if (scanMode) {
            const maxSymbols = parseInt(document.getElementById("bt-max").value) || 50;
            payload = {
                symbols: [],
                scan_all: true,
                max_symbols: maxSymbols,
                start_date: document.getElementById("bt-start").value,
                end_date: document.getElementById("bt-end").value,
                lookback_days: parseInt(document.getElementById("bt-lookback").value) || 60,
                hold_days: parseInt(document.getElementById("bt-hold").value) || 10,
                stop_loss_pct: (parseFloat(document.getElementById("bt-sl").value) || 5) / 100,
                take_profit_pct: (parseFloat(document.getElementById("bt-tp").value) || 8) / 100,
            };
        } else {
            const symbols = symbolInput.value.split(",").map(s => s.trim()).filter(Boolean);
            if (!symbols.length) {
                alert("请输入至少一个股票代码");
                return;
            }
            payload = {
                symbols,
                scan_all: false,
                start_date: document.getElementById("bt-start").value,
                end_date: document.getElementById("bt-end").value,
                lookback_days: parseInt(document.getElementById("bt-lookback").value) || 60,
                hold_days: parseInt(document.getElementById("bt-hold").value) || 10,
                stop_loss_pct: (parseFloat(document.getElementById("bt-sl").value) || 5) / 100,
                take_profit_pct: (parseFloat(document.getElementById("bt-tp").value) || 8) / 100,
            };
        }

        btnRun.disabled = true;
        btnStatus.classList.remove("hidden");
        btnStatus.textContent = scanMode ? "全A扫描中，请稍候..." : "回测中...";
        btnRun.querySelector("span:last-child").textContent = scanMode ? "扫描中..." : "回测中...";

        try {
            const data = await apiFetch("/market/backtest/batch", {
                method: "POST",
                body: JSON.stringify(payload),
            });
            renderResults(data.summary);
            btnStatus.textContent = "回测完成 ✓";
            setTimeout(() => btnStatus.classList.add("hidden"), 3000);
        } catch (err) {
            alert("回测失败: " + (err.data?.detail || err.message));
            btnStatus.textContent = "回测失败 ✗";
            setTimeout(() => btnStatus.classList.add("hidden"), 4000);
        } finally {
            btnRun.disabled = false;
            btnRun.querySelector("span:last-child").textContent = "运行批量回测";
        }
    });
}

// --- Top rankings table ---
const renderTopTable = (tbody, items, key, colorClass) => {
    if (!items || !items.length) {
        tbody.innerHTML = `<tr><td class="px-2 py-1 text-on-surface-variant text-[11px]">暂无</td></tr>`;
        return;
    }
    tbody.innerHTML = items.map((r, i) => `
        <tr class="border-b border-outline-variant/30 text-[11px]">
            <td class="px-2 py-1 text-on-surface-variant">${i + 1}</td>
            <td class="px-2 py-1 text-on-surface font-data-tabular">${r.symbol || "--"}</td>
            <td class="px-2 py-1 text-right ${colorClass}">${formatPct(r[key], 1)}</td>
            <td class="px-2 py-1 text-right text-on-surface-variant">${formatNum(r.trades)}笔</td>
        </tr>
    `).join("");
};

// --- Render backtest results ---
const renderResults = (summary) => {
    resultsContainer.classList.remove("hidden");

    summaryCards.innerHTML = `
        <div class="bg-surface-container-low p-3 border border-outline-variant rounded">
            <p class="font-label-xs text-on-surface-variant mb-1">标的数量</p>
            <p class="text-[24px] font-bold text-on-surface">${formatNum(summary.total_symbols)}</p>
        </div>
        <div class="bg-surface-container-low p-3 border border-outline-variant rounded">
            <p class="font-label-xs text-on-surface-variant mb-1">总交易次数</p>
            <p class="text-[24px] font-bold text-on-surface">${formatNum(summary.total_trades)}</p>
        </div>
        <div class="bg-surface-container-low p-3 border border-outline-variant rounded">
            <p class="font-label-xs text-on-surface-variant mb-1">总胜率</p>
            <p class="text-[24px] font-bold ${summary.total_win_rate >= 50 ? 'heat-up' : 'heat-down'}">${formatPct(summary.total_win_rate, 1)}</p>
        </div>
        <div class="bg-surface-container-low p-3 border border-outline-variant rounded">
            <p class="font-label-xs text-on-surface-variant mb-1">平均收益</p>
            <p class="text-[24px] font-bold ${summary.avg_return_pct >= 0 ? 'heat-up' : 'heat-down'}">${formatPct(summary.avg_return_pct, 2)}</p>
        </div>
    `;

    if (summary.top_win && summary.top_win.length) {
        topRankings.classList.remove("hidden");
        renderTopTable(topWinTbody, summary.top_win, "win_rate", "heat-up");
        renderTopTable(topRetTbody, summary.top_return, "avg_return_pct", "heat-up");
    } else {
        topRankings.classList.add("hidden");
    }

    const detailTitle = document.getElementById("bt-detail-title");
    if (detailTitle) {
        detailTitle.textContent = summary.scan_mode === "all" ? `按标的明细 (有效 ${summary.valid_symbols || 0} / 共 ${summary.total_symbols} 只)` : "按标的明细";
    }

    resultsTbody.innerHTML = (summary.results || []).map(r => {
        const winClass = r.win_rate >= 50 ? "heat-up" : "heat-down";
        const retClass = r.avg_return_pct >= 0 ? "heat-up" : "heat-down";
        const err = r.error ? ` title="${sanitize(r.error)}"` : "";
        return `
            <tr class="hover:bg-white/5 transition-colors h-table-row-height"${err}>
                <td class="px-3 py-2 font-data-tabular text-on-surface">${sanitize(r.symbol) || "--"}${r.error ? ' ⚠' : ''}</td>
                <td class="px-3 py-2 font-data-tabular text-on-surface text-right">${formatNum(r.trades)}</td>
                <td class="px-3 py-2 font-data-tabular text-on-surface text-right">${formatNum(r.wins)}</td>
                <td class="px-3 py-2 font-data-tabular text-right ${winClass}">${formatPct(r.win_rate, 1)}</td>
                <td class="px-3 py-2 font-data-tabular text-right ${retClass}">${formatPct(r.avg_return_pct, 2)}</td>
            </tr>
        `;
    }).join("");

    resultsContainer.scrollIntoView({ behavior: "smooth" });
    loadHistory();
};

// --- Load history ---
const loadHistory = async () => {
    if (!historyTbody) return;

    try {
        const logs = await apiFetch("/market/backtest/history");
        if (!logs.length) {
            historyTbody.innerHTML = `<tr class="h-table-row-height"><td class="px-4 py-3 text-on-surface-variant" colspan="7">暂无回测记录，请先运行批量回测</td></tr>`;
            historyCount.textContent = "共 0 条记录";
            updateStats([]);
            return;
        }

        historyTbody.innerHTML = logs.map(log => {
            const m = log.metadata || {};
            const winClass = (m.total_win_rate || 0) >= 50 ? "heat-up" : "heat-down";
            const retClass = (m.avg_return_pct || 0) >= 0 ? "heat-up" : "heat-down";
            const scanBadge = m.scan_mode === "all" ? ' 🔍' : '';
            return `
                <tr class="hover:bg-white/5 transition-colors cursor-pointer h-table-row-height group" data-log-id="${log.id}">
                    <td class="px-4 py-2 font-data-tabular text-on-surface">${log.log_date || "--"}</td>
                    <td class="px-4 py-2 font-data-tabular text-on-surface">${log.title || "--"}${scanBadge}</td>
                    <td class="px-4 py-2 font-data-tabular text-on-surface text-right">${formatNum(m.total_symbols)}</td>
                    <td class="px-4 py-2 font-data-tabular text-on-surface text-right">${formatNum(m.total_trades)}</td>
                    <td class="px-4 py-2 font-data-tabular text-right ${winClass}">${formatPct(m.total_win_rate, 1)}</td>
                    <td class="px-4 py-2 font-data-tabular text-right ${retClass}">${formatPct(m.avg_return_pct, 2)}</td>
                    <td class="px-4 py-2 text-right">
                        <button class="text-on-surface-variant hover:text-primary transition-colors detail-btn" data-log-id="${log.id}">
                            <span class="material-symbols-outlined text-[18px]">open_in_new</span>
                        </button>
                        <button class="text-on-surface-variant hover:text-error transition-colors ml-1 delete-btn" data-log-id="${log.id}">
                            <span class="material-symbols-outlined text-[16px]">delete</span>
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        historyCount.textContent = `共 ${logs.length} 条记录`;
        updateStats(logs);
        bindRowEvents(logs);
    } catch (err) {
        historyTbody.innerHTML = `<tr class="h-table-row-height"><td class="px-4 py-3 text-on-surface-variant" colspan="7">加载失败: ${err.message}</td></tr>`;
    }
};

const updateStats = (logs) => {
    if (totalEl) totalEl.textContent = formatNum(logs.length);

    let allTrades = 0, allWins = 0, totalReturns = 0, tradeCountForAvg = 0;
    logs.forEach(log => {
        const m = log.metadata || {};
        allTrades += m.total_trades || 0;
        allWins += m.total_wins || 0;
        if (m.avg_return_pct != null) {
            totalReturns += m.avg_return_pct * (m.total_symbols || 1);
            tradeCountForAvg += m.total_symbols || 1;
        }
    });

    if (totalTradesEl) totalTradesEl.textContent = formatNum(allTrades);
    if (winRateEl) {
        if (allTrades > 0) {
            const rate = (allWins / allTrades) * 100;
            winRateEl.textContent = `${rate.toFixed(1)}%`;
            winRateEl.className = "font-display-lg text-[28px] font-bold " + (rate >= 50 ? "heat-up" : "heat-down");
        } else {
            winRateEl.textContent = "--";
        }
    }
    if (avgReturnEl) {
        if (tradeCountForAvg > 0) {
            const avg = totalReturns / tradeCountForAvg;
            avgReturnEl.textContent = `${avg.toFixed(2)}%`;
            avgReturnEl.className = "font-display-lg text-[28px] font-bold " + (avg >= 0 ? "heat-up" : "heat-down");
        } else {
            avgReturnEl.textContent = "--";
        }
    }
    if (winLabel && allTrades > 0) {
        const rate = (allWins / allTrades) * 100;
        winLabel.textContent = rate >= 60 ? "高胜率" : rate >= 45 ? "中等" : "待优化";
    }
};

// --- Detail modal ---
const modal = document.getElementById("detail-modal");
const modalTitle = document.getElementById("modal-title");
const modalBody = document.getElementById("modal-body");
const modalClose = document.getElementById("modal-close");

if (modalClose) {
    modalClose.addEventListener("click", () => modal.classList.add("hidden"));
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.add("hidden"); });
}

const showDetail = (log) => {
    if (!modal || !modalTitle || !modalBody) return;
    const m = log.metadata || {};
    modalTitle.textContent = log.title || "回测详情";

    const rows = (m.results || []).slice(0, 100).map(r => {
        const winClass = (r.win_rate || 0) >= 50 ? "heat-up" : "heat-down";
        const retClass = (r.avg_return_pct || 0) >= 0 ? "heat-up" : "heat-down";
        return `
            <tr class="border-b border-outline-variant">
                <td class="px-3 py-2 text-body-md text-on-surface">${r.symbol || "--"}</td>
                <td class="px-3 py-2 text-body-md text-right text-on-surface">${formatNum(r.trades)}</td>
                <td class="px-3 py-2 text-body-md text-right text-on-surface">${formatNum(r.wins)}</td>
                <td class="px-3 py-2 text-body-md text-right ${winClass}">${formatPct(r.win_rate, 1)}</td>
                <td class="px-3 py-2 text-body-md text-right ${retClass}">${formatPct(r.avg_return_pct, 2)}</td>
            </tr>
        `;
    }).join("");

    const truncated = (m.results || []).length > 100 ? `<p class="text-[10px] text-on-surface-variant mt-1">仅显示前100个标的，共${m.total_symbols}个</p>` : "";

    modalBody.innerHTML = `
        <div class="space-y-4">
            <div class="grid grid-cols-4 gap-3 mb-4">
                <div class="bg-surface-container-low p-2 border border-outline-variant rounded">
                    <p class="font-label-xs text-on-surface-variant">回测区间</p>
                    <p class="text-body-md text-on-surface">${m.start_date || "--"} ~ ${m.end_date || "--"}</p>
                </div>
                <div class="bg-surface-container-low p-2 border border-outline-variant rounded">
                    <p class="font-label-xs text-on-surface-variant">回看/持仓</p>
                    <p class="text-body-md text-on-surface">${m.lookback_days || "--"}d / ${m.hold_days || "--"}d</p>
                </div>
                <div class="bg-surface-container-low p-2 border border-outline-variant rounded">
                    <p class="font-label-xs text-on-surface-variant">总胜率</p>
                    <p class="text-body-md font-bold ${(m.total_win_rate || 0) >= 50 ? 'heat-up' : 'heat-down'}">${formatPct(m.total_win_rate, 1)}</p>
                </div>
                <div class="bg-surface-container-low p-2 border border-outline-variant rounded">
                    <p class="font-label-xs text-on-surface-variant">平均收益</p>
                    <p class="text-body-md font-bold ${(m.avg_return_pct || 0) >= 0 ? 'heat-up' : 'heat-down'}">${formatPct(m.avg_return_pct, 2)}</p>
                </div>
            </div>
            ${truncated}
            <table class="w-full text-body-md">
                <thead>
                    <tr class="bg-surface-container-low text-left">
                        <th class="px-3 py-2 font-label-xs text-on-surface-variant uppercase">标的</th>
                        <th class="px-3 py-2 font-label-xs text-on-surface-variant uppercase text-right">交易</th>
                        <th class="px-3 py-2 font-label-xs text-on-surface-variant uppercase text-right">盈利</th>
                        <th class="px-3 py-2 font-label-xs text-on-surface-variant uppercase text-right">胜率</th>
                        <th class="px-3 py-2 font-label-xs text-on-surface-variant uppercase text-right">收益</th>
                    </tr>
                </thead>
                <tbody>${rows || '<tr><td class="px-3 py-2 text-on-surface-variant" colspan="5">无数据</td></tr>'}</tbody>
            </table>
            ${log.content ? `<p class="text-label-xs text-on-surface-variant mt-3">${log.content}</p>` : ""}
        </div>
    `;
    modal.classList.remove("hidden");
};

const deleteLog = async (logId) => {
    if (!confirm("确定删除此回测记录？")) return;
    try {
        await apiFetch(`/review/${logId}`, { method: "DELETE" });
        loadHistory();
    } catch (err) {
        alert("删除失败: " + (err.data?.detail || err.message));
    }
};

const bindRowEvents = (logs) => {
    document.querySelectorAll(".detail-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const logId = btn.dataset.logId;
            const log = logs.find(l => l.id === logId);
            if (log) showDetail(log);
        });
    });
    document.querySelectorAll(".delete-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteLog(btn.dataset.logId);
        });
    });
    document.querySelectorAll("#history-table-body tr[data-log-id]").forEach(row => {
        row.addEventListener("click", () => {
            const log = logs.find(l => l.id === row.dataset.logId);
            if (log) showDetail(log);
        });
    });
};

const btnRefresh = document.getElementById("bt-refresh-history");
if (btnRefresh) btnRefresh.addEventListener("click", loadHistory);

initStatus();
initNavigation();
initAvatarMenu();
loadHistory().catch(console.error);
