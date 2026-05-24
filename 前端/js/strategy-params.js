import { apiFetch } from './api.js';
import { apiFetch, formatDate } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
await requireTier("daoyou");

const sentimentText = document.getElementById("strategy-sentiment-text");
const sentimentBar = document.getElementById("strategy-sentiment-bar");
const industryListEl = document.getElementById("industry-exclusion-list");
const industryInputEl = document.getElementById("industry-exclusion-input");
const industryAddBtn = document.getElementById("industry-exclusion-add-btn");
const metricDailyTradesEl = document.getElementById("metric-daily-trades");
const metricBullishEl = document.getElementById("metric-bullish");
const metricHistoryWinRateEl = document.getElementById("metric-history-win-rate");
const metricEngineLatencyEl = document.getElementById("metric-engine-latency");
const metricPoolCountEl = document.getElementById("metric-pool-count");

const SYMBOLS = ["sh.600519", "sz.300750", "sz.002594"];
let industryExclusions = [];

async function loadSentiment() {
    const mode = window.__strategyMode || "swing";
    const endDate = formatDate(new Date());
    const startDate = formatDate(new Date(Date.now() - 1000 * 60 * 60 * 24 * 60));

    try {
        const scan = await apiFetch("/stock-board/scan", {
            method: "POST",
            body: JSON.stringify({
                symbols: SYMBOLS,
                start_date: startDate,
                end_date: endDate,
                mode: mode,
            }),
        });

        const buyCount = scan.results.filter((item) => item.should_buy).length;
        const promotionRate = scan.results.length ? buyCount / scan.results.length : 0;

        const sentiment = await apiFetch("/stock-board/sentiment", {
            method: "POST",
            body: JSON.stringify({
                promotion_rate: promotionRate,
                limit_up_count: buyCount,
                limit_down_count: 0,
                breadth_pct: promotionRate,
                leading_stock_negative_feedback: false,
            }),
        });

        const score = Math.round(sentiment.sentiment_score);
        const modeLabel = mode === "short_term" ? "短线" : "波段";
        if (sentimentText) sentimentText.textContent = `${modeLabel} · ${sentiment.label} ${score}%`;
        if (sentimentBar) sentimentBar.style.width = `${score}%`;
    } catch (e) {
        if (sentimentText) sentimentText.textContent = "情绪数据不可用";
    }
}

window.loadSentiment = loadSentiment;

const renderIndustryExclusions = () => {
    if (!industryListEl) return;
    if (!industryExclusions.length) {
        industryListEl.innerHTML = `<span class="text-label-xs text-on-surface-variant">暂无行业规避，默认不限制</span>`;
        return;
    }

    industryListEl.innerHTML = industryExclusions
        .map(
            (item) => `
            <span class="px-2 py-1 rounded-sm bg-surface-container-highest text-label-xs text-on-surface-variant flex items-center gap-1 border border-outline-variant">
                ${item}
                <button class="material-symbols-outlined text-[12px] cursor-pointer hover:text-error" data-remove-industry="${item}" type="button">close</button>
            </span>
        `
        )
        .join("");

    industryListEl.querySelectorAll("[data-remove-industry]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const target = btn.getAttribute("data-remove-industry");
            industryExclusions = industryExclusions.filter((v) => v !== target);
            await saveIndustryExclusions();
            renderIndustryExclusions();
        });
    });
};

const saveIndustryExclusions = async () => {
    await apiFetch("/market/strategy-panel/industry-exclusions", {
        method: "PUT",
        body: JSON.stringify({ industries: industryExclusions }),
    });
};

