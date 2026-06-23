import os
import json
import asyncio
import subprocess
import base64
import re
import socket
import ssl
import sys
import shutil
import uuid
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from urllib.parse import quote, unquote, urlsplit
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, JSONResponse
import glob
import httpx
import inspect

from canva_api import CanvaAPI

app = FastAPI()

# Config storage
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", APP_DIR)
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
CUSTOM_EMAILS_FILE = os.path.join(DATA_DIR, "custom_emails.json")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "api_key": "",
    "api_base": "https://rossa.cfd/api",
    "email_domain": "rossa.cfd",
    "email_domains": "rossa.cfd",
    "yescaptcha_key": "",
    "proxy_enabled": False,
    "proxy_scheme": "http",
    "proxy_url": "",
    "pool_api_url": "",
    "pool_api_key": "",
    "auto_import_enabled": False,
}

WORKER_TIMEOUT_SECONDS = max(180, int(os.getenv("WORKER_TIMEOUT_SECONDS", "900")))
STALE_PROFILE_SECONDS = max(300, int(os.getenv("STALE_PROFILE_SECONDS", "1800")))
PROFILE_PREFIX = "chrome_profile_"

def normalize_proxy(proxy_url: str, proxy_scheme: str = "http") -> dict:
    raw = (proxy_url or "").strip()
    scheme = (proxy_scheme or "http").strip().lower()
    if scheme not in ("http", "https", "socks5"):
        scheme = "http"
    if not raw:
        raise ValueError("请填写代理地址")

    target = raw if "://" in raw else f"{scheme}://{raw}"
    parsed = urlsplit(target)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https", "socks5"):
        raise ValueError("仅支持 http、https、socks5 代理")

    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")

    if (not host or not port) and "://" not in raw:
        if "@" in raw:
            left, right = raw.split("@", 1)
            left_parts = left.split(":")
            right_parts = right.split(":")
            if len(left_parts) >= 2 and left_parts[1].isdigit():
                host, port = left_parts[0], int(left_parts[1])
                username = right_parts[0] if len(right_parts) > 0 else ""
                password = ":".join(right_parts[1:]) if len(right_parts) > 1 else ""
            elif len(right_parts) >= 2 and right_parts[-1].isdigit():
                username = left_parts[0] if len(left_parts) > 0 else ""
                password = ":".join(left_parts[1:]) if len(left_parts) > 1 else ""
                host, port = ":".join(right_parts[:-1]), int(right_parts[-1])
        else:
            parts = raw.split(":")
            if len(parts) >= 4 and parts[1].isdigit():
                host, port = parts[0], int(parts[1])
                username = parts[2]
                password = ":".join(parts[3:])
            elif len(parts) == 2 and parts[1].isdigit():
                host, port = parts[0], int(parts[1])

    if not host or not port:
        raise ValueError("代理格式错误，请参考示例填写")

    auth = f"{username}:{password}@" if username or password else ""
    server = f"{scheme}://{host}:{port}"
    url = f"{scheme}://{auth}{host}:{port}"
    return {
        "scheme": scheme,
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "server": server,
        "url": url,
    }

def _proxy_auth_header(username: str, password: str) -> str:
    if not username and not password:
        return ""
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Proxy-Authorization: Basic {token}\r\n"

def _test_http_proxy(proxy: dict) -> tuple[bool, str]:
    proxy_url = proxy["url"]
    try:
        import inspect
        kwargs = {"timeout": 10.0, "verify": False}
        if "proxy" in inspect.signature(httpx.Client).parameters:
            kwargs["proxy"] = proxy_url
        else:
            kwargs["proxies"] = proxy_url
            
        with httpx.Client(**kwargs) as client:
            resp = client.get("https://api.ipify.org?format=json")
            resp.raise_for_status()
            ip_data = resp.json()
            return True, f"代理可用，出口IP: {ip_data.get('ip', '未知')}"
    except httpx.ProxyError as e:
        return False, f"代理连接失败，请检查账号密码或IP白名单: {e}"
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (407, 403):
            return False, f"代理需要认证或被拒绝 ({e.response.status_code})"
        return False, f"代理连通但目标网站返回错误: {e.response.status_code}"
    except Exception as e:
        return False, f"代理测试异常: {str(e)}"

def _test_socks5_proxy(proxy: dict) -> tuple[bool, str]:
    with socket.create_connection((proxy["host"], proxy["port"]), timeout=8) as sock:
        sock.settimeout(8)
        methods = [0x00]
        if proxy["username"] or proxy["password"]:
            methods.append(0x02)
        sock.sendall(bytes([0x05, len(methods), *methods]))
        resp = sock.recv(2)
        if len(resp) < 2 or resp[0] != 0x05:
            if resp.startswith(b"H"):
                return False, "当前端口返回 HTTP 响应，不是 SOCKS5；请改选 http/https 或更换 SOCKS5 端口"
            return False, f"SOCKS5 握手失败，代理返回: {resp.hex() or '空响应'}"
        if resp[1] == 0xFF:
            return False, "SOCKS5 代理不接受当前认证方式"
        if resp[1] == 0x02:
            username = proxy["username"].encode()
            password = proxy["password"].encode()
            if len(username) > 255 or len(password) > 255:
                return False, "SOCKS5 用户名或密码过长"
            sock.sendall(bytes([0x01, len(username)]) + username + bytes([len(password)]) + password)
            auth = sock.recv(2)
            if len(auth) < 2 or auth[1] != 0x00:
                return False, "SOCKS5 用户名或密码错误"

        host = b"example.com"
        sock.sendall(bytes([0x05, 0x01, 0x00, 0x03, len(host)]) + host + (80).to_bytes(2, "big"))
        resp = sock.recv(10)
        if len(resp) < 2 or resp[1] != 0x00:
            return False, f"SOCKS5 连接目标站点失败，错误码 {resp[1] if len(resp) > 1 else '未知'}"
        sock.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
        data = sock.recv(1024).decode("iso-8859-1", errors="ignore")
    return (True, "SOCKS5 代理可用") if data.startswith("HTTP/") else (False, "SOCKS5 已连接但目标站点响应异常")

def test_proxy_connectivity(proxy_url: str, proxy_scheme: str) -> tuple[bool, str, dict | None]:
    try:
        proxy = normalize_proxy(proxy_url, proxy_scheme)
        if proxy["scheme"] == "socks5":
            ok, message = _test_socks5_proxy(proxy)
        else:
            ok, message = _test_http_proxy(proxy)
        return ok, message, proxy
    except Exception as e:
        return False, f"代理检测失败: {e}", None

def load_config():
    if os.path.exists(CONFIG_FILE):
        data = json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
        # 兼容旧配置：如果只有 email_domain 没有 email_domains，自动迁移
        if "email_domains" not in data and "email_domain" in data:
            data["email_domains"] = data["email_domain"]
        for key, value in DEFAULT_CONFIG.items():
            data.setdefault(key, value)
        return data
    return DEFAULT_CONFIG.copy()

