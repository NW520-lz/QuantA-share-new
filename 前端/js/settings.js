import { apiFetch } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
await requireTier("daoyou");

const uidEl = document.getElementById("uid-value");
const roleEl = document.getElementById("role-value");
const apiKeyEl = document.getElementById("api-key-mask");
const versionEl = document.getElementById("system-version");
const baostockStatusEl = document.getElementById("baostock-status");
const dbStorageEl = document.getElementById("db-storage-text");
const dbLatencyEl = document.getElementById("db-latency-text");
const autoSyncToggle = document.getElementById("auto-sync-toggle");
const brokerSelect = document.getElementById("broker-select");
const autoOrderAuth = document.getElementById("auto-order-auth");
const riskAgreementStatus = document.getElementById("risk-agreement-status");
const riskAgreementText = document.getElementById("risk-agreement-text");
const saveBtn = document.getElementById("save-trade-settings-btn");
const testDbBtn = document.getElementById("test-db-btn");
const logsTbody = document.getElementById("system-log-tbody");
const exportLogsBtn = document.getElementById("export-logs-btn");
const darkBtn = document.getElementById("theme-dark-btn");
const lightBtn = document.getElementById("theme-light-btn");
const redUpEl = document.getElementById("color-mode-red-up");
const greenUpEl = document.getElementById("color-mode-green-up");
const languageSelect = document.getElementById("language-select");

let state = {
    theme: "dark",
    color_mode: "red_up_green_down",
    auto_order_enabled: false,
    auto_sync_enabled: true,
    default_broker: "中信证券 (机构通道)",
    language: "简体中文",
    logs: [],
};

const setText = (el, text) => {
    if (el) el.textContent = text;
};

const applyThemeState = () => {
    if (darkBtn && lightBtn) {
        const darkActive = state.theme !== "light";
        darkBtn.className = darkActive
            ? "px-3 py-1 bg-primary text-on-primary font-label-xs text-label-xs"
            : "px-3 py-1 hover:bg-outline-variant font-label-xs text-label-xs";
        lightBtn.className = darkActive
            ? "px-3 py-1 hover:bg-outline-variant font-label-xs text-label-xs"
            : "px-3 py-1 bg-primary text-on-primary font-label-xs text-label-xs";
    }
};

const applyColorModeState = () => {
    if (redUpEl && greenUpEl) {
        const redUp = state.color_mode !== "green_up_red_down";
        redUpEl.className = redUp ? "flex items-center gap-1 cursor-pointer" : "flex items-center gap-1 opacity-40 cursor-pointer";
        greenUpEl.className = redUp ? "flex items-center gap-1 opacity-40 cursor-pointer" : "flex items-center gap-1 cursor-pointer";
    }
};

const renderLogs = (logs) => {
    if (!logsTbody) return;
    if (!logs?.length) {
        logsTbody.innerHTML = `<tr><td class="px-4 h-table-row-height text-on-surface-variant" colspan="4">暂无系统日志</td></tr>`;
        return;
    }
    logsTbody.innerHTML = logs
        .map((log) => {
            const dt = new Date(log.timestamp);
            const ts = Number.isNaN(dt.getTime()) ? "--" : dt.toLocaleString();
            const levelClass = log.level === "DB_CONN" ? "text-error" : log.level === "SYS_CORE" ? "text-on-tertiary-container" : "text-primary";
            const statusClass = log.status === "SUCCESS" || log.status === "OK" ? "text-primary" : log.status === "WARN" ? "text-error" : "text-on-surface-variant";
            return `
                <tr class="hover:bg-surface-container-highest/50 transition-colors">
                    <td class="px-4 h-table-row-height">${ts}</td>
                    <td class="px-4 h-table-row-height ${levelClass}">${log.level}</td>
                    <td class="px-4 h-table-row-height">${log.message}</td>
                    <td class="px-4 h-table-row-height"><span class="${statusClass}">${log.status}</span></td>
                </tr>
            `;
        })
        .join("");
};

