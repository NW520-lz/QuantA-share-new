import { clearToken, getToken } from "./api.js";

const PAGE_MAP = {
    "选股看板": "选股看板.html",
    "策略参数": "策略参数.html",
    "ai对话": "AI对话.html",
    "持仓风控": "持仓风险.html",
    "复盘日志": "复盘日志.html",
    "系统配置": "系统设置.html",
};

const PROTECTED_PAGES = new Set(Object.values(PAGE_MAP));
const PUBLIC_PAGES = new Set(["登录.html", "注册.html", "付费中心.html"]);

const normalizeLabel = (label) =>
    (label || "")
        .replace(/\s+/g, "")
        .replace(/[|｜]/g, "")
        .trim()
        .toLowerCase();

const currentFileName = () => {
    const path = decodeURIComponent(window.location.pathname || "");
    const file = path.split("/").pop();
    return file || "登录.html";
};

function applyActiveStyle(item, isActive) {
    if (!item) return;
    if (isActive) {
        item.classList.add("text-primary", "font-bold", "border-r-2", "border-primary", "bg-primary-container/10");
        item.classList.remove("text-on-surface-variant");
    } else {
        item.classList.remove("text-primary", "font-bold", "border-r-2", "border-primary", "bg-primary-container/10");
        item.classList.add("text-on-surface-variant");
    }
}

function bindNavItem(item, targetPage) {
    if (!item || !targetPage) return;
    item.style.cursor = "pointer";
    item.setAttribute("tabindex", "0");
    item.setAttribute("role", "link");

    if (item.tagName.toLowerCase() === "a") {
        item.setAttribute("href", targetPage);
    }

    const go = () => {
        if (currentFileName() === targetPage) return;
        window.location.href = targetPage;
    };

    item.addEventListener("click", (event) => {
        if (event.target.closest("a") && item !== event.target.closest("a")) return;
        event.preventDefault();
        go();
    });

    item.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            go();
        }
    });
}

function initNavigation(options = {}) {
    const requireAuth = options.requireAuth !== false;
    const fileName = currentFileName();
    const hasToken = Boolean(getToken());

    if (requireAuth && PROTECTED_PAGES.has(fileName) && !hasToken) {
        window.location.href = "登录.html";
        return;
    }
    if (hasToken && PUBLIC_PAGES.has(fileName) && options.redirectAuthedTo) {
        window.location.href = options.redirectAuthedTo;
        return;
    }

    const navItems = document.querySelectorAll("aside nav a, aside nav > div");
    navItems.forEach((item) => {
        const rawLabel = item.querySelector("span.font-body-md")?.textContent || item.textContent || "";
        const key = normalizeLabel(rawLabel);
        const targetPage = PAGE_MAP[key];
        if (!targetPage) return;

        bindNavItem(item, targetPage);
        applyActiveStyle(item, fileName === targetPage || (fileName === "策略参数html" && targetPage === "策略参数.html"));
    });

    const logoutBtn = document.querySelector("[data-action='logout']");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", () => {
            clearToken();
            window.location.href = "登录.html";
        });
    }
}

export { initNavigation };