def save_config(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def resolve_data_file(path: str) -> str:
    if os.path.isabs(path):
        return path
    data_path = os.path.join(DATA_DIR, path)
    if os.path.exists(data_path):
        return data_path
    return path

def sanitize_filename(name: str, fallback: str = "导出文件") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", (name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return cleaned[:80] if cleaned else fallback

def export_timestamp() -> str:
    return datetime.now().strftime("%m-%d_%H-%M")

config = load_config()


def normalize_browser_mode(browser_mode: str = "", show_browser: bool = False) -> str:
    mode = (browser_mode or "").strip().lower()
    aliases = {
        "fingerprint": "bitbrowser",
        "fingerprint-browser": "bitbrowser",
        "bit": "bitbrowser",
        "local-browser": "local",
        "visible": "local",
        "headless": "new-headless",
        "headless-new": "new-headless",
        "cloak": "cloakbrowser",
        "cloak-browser": "cloakbrowser",
        "cloak-headless": "cloakbrowser",
    }
    mode = aliases.get(mode, mode)
    if mode in ("bitbrowser", "local", "new-headless", "cloakbrowser"):
        return mode
    return "local" if show_browser else "bitbrowser"

# ─── Task Management ───
class Task:
    def __init__(self, task_id, quantity, concurrency=1, show_browser=False, name="", invite_url="", email_mode="temp", custom_emails=None, browser_mode=""):
        self.id = task_id
        self.quantity = quantity
        self.concurrency = concurrency
        self.browser_mode = normalize_browser_mode(browser_mode, show_browser)
        self.show_browser = self.browser_mode == "local"
        self.name = (name or "").strip() or f"任务 #{task_id}"
        self.invite_url = (invite_url or "").strip()
        self.email_mode = email_mode if email_mode in ("temp", "custom", "microsoft") else "temp"
        self.custom_emails = custom_emails or []
        self.status = "pending"     # pending -> running -> stopping -> completed/stopped
        self.completed = 0
        self.failed = 0
        self.imported = 0
        self.invite_invalid_detected = False
        self.created_at = datetime.now().strftime("%m-%d %H:%M")
        self.result_files = []
        self.asyncio_tasks = []
        self.active_processes = {}
        self.active_profiles = {}

    def to_dict(self):
        return {
            "id": self.id,
            "quantity": self.quantity,
            "concurrency": self.concurrency,
            "show_browser": self.show_browser,
            "browser_mode": self.browser_mode,
            "name": self.name,
            "invite_url": self.invite_url,
            "email_mode": self.email_mode,
            "custom_email_count": len(self.custom_emails),
            "status": self.status,
            "completed": self.completed,
            "failed": self.failed,
            "imported": self.imported,
            "invite_invalid_detected": self.invite_invalid_detected,
            "created_at": self.created_at,
            "result_count": len(self.result_files),
            "result_files": self.result_files,
        }


def collect_active_profile_paths(tasks: dict[int, "Task"]) -> set[str]:
    active = set()
    for task in tasks.values():
        active.update(task.active_profiles.values())
    return active


def cleanup_stale_profiles(active_paths: set[str] | None = None) -> int:
    active_paths = {os.path.abspath(path) for path in (active_paths or set())}
    removed = 0
    now = datetime.now().timestamp()

    for entry in os.listdir(APP_DIR):
        if not entry.startswith(PROFILE_PREFIX):
            continue
        path = os.path.abspath(os.path.join(APP_DIR, entry))
        if path in active_paths or not os.path.isdir(path):
            continue
        try:
            age_seconds = now - os.path.getmtime(path)
        except OSError:
            continue
        if age_seconds < STALE_PROFILE_SECONDS:
            continue
        try:
            shutil.rmtree(path, ignore_errors=False)
            removed += 1
        except Exception:
            continue
    return removed

class TaskManager:
    def __init__(self):
        self.tasks: dict[int, Task] = {}
        self.next_id = 1
        self.websockets = []
        self.queue = asyncio.Queue()
        self._worker_running = False
        self.load_tasks()

    def save_tasks(self):
        data = {
            "next_id": self.next_id,
            "tasks": [t.to_dict() for t in self.tasks.values()]
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_tasks(self):
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.next_id = data.get("next_id", 1)
                    for t_data in data.get("tasks", []):
                        t = Task(
                            t_data["id"],
                            t_data["quantity"],
                            t_data.get("concurrency", 1),
                            t_data.get("show_browser", False),
                            t_data.get("name", ""),
                            t_data.get("invite_url", ""),
                            t_data.get("email_mode", "temp"),
                            [],
                            t_data.get("browser_mode", ""),
                        )
                        t.status = t_data["status"]
                        t.completed = t_data.get("completed", 0)
                        t.failed = t_data.get("failed", 0)
                        t.invite_invalid_detected = t_data.get("invite_invalid_detected", False)
                        t.created_at = t_data.get("created_at", "")
                        t.result_files = t_data.get("result_files", [])
                        # Mark interrupted tasks as stopped
                        if t.status in ("running", "pending", "stopping"):
                            t.status = "stopped"
                        self.tasks[t.id] = t
            except Exception as e:
                print(f"Failed to load tasks: {e}")

    def create_task(self, quantity, concurrency=1, show_browser=False, name="", invite_url="", email_mode="temp", custom_emails=None, browser_mode="") -> Task:
        task = Task(self.next_id, quantity, concurrency, show_browser, name, invite_url, email_mode, custom_emails, browser_mode)
        self.tasks[self.next_id] = task
        self.next_id += 1
        return task

    def delete_tasks(self, ids: list[int]):
        for tid in ids:
            if tid in self.tasks:
                t = self.tasks[tid]
                # Only delete non-running tasks
                if t.status not in ("running", "pending"):
                    del self.tasks[tid]

    async def stop_tasks(self, ids: list[int]):
        for tid in ids:
            if tid in self.tasks:
                t = self.tasks[tid]
                if t.status == "pending":
                    t.status = "stopped"
                elif t.status == "running":
                    t.status = "stopping"
                    await self.broadcast(f"🛑 任务 #{t.id} 已进入优雅停止：当前正在注册的账号会先完成，未开始的账号将跳过。")

    async def broadcast(self, message: str):
        if message == "__STATE_UPDATE__":
            self.save_tasks()

        disconnected = []
        for ws in self.websockets:
            try:
                await ws.send_text(message)
            except WebSocketDisconnect:
                disconnected.append(ws)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.websockets.remove(ws)

    async def start_queue_worker(self):
        """Single worker that processes tasks from the queue one by one."""
        if self._worker_running:
            return
        self._worker_running = True
        try:
            while True:
                task = await self.queue.get()
                if task.status == "stopped":
                    self.queue.task_done()
                    continue
                try:
                    await run_task(task)
                except Exception as e:
                    await self.broadcast(f"❌ 任务 #{task.id} 异常: {e}")
                    task.status = "completed"
                finally:
                    self.queue.task_done()
        finally:
            self._worker_running = False

task_manager = TaskManager()

# ─── Auto Loop Management ───
class AutoLoopManager:
    def __init__(self):
        self.is_running = False
        self.should_stop = False
        self.current_account_index = 0
        self.loop_task = None
        self.current_subtask_id = None
        self.quantity = 1
        self.concurrency = 1
        self.show_browser = False
        self.browser_mode = "bitbrowser"
        self.email_mode = "temp"
        self.account_order = []
        self.loop_run_mode = "infinite"
        self.once_remaining_account_ids = []
        self.success_rate_stop_threshold = 0.0
        self.schedule_start = ""
        self.schedule_stop = ""
        self.start_dt = None
        self.stop_dt = None

    def _get_next_datetime(self, time_str: str, from_dt: datetime = None) -> datetime:
        if not time_str:
            return None
        now = from_dt or datetime.now()
        try:
            h, m = map(int, time_str.split(':'))
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
        except:
            return None

    async def _disable_invalid_account(self, account: dict, reason: str):
        account_id = str(account.get("id", ""))
        account_name = account.get("name") or account_id or "未知账号"
        if account_id and account_id in account_manager.accounts:
            account_manager.accounts[account_id]["is_active"] = False
            account_manager.save_accounts()
        await task_manager.broadcast(
            f"⚠️ 全自动模式：账号 {account_name} 已自动停用并跳过。原因：{reason}"
        )

    def _is_fatal_canva_account_error(self, error: str) -> bool:
        err = str(error or "").lower()
        fatal_markers = [
            "未找到有效的 canva 凭证",
            "无法获取 brand id",
            "brand id",
            "x-canva-authz",
            "401",
            "unauthorized",
            "invalid token",
            "token invalid",
            "token 已失效",
            "token 无效",
            "凭证缺失",
            "无权限管理",
            "permission denied",
            "not authorized",
        ]
        return any(marker in err for marker in fatal_markers)

    async def _get_members_for_cleanup(self, api: CanvaAPI, account_name: str, max_attempts: int = 5):
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            if self.should_stop:
                return "stopped", None, ""

            res = await api.get_members()
            if "error" not in res:
                return "ok", res.get("users", []), ""

            last_error = str(res["error"])
            if self._is_fatal_canva_account_error(last_error):
                return "fatal", None, last_error

            if attempt < max_attempts:
                await task_manager.broadcast(
                    f"🔄 全自动模式：账号 {account_name} 获取成员失败，{attempt}/{max_attempts}，1秒后重试：{last_error}"
                )
                await asyncio.sleep(1)

        return "failed", None, last_error

    async def _cleanup_account_members(self, account: dict, api: CanvaAPI) -> str:
        account_name = account.get("name") or str(account.get("id") or "未知账号")
        max_batches = 5
        max_failures = 20
        max_seconds = 600
        batch_count = 0
        failure_count = 0
        start_time = datetime.now()

        while not self.should_stop:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= max_seconds:
                await task_manager.broadcast(
                    f"⚠️ 全自动模式：账号 {account_name} 成员清理超过 {max_seconds} 秒，跳过本轮账号，不停用"
                )
                return "skipped"

            status, users, error = await self._get_members_for_cleanup(api, account_name)
            if status == "stopped":
                return "stopped"
            if status == "fatal":
                await self._disable_invalid_account(account, f"获取成员失败：{error}")
                return "disabled"
            if status == "failed":
                await task_manager.broadcast(
                    f"⚠️ 全自动模式：账号 {account_name} 获取成员 5 次仍失败，跳过本轮账号，不停用：{error}"
                )
                return "skipped"

            users = users or []
            if not users:
                await task_manager.broadcast(
                    f"✅ 全自动模式：账号 {account_name} 成员已清空，确认可开始派发任务"
                )
                return "ready"

            if batch_count >= max_batches:
                await task_manager.broadcast(
                    f"⚠️ 全自动模式：账号 {account_name} 已清理 {max_batches} 批后仍有 {len(users)} 名成员，跳过本轮账号，不停用"
                )
                return "skipped"

            await task_manager.broadcast(
                f"🔄 全自动模式：账号 {account_name} 第 {batch_count + 1}/{max_batches} 批获取到 {len(users)} 名成员，开始清理"
            )

            batch_failed = False
            for u in users:
                if self.should_stop:
                    return "stopped"

                result = await api.remove_member(u["id"])
                if "error" in result:
                    error = str(result["error"])
                    if self._is_fatal_canva_account_error(error):
                        await self._disable_invalid_account(account, f"清理成员失败：{error}")
                        return "disabled"

                    failure_count += 1
                    batch_failed = True
                    await task_manager.broadcast(
                        f"⚠️ 全自动模式：账号 {account_name} 清理成员失败 {failure_count}/{max_failures}，将重新获取成员后继续：{error}"
                    )
                    if failure_count >= max_failures:
                        await task_manager.broadcast(
                            f"⚠️ 全自动模式：账号 {account_name} 清理成员失败达到 {max_failures} 次，跳过本轮账号，不停用"
                        )
                        return "skipped"
                    await asyncio.sleep(1)
                    break

                await asyncio.sleep(0.5)

            if not batch_failed:
                batch_count += 1

        return "stopped"

    async def run_loop(self):
        self.is_running = True
        self.should_stop = False
        try:
            if self.schedule_start:
                now = datetime.now()
                self.start_dt = self._get_next_datetime(self.schedule_start)
                if self.start_dt:
                    await task_manager.broadcast(f"🔄 全自动模式：等待定时启动 ({self.start_dt.strftime('%m-%d %H:%M')})")
                    while not self.should_stop:
                        if datetime.now() >= self.start_dt:
                            break
                        await asyncio.sleep(5)
            
            if self.should_stop:
                return

            if self.schedule_stop:
                self.stop_dt = self._get_next_datetime(self.schedule_stop)
                if self.stop_dt:
                    await task_manager.broadcast(f"🔄 全自动模式：将在 {self.stop_dt.strftime('%m-%d %H:%M')} 自动停止")

            if self.loop_run_mode == "once":
                active_pool = [a for a in account_manager.accounts.values() if a.get("is_active") and a.get("invite_url")]
                if self.account_order:
                    active_ids = {str(a.get("id")) for a in active_pool}
                    self.once_remaining_account_ids = [account_id for account_id in self.account_order if account_id in active_ids]
                else:
                    self.once_remaining_account_ids = [str(a.get("id")) for a in active_pool]
                await task_manager.broadcast(f"🔄 全自动模式：已启动（一轮，{len(self.once_remaining_account_ids)} 个账号）")
            else:
                self.once_remaining_account_ids = []
                await task_manager.broadcast("🔄 全自动模式：已启动（无限）")

            while not self.should_stop:
                if self.stop_dt and datetime.now() >= self.stop_dt:
                    await task_manager.broadcast(f"🔄 全自动模式：到达定时停止时间 ({self.schedule_stop})")
                    self.stop()
                    break

                active_pool = [a for a in account_manager.accounts.values() if a.get("is_active") and a.get("invite_url")]
                if self.account_order:
                    by_id = {str(a.get("id")): a for a in active_pool}
                    active_accounts = [by_id[account_id] for account_id in self.account_order if account_id in by_id]
                else:
                    active_accounts = active_pool

                if self.loop_run_mode == "once":
                    active_ids = {str(a.get("id")) for a in active_accounts}
                    self.once_remaining_account_ids = [account_id for account_id in self.once_remaining_account_ids if account_id in active_ids]
                    if not self.once_remaining_account_ids:
                        await task_manager.broadcast("🔄 全自动模式：一轮账号已轮用完，自动停止。")
                        break
                    remaining_ids = set(self.once_remaining_account_ids)
                    active_accounts = [a for a in active_accounts if str(a.get("id")) in remaining_ids]

                if not active_accounts:
                    if self.loop_run_mode == "once":
                        await task_manager.broadcast("🔄 全自动模式：一轮内没有可继续使用的启用账号，自动停止。")
                        break
                    else:
                        await task_manager.broadcast("🔄 全自动模式：未找到启用的账号，暂停10秒后重试...")
                        await asyncio.sleep(10)
                        continue

                if self.current_account_index >= len(active_accounts):
                    self.current_account_index = 0

                selected_account_index = self.current_account_index
                account = active_accounts[selected_account_index]
                if self.loop_run_mode == "once":
                    self.once_remaining_account_ids = [
                        account_id for account_id in self.once_remaining_account_ids
                        if account_id != str(account.get("id"))
                    ]
                    self.current_account_index = selected_account_index
                else:
                    self.current_account_index = (selected_account_index + 1) % len(active_accounts)

                await task_manager.broadcast(f"🔄 全自动模式：选择账号 {account['name']}，开始获取并清理成员...")
                
                api = CanvaAPI(account.get("token_data", {}))
                cleanup_status = await self._cleanup_account_members(account, api)
                if self.should_stop or cleanup_status == "stopped":
                    break
                if cleanup_status in ("disabled", "skipped"):
                    self.current_account_index = selected_account_index
                    continue
                if cleanup_status != "ready":
                    await task_manager.broadcast(
                        f"⚠️ 全自动模式：账号 {account['name']} 成员清理状态异常({cleanup_status})，跳过本轮账号，不停用"
                    )
                    self.current_account_index = selected_account_index
                    continue
                await task_manager.broadcast(f"🔄 全自动模式：账号 {account['name']} 成员清理完毕，开始派发注册任务。")

                # 创建子任务
                task_name = f"AutoLoop - {account['name']} - {export_timestamp()}"
                task = task_manager.create_task(
                    self.quantity,
                    self.concurrency,
                    self.show_browser,
                    task_name,
                    account['invite_url'],
                    self.email_mode,
                    [],
                    self.browser_mode,
                )
                if self.email_mode in ("custom", "microsoft"):
                    try:
                        task.custom_emails = custom_email_manager.claim(self.quantity, task.id)
                    except ValueError as e:
                        task_manager.tasks.pop(task.id, None)
                        await task_manager.broadcast(f"❌ 全自动模式：自备邮箱不足，无法派发任务：{e}")
                        self.should_stop = True
                        break
                if self.should_stop:
                    break
                self.current_subtask_id = task.id
                await task_manager.queue.put(task)
                
                # Ensure queue worker is running
                asyncio.create_task(task_manager.start_queue_worker())

                # Wait for task to finish
                while task.status in ("pending", "running", "stopping"):
                    await asyncio.sleep(2)
                    if self.should_stop:
                        await task_manager.stop_tasks([task.id])
                        break
                
                if self.should_stop: break

                if task.invite_invalid_detected:
                    await self._disable_invalid_account(account, "邀请链接失效、不存在或已被使用")
                    self.current_account_index = selected_account_index
                    continue

                finished = task.completed + task.failed
                if self.success_rate_stop_threshold > 0 and finished > 0:
                    success_rate = task.completed / finished * 100
                    await task_manager.broadcast(
                        f"AutoLoop success rate: {success_rate:.1f}% ({task.completed}/{finished}), threshold {self.success_rate_stop_threshold:.1f}%"
                    )
                    if success_rate < self.success_rate_stop_threshold:
                        await task_manager.broadcast(
                            f"AutoLoop stopped: success rate {success_rate:.1f}% is below threshold {self.success_rate_stop_threshold:.1f}%"
                        )
                        self.should_stop = True
                        break

        except Exception as e:
            await task_manager.broadcast(f"❌ 全自动模式发生异常: {str(e)}")
        finally:
            self.is_running = False
            self.should_stop = False
            self.current_subtask_id = None
            await task_manager.broadcast("🛑 全自动模式：已停止")

    def start(self, quantity, concurrency, show_browser, schedule_start="", schedule_stop="", email_mode="temp", browser_mode="", account_order=None, success_rate_stop_threshold=0, loop_run_mode="infinite"):
        if self.is_running:
            return False
        self.quantity = quantity
        self.concurrency = concurrency
        self.browser_mode = normalize_browser_mode(browser_mode, show_browser)
        self.show_browser = self.browser_mode == "local"
        self.email_mode = email_mode if email_mode in ("temp", "custom", "microsoft") else "temp"
        self.account_order = [str(item) for item in (account_order or []) if str(item).strip()]
        self.loop_run_mode = loop_run_mode if loop_run_mode in ("infinite", "once") else "infinite"
        self.once_remaining_account_ids = []
        try:
            self.success_rate_stop_threshold = max(0.0, min(float(success_rate_stop_threshold or 0), 100.0))
        except (TypeError, ValueError):
            self.success_rate_stop_threshold = 0.0
        self.schedule_start = schedule_start
        self.schedule_stop = schedule_stop
        self.start_dt = None
        self.stop_dt = None
        self.current_account_index = 0
        self.loop_task = asyncio.create_task(self.run_loop())
        return True

    def stop(self):
        self.should_stop = True
        if self.current_subtask_id:
            asyncio.create_task(task_manager.stop_tasks([self.current_subtask_id]))

auto_loop_manager = AutoLoopManager()

# ─── Account Management ───
class AccountManager:
    def __init__(self):
        self.accounts: dict[str, dict] = {}
        self.next_id = 1
        self.load_accounts()

    def load_accounts(self):
        if os.path.exists(ACCOUNTS_FILE):
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.next_id = data.get("next_id", 1)
                    for acc in data.get("accounts", []):
                        self.accounts[str(acc["id"])] = acc
            except Exception as e:
                print(f"Failed to load accounts: {e}")

    def save_accounts(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {
            "next_id": self.next_id,
            "accounts": list(self.accounts.values()),
        }
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_account(self, item: "AccountCreate") -> dict:
        account_id = str(self.next_id)
        account = {
            "id": account_id,
            "name": item.name,
            "email": item.email,
            "invite_url": item.invite_url,
            "notes": item.notes,
            "is_active": True,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "token_data": item.token_data
        }
        self.accounts[account_id] = account
        self.next_id += 1
        self.save_accounts()
        return account

    def delete_account(self, account_id: str):
        if account_id in self.accounts:
            del self.accounts[account_id]
            self.save_accounts()

    def toggle_account(self, account_id: str, is_active: bool):
        if account_id in self.accounts:
            self.accounts[account_id]["is_active"] = is_active
            self.save_accounts()

    def update_account(self, account_id: str, updates: dict):
        if account_id in self.accounts:
            for key in ["name", "email", "invite_url", "notes"]:
                if key in updates:
                    self.accounts[account_id][key] = updates[key]
            self.save_accounts()

    def get_account_with_invitees(self, account_id: str) -> dict | None:
        acc = self.accounts.get(account_id)
        if not acc:
            return None
        invitees = self._collect_invitees(acc)
        return {
            **acc,
            "invitee_count": len(invitees),
            "invitees": invitees,
        }

    def list_accounts(self) -> list[dict]:
        result = []
        for acc in sorted(self.accounts.values(), key=lambda a: a.get("id", "0"), reverse=True):
            invitees = self._collect_invitees(acc)
            result.append({**acc, "invitee_count": len(invitees)})
        return result

    def _collect_invitees(self, account: dict) -> list[dict]:
        """收集属于某账号的受邀人员（通过 invite_url 关联 task -> cookie）"""
        invite_url = (account.get("invite_url") or "").strip()
        if not invite_url:
            return []

        # 找出使用了这个 invite_url 的所有任务
        matching_task_ids = set()
        for task in task_manager.tasks.values():
            task_invite = (task.invite_url or "").strip()
            if task_invite and task_invite == invite_url:
                matching_task_ids.add(task.id)

        if not matching_task_ids:
            return []

        # 扫描 cookies 目录，找出属于这些任务的 cookie 文件
        cookies_dir = os.path.join(DATA_DIR, "cookies")
        if not os.path.isdir(cookies_dir):
            return []

        invitees = []
        for fname in os.listdir(cookies_dir):
            if not fname.startswith("cookie_task") or not fname.endswith(".json"):
                continue
            # 解析 task_id: cookie_task{id}_w{n}.json
            m = re.match(r"cookie_task(\d+)_w(\d+)\.json", fname)
            if not m:
                continue
            task_id = int(m.group(1))
            if task_id not in matching_task_ids:
                continue

            fpath = os.path.join(cookies_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                email = cdata.get("name", "")
                created_at = cdata.get("created_at", "")
                has_cookie = bool(cdata.get("cookie", ""))
                invitees.append({
                    "email": email,
                    "task_id": task_id,
                    "created_at": created_at,
                    "status": "success" if has_cookie and len(cdata.get("cookie", "")) > 100 else "failed",
                    "file": fname,
                })
            except Exception:
                continue

        # 按创建时间倒序
        invitees.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return invitees

account_manager = AccountManager()

# ─── Models ───
class ConfigUpdate(BaseModel):
    api_key: str
    api_base: str
    email_domain: str = "rossa.cfd"
    email_domains: str = ""  # 逗号分隔的多域名列表
    yescaptcha_key: str = ""
    proxy_enabled: bool = False
    proxy_scheme: str = "http"
    proxy_url: str = ""
    pool_api_url: str = ""
    pool_api_key: str = ""
    auto_import_enabled: bool = False

class ProxyTestRequest(BaseModel):
    proxy_scheme: str = "http"
    proxy_url: str = ""

class TaskStart(BaseModel):
    quantity: int
    concurrency: int = 1
    show_browser: bool = False
    browser_mode: str = ""
    name: str = ""
    invite_url: str = ""
    email_mode: str = "temp"
    custom_emails: str = ""
    schedule_start: str = ""
    schedule_stop: str = ""
    account_order: list[str] = Field(default_factory=list)
    success_rate_stop_threshold: float = 0
    loop_run_mode: str = "infinite"

class TaskDeleteRequest(BaseModel):
    ids: list[int]

class AccountCreate(BaseModel):
    name: str
    email: Optional[str] = None
    invite_url: str
    notes: Optional[str] = None
    token_data: Optional[dict] = None

class AccountUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    invite_url: str | None = None
    notes: str | None = None


def parse_custom_email_accounts(raw: str) -> list[dict]:
    accounts = []
    for line_no, raw_line in enumerate((raw or "").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("----", 2)]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"第 {line_no} 行格式错误，应为：邮箱----密码----取件api链接")
        email, password, api_url = parts
        if "@" not in email:
            raise ValueError(f"第 {line_no} 行邮箱格式错误：{email}")
        if not api_url.startswith(("http://", "https://")):
            raise ValueError(f"第 {line_no} 行取件 API 链接必须以 http:// 或 https:// 开头")
        accounts.append({
            "email": email,
            "password": password,
            "api_url": api_url,
        })
    return accounts


class CustomEmailManager:
    def __init__(self):
        self.emails: dict[str, dict] = {}
        self.next_id = 1
        self.load()

    def load(self):
        if os.path.exists(CUSTOM_EMAILS_FILE):
            try:
                with open(CUSTOM_EMAILS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.next_id = data.get("next_id", 1)
                for item in data.get("emails", []):
                    if item.get("status") == "claimed":
                        item["status"] = "available"
                        item["claimed_at"] = ""
                        item["claimed_task_id"] = None
                        item["claimed_worker_index"] = None
                    self.emails[str(item["id"])] = item
            except Exception as e:
                print(f"Failed to load custom emails: {e}")

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {
            "next_id": self.next_id,
            "emails": list(self.emails.values()),
        }
        with open(CUSTOM_EMAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def public_item(self, item: dict) -> dict:
        password = item.get("password", "")
        return {
            "id": item["id"],
            "email": item["email"],
            "password_mask": "*" * min(max(len(password), 8), 12) if password else "",
            "api_url": item.get("api_url", ""),
            "status": item.get("status", "available"),
            "created_at": item.get("created_at", ""),
            "claimed_at": item.get("claimed_at", ""),
            "claimed_task_id": item.get("claimed_task_id"),
            "claimed_worker_index": item.get("claimed_worker_index"),
            "used_at": item.get("used_at", ""),
            "used_task_id": item.get("used_task_id"),
            "used_worker_index": item.get("used_worker_index"),
            "failed_attempts": int(item.get("failed_attempts", 0) or 0),
            "last_failed_at": item.get("last_failed_at", ""),
        }

    def list_public(self) -> list[dict]:
        return [
            self.public_item(item)
            for item in sorted(self.emails.values(), key=lambda x: int(x.get("sort_order", x.get("id", 0))))
        ]

    def counts(self) -> dict:
        available = sum(1 for item in self.emails.values() if item.get("status") == "available")
        claimed = sum(1 for item in self.emails.values() if item.get("status") == "claimed")
        used = sum(1 for item in self.emails.values() if item.get("status") == "used")
        return {"total": len(self.emails), "available": available, "claimed": claimed, "used": used}

    def import_text(self, raw: str) -> dict:
        parsed = parse_custom_email_accounts(raw)
        existing_by_email = {item.get("email", "").lower(): item for item in self.emails.values()}
        added = 0
        updated = 0
        skipped = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for account in parsed:
            key = account["email"].lower()
            if key in existing_by_email:
                item = existing_by_email[key]
                item["password"] = account["password"]
                item["api_url"] = account["api_url"]
                item["updated_at"] = now
                item.setdefault("sort_order", int(item.get("id", 0)))
                updated += 1
                continue
            email_id = str(self.next_id)
            self.next_id += 1
            self.emails[email_id] = {
                "id": email_id,
                "email": account["email"],
                "password": account["password"],
                "api_url": account["api_url"],
                "status": "available",
                "sort_order": int(email_id),
                "created_at": now,
                "claimed_at": "",
                "claimed_task_id": None,
                "claimed_worker_index": None,
                "used_at": "",
                "used_task_id": None,
                "used_worker_index": None,
                "failed_attempts": 0,
                "last_failed_at": "",
            }
            existing_by_email[key] = self.emails[email_id]
            added += 1
        if not parsed:
            skipped += 1
        self.save()
        return {**self.counts(), "added": added, "updated": updated, "skipped": skipped}

    def available_count(self) -> int:
        return self.counts()["available"]

    def claim(self, count: int, task_id: int) -> list[dict]:
        available = [
            item for item in sorted(self.emails.values(), key=lambda x: int(x.get("sort_order", x.get("id", 0))))
            if item.get("status") == "available"
        ]
        if len(available) < count:
            raise ValueError(f"自备邮箱可用数量不足：需要 {count} 个，当前可用 {len(available)} 个")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        claimed = []
        for idx, item in enumerate(available[:count], 1):
            item["status"] = "claimed"
            item["claimed_at"] = now
            item["claimed_task_id"] = task_id
            item["claimed_worker_index"] = idx
            claimed.append({
                "id": item["id"],
                "email": item["email"],
                "password": item.get("password", ""),
                "api_url": item.get("api_url", ""),
            })
        self.save()
        return claimed

    def mark_used(self, email_id: str, task_id: int, worker_index: int):
        item = self.emails.get(str(email_id))
        if not item:
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item["status"] = "used"
        item["used_at"] = now
        item["used_task_id"] = task_id
        item["used_worker_index"] = worker_index
        item["claimed_at"] = ""
        item["claimed_task_id"] = None
        item["claimed_worker_index"] = None
        item["failed_attempts"] = 0
        item["last_failed_at"] = ""
        self.save()
        return True

    def mark_failed_or_release(self, email_id: str, task_id: int, worker_index: int, max_attempts: int = 3) -> tuple[bool, int]:
        item = self.emails.get(str(email_id))
        if not item or item.get("status") == "used":
            return False, int(item.get("failed_attempts", 0) or 0) if item else 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        attempts = int(item.get("failed_attempts", 0) or 0) + 1
        item["failed_attempts"] = attempts
        item["last_failed_at"] = now
        item["claimed_at"] = ""
        item["claimed_task_id"] = None
        item["claimed_worker_index"] = None

        if attempts >= max_attempts:
            item["status"] = "used"
            item["used_at"] = now
            item["used_task_id"] = task_id
            item["used_worker_index"] = worker_index
            self.save()
            return True, attempts

        max_order = max([int(x.get("sort_order", x.get("id", 0))) for x in self.emails.values()] or [0])
        item["status"] = "available"
        item["sort_order"] = max_order + 1
        item["last_released_at"] = now
        self.save()
        return False, attempts

    def release_to_tail(self, email_id: str):
        item = self.emails.get(str(email_id))
        if not item or item.get("status") == "used":
            return False
        max_order = max([int(x.get("sort_order", x.get("id", 0))) for x in self.emails.values()] or [0])
        item["status"] = "available"
        item["sort_order"] = max_order + 1
        item["claimed_at"] = ""
        item["claimed_task_id"] = None
        item["claimed_worker_index"] = None
        item["last_released_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()
        return True

    def reset(self, ids: list[str]) -> int:
        changed = 0
        for email_id in ids:
            item = self.emails.get(str(email_id))
            if not item:
                continue
            item["status"] = "available"
            item["claimed_at"] = ""
            item["claimed_task_id"] = None
            item["claimed_worker_index"] = None
            item["used_at"] = ""
            item["used_task_id"] = None
            item["used_worker_index"] = None
            item["failed_attempts"] = 0
            item["last_failed_at"] = ""
            changed += 1
        if changed:
            self.save()
        return changed

    def delete(self, ids: list[str]) -> int:
        deleted = 0
        for email_id in ids:
            if str(email_id) in self.emails:
                del self.emails[str(email_id)]
                deleted += 1
        if deleted:
            self.save()
        return deleted


custom_email_manager = CustomEmailManager()

# ─── Config Endpoints ───
@app.post("/api/config")
async def update_config(item: ConfigUpdate):
    global config
    proxy_scheme = item.proxy_scheme if item.proxy_scheme in ("http", "https", "socks5") else "http"
    config = {
        "api_key": item.api_key,
        "api_base": item.api_base,
        "email_domain": item.email_domain,
        "email_domains": item.email_domains,
        "yescaptcha_key": item.yescaptcha_key,
        "proxy_enabled": item.proxy_enabled,
        "proxy_scheme": proxy_scheme,
        "proxy_url": item.proxy_url.strip(),
        "pool_api_url": item.pool_api_url.strip(),
        "pool_api_key": item.pool_api_key.strip(),
        "auto_import_enabled": item.auto_import_enabled,
    }
    save_config(config)
    return {"status": "ok"}

@app.post("/api/test-proxy")
async def test_proxy(item: ProxyTestRequest):
    ok, message, proxy = test_proxy_connectivity(item.proxy_url, item.proxy_scheme)
    return {
        "valid": ok,
        "message": message,
        "normalized": proxy["url"] if proxy else "",
    }

@app.post("/api/test-config")
async def test_config(item: ConfigUpdate):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{item.api_base}/emails",
                headers={"X-API-Key": item.api_key},
                timeout=5.0
            )
            if response.status_code == 401:
                return {"valid": False, "message": "API Key 无效 (401 Auth Error)"}
            elif response.status_code in (301, 302, 307, 308):
                return {"valid": False, "message": f"连接被重定向 ({response.status_code})，请检查 URL 是否缺少 '/api' 结尾"}
            elif response.status_code == 200:
                return {"valid": True, "message": "API 配置有效可用！"}
            else:
                 return {"valid": False, "message": f"连接异常，状态码: {response.status_code}"}
    except Exception as e:
        return {"valid": False, "message": f"连接异常: {str(e)}"}

@app.post("/api/test-captcha-config")
async def test_captcha_config(data: dict):
    key = data.get("yescaptcha_key", "")
    if not key:
        return {"valid": False, "message": "请填写 API Key"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.yescaptcha.com/getBalance",
                json={"clientKey": key},
                timeout=10.0
            )
            result = resp.json()
            if result.get("errorId") == 0:
                balance = result.get("balance", 0)
                return {"valid": True, "message": f"有效！余额: {balance} 点"}
            else:
                return {"valid": False, "message": f"无效: {result.get('errorDescription', '未知错误')}"}
    except Exception as e:
        return {"valid": False, "message": f"连接异常: {str(e)}"}

@app.get("/api/config")
async def get_config():
    return config


@app.get("/api/custom-emails")
async def list_custom_emails():
    return {
        "counts": custom_email_manager.counts(),
        "emails": custom_email_manager.list_public(),
    }


@app.post("/api/custom-emails/import")
async def import_custom_emails(body: dict):
    try:
        return custom_email_manager.import_text(body.get("text", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/custom-emails/batch")
async def batch_custom_emails(body: dict):
    ids = [str(i) for i in body.get("ids", [])]
    action = body.get("action", "")
    if action == "reset":
        changed = custom_email_manager.reset(ids)
    elif action == "delete":
        changed = custom_email_manager.delete(ids)
    else:
        raise HTTPException(status_code=400, detail="未知操作")
    return {"status": "ok", "changed": changed, "counts": custom_email_manager.counts()}


# ─── Task Endpoints ───
@app.post("/api/tasks")
async def start_task(item: TaskStart):
    conc = max(1, min(item.concurrency, 10))
    qty = max(1, item.quantity)
    email_mode = item.email_mode if item.email_mode in ("temp", "custom", "microsoft") else "temp"
    uses_custom_email = email_mode in ("custom", "microsoft")
    custom_accounts = []
    if uses_custom_email:
        if item.custom_emails.strip():
            try:
                custom_email_manager.import_text(item.custom_emails)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        available = custom_email_manager.available_count()
        if qty > available:
            raise HTTPException(status_code=400, detail=f"自备邮箱可用数量不足：需要 {qty} 个，当前可用 {available} 个")
    browser_mode = normalize_browser_mode(item.browser_mode, item.show_browser)
    task = task_manager.create_task(qty, conc, item.show_browser, item.name, item.invite_url, email_mode, [], browser_mode)
    if uses_custom_email:
        try:
            task.custom_emails = custom_email_manager.claim(qty, task.id)
        except ValueError as e:
            task_manager.tasks.pop(task.id, None)
            raise HTTPException(status_code=400, detail=str(e))
    await task_manager.queue.put(task)

    # Ensure queue worker is running
    asyncio.create_task(task_manager.start_queue_worker())

    return task.to_dict()

@app.get("/api/tasks")
async def list_tasks():
    return [t.to_dict() for t in reversed(task_manager.tasks.values())]

@app.post("/api/tasks/delete")
async def delete_tasks(req: TaskDeleteRequest):
    task_manager.delete_tasks(req.ids)
    await task_manager.broadcast("__STATE_UPDATE__")
    return {"status": "ok", "deleted": len(req.ids)}

@app.post("/api/tasks/stop")
async def stop_tasks(req: TaskDeleteRequest):
    await task_manager.stop_tasks(req.ids)
    await task_manager.broadcast("__STATE_UPDATE__")
    return {"status": "ok", "stopped": len(req.ids)}

# ─── Auto Loop Endpoints ───
@app.get("/api/autoloop/status")
async def autoloop_status():
    return {
        "is_running": auto_loop_manager.is_running,
        "quantity": auto_loop_manager.quantity,
        "concurrency": auto_loop_manager.concurrency,
        "show_browser": auto_loop_manager.show_browser,
        "browser_mode": auto_loop_manager.browser_mode,
        "email_mode": auto_loop_manager.email_mode,
        "account_order": auto_loop_manager.account_order,
        "loop_run_mode": auto_loop_manager.loop_run_mode,
        "success_rate_stop_threshold": auto_loop_manager.success_rate_stop_threshold,
        "schedule_start": auto_loop_manager.schedule_start,
        "schedule_stop": auto_loop_manager.schedule_stop
    }

@app.post("/api/autoloop/start")
async def start_autoloop(item: TaskStart):
    conc = max(1, min(item.concurrency, 10))
    email_mode = item.email_mode if item.email_mode in ("temp", "custom", "microsoft") else "temp"
    if email_mode in ("custom", "microsoft") and item.quantity > custom_email_manager.available_count():
        raise HTTPException(status_code=400, detail=f"自备邮箱可用数量不足：需要 {item.quantity} 个，当前可用 {custom_email_manager.available_count()} 个")
    started = auto_loop_manager.start(
        item.quantity,
        conc,
        item.show_browser,
        item.schedule_start,
        item.schedule_stop,
        email_mode,
        item.browser_mode,
        item.account_order,
        item.success_rate_stop_threshold,
        item.loop_run_mode,
    )
    return {"status": "ok", "started": started}

@app.post("/api/autoloop/stop")
async def stop_autoloop():
    auto_loop_manager.stop()
    return {"status": "ok"}

# ─── Account Endpoints ───
@app.get("/api/accounts")
async def list_accounts():
    return account_manager.list_accounts()

@app.post("/api/accounts")
async def create_account(item: AccountCreate):
    if not item.name.strip():
        return JSONResponse(status_code=400, content={"error": "请填写账号名称"})
    if not item.invite_url.strip():
        return JSONResponse(status_code=400, content={"error": "请填写邀请链接"})
    acc = account_manager.add_account(item)
    return acc

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str):
    acc = account_manager.get_account_with_invitees(account_id)
    if not acc:
        return JSONResponse(status_code=404, content={"error": "账号不存在"})
    return acc

@app.put("/api/accounts/{account_id}")
async def update_account(account_id: str, item: AccountUpdate):
    if account_id not in account_manager.accounts:
        return JSONResponse(status_code=404, content={"error": "账号不存在"})
    updates = {k: v for k, v in item.model_dump().items() if v is not None}
    account_manager.update_account(account_id, updates)
    return {"status": "ok"}

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str):
    account_manager.delete_account(account_id)
    return {"status": "ok"}

@app.post("/api/accounts/{account_id}/toggle")
async def toggle_account(account_id: str, body: dict):
    is_active = body.get("is_active", True)
    account_manager.toggle_account(account_id, is_active)
    return {"status": "ok"}

@app.post("/api/accounts/batch")
async def batch_accounts(body: dict):
    ids = body.get("ids", [])
    action = body.get("action", "")
    if not ids or action not in ("delete", "enable", "disable"):
        return JSONResponse(status_code=400, content={"error": "参数错误"})
    count = 0
    for aid in ids:
        aid = str(aid)
        if aid in account_manager.accounts:
            if action == "delete":
                del account_manager.accounts[aid]
            elif action == "enable":
                account_manager.accounts[aid]["is_active"] = True
            elif action == "disable":
                account_manager.accounts[aid]["is_active"] = False
            count += 1
    account_manager.save_accounts()
    return {"status": "ok", "affected": count}

@app.get("/api/accounts/{account_id}/invitees")
async def get_invitees(account_id: str):
    acc = account_manager.get_account_with_invitees(account_id)
    if not acc:
        return JSONResponse(status_code=404, content={"error": "账号不存在"})
    return {
        "account_name": acc["name"],
        "invitees": acc["invitees"],
    }

@app.get("/api/accounts/{account_id}/invitees/export")
async def export_invitees(account_id: str):
    acc = account_manager.get_account_with_invitees(account_id)
    if not acc:
        return JSONResponse(status_code=404, content={"error": "账号不存在"})
    invitees = acc.get("invitees", [])
    if not invitees:
        return JSONResponse(status_code=404, content={"error": "暂无受邀人员"})

    # Generate CSV content
    lines = ["序号,邮箱,状态,任务ID,注册时间"]
    for idx, inv in enumerate(invitees, 1):
        status_text = {"success": "成功", "failed": "失败"}.get(inv.get("status", ""), "未知")
        lines.append(f'{idx},{inv["email"]},{status_text},{inv.get("task_id", "")},{inv.get("created_at", "")}')

    csv_content = "\n".join(lines)
    export_name = f"{sanitize_filename(acc['name'], '受邀人员')}_受邀人员.csv"

    from fastapi.responses import Response
    # UTF-8 BOM for Excel compatibility
    return Response(
        content=("\ufeff" + csv_content).encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(export_name)}"
        },
    )

# ─── Worker Logic ───
async def terminate_process(process: asyncio.subprocess.Process | None):
    if process is None or process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
        return
    except asyncio.TimeoutError:
        pass
    with suppress(ProcessLookupError):
        process.kill()
    with suppress(asyncio.TimeoutError):
        await asyncio.wait_for(process.wait(), timeout=5)


async def stop_task_processes(task: Task, reason: str, exclude_worker: int | None = None):
    if task.status == "running":
        task.status = "stopping"
        await task_manager.broadcast(f"🛑 任务 #{task.id} 已停止：{reason}")
    for worker_id, process in list(task.active_processes.items()):
        if exclude_worker is not None and worker_id == exclude_worker:
            continue
        await terminate_process(process)


async def stream_process_output(process: asyncio.subprocess.Process, prefix: str):
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="ignore").strip()
        if decoded:
            await task_manager.broadcast(f"{prefix} {decoded}")


async def execute_single_worker(task: Task, worker_index: int):
    cleaned = cleanup_stale_profiles(collect_active_profile_paths(task_manager.tasks))
    if cleaned:
        await task_manager.broadcast(f"[任务#{task.id}-{worker_index}] 已清理 {cleaned} 个残留浏览器目录")

    env = os.environ.copy()
    env["API_KEY"] = config["api_key"]
    env["API_BASE"] = config["api_base"]
    env["EMAIL_DOMAIN"] = config.get("email_domain", "rossa.cfd")
    # 多域名列表：传给 worker 进程，实现均匀分布
    env["EMAIL_DOMAINS"] = config.get("email_domains", "") or config.get("email_domain", "rossa.cfd")
    env["YESCAPTCHA_KEY"] = config.get("yescaptcha_key", "")
    env["PROXY_ENABLED"] = "1" if config.get("proxy_enabled") else "0"
    env["PROXY_SCHEME"] = config.get("proxy_scheme", "http")
    env["PROXY_URL"] = config.get("proxy_url", "")
    env["DATA_DIR"] = DATA_DIR
    env["SCREENSHOT_DIR"] = SCREENSHOT_DIR
    env["CONFIG_FILE"] = CONFIG_FILE
    env["BROWSER_MODE"] = task.browser_mode
    env["SHOW_BROWSER"] = "1" if task.browser_mode == "local" else "0"
    # 使用本地浏览器时禁用比特浏览器，反之亦然
    env["BITBROWSER_ENABLED"] = "1" if task.browser_mode == "bitbrowser" else "0"
    env["INVITE_URL"] = task.invite_url or ""
    env["REGISTRATION_MODE"] = task.email_mode
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    custom_email_id = None

    if task.email_mode in ("custom", "microsoft"):
        account = task.custom_emails[worker_index - 1] if worker_index - 1 < len(task.custom_emails) else None
        if not account:
            task.failed += 1
            await task_manager.broadcast(f"[任务#{task.id}-{worker_index}] ❌ 自备邮箱不足，跳过")
            return
        env["SELF_EMAIL_MODE"] = "1"
        env["SELF_EMAIL_ADDRESS"] = account["email"]
        env["SELF_EMAIL_PASSWORD"] = account["password"]
        env["SELF_EMAIL_API_URL"] = account["api_url"]
        custom_email_id = account.get("id")
        env["SELF_EMAIL_ID"] = str(custom_email_id or "")
        await task_manager.broadcast(f"[任务#{task.id}-{worker_index}] 📬 使用自备邮箱: {account['email']}")
    else:
        env["SELF_EMAIL_MODE"] = "0"

    # 给每个 worker 分配唯一的 Cookie 文件名，避免并发时互相"偷"文件
    cookie_id = f"task{task.id}_w{worker_index}"
    env["COOKIE_ID"] = cookie_id
    expected_cookie_file = os.path.join(DATA_DIR, "cookies", f"cookie_{cookie_id}.json")
    verify_success_file = os.path.join(DATA_DIR, "cookies", f"verify_success_{cookie_id}.marker")
    invite_invalid_file = os.path.join(DATA_DIR, "cookies", f"invite_invalid_{cookie_id}.marker")
    env["VERIFY_SUCCESS_FILE"] = verify_success_file
    env["INVITE_INVALID_FILE"] = invite_invalid_file
    profile_id = f"{task.id}_{worker_index}_{uuid.uuid4().hex[:10]}"
    user_data_dir = os.path.join(APP_DIR, f"{PROFILE_PREFIX}{profile_id}")
    env["USER_DATA_DIR"] = user_data_dir
    task.active_profiles[worker_index] = user_data_dir

    prefix = f"[任务#{task.id}-{worker_index}]"

    script_path = os.path.join(APP_DIR, "auto_register_leo.py")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", script_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env
    )
    task.active_processes[worker_index] = process
    output_task = asyncio.create_task(stream_process_output(process, prefix))

    try:
        try:
            await asyncio.wait_for(process.wait(), timeout=WORKER_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await task_manager.broadcast(f"{prefix} 运行超时，已强制结束浏览器和脚本")
            await terminate_process(process)

        invite_invalid_detected = os.path.exists(invite_invalid_file)
        verify_submitted = os.path.exists(verify_success_file)
        if task.email_mode in ("custom", "microsoft") and custom_email_id:
            if verify_submitted:
                custom_email_manager.mark_used(str(custom_email_id), task.id, worker_index)
                await task_manager.broadcast(f"{prefix} 📧 自备邮箱已确认提交验证码，标记为已使用")
            else:
                exhausted, attempts = custom_email_manager.mark_failed_or_release(str(custom_email_id), task.id, worker_index)
                if exhausted:
                    await task_manager.broadcast(f"{prefix} 📧 自备邮箱连续 {attempts} 次未成功，已标记为已使用，不再复用")
                else:
                    await task_manager.broadcast(f"{prefix} 📧 自备邮箱未完成验证码提交，第 {attempts}/3 次失败，已恢复未使用并移到队尾")

        if invite_invalid_detected:
            task.invite_invalid_detected = True
            task.failed += 1
            await task_manager.broadcast(f"{prefix} ❌ 检测到 Canva 邀请链接失效，正在停止该账号子任务")
            await stop_task_processes(task, "Canva 邀请链接失效", exclude_worker=worker_index)
            return

        if task.invite_invalid_detected:
            task.failed += 1
            await task_manager.broadcast(f"{prefix} ⏭️ 邀请链接已判定失效，跳过")
            return

        # 只检查该 worker 专属的 cookie 文件是否存在
        if os.path.exists(expected_cookie_file):
            task.completed += 1
            task.result_files.append(expected_cookie_file)
            await task_manager.broadcast(f"{prefix} ✅ 注册成功！(已导出 Cookie)")
            
            # --- Auto Import to Token Pool ---
            if config.get("auto_import_enabled"):
                try:
                    with open(expected_cookie_file, "r", encoding="utf-8") as f:
                        cookie_data = json.load(f)
                    pool_url = config.get("pool_api_url", "").strip()
                    pool_key = config.get("pool_api_key", "").strip()
                    if pool_url and pool_key:
                        # 确保路径正确
                        if not pool_url.endswith("/api/v1/tokens/import-cookie"):
                            pool_url = pool_url.rstrip("/") + "/api/v1/tokens/import-cookie"
                        
                        payload = {
                            "name": cookie_data.get("name", ""),
                            "cookie": cookie_data.get("cookie", "")
                        }
                        headers = {
                            "Authorization": f"Bearer {pool_key}", 
                            "X-Import-Key": pool_key,
                            "Content-Type": "application/json"
                        }
                        import_success = False
                        max_import_attempts = 8
                        import_retry_delay = 3
                        # 直连模式，最多 8 次重试
                        for attempt in range(max_import_attempts):
                            try:
                                async with httpx.AsyncClient(timeout=15) as client:
                                    resp = await client.post(pool_url, json=payload, headers=headers, timeout=15)
                                    try:
                                        resp_json = resp.json()
                                        if resp.status_code == 200 and resp_json.get("ok"):
                                            await task_manager.broadcast(f"{prefix} 🌐 自动导入 Token 池成功！")
                                            task.imported += 1
                                            import_success = True
                                            break
                                        else:
                                            await task_manager.broadcast(f"{prefix} ⚠️ 自动导入失败 (尝试 {attempt+1}/{max_import_attempts}): {resp.text}")
                                    except Exception:
                                        await task_manager.broadcast(f"{prefix} ⚠️ 自动导入失败(非预期返回) (尝试 {attempt+1}/{max_import_attempts}): {resp.text}")
                            except Exception as e:
                                await task_manager.broadcast(f"{prefix} ⚠️ 自动导入异常 (尝试 {attempt+1}/{max_import_attempts}): {str(e)}")
                            
                            if not import_success and attempt < max_import_attempts - 1:
                                await asyncio.sleep(import_retry_delay)  # 重试前等待3秒

                        if not import_success:
                            await task_manager.broadcast(f"{prefix} ❌ 自动导入 Token 池彻底失败，判定任务失败。")
                            # 从 completed 中撤销，改为 failed
                            task.completed -= 1
                            task.failed += 1
                except Exception as e:
                    import traceback
                    await task_manager.broadcast(f"{prefix} ⚠️ 自动导入异常: {str(e)}")
                    print(traceback.format_exc())
                    # 如果有异常，也算失败
                    task.completed -= 1
                    task.failed += 1
        else:
            task.failed += 1
            await task_manager.broadcast(f"{prefix} ❌ 失败 (未导出 Cookie)")
    except asyncio.CancelledError:
        await terminate_process(process)
        if task.email_mode in ("custom", "microsoft") and custom_email_id:
            custom_email_manager.release_to_tail(str(custom_email_id))
            await task_manager.broadcast(f"{prefix} 📧 任务停止，自备邮箱已恢复未使用并移到队尾")
        task.failed += 1
        await task_manager.broadcast(f"{prefix} 🛑 操作已停止")
        raise
    finally:
        with suppress(asyncio.CancelledError):
            await output_task
        if process.returncode is None:
            await terminate_process(process)
        task.active_processes.pop(worker_index, None)
        task.active_profiles.pop(worker_index, None)
        cleanup_stale_profiles(collect_active_profile_paths(task_manager.tasks))
        await task_manager.broadcast("__STATE_UPDATE__")

async def run_task(task: Task):
    task.status = "running"
    task.asyncio_tasks = []
    task.active_processes = {}
    task.active_profiles = {}
    await task_manager.broadcast("__STATE_UPDATE__")

    sem = asyncio.Semaphore(task.concurrency)

    async def wrapper(idx):
        async with sem:
            # 优雅停止：获取信号量后检查任务是否已标记停止
            if task.status == "stopping":
                await task_manager.broadcast(f"[任务#{task.id}-{idx}] ⏭️ 任务已停止，跳过")
                return
            await execute_single_worker(task, idx)

    workers = [asyncio.create_task(wrapper(i)) for i in range(1, task.quantity + 1)]
    task.asyncio_tasks = workers
    await asyncio.gather(*workers, return_exceptions=True)
    task.asyncio_tasks = []
    task.active_processes = {}
    task.active_profiles = {}

    if task.status == "stopping":
        task.status = "stopped"
        await task_manager.broadcast(f"🏁 任务 #{task.id} 已优雅停止 (成功 {task.completed}, 失败 {task.failed}, 入池 {task.imported})")
    elif task.status != "stopped":
        task.status = "completed"
        await task_manager.broadcast(f"🏁 任务 #{task.id} 结束 (成功 {task.completed}, 失败 {task.failed}, 入池 {task.imported})")
    await task_manager.broadcast("__STATE_UPDATE__")

# ─── WebSocket ───
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    task_manager.websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in task_manager.websockets:
            task_manager.websockets.remove(websocket)

# ─── Export ───
@app.get("/api/export")
async def export_results(ids: str = ""):
    # Filter by task IDs if provided
    export_filename = ""
    if ids:
        target_ids = set(int(x) for x in ids.split(",") if x.strip().isdigit())
        selected_tasks = [t for t in task_manager.tasks.values() if t.id in target_ids]
        result_files = []
        for t in task_manager.tasks.values():
            if t.id in target_ids:
                if t.result_files:
                    result_files.extend(resolve_data_file(f) for f in t.result_files)
                else:
                    # Fallback for older tasks before result_files was saved to JSON
                    import glob
                    result_files.extend(glob.glob(os.path.join(SCREENSHOT_DIR, f"cookie_task{t.id}_*.json")))
        if len(selected_tasks) == 1:
            task = selected_tasks[0]
            export_filename = f"{sanitize_filename(task.name, f'任务_{task.id}')}_#{task.id}.json"
        else:
            export_filename = f"批量导出_{len(selected_tasks)}个任务_{export_timestamp()}.json"
    else:
        selected_tasks = list(task_manager.tasks.values())
        result_files = []
        for t in task_manager.tasks.values():
            if t.result_files:
                result_files.extend(resolve_data_file(f) for f in t.result_files)
            else:
                import glob
                result_files.extend(glob.glob(os.path.join(SCREENSHOT_DIR, f"cookie_task{t.id}_*.json")))
        export_filename = f"全部任务_{export_timestamp()}.json"

    combined = []
    for f in result_files:
        try:
            data = json.load(open(f, "r", encoding="utf-8"))
            if "cookie" in data:
                combined.append(data)
        except:
            pass

    if not combined:
        return JSONResponse(status_code=404, content={"error": "暂无成功记录可导出"})

    # 直接从内存返回 JSON，不再写临时文件到根目录
    from fastapi.responses import Response
    content = json.dumps(combined, ensure_ascii=False, indent=4)
    if not export_filename:
        export_filename = f"批量导出_{len(selected_tasks)}个任务_{export_timestamp()}.json"
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(export_filename)}"
        },
    )

