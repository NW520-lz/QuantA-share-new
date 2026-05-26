const DEFAULT_API_BASE = `${window.location.origin}/api/v1`;
const API_BASE = window.API_BASE || DEFAULT_API_BASE;
const TOKEN_KEY = "quanta_token";
const LOGIN_PAGE = "登录.html";

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

function requireAuth() {
    if (!getToken()) {
        const current = encodeURIComponent(window.location.pathname.split("/").pop() || "");
        window.location.href = current ? `${LOGIN_PAGE}?redirect=${current}` : LOGIN_PAGE;
        return false;
    }
    return true;
}

function sanitize(str) {
    if (str === null || str === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
}

function sanitizeHTML(html) {
    if (!html) return "";
    const div = document.createElement("div");
    div.innerHTML = html;
    div.querySelectorAll("script,style,iframe,object,embed,form,input,textarea,select,button,link,meta").forEach((el) => el.remove());
    div.querySelectorAll("*").forEach((el) => {
        [...el.attributes].forEach((attr) => {
            if (attr.name.startsWith("on") || attr.name === "srcdoc") {
                el.removeAttribute(attr.name);
            }
            if ((attr.name === "href" || attr.name === "src" || attr.name === "action") && /^\s*javascript:/i.test(attr.value)) {
                el.removeAttribute(attr.name);
            }
        });
    });
    return div.innerHTML;
}

async function apiFetch(path, options = {}) {
    const headers = options.headers ? { ...options.headers } : {};
    if (options.body && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }

    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const maxRetries = options.retries ?? 2;
    let lastError;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const response = await fetch(`${API_BASE}${path}`, {
                ...options,
                headers,
            });

            const text = await response.text();
            let data = null;
            if (text) {
                try {
                    data = JSON.parse(text);
                } catch {
                    data = { detail: text };
                }
            }

            if (!response.ok) {
                if (response.status === 401) {
                    clearToken();
                    window.location.href = LOGIN_PAGE;
                    throw new Error("未登录，正在跳转到登录页...");
                }
                const error = new Error(data?.detail || response.statusText || "Request failed");
                error.status = response.status;
                error.data = data;
                throw error;
            }

            return data;
        } catch (error) {
            lastError = error;
            if (error.status === 401 || error.status === 403 || error.status === 404 || error.status === 422) {
                throw error;
            }
            if (attempt < maxRetries) {
                await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
            }
        }
    }
    throw lastError;
}

function formatDate(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

export { API_BASE, apiFetch, getToken, setToken, clearToken, formatDate, requireAuth, sanitize, sanitizeHTML, LOGIN_PAGE };