const syncUiByState = () => {
    if (autoSyncToggle) autoSyncToggle.checked = !!state.auto_sync_enabled;
    if (brokerSelect) brokerSelect.value = state.default_broker;
    if (languageSelect) languageSelect.value = state.language || "简体中文";
    if (autoOrderAuth) {
        autoOrderAuth.textContent = state.auto_order_enabled ? "已开启 (点击关闭)" : "未开启 (点击授权)";
    }
    applyThemeState();
    applyColorModeState();
};

const loadSettings = async () => {
    const [user, overview] = await Promise.all([apiFetch("/auth/me"), apiFetch("/system/overview")]);
    setText(uidEl, user.uid || user.email || user.phone || "--");
    setText(roleEl, user.role || "user");
    if (apiKeyEl) apiKeyEl.textContent = "已配置 (后端托管)";
    setText(versionEl, `Version ${overview.version} (Stable)`);
    if (baostockStatusEl) baostockStatusEl.innerHTML = `<span class="w-2 h-2 ${overview.baostock_connected ? "bg-primary" : "bg-error"} rounded-full ${overview.baostock_connected ? "animate-pulse" : ""}"></span><span class="font-label-xs text-label-xs font-bold">${overview.baostock_connected ? "CONNECTED" : "DISCONNECTED"}</span>`;
    setText(dbStorageEl, `存储占用: ${Number(overview.db_storage_gb || 0).toFixed(1)} GB`);
    setText(dbLatencyEl, `延迟: ${overview.db_latency_ms}ms`);
    setText(riskAgreementStatus, overview.risk_agreement_status || "未签署");
    setText(riskAgreementText, overview.risk_agreement_text || "未配置");

    state = {
        ...state,
        ...(overview.settings || {}),
        theme: overview.theme || state.theme,
        color_mode: overview.color_mode || state.color_mode,
        auto_order_enabled: overview.auto_order_enabled,
        auto_sync_enabled: overview.auto_sync_enabled,
        default_broker: overview.default_broker || state.default_broker,
        logs: overview.logs || [],
    };
    renderLogs(state.logs);
    syncUiByState();
};

const saveSettings = async () => {
    if (saveBtn) saveBtn.disabled = true;
    try {
        const payload = {
            settings: {
                theme: state.theme,
                color_mode: state.color_mode,
                auto_order_enabled: state.auto_order_enabled,
                auto_sync_enabled: state.auto_sync_enabled,
                default_broker: state.default_broker,
                language: state.language,
                db_storage_gb: state.db_storage_gb || 0,
                risk_agreement_status: riskAgreementStatus?.textContent || "已完成",
                risk_agreement_text: riskAgreementText?.textContent || "",
            },
        };
        await apiFetch("/system/settings", { method: "PUT", body: JSON.stringify(payload) });
        alert("系统配置已保存");
    } catch (error) {
        alert(`保存失败: ${error.message}`);
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
};

darkBtn?.addEventListener("click", () => {
    state.theme = "dark";
    applyThemeState();
});
lightBtn?.addEventListener("click", () => {
    state.theme = "light";
    applyThemeState();
});
redUpEl?.addEventListener("click", () => {
    state.color_mode = "red_up_green_down";
    applyColorModeState();
});
greenUpEl?.addEventListener("click", () => {
    state.color_mode = "green_up_red_down";
    applyColorModeState();
});
autoOrderAuth?.addEventListener("click", () => {
    state.auto_order_enabled = !state.auto_order_enabled;
    syncUiByState();
});
autoSyncToggle?.addEventListener("change", () => {
    state.auto_sync_enabled = !!autoSyncToggle.checked;
});
brokerSelect?.addEventListener("change", () => {
    state.default_broker = brokerSelect.value;
});
languageSelect?.addEventListener("change", () => {
    state.language = languageSelect.value;
});
saveBtn?.addEventListener("click", saveSettings);
testDbBtn?.addEventListener("click", async () => {
    await loadSettings();
    alert("连接测试完成");
});
exportLogsBtn?.addEventListener("click", () => {
    const rows = [["timestamp", "level", "message", "status"], ...(state.logs || []).map((l) => [l.timestamp, l.level, l.message, l.status])];
    const csv = rows.map((r) => r.map((x) => `"${String(x ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `system_logs_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

initStatus();
initNavigation();
initAvatarMenu();
loadSettings().catch((error) => {
    console.error(error);
    alert(`加载系统配置失败: ${error.message}`);
});
