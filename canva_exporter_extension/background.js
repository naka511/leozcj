// ─── Canva Token 自动拦截 & 自动推送 ───

let latestHeaders = {};
let interceptCount = 0;

// 启动时恢复计数器
chrome.storage.local.get(["interceptCount"], (r) => {
  interceptCount = r.interceptCount || 0;
});

// 核心：拦截所有 canva.com 的 AJAX 请求头
chrome.webRequest.onSendHeaders.addListener(
  (details) => {
    let authz = "";
    let brand = "";
    let user = "";
    let activeUser = "";

    for (const header of details.requestHeaders) {
      const name = header.name.toLowerCase();
      if (name === "x-canva-authz") authz = header.value;
      if (name === "x-canva-brand") brand = header.value;
      if (name === "x-canva-user") user = header.value;
      if (name === "x-canva-active-user") activeUser = header.value;
    }

    // 只要拦截到了核心的 Authz 和 Brand，就自动保存
    if (authz && brand) {
      latestHeaders = {
        "X-Canva-Authz": authz,
        "X-Canva-Brand": brand,
        "X-Canva-User": user,
        "X-Canva-Active-User": activeUser
      };

      interceptCount++;
      const now = Date.now();
      chrome.storage.local.set({
        canvaHeaders: latestHeaders,
        timestamp: now,
        interceptCount: interceptCount
      });

      // 更新 badge
      chrome.action.setBadgeText({ text: String(interceptCount) });
      chrome.action.setBadgeBackgroundColor({ color: "#10b981" });

      // 自动推送到本地后端
      autoPushToBackend(latestHeaders);
    }
  },
  { urls: ["*://*.canva.com/_ajax/*"] },
  ["requestHeaders", "extraHeaders"]
);

// 自动推送 Token 到本地后端
async function autoPushToBackend(headers) {
  try {
    const config = await chrome.storage.local.get(["backendUrl", "accountId", "autoPush"]);
    if (!config.autoPush || !config.accountId) return;

    const backendUrl = config.backendUrl || "http://localhost:18157";
    
    // 同时抓取最新 cookies
    const cookies = await chrome.cookies.getAll({ url: "https://www.canva.com" });
    const cookieObj = {};
    cookies.forEach(c => cookieObj[c.name] = c.value);

    const tokenData = {
      api_requests: [{ headers }],
      cookies: cookieObj
    };

    const resp = await fetch(`${backendUrl}/api/accounts/${config.accountId}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token_data: tokenData })
    });

    if (resp.ok) {
      chrome.storage.local.set({ lastPushTime: Date.now(), pushStatus: "ok" });
    } else {
      chrome.storage.local.set({ pushStatus: "fail" });
    }
  } catch (e) {
    chrome.storage.local.set({ pushStatus: "fail" });
  }
}

// 每 5 分钟自动刷新一次 cookies 推送（保持活性）
chrome.alarms.create("refreshPush", { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "refreshPush") {
    chrome.storage.local.get(["canvaHeaders", "autoPush"], (result) => {
      if (result.canvaHeaders && result.autoPush) {
        autoPushToBackend(result.canvaHeaders);
      }
    });
  }
});