const loadStrategyPanel = async () => {
    try {
        const panel = await apiFetch("/market/strategy-panel", { method: "GET" });
        industryExclusions = (panel.industry_exclusions || []).filter(Boolean);
        renderIndustryExclusions();

        if (metricDailyTradesEl) {
            const min = Number(panel.estimated_daily_trades_min || 0);
            const max = Number(panel.estimated_daily_trades_max || 0);
            metricDailyTradesEl.textContent = max > 0 ? `${min} - ${max}` : "--";
        }
        if (metricBullishEl) metricBullishEl.textContent = `看多 ${Number(panel.bullish_pct || 0).toFixed(1)}%`;
        if (metricHistoryWinRateEl) metricHistoryWinRateEl.textContent = `${Number(panel.history_win_rate || 0).toFixed(1)}%`;
        if (metricEngineLatencyEl) metricEngineLatencyEl.textContent = `${Number(panel.engine_latency_ms || 0)}ms`;
        if (metricPoolCountEl) metricPoolCountEl.textContent = Number(panel.pool_sample_count || 0).toLocaleString();
    } catch (error) {
        if (industryListEl) industryListEl.innerHTML = `<span class="text-label-xs text-error">加载失败: ${error.message}</span>`;
        if (metricDailyTradesEl) metricDailyTradesEl.textContent = "--";
        if (metricBullishEl) metricBullishEl.textContent = "--";
        if (metricHistoryWinRateEl) metricHistoryWinRateEl.textContent = "--";
        if (metricEngineLatencyEl) metricEngineLatencyEl.textContent = "--";
        if (metricPoolCountEl) metricPoolCountEl.textContent = "--";
    }
};

industryAddBtn?.addEventListener("click", async () => {
    const value = industryInputEl?.value?.trim();
    if (!value) return;
    if (!industryExclusions.includes(value)) {
        industryExclusions.push(value);
    }
    industryExclusions = [...new Set(industryExclusions)];
    try {
        await saveIndustryExclusions();
        renderIndustryExclusions();
        if (industryInputEl) industryInputEl.value = "";
    } catch (error) {
        alert(`保存失败: ${error.message}`);
    }
});

initStatus();
initNavigation();
initAvatarMenu();
loadSentiment();
loadStrategyPanel();




// Bind Inputs Sync (Range <=> Number) and Save/Load functionality

setTimeout(() => {
    // Sync ranges and numbers
    const panels = document.querySelectorAll('.mode-panel');
    panels.forEach(panel => {
        const rows = panel.querySelectorAll('.grid.grid-cols-12');
        rows.forEach((row, rowIndex) => {
            const rangeInput = row.querySelector('input[type="range"]');
            const numInput = row.querySelector('input[type="number"]');
            
            if (rangeInput && numInput) {
                // Assign deterministic IDs if missing
                if (!rangeInput.id) rangeInput.id = `range-${panel.className.includes('swing') ? 'swing' : 'short'}-${rowIndex}`;
                if (!numInput.id) numInput.id = `num-${panel.className.includes('swing') ? 'swing' : 'short'}-${rowIndex}`;

                rangeInput.addEventListener('input', () => numInput.value = rangeInput.value);
                numInput.addEventListener('input', () => rangeInput.value = numInput.value);
            }
        });
    });

    // Checkboxes 
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach((cb, i) => {
        if (!cb.id) cb.id = `filter-cb-${i}`;
    });

    // Load from localStorage
    const saved = localStorage.getItem('quantA_strategy_params');
    if (saved) {
        try {
            const data = JSON.parse(saved);
            Object.keys(data).forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    if (el.type === 'checkbox') {
                        el.checked = data[id];
                    } else {
                        el.value = data[id];
                    }
                }
            });
        } catch(e) {}
    }

    // Bind Save Button
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('保存并下发'));
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> 保存中...';
            
            const dataToSave = {};
            document.querySelectorAll('input[type="range"], input[type="number"]').forEach(input => {
                if (input.id) dataToSave[input.id] = input.value;
            });
            document.querySelectorAll('input[type="checkbox"]').forEach(input => {
                if (input.id) dataToSave[input.id] = input.checked;
            });

            localStorage.setItem('quantA_strategy_params', JSON.stringify(dataToSave));
            
            // Push to backend user settings as well
            apiFetch('/system/settings', {
                method: 'PUT',
                body: JSON.stringify({ settings: { strategy_params: dataToSave } })
            }).catch(console.error);

            setTimeout(() => {
                saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">check</span> 已下发引擎';
                saveBtn.classList.remove('bg-primary');
                saveBtn.classList.add('bg-emerald-500');
                
                setTimeout(() => {
                    saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">save</span> 保存并下发';
                    saveBtn.classList.add('bg-primary');
                    saveBtn.classList.remove('bg-emerald-500');
                }, 2000);
            }, 600);
        });
    }

    // Bind Reset Button
    const resetBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('重置默认'));
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if(confirm('确定要恢复默认策略参数吗？')) {
                localStorage.removeItem('quantA_strategy_params');
                location.reload();
            }
        });
    }
}, 100);