# ==========================================
# Canva Native API 端点
# ==========================================

@app.get("/api/accounts/{account_id}/canva/members")
async def get_canva_members(account_id: str):
    """获取真正的 Canva 后台成员列表"""
    account = account_manager.accounts.get(account_id)
    if not account or not account.get("token_data"):
        return JSONResponse(status_code=400, content={"error": "此账号尚未导入 Canva Token 文件"})
    
    def save_refreshed_token(new_token_data):
        account["token_data"] = new_token_data
        account_manager.save_accounts()
        
    api = CanvaAPI(account["token_data"], on_token_refreshed=save_refreshed_token)
    data = await api.get_members()
    if "error" in data:
        return JSONResponse(status_code=400, content={"error": data["error"]})
    return data

@app.post("/api/accounts/{account_id}/canva/members/{user_id}/remove")
async def remove_canva_member(account_id: str, user_id: str):
    """从 Canva 真实移除该成员"""
    account = account_manager.accounts.get(account_id)
    if not account or not account.get("token_data"):
        return JSONResponse(status_code=400, content={"error": "此账号尚未导入 Canva Token 文件"})
    
    def save_refreshed_token(new_token_data):
        account["token_data"] = new_token_data
        account_manager.save_accounts()
        
    api = CanvaAPI(account["token_data"], on_token_refreshed=save_refreshed_token)
    result = await api.remove_member(user_id)
    if "error" in result:
        return JSONResponse(status_code=400, content={"error": result["error"]})
    return result

@app.post("/api/accounts/{account_id}/token")
async def update_account_token(account_id: str, body: dict):
    """浏览器插件自动推送最新 Token（自动刷新保活）"""
    account = account_manager.accounts.get(account_id)
    if not account:
        return JSONResponse(status_code=404, content={"error": "账号不存在"})
    
    token_data = body.get("token_data")
    if not token_data:
        return JSONResponse(status_code=400, content={"error": "token_data 不能为空"})
    
    account["token_data"] = token_data
    account_manager.save_accounts()
    print(f"[Token 同步] 账号 #{account_id} ({account.get('name', '')}) 的 Token 已自动更新")
    return {"status": "ok", "message": f"账号 {account.get('name', '')} 的 Token 已更新"}



# Mount static frontend
static_dir = os.path.join(APP_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.on_event("startup")
async def cleanup_profiles_on_startup():
    cleanup_stale_profiles(collect_active_profile_paths(task_manager.tasks))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
