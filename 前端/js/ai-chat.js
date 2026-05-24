import { API_BASE, apiFetch, getToken } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";
import { requireTier } from "./tier-guard.js";
import { initAvatarMenu } from "./avatar-menu.js";
await requireTier("daoyou");

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

const appendLog = (text) => {
    if (!logContainer) return;
    const div = document.createElement("div");
    div.className = "text-on-tertiary-container";
    div.textContent = text;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
};

const loadSystemLogs = async () => {
    if (!logContainer) return;
    logContainer.innerHTML = "";
    try {
        const logs = await apiFetch("/system/logs?channel=ai,system,review&limit=80", { method: "GET" });
        if (!logs.length) {
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

function parseMarkdown(md) {
    let html = md;
    html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    html = html
        .replace(/^#### (.+)$/gm, '<h5 class="text-body-md font-bold text-on-surface mt-4 mb-1">$1</h5>')
        .replace(/^### (.+)$/gm, '<h4 class="text-headline-md font-bold text-primary mt-5 mb-2">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 class="text-headline-md font-bold text-primary mt-6 mb-2">$1</h3>')
        .replace(/^# (.+)$/gm, '<h2 class="text-display-lg font-bold text-primary mt-6 mb-3">$1</h2>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-on-surface font-semibold">$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em class="text-on-surface-variant">$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code class="bg-surface-container-low text-primary text-[12px] px-1.5 py-0.5 rounded font-data-tabular">$1</code>');
    html = html.replace(/---/g, '<hr class="border-outline-variant my-4">');

    const lines = html.split("\n");
    const out = [];
    let inUl = false, inOl = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const ulMatch = line.match(/^- (.+)$/);
        const olMatch = line.match(/^(\d+)\. (.+)$/);

        if (ulMatch) {
            if (inOl) { out.push("</ol>"); inOl = false; }
            if (!inUl) { out.push('<ul class="list-disc pl-5 space-y-1 text-body-md text-on-surface-variant leading-relaxed">'); inUl = true; }
            out.push(`<li>${ulMatch[1]}</li>`);
            continue;
        }
        if (olMatch) {
            if (inUl) { out.push("</ul>"); inUl = false; }
            if (!inOl) { out.push('<ol class="list-decimal pl-5 space-y-1 text-body-md text-on-surface-variant leading-relaxed">'); inOl = true; }
            out.push(`<li>${olMatch[2]}</li>`);
            continue;
        }
        if (inUl) { out.push("</ul>"); inUl = false; }
        if (inOl) { out.push("</ol>"); inOl = false; }
        if (line.trim() === "") {
            out.push('<div class="h-2"></div>');
        } else if (!line.startsWith("<")) {
            out.push(`<p class="text-body-md text-on-surface-variant leading-relaxed">${line}</p>`);
        } else {
            out.push(line);
        }
    }
    if (inUl) out.push("</ul>");
    if (inOl) out.push("</ol>");
    return out.join("\n");
}

const appendMessage = (role, text) => {
    if (!messageContainer) return null;
    const wrapper = document.createElement("div");

    if (role === "user") {
        wrapper.className = "flex justify-end";
        wrapper.innerHTML = `
            <div class="max-w-[70%] bg-surface-container-highest text-on-surface p-4 rounded-xl rounded-tr-none border border-outline-variant">
                <p class="text-body-md" data-message-text></p>
            </div>
        `;
    } else {
        wrapper.className = "flex gap-4";
        wrapper.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-on-primary">memory</span>
            </div>
            <div class="max-w-[85%] ai-bubble p-5 rounded-xl rounded-tl-none shadow-lg border border-outline-variant/30 ai-prose">
                <div class="flex items-center gap-2 mb-3">
                    <span class="text-primary font-bold text-label-xs tracking-wider">量化 AI 助手</span>
                    <span class="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] border border-primary/20">DeepSeek</span>
                </div>
                <div class="text-on-surface-variant leading-relaxed" data-message-text></div>
            </div>
        `;
    }

    messageContainer.appendChild(wrapper);
    const textEl = wrapper.querySelector("[data-message-text]");
    if (textEl) textEl.textContent = text;
    messageContainer.scrollTop = messageContainer.scrollHeight;
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
        appendMessage("assistant", "请先登录获取访问令牌。");
        return;
    }

    const conversationId = getConversationId();
    const payload = { conversationId, message, attachments: [], debug: false };

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

    const decoder = new TextDecoder("utf-8");
    const reader = response.body.getReader();
    let buffer = "";
    const assistantTextEl = appendMessage("assistant", "");
    let contentAcc = "";

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
                        if (assistantTextEl) assistantTextEl.innerHTML = parseMarkdown(contentAcc);
                    }
                    if (payload.eventType === "SYSTEM_LOG" && payload.data?.text) {
                        appendLog(`[${new Date().toLocaleTimeString()}] INFO: ${payload.data.text}`);
                    }
                    if (payload.eventType === "FINAL_RESULT" && payload.data?.outputText) {
                        if (assistantTextEl && !contentAcc) {
                            contentAcc = payload.data.outputText;
                            assistantTextEl.innerHTML = parseMarkdown(contentAcc);
                        }
                    }
                } catch (error) {
                    appendLog(`解析失败: ${jsonText}`);
                }
            }
        }
        if (assistantTextEl) messageContainer.scrollTop = messageContainer.scrollHeight;
    }
};

const handleSend = async () => {
    const text = inputEl?.value?.trim();
    if (!text) return;
    appendMessage("user", text);
    if (inputEl) inputEl.value = "";
    appendLog(`[${new Date().toLocaleTimeString()}] 用户发送消息`);

    try {
        await streamChat(text);
        appendLog(`[${new Date().toLocaleTimeString()}] AI 响应完成`);
    } catch (error) {
        appendMessage("assistant", "AI 服务暂时不可用，请稍后重试。");
        appendLog(`[${new Date().toLocaleTimeString()}] AI 请求失败: ${error.message}`);
    } finally {
        loadSystemLogs().catch(() => {});
    }
};

if (sendButton) sendButton.addEventListener("click", handleSend);
if (inputEl) {
    inputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            handleSend();
        }
    });
}
if (messageContainer) messageContainer.innerHTML = "";
loadSystemLogs().catch(() => {});

quickButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const key = button.dataset.quickAction;
        const prompt = QUICK_ACTION_PROMPTS[key] || "";
        if (!prompt || !inputEl) return;
        inputEl.value = prompt;
        handleSend();
    });
});

initStatus();
initNavigation();
initAvatarMenu();
