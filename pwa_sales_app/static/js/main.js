// static/js/main.js

    document.addEventListener("DOMContentLoaded", () => {
    const shell = document.querySelector(".app-shell");
    if (!shell) return;

    // 点击带 data-transition 的链接时，先做动画再跳转
    document.body.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-transition]");
        if (!link) return;

        const url = link.getAttribute("href");
        const type = link.dataset.transition;

        // 外部链接 / 空链接直接放行
        if (!url || url.startsWith("http")) return;

        event.preventDefault();

        // 区分“返回”还是“前进”
        if (type === "back") {
        shell.classList.add("page-slide-out-right");
        } else {
        // tab 切换、前进都用左滑出去
        shell.classList.add("page-slide-out-left");
        }

        setTimeout(() => {
        window.location.href = url;
        }, 180); // 和 CSS 动画时间对上
    });
    });