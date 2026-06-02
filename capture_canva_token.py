"""
Canva Token 抓取工具
====================
打开浏览器 → 你登录 Canva → 自动捕获 Token 和团队信息
"""

import json
import os
import sys
import time
import re
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from DrissionPage import ChromiumPage, ChromiumOptions

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", APP_DIR)


def log(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")


def setup_browser():
    """启动本地 Chrome（不用比特浏览器，保证你能手动登录）"""
    co = ChromiumOptions()

    # 自动检测 Chrome 路径
    import shutil
    chrome_path = None
    for candidate in [
        shutil.which("google-chrome-stable"),
        shutil.which("google-chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]:
        if candidate and os.path.isfile(candidate):
            chrome_path = candidate
            break
    if chrome_path:
        co.set_browser_path(chrome_path)

    # 使用独立 profile，防止影响你的日常浏览器
    profile_dir = os.path.join(APP_DIR, "canva_capture_profile")
    co.set_user_data_path(profile_dir)
    co.set_local_port(19100)
    co.auto_port()

    # 正常浏览器模式（不隐藏，你需要手动操作）
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--no-sandbox')
    co.set_argument('--window-size=1400,900')

    return ChromiumPage(co)


def capture_cookies(page) -> dict:
    """捕获 Canva 所有 Cookie"""
    all_cookies = page.cookies()
    canva_cookies = {}
    for c in all_cookies:
        domain = c.get('domain', '')
        if 'canva' in domain.lower():
            canva_cookies[c['name']] = c['value']
    return canva_cookies


def extract_auth_info_via_js(page) -> dict:
    """通过 JS 从页面中提取认证信息"""
    info = {}

    # 1. 提取 CSRF Token（Canva 页面通常在 meta tag 或 JS 变量中）
    try:
        csrf = page.run_js("""
            // 从 meta tag
            var meta = document.querySelector('meta[name="csrf-token"]') || 
                       document.querySelector('meta[name="_csrf"]');
            if (meta) return meta.content;
            
            // 从 cookie
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var c = cookies[i].trim();
                if (c.startsWith('csrf') || c.startsWith('CSRF') || c.startsWith('_csrf') || c.startsWith('csrftoken')) {
                    return c.split('=')[1];
                }
            }
            
            // 从 window 对象
            if (window.__NEXT_DATA__) return JSON.stringify(window.__NEXT_DATA__.props?.pageProps?.csrfToken || '');
            if (window.__csrf) return window.__csrf;
            
            return null;
        """)
        if csrf:
            info['csrf_token'] = csrf
            log(f"  🔑 CSRF Token: {csrf[:30]}...")
    except:
        pass

    # 2. 提取团队/品牌 ID
    try:
        team_info = page.run_js("""
            var url = window.location.href;
            var result = {};
            
            // 从 URL 提取
            var brandMatch = url.match(/brand\\/([A-Za-z0-9_-]+)/);
            if (brandMatch) result.brand_id = brandMatch[1];
            
            var teamMatch = url.match(/team\\/([A-Za-z0-9_-]+)/);
            if (teamMatch) result.team_id = teamMatch[1];
            
            // 从 __NEXT_DATA__ 提取
            if (window.__NEXT_DATA__) {
                var pageProps = window.__NEXT_DATA__.props?.pageProps || {};
                if (pageProps.teamId) result.team_id = pageProps.teamId;
                if (pageProps.brandId) result.brand_id = pageProps.brandId;
            }
            
            return JSON.stringify(result);
        """)
        if team_info:
            parsed = json.loads(team_info) if isinstance(team_info, str) else team_info
            info.update(parsed)
            log(f"  🏢 团队信息: {parsed}")
    except:
        pass

    return info


def intercept_api_calls(page) -> list:
    """注入 XHR/fetch 拦截器，捕获 API 请求的 Authorization headers"""
    # 注入拦截器
    page.run_js("""
        window.__captured_requests = [];
        
        // 拦截 fetch
        var originalFetch = window.fetch;
        window.fetch = function() {
            var url = arguments[0];
            var options = arguments[1] || {};
            var headers = options.headers || {};
            
            // 转换 Headers 对象
            var headerObj = {};
            if (headers instanceof Headers) {
                headers.forEach(function(value, key) { headerObj[key] = value; });
            } else if (typeof headers === 'object') {
                headerObj = Object.assign({}, headers);
            }
            
            window.__captured_requests.push({
                type: 'fetch',
                url: typeof url === 'string' ? url : url.url,
                method: options.method || 'GET',
                headers: headerObj,
                timestamp: Date.now()
            });
            
            return originalFetch.apply(this, arguments);
        };
        
        // 拦截 XMLHttpRequest
        var originalOpen = XMLHttpRequest.prototype.open;
        var originalSetHeader = XMLHttpRequest.prototype.setRequestHeader;
        var originalSend = XMLHttpRequest.prototype.send;
        
        XMLHttpRequest.prototype.open = function(method, url) {
            this.__captured_info = { type: 'xhr', method: method, url: url, headers: {}, timestamp: Date.now() };
            return originalOpen.apply(this, arguments);
        };
        
        XMLHttpRequest.prototype.setRequestHeader = function(key, value) {
            if (this.__captured_info) {
                this.__captured_info.headers[key] = value;
            }
            return originalSetHeader.apply(this, arguments);
        };
        
        XMLHttpRequest.prototype.send = function() {
            if (this.__captured_info) {
                window.__captured_requests.push(this.__captured_info);
            }
            return originalSend.apply(this, arguments);
        };
        
        console.log('[Canva Capture] 请求拦截器已注入');
    """)
    log("  🕵️ API 请求拦截器已注入")
    return []


def collect_captured_requests(page) -> list:
    """收集已拦截的请求"""
    try:
        data = page.run_js("return JSON.stringify(window.__captured_requests || []);")
        if data:
            return json.loads(data) if isinstance(data, str) else data
    except:
        pass
    return []


def extract_auth_headers(requests: list) -> dict:
    """从拦截到的请求中提取认证 headers"""
    auth_info = {}
    for req in requests:
        headers = req.get('headers', {})
        url = req.get('url', '')

        # 只关注 Canva API 请求
        if 'canva' not in url and not url.startswith('/'):
            continue

        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in ('authorization', 'x-csrf-token', 'x-canva-csrf',
                             'x-requested-with', 'x-canva-request-id'):
                if key_lower not in auth_info or len(value) > len(auth_info.get(key_lower, '')):
                    auth_info[key_lower] = value

    return auth_info


def try_canva_members_api(page, cookies: dict, auth_headers: dict, team_info: dict):
    """尝试调用 Canva 团队成员 API"""
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("尝试获取团队成员列表...")

    # 通过浏览器直接请求 API（带着已有的 Cookie）
    try:
        result = page.run_js("""
            async function fetchMembers() {
                try {
                    // 尝试不同的 API 端点
                    var endpoints = [
                        '/rest/v1/teams/current/members',
                        '/api/teams/members',
                        '/api/brand/members',
                        '/_ajax/teams/members'
                    ];
                    
                    for (var i = 0; i < endpoints.length; i++) {
                        try {
                            var resp = await fetch(endpoints[i], {
                                method: 'GET',
                                credentials: 'include',
                                headers: {
                                    'Accept': 'application/json',
                                    'X-Requested-With': 'XMLHttpRequest'
                                }
                            });
                            if (resp.ok) {
                                var data = await resp.json();
                                return JSON.stringify({endpoint: endpoints[i], status: resp.status, data: data});
                            }
                        } catch(e) {}
                    }
                    return JSON.stringify({error: 'no_endpoint_worked'});
                } catch(e) {
                    return JSON.stringify({error: e.message});
                }
            }
            return fetchMembers();
        """)
        if result:
            parsed = json.loads(result) if isinstance(result, str) else result
            if 'error' not in parsed:
                log(f"  ✅ API 端点: {parsed.get('endpoint')}")
                return parsed
            else:
                log(f"  ⚠️ 直接 API 未成功: {parsed.get('error')}")
    except Exception as e:
        log(f"  ⚠️ API 测试异常: {e}")

    return None


def main():
    log("╔═══════════════════════════════════════════════════╗")
    log("║     Canva Token 抓取工具 v1.0                    ║")
    log("╚═══════════════════════════════════════════════════╝")

    # ── Step 1: 启动浏览器 ──
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("Step 1: 启动浏览器")
    page = setup_browser()
    log("  ✅ 浏览器已启动")

    # ── Step 2: 打开 Canva 登录页 ──
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("Step 2: 打开 Canva")
    page.get("https://www.canva.com/")
    time.sleep(3)
    log(f"  ✅ 页面: {page.url[:80]}")

    # 注入拦截器
    intercept_api_calls(page)

    # ── Step 3: 等待用户登录 ──
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("Step 3: 请在浏览器中登录你的 Canva 主账号")
    log("  📌 登录完成后，请手动导航到 [设置 → 成员] 页面")
    log("  📌 或者访问: https://www.canva.com/settings/team-members")
    log("")
    log("  ⏳ 等待你完成操作... (检测到成员页面后自动继续)")
    log("")

    # 等待用户登录并进入成员管理页面
    max_wait = 300  # 最多等 5 分钟
    start = time.time()
    logged_in = False

    while time.time() - start < max_wait:
        try:
            current_url = page.url.lower()

            # 检测是否已登录（URL 不再是登录页）
            if any(kw in current_url for kw in ['settings', 'team', 'members', 'brand', 'home', 'projects', 'people']):
                if not logged_in:
                    logged_in = True
                    log(f"  ✅ 检测到已登录! 当前页面: {page.url[:80]}")

                    # 重新注入拦截器（页面跳转后需要重新注入）
                    time.sleep(2)
                    intercept_api_calls(page)

                # 检测是否在成员管理页面
                if 'member' in current_url or 'team' in current_url or 'people' in current_url:
                    log(f"  ✅ 检测到成员管理页面!")
                    time.sleep(3)
                    break

            # 定期提示
            elapsed = int(time.time() - start)
            if elapsed % 15 == 0 and elapsed > 0:
                log(f"  ⏳ 已等待 {elapsed}s... 当前: {page.url[:60]}")

        except:
            pass
        time.sleep(2)

    if not logged_in:
        log("  ❌ 等待超时，请重新运行脚本")
        page.quit()
        return

    # ── Step 4: 抓取认证信息 ──
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("Step 4: 抓取认证信息")

    # 4.1 Cookies
    cookies = capture_cookies(page)
    log(f"  🍪 Canva Cookie: {len(cookies)} 项")
    for name in list(cookies.keys())[:10]:
        log(f"     {name}: {cookies[name][:40]}...")

    # 4.2 页面内嵌认证信息
    page_auth = extract_auth_info_via_js(page)

    # 4.3 等一下让拦截器捕获 API 请求
    log("  📡 触发页面 API 请求...")
    # 刷新成员列表触发 API 调用
    try:
        page.run_js("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        page.run_js("window.scrollTo(0, 0);")
        time.sleep(2)
    except:
        pass

    # 收集拦截到的请求
    captured = collect_captured_requests(page)
    log(f"  📦 捕获到 {len(captured)} 个 API 请求")

    # 过滤有意义的请求
    canva_api_requests = [r for r in captured if 'canva' in r.get('url', '') or r.get('url', '').startswith('/')]
    for req in canva_api_requests[:15]:
        log(f"     {req.get('method', '?')} {req.get('url', '?')[:80]}")

    # 4.4 提取认证 Headers
    auth_headers = extract_auth_headers(captured)
    if auth_headers:
        log(f"  🔐 认证 Headers:")
        for k, v in auth_headers.items():
            log(f"     {k}: {v[:60]}...")

    # 4.5 尝试获取团队成员 API
    api_result = try_canva_members_api(page, cookies, auth_headers, page_auth)

    # ── Step 5: 保存结果 ──
    log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log("Step 5: 保存抓取结果")

    result = {
        "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "canva_url": page.url,
        "cookies": cookies,
        "cookie_string": "; ".join([f"{k}={v}" for k, v in cookies.items()]),
        "auth_headers": auth_headers,
        "page_auth_info": page_auth,
        "api_requests": canva_api_requests[:30],
        "api_test_result": api_result,
    }

    output_file = os.path.join(DATA_DIR, "canva_token.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log(f"  ✅ Token 已保存到: {output_file}")
    log("")
    log("╔═══════════════════════════════════════════════════╗")
    log("║              抓取完成!                            ║")
    log("╠═══════════════════════════════════════════════════╣")
    log(f"║  Cookie 数量: {len(cookies):>4} 项                          ║")
    log(f"║  API 请求数:  {len(canva_api_requests):>4} 个                          ║")
    log(f"║  认证 Header: {len(auth_headers):>4} 个                          ║")
    log("╚═══════════════════════════════════════════════════╝")
    log("")
    log("📌 接下来请不要关闭浏览器！")
    log("   按 Enter 键关闭浏览器并退出...")

    try:
        input()
    except:
        pass

    page.quit()
    log("浏览器已关闭")


if __name__ == "__main__":
    main()
