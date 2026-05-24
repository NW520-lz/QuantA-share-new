import { API_BASE, apiFetch } from "./api.js";

function initStatus() {
    const statusEls = document.querySelectorAll("[data-status]");
    const syncEls = document.querySelectorAll("[data-sync]");
    const latencyEls = document.querySelectorAll("[data-latency]");

    const updateAll = (nodeList, text) => {
        nodeList.forEach((el) => {
            el.textContent = text;
        });
    };

    const refresh = async () => {
        const start = performance.now();
        try {
            await apiFetch("/system/status");
            const latency = Math.round(performance.now() - start);
            updateAll(statusEls, "在线");
            updateAll(syncEls, "同步中");
            updateAll(latencyEls, `${latency}ms`);
        } catch (error) {
            updateAll(statusEls, "断开");
            updateAll(syncEls, "未同步");
        }
    };

    const startHeartbeat = () => {
        if (!statusEls.length && !syncEls.length) return;
        const source = new EventSource(`${API_BASE}/system/heartbeat`);
        source.onmessage = () => {
            updateAll(statusEls, "在线");
            updateAll(syncEls, "同步中");
        };
        source.onerror = () => {
            updateAll(statusEls, "断开");
            updateAll(syncEls, "未同步");
        };
    };

    refresh();
    setInterval(refresh, 15000);
    startHeartbeat();
}

export { initStatus };
