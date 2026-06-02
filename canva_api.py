import json
import asyncio
import httpx

# curl_cffi 可选 — 如果 TLS 指纹不可用，自动回退到 httpx
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

class CanvaAPI:
    def __init__(self, token_data: dict, on_token_refreshed=None):
        self.token_data = token_data
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Origin": "https://www.canva.com",
            "Referer": "https://www.canva.com/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.cookies = {}
        self.brand_id = None
        self.on_token_refreshed = on_token_refreshed
        self._parse_token(token_data)

    def _parse_token(self, token_data):
        # 提取 cookies
        cookies_data = token_data.get("cookies", {})
        if isinstance(cookies_data, dict):
            self.cookies = cookies_data
        elif isinstance(cookies_data, list):
            self.cookies = {c.get("name"): c.get("value") for c in cookies_data if "name" in c}
        
        # 提取 headers
        for req in token_data.get("api_requests", []):
            h = req.get("headers", {})
            if "X-Canva-Authz" in h:
                for k, v in h.items():
                    if k.startswith("X-Canva-") or k.lower() in ("origin", "referer"):
                        self.headers[k] = v
                self.brand_id = h.get("X-Canva-Brand", "")
                break

    async def _request(self, method: str, url: str, json_data: dict = None) -> dict:
        if not self.brand_id or not self.headers.get("X-Canva-Authz"):
            return {"error": "未找到有效的 Canva 凭证，请检查上传的 Token 是否完整。"}

        max_retries = 5
        last_error = None

        for attempt in range(1, max_retries + 1):
            # 优先用 curl_cffi（TLS 指纹模拟），失败则回退到 httpx
            if HAS_CURL_CFFI:
                result = await self._request_curl_cffi(method, url, json_data)
                if result and "error" in result and "TLS" in str(result.get("error", "")):
                    result = await self._request_httpx(method, url, json_data)
            else:
                result = await self._request_httpx(method, url, json_data)

            # 成功（没有 error 字段）→ 直接返回
            if "error" not in result:
                return result

            # 记录错误
            last_error = result["error"]

            # 不可恢复的错误，不重试
            err_str = str(last_error)
            if "未找到有效" in err_str or "Token" in err_str and "过期" not in err_str:
                return result

            # 可重试的错误（403、TLS、网络超时等），等待后重试
            if attempt < max_retries:
                wait = attempt * 2  # 2s, 4s
                await asyncio.sleep(wait)

        return {"error": f"重试 {max_retries} 次后仍失败: {last_error}"}

    async def _request_curl_cffi(self, method: str, url: str, json_data: dict = None) -> dict:
        try:
            async with curl_requests.AsyncSession(impersonate="chrome120") as session:
                response = await session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    cookies=self.cookies,
                    json=json_data,
                    timeout=30
                )
                return self._parse_response(response.status_code, response.text)
        except Exception as e:
            return {"error": f"请求异常: {str(e)}"}

    async def _request_httpx(self, method: str, url: str, json_data: dict = None) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                http2=True,
                cookies=self.cookies
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data
                )
                return self._parse_response(response.status_code, response.text)
        except Exception as e:
            return {"error": f"请求异常: {str(e)}"}

    def _parse_response(self, status_code: int, text: str) -> dict:
        if status_code == 403:
            return {"error": "Canva API 拒绝了请求 (403 Forbidden)。Cloudflare 可能拦截了请求，或 Token/Cookie 已过期。"}
        if status_code >= 400:
            return {"error": f"API 请求失败: {status_code} - {text}"}

        # 清理 Canva 防劫持前缀
        if "while(1)" in text:
            idx = text.find("\n")
            if idx != -1:
                text = text[idx+1:]
            elif "</x>//" in text:
                text = text.split("</x>//", 1)[1]

        try:
            data = json.loads(text)
            # 处理新版 API 的特殊返回结构
            if "results" in data:
                users = []
                for res in data["results"]:
                    c = res.get("C", {})
                    user_info = c.get("user", {})
                    if not user_info:
                        continue
                    users.append({
                        "id": user_info.get("id"),
                        "displayName": user_info.get("displayName", ""),
                        "email": c.get("email", ""),
                        "role": c.get("role", "")
                    })
                return {"users": users}

            # 兼容可能返回原本 users 的老接口或其他响应
            return data
        except Exception:
            return {"status": "ok", "raw": text}

    async def get_members(self):
        if not self.brand_id:
            return {"error": "无法获取 Brand ID"}
            
        url = f"https://www.canva.com/_ajax/profilesearch/search_brand_members?searchEmail&roles=MEMBER&projection=B&projection=C&projection=D&limit=50"
        return await self._request("GET", url)

    async def remove_member(self, user_id):
        if not self.brand_id:
            return {"error": "无法获取 Brand ID"}
            
        url = "https://www.canva.com/_ajax/profile/brands/members"
        data = {
            "brand": self.brand_id,
            "remove": [user_id],
            "sendBrandMemberRemovedMessage": True
        }
        return await self._request("POST", url, json_data=data)
