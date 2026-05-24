import { apiFetch, setToken } from "./api.js";
import { initStatus } from "./status.js";
import { initNavigation } from "./navigation.js";

const form = document.getElementById("login-form");
const accountInput = document.getElementById("login-account");
const passwordInput = document.getElementById("password-input");
const errorEl = document.getElementById("login-error");
const submitButton = document.getElementById("login-submit");

const setError = (message) => {
    if (!errorEl) return;
    if (!message) {
        errorEl.textContent = "";
        errorEl.classList.add("hidden");
        return;
    }
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
};

if (form) {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setError("");

        const login = accountInput?.value?.trim();
        const password = passwordInput?.value;
        if (!login || !password) {
            setError("请输入账号和密码");
            return;
        }

        if (submitButton) submitButton.disabled = true;
        try {
            const data = await apiFetch("/auth/login", {
                method: "POST",
                body: JSON.stringify({ login, password }),
            });
            setToken(data.access_token);
            const params = new URLSearchParams(window.location.search);
            const redirect = params.get("redirect");
            const target = redirect || (data.is_subscribed ? "选股看板.html" : "付费中心.html");
            window.location.href = target;
        } catch (error) {
            setError(error.message || "登录失败");
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
}

initStatus();
initNavigation({ requireAuth: false, redirectAuthedTo: "选股看板.html" });
