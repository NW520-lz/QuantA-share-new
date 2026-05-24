import { apiFetch, clearToken } from "./api.js";

const TIER_LABEL = {
    "lüyi": "蝼蚁期",
    daoyou: "道友期",
    qianbei: "前辈期",
    trial: "试用期",
};

const TIER_COLOR = {
    "lüyi": "bg-zinc-700 text-zinc-300",
    daoyou: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    qianbei: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    trial: "bg-zinc-700 text-zinc-300",
};

let _userInfo = null;
let _subInfo = null;

async function loadUserInfo() {
    if (_userInfo && _subInfo) return { user: _userInfo, sub: _subInfo };
    try {
        const [user, sub] = await Promise.all([
            apiFetch("/auth/me"),
            apiFetch("/billing/subscription"),
        ]);
        _userInfo = user;
        _subInfo = sub;
        return { user, sub };
    } catch {
        return { user: null, sub: null };
    }
}

function formatDate(iso) {
    if (!iso) return "--";
    try {
        return new Date(iso).toLocaleDateString("zh-CN");
    } catch {
        return iso.slice(0, 10);
    }
}

function createDropdown(user, sub, rect) {
    const email = user?.email || "未知";
    const tier = sub?.tier || "lüyi";
    const tierLabel = TIER_LABEL[tier] || tier;
    const tierColor = TIER_COLOR[tier] || "";
    const expiry = formatDate(sub?.ends_at);
    const planName = sub?.is_subscribed
        ? (sub?.plan_code === "qianbei_yearly" ? "前辈期"
            : sub?.plan_code === "daoyou_monthly" ? "道友期"
            : tierLabel)
        : "蝼蚁期（免费）";

    const panel = document.createElement("div");
    // 挂到 body，fixed 定位跟随头像，彻底避免 overflow-hidden 裁剪
    panel.style.cssText = `position:fixed;top:${rect.bottom + 8}px;right:${window.innerWidth - rect.right}px;z-index:9999;`;
    panel.className = "w-56 bg-[#2a2a2c] border border-[#44474d] rounded-lg shadow-2xl";
    panel.innerHTML = `
        <div class="p-3 border-b border-[#44474d] space-y-1.5">
            <p class="text-sm text-[#e4e2e4] font-medium truncate">${email}</p>
            <div class="flex items-center gap-2">
                <span class="text-[11px] ${tierColor} px-1.5 py-0.5 rounded border">${planName}</span>
            </div>
            <p class="text-[11px] text-[#c5c6cd]">到期: ${expiry}</p>
        </div>
        <a href="付费中心.html" class="w-full text-left px-3 py-2 text-sm text-[#e4e2e4] hover:bg-white/5 flex items-center gap-2 transition-colors">
            <span class="material-symbols-outlined text-[16px]">upgrade</span>
            升级会员
        </a>
        <button data-action="logout" class="w-full text-left px-3 py-2 text-sm text-[#ffb4ab] hover:bg-red-500/10 flex items-center gap-2 rounded-b-lg transition-colors">
            <span class="material-symbols-outlined text-[16px]">logout</span>
            退出登录
        </button>
    `;
    return panel;
}

let _openPanel = null;

function closePanel() {
    if (_openPanel) {
        _openPanel.remove();
        _openPanel = null;
        document.removeEventListener("click", onDocumentClick, true);
    }
}

function onDocumentClick(e) {
    if (!_openPanel) return;
    const avatar = document.querySelector("[data-action='avatar-menu']");
    if (avatar?.contains(e.target) || _openPanel.contains(e.target)) return;
    closePanel();
}

export async function initAvatarMenu() {
    const avatar = document.querySelector("[data-action='avatar-menu']");
    if (!avatar) return;

    avatar.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (_openPanel) { closePanel(); return; }

        const rect = avatar.getBoundingClientRect();
        const { user, sub } = await loadUserInfo();
        const panel = createDropdown(user, sub, rect);
        document.body.appendChild(panel);
        _openPanel = panel;

        panel.querySelector("[data-action='logout']")?.addEventListener("click", (ev) => {
            ev.stopPropagation();
            clearToken();
            window.location.href = "登录.html";
        });

        requestAnimationFrame(() => {
            document.addEventListener("click", onDocumentClick, true);
        });
    });
}
