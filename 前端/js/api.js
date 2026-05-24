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

async function apiFetch(path, options = {}) {
    const headers = options.headers ? { ...options.headers } : {};
    if (options.body && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }

    const token = getToken();
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

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
}

function formatDate(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

export { API_BASE, apiFetch, getToken, setToken, clearToken, formatDate, requireAuth, LOGIN_PAGE };
