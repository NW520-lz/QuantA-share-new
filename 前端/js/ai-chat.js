import { API_BASE, apiFetch, getToken, sanitizeHTML } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";

// 全局配置 marked
if (window.marked) {
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
    });
}

const messageContainer = document.getElementById("chat-messages");
const inputEl = document.getElementById("chat-input");
const sendButton = document.getElementById("chat-send");
const logContainer = document.getElementById("log-container");
const quickButtons = document.querySelectorAll("[data-quick-action]");

const QUICK_ACTION_PROMPTS = {
    pick_now: "立即选股：请只返回今天高胜率标的，按胜率从高到低给出买入参考、止损价、止盈价。",
    empty_or_hold: "判断今日是否空仓：结合最新市场情绪、涨跌家数和我的持仓风险，给出明确结论（空仓/持仓）。",
    analyze_stock: "分析某只股票：请先向我确认股票代码，然后输出趋势、支撑阻力、风险点和交易计划。",
    optimize_params: "优化策略参数：基于最近回测结果，给出回看天数、持仓天数、止损和止盈参数优化建议。",
};

const scrollToBottom = () => {
    if (messageContainer) {
        messageContainer.scrollTo({
            top: messageContainer.scrollHeight,
            behavior: "smooth"
        });
    }
};

const appendLog = (text) => {
    if (!logContainer) return;
    const div = document.createElement("div");
    div.className = "text-on-tertiary-container border-l-2 border-primary/30 pl-2 mb-1 py-1 text-[11px] opacity-80 hover:opacity-100 transition-opacity";
    div.textContent = text;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
};

const loadSystemLogs = async () => {
    if (!logContainer) return;
    logContainer.innerHTML = "";
    try {
        const logs = await apiFetch("/system/logs?channel=ai,system,review&limit=80", { method: "GET" });
        if (!logs || !logs.length) {
            appendLog(`[${new Date().toLocaleTimeString()}] INFO: 暂无日志`);
            return;
        }
        logs
            .slice()
            .reverse()
            .forEach((item) => {
                const dt = new Date(item.timestamp);
                const ts = Number.isNaN(dt.getTime()) ? "--:--:--" : dt.toLocaleTimeString();
                const level = (item.level || "INFO").toUpperCase();
                const source = item.source ? `${item.source} ` : "";
                appendLog(`[${ts}] ${level}: ${source}${item.message}`);
            });
    } catch (error) {
        appendLog(`[${new Date().toLocaleTimeString()}] WARN: 日志加载失败: ${error.message}`);
    }
};

const createTypingIndicator = () => {
    const div = document.createElement("div");
    div.className = "flex gap-4 items-start animate-in fade-in slide-in-from-bottom-2 duration-300";
    div.id = "typing-indicator";
    div.innerHTML = `
        <div class="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-outlined text-primary text-[18px]">memory</span>
        </div>
        <div class="ai-bubble p-4 rounded-xl rounded-tl-none border border-outline-variant/30 flex items-center gap-3">
            <span class="text-label-xs text-on-surface-variant">AI 正在思考</span>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    return div;
};

const appendMessage = (role, text) => {
    if (!messageContainer) return null;
    const wrapper = document.createElement("div");
    wrapper.className = "animate-in fade-in slide-in-from-bottom-2 duration-500";

    if (role === "user") {
        wrapper.classList.add("flex", "justify-end");
        wrapper.innerHTML = `
            <div class="max-w-[75%] bg-primary-container/40 text-on-surface p-4 rounded-2xl rounded-tr-none border border-primary/20 shadow-sm">
                <div class="text-body-md whitespace-pre-wrap" data-message-text></div>
            </div>
        `;
    } else {
        wrapper.classList.add("flex", "gap-4");
        wrapper.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0 shadow-lg shadow-primary/10">
                <span class="material-symbols-outlined text-on-primary text-[18px]">memory</span>
            </div>
            <div class="max-w-[88%] ai-bubble p-5 rounded-2xl rounded-tl-none shadow-xl border border-outline-variant/20 ai-prose overflow-hidden">
                <div class="flex items-center justify-between mb-4 pb-2 border-b border-outline-variant/10">
                    <div class="flex items-center gap-2">
                        <span class="text-primary font-bold text-label-xs tracking-widest uppercase">Quant Engine AI</span>
                        <span class="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-[9px] border border-primary/20 font-bold">V2.4</span>
                    </div>
                    <span class="text-[10px] text-on-surface-variant/50">${new Date().toLocaleTimeString()}</span>
                </div>
                <div class="text-on-surface-variant leading-relaxed selection:bg-primary/30" data-message-text></div>
            </div>
        `;
    }

    messageContainer.appendChild(wrapper);
    const textEl = wrapper.querySelector("[data-message-text]");
    if (textEl) {
        if (role === "user") {
            textEl.textContent = text;
        } else {
            textEl.innerHTML = window.marked ? sanitizeHTML(marked.parse(text || "")) : sanitizeHTML(text);
        }
    }
    scrollToBottom();
    return textEl;
};

