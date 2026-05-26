const PAGE_MAP = {
    "选股看板": "选股看板.html",
    "策略参数": "策略参数.html",
    "AI对话": "AI对话.html",
    "持仓风控": "持仓风险.html",
    "复盘日志": "复盘日志.html",
    "系统配置": "系统设置.html",
};

function initNavigation() {
    // 支持原有的 div 结构和新的 .nav-item 结构
    const navItems = document.querySelectorAll("aside nav > div, .nav-item");
    navItems.forEach((item) => {
        const label = item.getAttribute("data-page") || item.querySelector("span.font-body-md")?.textContent?.trim();
        if (label && PAGE_MAP[label]) {
            item.style.cursor = "pointer";
            item.onclick = () => {
                window.location.href = PAGE_MAP[label];
            };
        }
    });
}

export { initNavigation };