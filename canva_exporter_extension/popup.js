document.addEventListener("DOMContentLoaded", () => {
    const backendUrlInput = document.getElementById("backend-url");
    const accountIdInput = document.getElementById("account-id");
    const autoPushToggle = document.getElementById("auto-push");
    const exportFilenameInput = document.getElementById("export-filename");
    const saveBtn = document.getElementById("save-btn");
    const pushNowBtn = document.getElementById("push-now-btn");
    const exportBtn = document.getElementById("export-btn");
    const clearDataBtn = document.getElementById("clear-data-btn");
    const clearCookiesBtn = document.getElementById("clear-cookies-btn");
    const interceptStatus = document.getElementById("intercept-status");
    const interceptCountEl = document.getElementById("intercept-count");
    const pushStatus = document.getElementById("push-status");
    const cookieCountLine = document.getElementById("cookie-count-line");
    const msgEl = document.getElementById("msg");

    // ─── 加载已保存的配置 ───
    chrome.storage.local.get(
        ["backendUrl", "accountId", "autoPush", "canvaHeaders", "timestamp", "lastPushTime", "pushStatus", "interceptCount", "exportFilename"],
        (cfg) => {
            backendUrlInput.value = cfg.backendUrl || "http://localhost:18157";
            accountIdInput.value = cfg.accountId || "";
            autoPushToggle.checked = !!cfg.autoPush;
            exportFilenameInput.value = cfg.exportFilename || "canva_token";
            updateInterceptUI(cfg);
            updateCookieCount();
        }
    );

    // ─── 定时刷新状态 ───
    setInterval(() => {
        chrome.storage.local.get(
            ["canvaHeaders", "timestamp", "lastPushTime", "pushStatus", "interceptCount"],
            (cfg) => updateInterceptUI(cfg)
        );
        updateCookieCount();
    }, 2000);

    function updateInterceptUI(cfg) {
        const count = cfg.interceptCount || 0;

        if (cfg.canvaHeaders && cfg.timestamp) {
            const time = new Date(cfg.timestamp).toLocaleTimeString();
            interceptStatus.innerHTML = `<span class="status-dot green"></span> 已拦截 · 最后更新: ${time}`;
            interceptCountEl.textContent = `${count} 次`;
            interceptCountEl.style.display = "inline-block";
        } else {
            interceptStatus.innerHTML = `<span class="status-dot yellow"></span> 等待拦截... 请打开 Canva 页面`;
            interceptCountEl.style.display = "none";
        }
        // Re-append count element (innerHTML replaces children)
        interceptStatus.appendChild(interceptCountEl);

        if (cfg.lastPushTime) {
            const pushTime = new Date(cfg.lastPushTime).toLocaleTimeString();
            const ok = cfg.pushStatus === "ok";
            pushStatus.innerHTML = ok
                ? `<span class="status-dot green"></span> 上次推送成功: ${pushTime}`
                : `<span class="status-dot red"></span> 推送失败，请检查后台是否运行`;
        }
    }

    function updateCookieCount() {
        chrome.cookies.getAll({ url: "https://www.canva.com" }, (cookies) => {
            if (cookies && cookies.length > 0) {
                cookieCountLine.innerHTML = `🍪 当前 Canva Cookies: <strong style="color:#a855f7;">${cookies.length}</strong> 条`;
            } else {
                cookieCountLine.innerHTML = `🍪 当前 Canva Cookies: 0 条`;
            }
        });
    }

    // ─── 保存配置 ───
    saveBtn.addEventListener("click", () => {
        chrome.storage.local.set({
            backendUrl: backendUrlInput.value.trim().replace(/\/$/, ""),
            accountId: accountIdInput.value.trim(),
            autoPush: autoPushToggle.checked,
            exportFilename: exportFilenameInput.value.trim() || "canva_token"
        }, () => {
            showMsg("✅ 配置已保存", "#10b981");
        });
    });

    // ─── 立即推送一次 ───
    pushNowBtn.addEventListener("click", async () => {
        pushNowBtn.disabled = true;
        pushNowBtn.textContent = "推送中...";

        const cfg = await getStorage(["canvaHeaders", "backendUrl", "accountId"]);

        if (!cfg.canvaHeaders) {
            showMsg("❌ 还没拦截到 Token，请先打开 Canva 页面", "#ef4444");
            pushNowBtn.disabled = false;
            pushNowBtn.textContent = "⚡ 立即推送一次";
            return;
        }
        if (!cfg.accountId) {
            showMsg("❌ 请先填写并保存账号 ID", "#ef4444");
            pushNowBtn.disabled = false;
            pushNowBtn.textContent = "⚡ 立即推送一次";
            return;
        }

        const backendUrl = cfg.backendUrl || "http://localhost:18157";

        try {
            const cookies = await getCookies();
            const tokenData = {
                api_requests: [{ headers: cfg.canvaHeaders }],
                cookies: cookies
            };

            const resp = await fetch(`${backendUrl}/api/accounts/${cfg.accountId}/token`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token_data: tokenData })
            });

            if (resp.ok) {
                chrome.storage.local.set({ lastPushTime: Date.now(), pushStatus: "ok" });
                showMsg("✅ 推送成功！后台已更新最新 Token", "#10b981");
            } else {
                const err = await resp.json().catch(() => ({}));
                chrome.storage.local.set({ pushStatus: "fail" });
                showMsg(`❌ 推送失败: ${err.error || resp.status}`, "#ef4444");
            }
        } catch (e) {
            chrome.storage.local.set({ pushStatus: "fail" });
            showMsg("❌ 无法连接后台，请确认服务已启动", "#ef4444");
        }

        pushNowBtn.disabled = false;
        pushNowBtn.textContent = "⚡ 立即推送一次";
    });

    // ─── 手动导出文件 ───
    exportBtn.addEventListener("click", () => {
        chrome.storage.local.get(["canvaHeaders", "exportFilename"], (result) => {
            if (!result.canvaHeaders) {
                showMsg("❌ 没有可导出的 Token", "#ef4444");
                return;
            }
            chrome.cookies.getAll({ url: "https://www.canva.com" }, (cookies) => {
                const cookieObj = {};
                cookies.forEach(c => cookieObj[c.name] = c.value);

                const exportData = {
                    api_requests: [{ headers: result.canvaHeaders }],
                    cookies: cookieObj
                };

                // 使用自定义文件名
                let filename = (result.exportFilename || exportFilenameInput.value || "canva_token").trim();
                if (!filename) filename = "canva_token";
                // 移除用户可能手动加的 .json 后缀
                filename = filename.replace(/\.json$/i, "");
                filename += ".json";

                const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                chrome.downloads.download({ url, filename, saveAs: true }, () => {
                    showMsg("✅ 文件已导出", "#10b981");
                });
            });
        });
    });

    // ─── 清除拦截数据（切换账号时使用） ───
    clearDataBtn.addEventListener("click", () => {
        if (!confirm("确认清除所有已拦截的 Token 数据吗？\n（切换账号前建议先清除，防止数据混淆）")) return;

        chrome.storage.local.remove(
            ["canvaHeaders", "timestamp", "interceptCount", "lastPushTime", "pushStatus"],
            () => {
                // 清除 badge
                chrome.action.setBadgeText({ text: "" });
                showMsg("✅ 拦截数据已清除，可以切换账号了", "#10b981");
                // 刷新 UI
                interceptStatus.innerHTML = `<span class="status-dot yellow"></span> 等待拦截... 请打开 Canva 页面`;
                interceptCountEl.style.display = "none";
                interceptStatus.appendChild(interceptCountEl);
                pushStatus.innerHTML = "";
            }
        );
    });

    // ─── 清除 Canva Cookies ───
    clearCookiesBtn.addEventListener("click", async () => {
        if (!confirm("确认清除浏览器中所有 Canva 的 Cookies 吗？\n清除后需要重新登录 Canva。")) return;

        clearCookiesBtn.disabled = true;
        clearCookiesBtn.textContent = "清除中...";

        try {
            const cookies = await new Promise(resolve => {
                chrome.cookies.getAll({ url: "https://www.canva.com" }, resolve);
            });

            let removed = 0;
            for (const cookie of cookies) {
                const protocol = cookie.secure ? "https" : "http";
                const cookieUrl = `${protocol}://${cookie.domain.replace(/^\./, "")}${cookie.path}`;
                await new Promise(resolve => {
                    chrome.cookies.remove({ url: cookieUrl, name: cookie.name }, resolve);
                });
                removed++;
            }

            showMsg(`✅ 已清除 ${removed} 条 Canva Cookies`, "#10b981");
            updateCookieCount();
        } catch (e) {
            showMsg("❌ 清除 Cookies 失败", "#ef4444");
        }

        clearCookiesBtn.disabled = false;
        clearCookiesBtn.textContent = "🍪 清除 Canva Cookies";
    });

    // ─── 工具函数 ───
    function getStorage(keys) {
        return new Promise(resolve => chrome.storage.local.get(keys, resolve));
    }

    function getCookies() {
        return new Promise(resolve => {
            chrome.cookies.getAll({ url: "https://www.canva.com" }, (cookies) => {
                const obj = {};
                cookies.forEach(c => obj[c.name] = c.value);
                resolve(obj);
            });
        });
    }

    function showMsg(text, color) {
        msgEl.textContent = text;
        msgEl.style.color = color;
        setTimeout(() => { msgEl.textContent = ""; }, 5000);
    }
});