const getConversationId = () => {
    const key = "quanta_conversation_id";
    const existing = localStorage.getItem(key);
    if (existing) return Number(existing);
    const next = Date.now();
    localStorage.setItem(key, String(next));
    return next;
};

const streamChat = async (message) => {
    const token = getToken();
    if (!token) {
        appendMessage("assistant", "⚠️ **请先登录** 以访问 AI 交易助手。");
        return;
    }

    const conversationId = getConversationId();
    const payload = { conversationId, message, attachments: [], debug: false };

    // 显示思考状态
    const indicator = createTypingIndicator();
    messageContainer.appendChild(indicator);
    scrollToBottom();

    try {
        const response = await fetch(`${API_BASE}/ai/chat/${conversationId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify(payload),
        });

        if (!response.ok || !response.body) {
            let detail = "AI 请求失败";
            try {
                const text = await response.text();
                if (text) {
                    try { const json = JSON.parse(text); detail = json?.detail || detail; } catch { detail = text; }
                }
            } catch { /* ignore */ }
            throw new Error(detail);
        }

        // 移除思考状态
        indicator.remove();

        const decoder = new TextDecoder("utf-8");
        const reader = response.body.getReader();
        let buffer = "";
        const assistantTextEl = appendMessage("assistant", "");
        let contentAcc = "";
        let lastScrollTime = 0;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
                const lines = part.split("\n");
                for (const line of lines) {
                    if (!line.startsWith("data:")) continue;
                    const jsonText = line.slice(5).trim();
                    if (!jsonText) continue;
                    try {
                        const payload = JSON.parse(jsonText);
                        if (payload.eventType === "MESSAGE" && payload.data?.text) {
                            contentAcc += payload.data.text;
                            if (assistantTextEl) {
                                assistantTextEl.innerHTML = window.marked ? marked.parse(contentAcc) : contentAcc;
                                // 限制滚动频率，避免过于频繁导致卡顿
                                const now = Date.now();
                                if (now - lastScrollTime > 100) {
                                    scrollToBottom();
                                    lastScrollTime = now;
                                }
                            }
                        }
                        if (payload.eventType === "SYSTEM_LOG" && payload.data?.text) {
                            appendLog(`[${new Date().toLocaleTimeString()}] INFO: ${payload.data.text}`);
                        }
                    } catch (e) {
                        console.warn("Parse SSE failed", e, jsonText);
                    }
                }
            }
        }
        scrollToBottom(); // 最终滚动到底部
    } catch (error) {
        indicator.remove();
        appendMessage("assistant", `❌ **错误**: ${error.message}`);
    }
};

const handleSend = async () => {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = "";
    inputEl.style.height = "auto";
    appendMessage("user", text);
    await streamChat(text);
};

// 事件监听
sendButton?.addEventListener("click", handleSend);
inputEl?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

// 自动调整输入框高度
inputEl?.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = `${Math.min(inputEl.scrollHeight, 200)}px`;
});

quickButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
        const action = btn.getAttribute("data-quick-action");
        const prompt = QUICK_ACTION_PROMPTS[action];
        if (!prompt) return;
        inputEl.value = prompt;
        inputEl.dispatchEvent(new Event("input"));
        const text = inputEl.value.trim();
        if (!text) return;
        inputEl.value = "";
        inputEl.style.height = "auto";
        appendMessage("user", text);
        await streamChat(text);
    });
});

// 初始化
(async () => {
    initStatus();
    initNavigation();
    initAvatarMenu();
    loadSystemLogs();
    setInterval(loadSystemLogs, 30000);

    // 等待权限检查，但不阻塞 UI
    requireTier("daoyou").catch(err => {
        console.error("Tier check failed", err);
    });
})();
