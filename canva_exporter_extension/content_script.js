// ─── Canva 内容脚本：在 canva.com 页面上下文中执行 API 请求 ───
// 这个脚本注入到真实的 canva.com 页面中运行，
// 拥有完整的 Cookie、Cloudflare clearance 和会话状态，
// 因此可以直接调用 Canva 的内部 API 不会被拦截。

(function () {
    let polling = false;
    let pollTimer = null;

    // 启动轮询
    function startPolling() {
        if (polling) return;
        polling = true;
        poll();
    }

    async function poll() {
        if (!polling) return;
        try {
            const config = await chrome.storage.local.get(["backendUrl", "accountId"]);
            const backendUrl = config.backendUrl || "http://localhost:18157";
            const accountId = config.accountId;
            if (!accountId) {
                pollTimer = setTimeout(poll, 3000);
                return;
            }

            // 向后端询问：有没有待执行的任务？
            const resp = await fetch(`${backendUrl}/api/extension/pending?account_id=${accountId}`);
            if (!resp.ok) {
                pollTimer = setTimeout(poll, 3000);
                return;
            }

            const tasks = await resp.json();
            if (tasks && tasks.length > 0) {
                for (const task of tasks) {
                    await executeTask(task, backendUrl);
                }
            }
        } catch (e) {
            // 后台可能没启动，静默忽略
        }
        pollTimer = setTimeout(poll, 2000);
    }

    async function executeTask(task, backendUrl) {
        const taskId = task.task_id;
        const action = task.action; // "get_members" | "remove_member"
        const brandId = task.brand_id;
        const headers = task.headers || {};
        const payload = task.payload || {};

        let result;
        try {
            if (action === "get_members") {
                result = await fetchMembers(brandId, headers);
            } else if (action === "remove_member") {
                result = await removeMember(brandId, headers, payload);
            } else {
                result = { error: `未知操作: ${action}` };
            }
        } catch (e) {
            result = { error: e.message };
        }

        // 把结果推回后端
        try {
            await fetch(`${backendUrl}/api/extension/result`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ task_id: taskId, result })
            });
        } catch (e) {
            console.error("[Canva Extension] 推送结果失败:", e);
        }
    }

    async function fetchMembers(brandId, headers) {
        const url = `https://www.canva.com/_ajax/profile/v2/brands/${brandId}/members?type=ALL&includeAvatars=true&includeEmails=true&includeDeleted=false&limit=1000&requireConsistentRead=false`;
        const resp = await fetch(url, {
            method: "GET",
            headers: headers,
            credentials: "include"
        });
        if (!resp.ok) {
            return { error: `Canva API 返回 ${resp.status}`, status: resp.status };
        }
        let text = await resp.text();
        // 清除 Canva 防劫持前缀
        if (text.includes("while(1)")) {
            const idx = text.indexOf("\n");
            if (idx !== -1) text = text.substring(idx + 1);
        }
        return JSON.parse(text);
    }

    async function removeMember(brandId, headers, payload) {
        const url = "https://www.canva.com/_ajax/profile/brands/members";
        const body = {
            brand: brandId,
            remove: [payload.user_id],
            sendBrandMemberRemovedMessage: true
        };
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                ...headers,
                "Content-Type": "application/json;charset=UTF-8"
            },
            credentials: "include",
            body: JSON.stringify(body)
        });
        if (!resp.ok) {
            return { error: `踢人请求失败 (${resp.status})`, status: resp.status };
        }
        let text = await resp.text();
        if (text.includes("while(1)")) {
            const idx = text.indexOf("\n");
            if (idx !== -1) text = text.substring(idx + 1);
        }
        try {
            return JSON.parse(text);
        } catch {
            return { status: "ok" };
        }
    }

    // 监听来自 popup / background 的消息
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        if (msg.type === "ping") {
            sendResponse({ alive: true });
        }
    });

    // 页面加载后立刻开始轮询
    startPolling();

    console.log("[Canva Extension] Content script 已注入，开始轮询后端任务...");
})();
