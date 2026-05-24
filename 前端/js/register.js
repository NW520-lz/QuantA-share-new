import { apiFetch, setToken } from "./api.js?v=20260525-1";
import { initNavigation } from "./navigation.js?v=20260525-1";

const emailInput = document.getElementById("reg-email");
const codeInput = document.getElementById("reg-code");
const uidInput = document.getElementById("reg-uid");
const passwordInput = document.getElementById("reg-password");
const sendCodeBtn = document.getElementById("send-code-btn");
const submitBtn = document.getElementById("register-submit");
const errorEl = document.getElementById("register-error");

let cooldown = 0;
let cooldownEndsAt = 0;
let timerId = null;

const setError = (message) => {
    if (!errorEl) return;
    if (!message) {
        errorEl.classList.add("hidden");
        errorEl.textContent = "";
        return;
    }
    errorEl.classList.remove("hidden");
    errorEl.textContent = message;
};

const renderCooldown = () => {
    if (!sendCodeBtn) return;
    const remainingMs = cooldownEndsAt - Date.now();
    cooldown = Math.max(0, Math.floor((remainingMs + 999) / 1000));
    if (cooldown <= 0) {
        sendCodeBtn.disabled = false;
        sendCodeBtn.textContent = "发送验证码";
        cooldownEndsAt = 0;
        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }
        return;
    }
    sendCodeBtn.disabled = true;
    sendCodeBtn.textContent = `${cooldown}s 后重试`;
};

sendCodeBtn?.addEventListener("click", async () => {
    setError("");
    const email = emailInput?.value?.trim();
    if (!email) {
        setError("请输入邮箱地址");
        return;
    }
    try {
        const result = await apiFetch("/auth/email/send-code", {
            method: "POST",
            body: JSON.stringify({ email, purpose: "register" }),
        });
        cooldownEndsAt = Date.now() + (result?.retry_after || 60) * 1000;
        renderCooldown();
        if (timerId) {
            clearInterval(timerId);
        }
        timerId = setInterval(renderCooldown, 1000);
    } catch (error) {
        setError(error.message || "发送验证码失败");
    }
});

submitBtn?.addEventListener("click", async () => {
    setError("");
    const email = emailInput?.value?.trim();
    const code = codeInput?.value?.trim();
    const uid = uidInput?.value?.trim();
    const password = passwordInput?.value;
    if (!email || !code || !password) {
        setError("请完整填写邮箱、验证码和密码");
        return;
    }
    submitBtn.disabled = true;
    try {
        await apiFetch("/auth/email/register", {
            method: "POST",
            body: JSON.stringify({ email, code, uid: uid || null, password }),
        });
        const token = await apiFetch("/auth/login", {
            method: "POST",
            body: JSON.stringify({ login: email, password }),
        });
        setToken(token.access_token);
        window.location.href = "选股看板.html";
    } catch (error) {
        setError(error.message || "注册失败");
    } finally {
        submitBtn.disabled = false;
    }
});

initNavigation({ requireAuth: false, redirectAuthedTo: "选股看板.html" });
