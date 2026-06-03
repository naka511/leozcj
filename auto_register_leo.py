"""
Leonardo.Ai 自动注册 (DrissionPage 模式 - 通过 Canva 邀请)
============================================================
使用 DrissionPage 接管本地 Chrome，绕过 Playwright/Selenium 检测。
"""

import asyncio
import json
import os
import re
import sys
import time
import random
import string
import socket
import shutil
from datetime import datetime
from urllib.parse import unquote, urlsplit

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import httpx
from DrissionPage import ChromiumPage, ChromiumOptions

# ════════════════════════ 配置 ════════════════════════

API_KEY = os.getenv("API_KEY", "")
API_BASE = os.getenv("API_BASE", "https://rossa.cfd/api")
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "rossa.cfd")
BROWSER_MODE = os.getenv("BROWSER_MODE", "").strip().lower()
if BROWSER_MODE in ("headless", "headless-new"):
    BROWSER_MODE = "new-headless"
elif BROWSER_MODE in ("cloak", "cloak-browser", "cloak-headless"):
    BROWSER_MODE = "cloakbrowser"
elif BROWSER_MODE in ("local-browser", "visible"):
    BROWSER_MODE = "local"
elif BROWSER_MODE in ("fingerprint", "fingerprint-browser", "bit"):
    BROWSER_MODE = "bitbrowser"
SHOW_BROWSER = os.getenv("SHOW_BROWSER", "1") == "1"
MINIMIZE_BROWSER = os.getenv("MINIMIZE_BROWSER", "1") == "1"
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "0") == "1"
PROXY_SCHEME = os.getenv("PROXY_SCHEME", "http")
PROXY_URL = os.getenv("PROXY_URL", "")
API_PROXY_ENABLED = os.getenv("API_PROXY_ENABLED", "0") == "1"
YESCAPTCHA_KEY = os.getenv("YESCAPTCHA_KEY", "")
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", os.path.join(DATA_DIR, "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
SELF_EMAIL_MODE = os.getenv("SELF_EMAIL_MODE", "0") == "1"
SELF_EMAIL_ADDRESS = os.getenv("SELF_EMAIL_ADDRESS", "").strip()
SELF_EMAIL_PASSWORD = os.getenv("SELF_EMAIL_PASSWORD", "").strip()
SELF_EMAIL_API_URL = os.getenv("SELF_EMAIL_API_URL", "").strip()
VERIFY_SUCCESS_FILE = os.getenv("VERIFY_SUCCESS_FILE", "").strip()
INVITE_INVALID_FILE = os.getenv("INVITE_INVALID_FILE", "").strip()
REGISTRATION_MODE = os.getenv("REGISTRATION_MODE", "temp").strip().lower()

CANVA_INVITE_URL = os.getenv("INVITE_URL", "").strip() or "https://www.canva.com/brand/join?token=ifZNbrrBx-pxrbOGM2yHOA&referrer=team-invite"

BITBROWSER_ENABLED = os.getenv("BITBROWSER_ENABLED", "1") == "1"
BITBROWSER_URL = os.getenv("BITBROWSER_URL", "http://127.0.0.1:54345")
BITBROWSER_API_TIMEOUT = int(os.getenv("BITBROWSER_API_TIMEOUT", "30"))
BITBROWSER_API_RETRIES = int(os.getenv("BITBROWSER_API_RETRIES", "3"))
if BROWSER_MODE == "local":
    SHOW_BROWSER = True
    BITBROWSER_ENABLED = False
elif BROWSER_MODE == "new-headless":
    SHOW_BROWSER = False
    BITBROWSER_ENABLED = False
elif BROWSER_MODE == "cloakbrowser":
    SHOW_BROWSER = False
    BITBROWSER_ENABLED = False
elif BROWSER_MODE == "bitbrowser":
    SHOW_BROWSER = False
    BITBROWSER_ENABLED = True

EMAIL_LOGIN_KEYWORDS = [
    "email", "e-mail", "邮箱", "邮件", "郵箱", "郵件", "電子郵件",
    "電郵", "電郵地址", "使用電郵",
    "メール", "メールアドレス", "メールアドレスで続行", "仕事用メールアドレス",
    "仕事用メールアドレスで続行", "이메일", "전자 메일",
    "correo electrónico", "correo electronico", "correo", "courriel",
    "adresse e-mail", "e-mail-adresse", "posta elettronica",
    "электронная почта", "почта", "อีเมล", "email address",
]

OTHER_LOGIN_TEXTS = [
    "其他登录方式", "其他登入方式", "其他方式登录", "更多登录方式",
    "透過其他方式繼續操作", "通过其他方式继续操作",
    "透過其他方式繼續", "通过其他方式继续",
    "其他方式繼續", "其他方式继续",
    "Other login options", "Other ways to log in", "More login options",
    "Continue another way", "Sign in another way",
    "別の方法で続ける", "別の方法で続行", "他の方法で続ける", "他の方法で続行",
]

MICROSOFT_LOGIN_TEXTS = [
    "Microsoft帐户登录", "Microsoft 帐户登录", "Microsoft账户登录",
    "Microsoft 账户登录", "Microsoft帐号登录", "Microsoft 帐号登录",
    "以 Microsoft 繼續", "以 Microsoft 继续",
    "Sign in with Microsoft", "Continue with Microsoft", "Microsoft account",
    "Microsoftで続行", "Microsoft で続行", "Microsoftで続ける", "Microsoft で続ける",
]

COOKIE_ACCEPT_TEXTS = [
    "Accept all cookies", "Accept cookies", "I accept", "接受所有", "接受全部",
    "接受所有 Cookie", "接受所有 cookies", "同意", "同意する", "すべて同意",
    "すべてのCookieを受け入れる", "すべてのCookieを許可する",
    "すべての Cookie を許可する", "Cookieを許可する", "Cookie を許可する",
    "모든 쿠키 허용", "동의", "허용",
    "Aceptar todas", "Aceptar cookies", "Aceitar todos", "Accepter tous",
    "Alle akzeptieren", "Accetta tutto", "Принять все",
]

CONTINUE_BUTTON_TEXTS = [
    "继续", "繼續", "Continue", "Next", "下一步",
    "次へ", "次へ進む", "続行", "続ける", "進む", "다음", "계속", "继续操作",
    "Continuar", "Siguiente", "Próximo", "Suivant", "Weiter", "Avanti",
    "Продолжить", "Далее", "Lanjut", "Berikutnya", "Tiếp tục", "ถัดไป", "ดำเนินการต่อ",
]

CREATE_ACCOUNT_BUTTON_TEXTS = [
    *CONTINUE_BUTTON_TEXTS,
    "创建账户", "创建帐号", "建立帳戶", "建立帳號", "建立账户",
    "註冊", "註冊帳戶", "註冊帳號", "使用電郵繼續",
    "Create account", "Create an account", "Sign up",
    "アカウントを作成", "アカウント作成", "계정 만들기", "계정 생성",
    "Crear cuenta", "Criar conta", "Créer un compte", "Konto erstellen",
    "Crea account", "Создать аккаунт", "Buat akun",
]

RESEND_CODE_TEXTS = [
    "Resend code", "重新发送", "Resend", "重发验证码", "重新发送验证码",
    "重新傳送", "重新傳送驗證碼", "重發驗證碼", "Didn't get the code",
    "コードを再送信", "認証コードを再送信", "再送信",
    "코드 다시 보내기", "인증 코드 다시 보내기", "다시 보내기",
    "Reenviar código", "Reenviar", "Renvoyer le code", "Erneut senden",
    "Invia di nuovo", "Отправить код еще раз", "Отправить повторно", "Kirim ulang kode",
]

SUBMIT_CODE_BUTTON_TEXTS = [
    *CONTINUE_BUTTON_TEXTS,
    "Submit", "提交", "送出", "Verify", "验证", "驗證",
    "確認", "認証", "送信", "完了", "登録を完了", "登録を完了する", "확인", "인증", "제출",
    "Verificar", "Enviar", "Vérifier", "Envoyer", "Bestätigen",
    "Senden", "Verifica", "Invia", "Подтвердить", "Отправить", "Verifikasi",
]

SECURITY_REASON_TEXTS = [
    "security reasons", "出于安全原因", "基於安全原因", "安全上の理由",
    "為安全", "無法讓你註冊", "无法让你注册",
    "보안상의 이유", "razones de seguridad", "raisons de sécurité",
    "Sicherheitsgründen", "motivi di sicurezza", "соображениям безопасности", "RRS-",
]

OAUTH_ALLOW_TEXTS = [
    "允许", "允許", "Allow", "Authorize", "Grant access", "Continue",
    "許可", "承認", "同意", "同意する", "アクセスを許可", "共有を許可", "連携を許可", "허용", "승인",
    "Autorizar", "Permitir", "Autoriser", "Zulassen", "Autorizza", "Разрешить",
]

ONBOARDING_SKIP_TEXTS = [
    "Let's Go", "Let's Go!", "Get Started", "Continue", "OK", "Got it",
    "开始", "開始", "知道了", "了解", "我知道了",
    "始める", "はじめる", "OK", "了解", "시작하기", "확인", "알겠습니다",
    "Comenzar", "Entendido", "Commencer", "Compris", "Loslegen", "Verstanden",
    "Начать", "Понятно",
]


def log(msg: str):
    t = datetime.now().strftime("%H:%M:%S")
    try:
        print(f"[{t}] {msg}")
    except UnicodeEncodeError:
        print(f"[{t}] {msg}".encode("utf-8", errors="replace").decode("utf-8", errors="replace"))


# ════════════════════════ 代理 ════════════════════════

def build_proxy_string() -> str | None:
    if not PROXY_ENABLED:
        return None
    raw = (PROXY_URL or "").strip()
    if not raw:
        return None
    scheme = (PROXY_SCHEME or "http").strip().lower()
    if "://" not in raw:
        return f"{scheme}://{raw}"
    return raw

def build_api_proxy() -> str | None:
    if not API_PROXY_ENABLED:
        return None
    return build_proxy_string()


# ════════════════════════ 临时邮箱 ════════════════════════

class TempMail:
    def __init__(self):
        proxy_kwargs = {}
        api_proxy = build_api_proxy()
        if api_proxy:
            proxy_kwargs["proxy"] = api_proxy
        self.client = httpx.AsyncClient(
            base_url=API_BASE,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=30.0,
            **proxy_kwargs,
        )
        self.email_id = None
        self.address = None

    def _pick_random_domain(self) -> str:
        domains_str = os.getenv("EMAIL_DOMAINS", "")
        if domains_str:
            domains = [d.strip() for d in domains_str.split(",") if d.strip()]
            if domains:
                return random.choice(domains)
        return EMAIL_DOMAIN

    async def create(self) -> str:
        domain = self._pick_random_domain()
        prefix = generate_human_email_prefix()
        for attempt in range(1, 4):
            try:
                r = await self.client.post("/emails/generate", json={
                    "name": prefix, "expiryTime": 3600000, "domain": domain,
                })
                r.raise_for_status()
                data = r.json()
                self.email_id = data["id"]
                self.address = data["email"]
                log(f"📬 临时邮箱: {self.address}")
                return self.address
            except Exception as e:
                if attempt < 3:
                    await asyncio.sleep(attempt * 2)
                else:
                    raise RuntimeError(f"临时邮箱创建失败: {e}")

    async def wait_for_code(self, max_wait=120, interval=5) -> str | None:
        log(f"⏳ 等待验证邮件 (最长 {max_wait}s)...")
        start = time.time()
        attempt = 0
        while time.time() - start < max_wait:
            attempt += 1
            try:
                r = await self.client.get(f"/emails/{self.email_id}")
                r.raise_for_status()
                messages = r.json().get("messages", [])
                if messages:
                    for msg in messages:
                        code = extract_code(msg)
                        if code:
                            log(f"🔑 验证码: {code}")
                            return code
                elif attempt % 3 == 1:
                    log(f"  轮询 #{attempt} ({int(time.time()-start)}s) 暂无邮件...")
            except Exception as e:
                log(f"  轮询出错: {e}")
            await asyncio.sleep(interval)
        log("❌ 等待验证邮件超时")
        return None

    async def close(self):
        await self.client.aclose()

    def wait_for_code_sync(self, max_wait=120, interval=5) -> str | None:
        """同步版本的验证码等待（供 DrissionPage 同步流程调用）"""
        log(f"⏳ 等待验证邮件 (最长 {max_wait}s)...")
        import httpx as _httpx
        sync_client = _httpx.Client(
            base_url=API_BASE,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
            timeout=30.0,
        )
        start = time.time()
        attempt = 0
        try:
            while time.time() - start < max_wait:
                attempt += 1
                try:
                    r = sync_client.get(f"/emails/{self.email_id}")
                    r.raise_for_status()
                    messages = r.json().get("messages", [])
                    if messages:
                        for msg in messages:
                            code = extract_code(msg)
                            if code:
                                log(f"🔑 验证码: {code}")
                                return code
                    elif attempt % 3 == 1:
                        log(f"  轮询 #{attempt} ({int(time.time()-start)}s) 暂无邮件...")
                except Exception as e:
                    log(f"  轮询出错: {e}")
                time.sleep(interval)
        finally:
            sync_client.close()
        log("❌ 等待验证邮件超时")
        return None


class SelfProvidedMail:
    def __init__(self, address: str, password: str, api_url: str):
        self.address = address.strip()
        self.password = password.strip()
        self.api_url = api_url.strip()

    async def create(self) -> str:
        if not self.address or not self.api_url:
            raise RuntimeError("自备邮箱配置不完整，请提供 邮箱----密码----取件api链接")
        log(f"📬 自备邮箱: {self.address}")
        return self.address

    async def close(self):
        return None

    def wait_for_code_sync(self, max_wait=120, interval=5) -> str | None:
        log(f"⏳ 通过自备邮箱 API 等待验证码 (最长 {max_wait}s)...")
        import httpx as _httpx
        start = time.time()
        attempt = 0
        with _httpx.Client(timeout=30.0, follow_redirects=True) as client:
            while time.time() - start < max_wait:
                attempt += 1
                try:
                    resp = client.get(self.api_url)
                    resp.raise_for_status()
                    code = extract_code_from_response(resp)
                    if code:
                        log(f"🔑 验证码: {code}")
                        return code
                    if attempt % 3 == 1:
                        log(f"  轮询自备邮箱 #{attempt} ({int(time.time()-start)}s) 暂无验证码...")
                except Exception as e:
                    log(f"  自备邮箱 API 轮询出错: {e}")
                time.sleep(interval)
        log("❌ 自备邮箱验证码等待超时")
        return None


def extract_code_from_text(text: str, source: str = "文本") -> str | None:
    if not text:
        return None
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    patterns = [
        r'(?:验证码|驗證碼|認證碼|认证码|code|OTP|verification)\D{0,20}(\d{4,8})',
        r'(\d{6})\D{0,20}(?:验证码|驗證碼|認證碼|认证码|code|OTP|verification)',
        r'(?<![A-Za-z0-9])(\d{6})(?![A-Za-z0-9])',
    ]
    for pattern in patterns:
        m = re.search(pattern, cleaned, re.I)
        if m:
            log(f"  📧 从{source}提取验证码: {m.group(1)}")
            return m.group(1)
    return None


def _flatten_json_text(data) -> str:
    parts = []
    if isinstance(data, dict):
        for value in data.values():
            parts.append(_flatten_json_text(value))
    elif isinstance(data, list):
        for item in data:
            parts.append(_flatten_json_text(item))
    elif data is not None:
        parts.append(str(data))
    return " ".join(part for part in parts if part)


def extract_code_from_response(resp) -> str | None:
    try:
        data = resp.json()
        code = extract_code_from_text(_flatten_json_text(data), "自备邮箱 API JSON")
        if code:
            return code
    except Exception:
        pass
    return extract_code_from_text(resp.text or "", "自备邮箱 API 返回")


def extract_code(mail: dict) -> str | None:
    """从邮件中提取验证码。优先从 subject 提取，再从 content/html body 提取。"""

    # 1. 优先从邮件主题提取（Canva 主题格式: "你的Canva可画验证码是160798"）
    subject = mail.get("subject", "")
    if subject:
        code = extract_code_from_text(subject, "主题")
        if code:
            return code

    # 2. 从纯文本内容提取（content 字段，不含 HTML 标签）
    content = mail.get("content", "") or mail.get("text", "") or ""
    if content:
        # 先尝试关键词匹配
        code = extract_code_from_text(content, "内容")
        if code:
            return code

    # 3. 最后从 HTML body 提取（去除标签后匹配）
    html = mail.get("html", "") or mail.get("body", "") or ""
    if html:
        code = extract_code_from_text(html, "HTML")
        if code:
            return code

    log(f"  ⚠️ 未能从邮件中提取验证码 (keys: {list(mail.keys())})")
    return None


# ════════════════════════ 人类行为模拟 ════════════════════════

# ── 真实姓名库（用于生成更像真人的邮箱前缀） ──
_FIRST_NAMES = [
    'james', 'mary', 'robert', 'patricia', 'john', 'jennifer', 'michael', 'linda',
    'david', 'elizabeth', 'william', 'barbara', 'richard', 'susan', 'joseph', 'jessica',
    'thomas', 'sarah', 'charles', 'karen', 'christopher', 'lisa', 'daniel', 'nancy',
    'matthew', 'betty', 'anthony', 'margaret', 'mark', 'sandra', 'donald', 'ashley',
    'steven', 'kimberly', 'paul', 'emily', 'andrew', 'donna', 'joshua', 'michelle',
    'brian', 'carol', 'kevin', 'amanda', 'george', 'melissa', 'timothy', 'deborah',
    'alex', 'emma', 'ryan', 'olivia', 'jason', 'sophie', 'ethan', 'chloe',
    'nathan', 'grace', 'tyler', 'lily', 'jacob', 'mia', 'dylan', 'ava',
    'logan', 'zoe', 'lucas', 'ella', 'mason', 'aria', 'owen', 'isla',
]
_LAST_NAMES = [
    'smith', 'johnson', 'williams', 'brown', 'jones', 'garcia', 'miller', 'davis',
    'rodriguez', 'martinez', 'hernandez', 'lopez', 'gonzalez', 'wilson', 'anderson',
    'thomas', 'taylor', 'moore', 'jackson', 'martin', 'lee', 'perez', 'thompson',
    'white', 'harris', 'sanchez', 'clark', 'ramirez', 'lewis', 'robinson',
    'walker', 'young', 'allen', 'king', 'wright', 'scott', 'torres', 'nguyen',
    'hill', 'flores', 'green', 'adams', 'nelson', 'baker', 'hall', 'rivera',
    'campbell', 'mitchell', 'carter', 'roberts', 'turner', 'phillips', 'parker',
]

def generate_human_email_prefix() -> str:
    """生成看起来像真人的邮箱前缀，比如 james.smith92"""
    first = random.choice(_FIRST_NAMES)
    last = random.choice(_LAST_NAMES)
    style = random.randint(1, 6)
    if style == 1:
        return f"{first}.{last}{random.randint(1, 99)}"
    elif style == 2:
        return f"{first}{last}{random.randint(10, 999)}"
    elif style == 3:
        return f"{first}_{last}{random.randint(1, 99)}"
    elif style == 4:
        return f"{first[0]}{last}{random.randint(10, 99)}"
    elif style == 5:
        year = random.randint(85, 99)  # 85-99 → 模拟 1985-1999 出生
        return f"{first}.{last}{year}"
    else:
        return f"{first}{random.randint(100, 9999)}"

def human_delay(min_s=0.8, max_s=2.5):
    """模拟人类操作间隔，带微小随机抖动"""
    base = random.uniform(min_s, max_s)
    # 偶尔额外停顿，模拟人类"思考"或"分心"
    if random.random() < 0.15:
        base += random.uniform(0.5, 2.0)
    time.sleep(base)

def type_like_human(element, text, min_delay=0.04, max_delay=0.16, random_pause=True):
    """模拟人类打字速度，带偶尔停顿和速度变化"""
    element.clear()
    for i, ch in enumerate(text):
        element.input(ch)
        # 基础打字间隔
        delay = random.uniform(min_delay, max_delay) if max_delay > 0 else 0
        # 偶尔停顿（模拟人类看键盘或思考）
        if random_pause and random.random() < 0.08:
            delay += random.uniform(0.3, 0.8)
        if delay > 0:
            time.sleep(delay)


def get_input_value(element) -> str:
    """Read the real DOM value after automation input."""
    try:
        value = element.run_js("return this.value || '';")
        return "" if value is None else str(value)
    except Exception:
        pass
    try:
        value = element.attr("value")
        return "" if value is None else str(value)
    except Exception:
        return ""


def set_input_value_by_js(element, text: str) -> bool:
    """Set a controlled input value and fire events React-style forms listen for."""
    value_js = json.dumps(text, ensure_ascii=False)
    js_code = f"""
    try {{
        this.focus();
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(this, {value_js});
        this.dispatchEvent(new Event('input', {{ bubbles: true }}));
        this.dispatchEvent(new Event('change', {{ bubbles: true }}));
        this.dispatchEvent(new Event('blur', {{ bubbles: true }}));
        return this.value || '';
    }} catch (e) {{
        return '';
    }}
    """
    try:
        return str(element.run_js(js_code) or "") == text
    except Exception:
        return False


def is_input_ready(element) -> bool:
    """Return True when an input is visible, enabled, and writable."""
    js_code = """
    try {
        var style = window.getComputedStyle(this);
        var rect = this.getBoundingClientRect();
        return !!(
            rect.width > 0 &&
            rect.height > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !this.disabled &&
            !this.readOnly
        );
    } catch (e) {
        return false;
    }
    """
    try:
        return bool(element.run_js(js_code))
    except Exception:
        return False


def wait_for_stable_input(page, selectors, label: str, timeout: float = 8):
    """Wait until the same input is writable across two short checks."""
    start = time.time()
    last_signature = None
    while time.time() - start < timeout:
        element = find_first_element(page, selectors, timeout=0.8)
        if not element or not is_input_ready(element):
            time.sleep(0.3)
            continue

        try:
            signature = element.run_js("""
                return [
                    this.id || '',
                    this.name || '',
                    this.type || '',
                    this.getAttribute('autocomplete') || '',
                    this.getBoundingClientRect().width + 'x' + this.getBoundingClientRect().height
                ].join('|');
            """)
        except Exception:
            signature = None

        if signature and signature == last_signature:
            return element
        last_signature = signature
        time.sleep(0.4)

    log(f"  ⚠️ {label}输入框等待稳定超时，继续按当前页面尝试")
    return find_first_element(page, selectors, timeout=1)


def type_text_verified(
    page,
    selectors,
    text: str,
    label: str,
    max_attempts: int = 3,
    prefer_js: bool = False,
    fast_type: bool = False,
    js_fallback: bool = True,
):
    """Input text, verify the DOM value, and retry with a JS fallback if needed."""
    last_value_len = -1
    for attempt in range(1, max_attempts + 1):
        element = wait_for_stable_input(page, selectors, label, timeout=4)
        if not element:
            log(f"  ⚠️ {label}输入框未找到，重试 {attempt}/{max_attempts}")
            time.sleep(0.8)
            continue

        try:
            element.click(by_js=False)
            time.sleep(random.uniform(0.15, 0.35))
        except Exception:
            try:
                element.click()
            except Exception:
                pass

        if prefer_js and set_input_value_by_js(element, text):
            value = get_input_value(element)
            if value == text:
                return element
        else:
            try:
                if fast_type:
                    type_like_human(element, text, min_delay=0, max_delay=0, random_pause=False)
                else:
                    type_like_human(element, text)
            except Exception as e:
                log(f"  ⚠️ {label}输入异常，重试 {attempt}/{max_attempts}: {e}")

        value = get_input_value(element)
        last_value_len = len(value)
        if value == text:
            return element

        if js_fallback:
            log(f"  ⚠️ {label}输入校验失败，当前长度 {last_value_len}/{len(text)}，尝试 JS 兜底")
        else:
            log(f"  ⚠️ {label}输入校验失败，当前长度 {last_value_len}/{len(text)}，准备重试")
        if js_fallback and set_input_value_by_js(element, text):
            value = get_input_value(element)
            if value == text:
                return element

        time.sleep(0.8)

    log(f"  ❌ {label}输入失败，最终长度 {last_value_len}/{len(text)}")
    return None


def type_code_like_human(element, text):
    """专门针对验证码输入的拟人化操作（鼠标悬停、真实点击聚焦、分段打字）"""
    try:
        # 强制将鼠标移动到该元素上（留下鼠标轨迹）
        element.hover()
        time.sleep(random.uniform(0.2, 0.6))
        # 真实模拟物理点击（不使用 JS）
        element.click(by_js=False)
        # 点击后思考一下
        time.sleep(random.uniform(0.5, 1.2))
    except Exception:
        pass

    element.clear()
    # 模拟人类记不住 6 位数，分段输入的行为：前 3 位 -> 看一眼 -> 后 3 位
    for i, ch in enumerate(text):
        element.input(ch)
        delay = random.uniform(0.08, 0.25)
        time.sleep(delay)


def click_text_button_by_js(page, texts) -> str | None:
    """用页面 DOM 文本兜底点击按钮，解决嵌套 span/繁体文案导致 Drission 文本选择器漏找。"""
    texts_js = json.dumps([str(text).lower() for text in texts], ensure_ascii=False)
    js_code = """
    var targets = __TEXTS__;
    var selectors = [
        'button',
        'a[role="button"]',
        'div[role="button"]',
        '[data-testid]',
        'input[type="button"]',
        'input[type="submit"]'
    ];
    var nodes = Array.from(document.querySelectorAll(selectors.join(',')));
    function visible(el) {
        var rect = el.getBoundingClientRect();
        var style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !el.disabled &&
            el.getAttribute('aria-disabled') !== 'true';
    }
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!visible(el)) continue;
        var label = [
            el.innerText || '',
            el.textContent || '',
            el.value || '',
            el.getAttribute('aria-label') || '',
            el.getAttribute('title') || ''
        ].join(' ').toLowerCase().replace(/\\s+/g, ' ').trim();
        for (var j = 0; j < targets.length; j++) {
            if (label.includes(targets[j])) {
                el.scrollIntoView({block: 'center', inline: 'center'});
                el.click();
                return targets[j];
            }
        }
    }
    return '';
    """.replace("__TEXTS__", texts_js)
    try:
        clicked_text = page.run_js(js_code)
        return clicked_text or None
    except Exception:
        return None


def click_any_text_by_js(page, texts, selectors=None) -> str | None:
    """点击包含指定文本的可见元素，适合 Canva 嵌套 div/p/span 的登录入口。"""
    selectors = selectors or [
        'button', 'a', 'div[role="button"]', '[data-testid]',
        '[aria-label]', 'div', 'p', 'span',
    ]
    texts_js = json.dumps([str(text).lower() for text in texts], ensure_ascii=False)
    selectors_js = json.dumps(selectors, ensure_ascii=False)
    js_code = """
    var targets = __TEXTS__;
    var selectors = __SELECTORS__;
    var nodes = Array.from(document.querySelectorAll(selectors.join(',')));
    function visible(el) {
        var rect = el.getBoundingClientRect();
        var style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !el.disabled &&
            el.getAttribute('aria-disabled') !== 'true';
    }
    function labelOf(el) {
        return [
            el.innerText || '',
            el.textContent || '',
            el.value || '',
            el.getAttribute('aria-label') || '',
            el.getAttribute('title') || ''
        ].join(' ').toLowerCase().replace(/\\s+/g, ' ').trim();
    }
    var matches = [];
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!visible(el)) continue;
        var label = labelOf(el);
        for (var j = 0; j < targets.length; j++) {
            if (!label.includes(targets[j])) continue;
            matches.push({ el: el, label: label, text: targets[j] });
        }
    }
    matches.sort(function(a, b) { return a.label.length - b.label.length; });
    for (var k = 0; k < matches.length; k++) {
        var match = matches[k];
        var target = match.el.closest('button,a,[role="button"],input[type="button"],input[type="submit"]') || match.el;
        if ((target.tagName === 'P' || target.tagName === 'SPAN') && target.parentElement) {
            target = target.parentElement;
        }
        target.scrollIntoView({block: 'center', inline: 'center'});
        target.click();
        return match.text;
    }
    return '';
    """.replace("__TEXTS__", texts_js).replace("__SELECTORS__", selectors_js)
    try:
        clicked_text = page.run_js(js_code)
        return clicked_text or None
    except Exception:
        return None


def find_first_element(page, selectors, timeout=2):
    for sel in selectors:
        try:
            el = page.ele(sel, timeout=timeout)
            if el:
                return el
        except Exception:
            continue
    return None


def click_first_element(page, selectors, timeout=1) -> bool:
    el = find_first_element(page, selectors, timeout=timeout)
    if not el:
        return False
    try:
        el.click(by_js=False)
    except Exception:
        try:
            el.click()
        except Exception:
            return False
    return True


def minimize_browser_window(page):
    if not MINIMIZE_BROWSER:
        return
    try:
        page.set.window.mini()
        log("  🔽 浏览器窗口已自动最小化")
    except Exception as e:
        log(f"  ⚠️ 浏览器窗口最小化失败: {e}")


def has_turnstile_challenge(page) -> bool:
    try:
        title = page.title.lower() if page.title else ""
        if any(kw in title for kw in ["just a moment", "attention required", "请稍候", "检查您的浏览器"]):
            return True
    except Exception:
        pass

    try:
        cf_el = page.ele('tag:iframe@@src:challenges.cloudflare.com', timeout=0.5)
        if cf_el:
            return True
    except Exception:
        pass

    try:
        html_text = page.html[:5000].lower() if page.html else ""
        return any(kw in html_text for kw in [
            "challenges.cloudflare.com",
            "verify you are human",
            "请验证您是真人",
            "we'll have you designing again soon",
            "ray id",
        ])
    except Exception:
        return False


def is_canva_verification_page(page) -> bool:
    try:
        if "canva.com" not in (page.url or ""):
            return False
        return bool(find_first_element(page, [
            'tag:input@@name=code',
            'tag:input@@name=otp',
            'tag:input@@type=tel',
            'tag:input@@autocomplete=one-time-code',
            'tag:input@@maxlength=6',
            'tag:input@@type=number',
        ], timeout=0.5))
    except Exception:
        return False


def is_canva_templates_page(page) -> bool:
    try:
        url = (page.url or "").lower()
        return "canva.com/templates" in url or "canva.com/templates/" in url
    except Exception:
        return False


def wait_for_microsoft_page(browser, fallback_page, timeout=20):
    start = time.time()
    microsoft_hosts = ("login.live.com", "account.live.com", "login.microsoftonline.com", "microsoft.com")
    while time.time() - start < timeout:
        try:
            for tab_id in browser.tab_ids:
                tab = browser.get_tab(tab_id)
                url = (tab.url or "").lower()
                if any(host in url for host in microsoft_hosts):
                    return tab
                if find_first_element(tab, ['tag:input@@id=i0116', 'tag:input@@name=loginfmt'], timeout=0.2):
                    return tab
        except Exception:
            pass
        try:
            url = (fallback_page.url or "").lower()
            if any(host in url for host in microsoft_hosts):
                return fallback_page
        except Exception:
            pass
        time.sleep(0.5)
    return None


def close_microsoft_login_popup(browser, auth_page=None, main_page=None):
    microsoft_hosts = ("login.live.com", "account.live.com", "login.microsoftonline.com", "microsoft.com")
    closed = False

    candidates = []
    if auth_page and auth_page is not main_page:
        candidates.append(auth_page)
    try:
        for tab_id in browser.tab_ids:
            tab = browser.get_tab(tab_id)
            if tab is main_page:
                continue
            try:
                url = (tab.url or "").lower()
            except Exception:
                url = ""
            if any(host in url for host in microsoft_hosts) and tab not in candidates:
                candidates.append(tab)
    except Exception:
        pass

    for tab in candidates:
        try:
            browser.close_tabs(tab)
            closed = True
            continue
        except Exception:
            pass
        try:
            tab.run_js("window.close();")
            closed = True
        except Exception:
            pass

    if closed:
        log("  ✅ 已关闭 Microsoft 登录弹窗")
    else:
        log("  ⚠️ 未能确认关闭 Microsoft 登录弹窗，继续重新打开邀请链接")
    human_delay(0.8, 1.5)


def wait_for_canva_verification_page(browser, fallback_page, timeout=45):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if is_canva_verification_page(fallback_page):
                return fallback_page
        except Exception:
            pass

        try:
            for tab_id in browser.tab_ids:
                tab = browser.get_tab(tab_id)
                if is_canva_verification_page(tab):
                    return tab
        except Exception:
            pass
        time.sleep(1)
    return None


def wait_for_canva_templates_page(browser, fallback_page, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if is_canva_templates_page(fallback_page):
                return fallback_page
        except Exception:
            pass

        try:
            for tab_id in browser.tab_ids:
                tab = browser.get_tab(tab_id)
                if is_canva_templates_page(tab):
                    return tab
        except Exception:
            pass
        time.sleep(0.5)
    return None


def has_canva_transient_login_error(page) -> bool:
    try:
        visible_text = ""
        try:
            visible_text = page.run_js("return document.body ? document.body.innerText : '';") or ""
        except Exception:
            pass
        text = " ".join([
            page.html[:20000] if page.html else "",
            visible_text,
            page.title or "",
            page.url or "",
        ]).lower()
        return any(marker in text for marker in [
            "there’s an issue on our end",
            "there's an issue on our end",
            "contact support",
            "describe the issue",
            "error code",
            "發生問題",
            "发生问题",
            "發生錯誤",
            "发生错误",
            "請你聯絡支援團隊",
            "请你联系支持团队",
            "請聯絡支援",
            "请联系支持",
            "說明問題",
            "说明问题",
            "錯誤代碼",
            "错误代码",
            "問題が発生しました",
            "問題が起きました",
            "サポートにお問い合わせ",
            "エラーコード",
        ])
    except Exception:
        return False


def is_canva_invite_invalid_page(page) -> bool:
    try:
        if "canva.com" not in (page.url or "").lower():
            return False

        visible_text = ""
        try:
            visible_text = page.run_js("return document.body ? document.body.innerText : '';") or ""
        except Exception:
            pass

        text = " ".join([
            page.html[:20000] if page.html else "",
            visible_text,
            page.title or "",
            page.url or "",
        ]).lower()

        return (
            "looks like you don't have access" in text
            or "looks like you don’t have access" in text
            or "team invite doesn't exist anymore" in text
            or "team invite doesn’t exist anymore" in text
            or "has already been used" in text and "team invite" in text
            or "你好像没有访问权限" in text
            or "你好像沒有訪問權限" in text
            or "你好像沒有存取權限" in text
            or "你似乎沒有存取權限" in text
            or "該團隊邀請已不存在" in text
            or "該團隊邀請已不存在或已有" in text
            or "已有人使用" in text and "團隊邀請" in text
            or "团队邀请不存在" in text
            or "團隊邀請不存在" in text
            or "邀请不存在" in text and "已被使用" in text
            or "邀請不存在" in text and "已被使用" in text
            or "アクセス権がありません" in text
            or "アクセス権限がありません" in text
            or "アクセスできません" in text
            or "チームへの招待はもう存在しない" in text
            or "チームへの招待がもう存在しない" in text
            or "すでに使用されています" in text and "招待" in text
            or "別の招待をチームにリクエスト" in text
            or "もう一度お試しください" in text and "招待" in text
        )
    except Exception:
        return False


def mark_invite_invalid(reason: str):
    log(f"  ❌ Canva 邀请链接失效：{reason}")
    if not INVITE_INVALID_FILE:
        return
    try:
        os.makedirs(os.path.dirname(INVITE_INVALID_FILE), exist_ok=True)
        payload = {
            "reason": reason,
            "url": CANVA_INVITE_URL,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(INVITE_INVALID_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log("  ✅ 已记录邀请链接失效标记")
    except Exception as e:
        log(f"  ⚠️ 写入邀请链接失效标记失败: {e}")


def mark_verify_success(reason: str = "验证码提交成功"):
    if not VERIFY_SUCCESS_FILE:
        return
    try:
        os.makedirs(os.path.dirname(VERIFY_SUCCESS_FILE), exist_ok=True)
        with open(VERIFY_SUCCESS_FILE, "w", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        log(f"  ✅ 已记录验证码/登录成功标记：{reason}")
    except Exception as e:
        log(f"  ⚠️ 写入验证码/登录成功标记失败: {e}")


def is_canva_login_options_page(page) -> bool:
    try:
        if "canva.com" not in (page.url or "").lower():
            return False
        visible_text = ""
        try:
            visible_text = page.run_js("return document.body ? document.body.innerText : '';") or ""
        except Exception:
            pass
        text = " ".join([
            page.html[:20000] if page.html else "",
            visible_text,
            page.title or "",
        ]).lower()
        return any(marker in text for marker in [
            "以 microsoft 繼續",
            "以 microsoft 继续",
            "continue with microsoft",
            "microsoft帳戶",
            "microsoft 帳戶",
            "microsoft账户",
            "microsoft 账户",
            "以 google 繼續",
            "以 google 继续",
            "continue with google",
        ])
    except Exception:
        return False


def is_canva_identity_confirmation_page(page) -> bool:
    try:
        if "canva.com" not in (page.url or "").lower():
            return False
        visible_text = ""
        try:
            visible_text = page.run_js("return document.body ? document.body.innerText : '';") or ""
        except Exception:
            pass
        text = " ".join([
            page.html[:20000] if page.html else "",
            visible_text,
            page.title or "",
        ]).lower()
        return any(marker in text for marker in [
            "完成身份验证",
            "完成身分驗證",
            "我們需要確認你的身分",
            "我們需要確認你的身份",
            "我们需要确认你的身份",
            "本次登录需验证邮箱地址",
            "本次登入需驗證郵箱地址",
            "本次登入需驗證電子郵件地址",
            "we need to confirm your identity",
            "第一次透過 microsoft 登入",
            "第一次通过 microsoft 登录",
        ])
    except Exception:
        return False


def click_canva_identity_continue(page) -> bool:
    js_code = """
    var identityMarkers = [
        '完成身份验证',
        '完成身分驗證',
        '我們需要確認你的身分',
        '我們需要確認你的身份',
        '我们需要确认你的身份',
        'we need to confirm your identity'
    ];
    var continueMarkers = ['继续', '繼續', 'Continue', '下一步', 'Next'];
    var bodyText = document.body ? (document.body.innerText || '') : '';
    if (!identityMarkers.some(function(t) { return bodyText.includes(t); })) return '';
    var nodes = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'));
    function visible(el) {
        var rect = el.getBoundingClientRect();
        var style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !el.disabled &&
            el.getAttribute('aria-disabled') !== 'true';
    }
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!visible(el)) continue;
        var label = [
            el.innerText || '',
            el.textContent || '',
            el.value || '',
            el.getAttribute('aria-label') || '',
            el.getAttribute('title') || ''
        ].join(' ').trim();
        for (var j = 0; j < continueMarkers.length; j++) {
            if (label.includes(continueMarkers[j])) {
                el.scrollIntoView({block: 'center', inline: 'center'});
                el.click();
                return continueMarkers[j];
            }
        }
    }
    return '';
    """
    try:
        clicked = page.run_js(js_code)
        return bool(clicked)
    except Exception:
        return False


def click_canva_oauth_allow(page) -> bool:
    """Click Canva OAuth authorization buttons such as Allow/允许/允許."""
    def click_rect_like_human(rect_info: dict, label: str) -> bool:
        try:
            x = int(rect_info["x"] + rect_info["w"] * random.uniform(0.35, 0.65))
            y = int(rect_info["y"] + rect_info["h"] * random.uniform(0.35, 0.65))
            page.actions.move_to((x + random.randint(-3, 3), y + random.randint(-2, 2)))
            human_delay(0.2, 0.6)
            page.actions.click()
            log(f"  ✅ 已模拟真人点击授权按钮 [{label}] @ ({x},{y})")
            human_delay(2.0, 3.0)
            return True
        except Exception as e:
            log(f"  ⚠️ 模拟真人点击授权按钮失败: {e}")
            return False

    js_code = """
    var allowMarkers = [
        'Allow', '允许', '允許', 'Authorize', 'Grant access', 'Continue',
        '許可', '承認', '同意', '同意する', 'アクセスを許可', '共有を許可', '連携を許可',
        '허용', '승인', 'Autorizar', 'Permitir',
        'Autoriser', 'Zulassen', 'Autorizza', 'Разрешить'
    ];
    var denyMarkers = ['Cancel', '取消', '拒否', 'キャンセル', '취소'];
    var bodyText = document.body ? (document.body.innerText || '') : '';
    var looksLikeOauth = /would like access|allow canva to share|oauth|authorize|授權|授权|允許|允许|アクセスを希望|共有を許可|許可してください|連携/i.test(bodyText + ' ' + location.href);
    if (!looksLikeOauth) return '';
    var nodes = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'));
    function visible(el) {
        var rect = el.getBoundingClientRect();
        var style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
            style.visibility !== 'hidden' &&
            style.display !== 'none' &&
            !el.disabled &&
            el.getAttribute('aria-disabled') !== 'true';
    }
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!visible(el)) continue;
        var label = [
            el.innerText || '',
            el.textContent || '',
            el.value || '',
            el.getAttribute('aria-label') || '',
            el.getAttribute('title') || ''
        ].join(' ').trim();
        if (denyMarkers.some(function(t) { return label.includes(t); })) continue;
        for (var j = 0; j < allowMarkers.length; j++) {
            if (label.includes(allowMarkers[j])) {
                el.scrollIntoView({block: 'center', inline: 'center'});
                var rect = el.getBoundingClientRect();
                return { label: allowMarkers[j], x: rect.left, y: rect.top, w: rect.width, h: rect.height };
            }
        }
    }
    return null;
    """
    try:
        target = page.run_js(js_code)
        if target and click_rect_like_human(target, target.get("label", "Allow")):
            return True
    except Exception:
        pass

    try:
        attr_target = page.run_js("""
        var bodyText = document.body ? (document.body.innerText || '') : '';
        var looksLikeOauth = /would like access|allow canva to share|oauth|authorize|授權|授权|允許|允许|アクセスを希望|共有を許可|許可してください|連携/i.test(bodyText + ' ' + location.href);
        if (!looksLikeOauth) return null;
        var buttons = Array.from(document.querySelectorAll('button[type="button"]'));
        function visible(el) {
            var rect = el.getBoundingClientRect();
            var style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 &&
                style.visibility !== 'hidden' &&
                style.display !== 'none' &&
                !el.disabled &&
                el.getAttribute('aria-disabled') !== 'true';
        }
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            if (!visible(btn)) continue;
            var text = (btn.innerText || btn.textContent || '').trim();
            if (/Cancel|取消|拒否|キャンセル/i.test(text)) continue;
            var span = btn.querySelector('span.khPe7Q');
            if (span && /允许|允許|Allow|Authorize|Grant access|許可|承認|同意|アクセスを許可|共有を許可|連携を許可/i.test(span.innerText || span.textContent || '')) {
                btn.scrollIntoView({block: 'center', inline: 'center'});
                var rect = btn.getBoundingClientRect();
                return {
                    label: span.innerText || span.textContent || text || 'button[type=button]',
                    x: rect.left,
                    y: rect.top,
                    w: rect.width,
                    h: rect.height
                };
            }
        }
        for (var j = 0; j < buttons.length; j++) {
            var fallback = buttons[j];
            if (!visible(fallback)) continue;
            var fallbackText = (fallback.innerText || fallback.textContent || '').trim();
            if (/Cancel|取消/i.test(fallbackText)) continue;
            fallback.scrollIntoView({block: 'center', inline: 'center'});
            var fallbackRect = fallback.getBoundingClientRect();
            return {
                label: fallbackText || 'button[type=button]',
                x: fallbackRect.left,
                y: fallbackRect.top,
                w: fallbackRect.width,
                h: fallbackRect.height
            };
        }
        return null;
        """)
        if attr_target and click_rect_like_human(attr_target, attr_target.get("label", "button[type=button]")):
            return True
    except Exception:
        pass

    return False


def submit_canva_identity_confirmation(page) -> bool:
    if not is_canva_identity_confirmation_page(page):
        return False

    if click_canva_identity_continue(page):
        log("  ✅ 已点击 Canva 身份确认页继续按钮")
        human_delay(1.0, 2.0)
        return True

    clicked = click_any_text_by_js(
        page,
        ["繼續", "继续", "Continue", "下一步", "Next", "次へ", "続行", "続ける"],
        selectors=['button', 'input[type="submit"]', 'div[role="button"]', '[data-testid]']
    )
    if clicked:
        log(f"  ✅ 已提交 Canva 身份确认页: {clicked}")
        human_delay(1.0, 2.0)
        return True

    log("  ⚠️ 检测到 Canva 身份确认页，但未找到继续按钮")
    return False


def open_microsoft_login_with_retries(browser, page, max_retries=2):
    for attempt in range(max_retries + 1):
        if attempt:
            log(f"  ↻ Microsoft 登录入口重试 {attempt}/{max_retries}")

        clicked = click_any_text_by_js(page, MICROSOFT_LOGIN_TEXTS)
        if not clicked:
            log("  ❌ 未找到 Microsoft 帐户登录入口")
            return None

        log(f"  ✅ 已点击 Microsoft 帐户登录入口: {clicked}")
        human_delay(1.0, 1.8)

        auth_page = wait_for_microsoft_page(browser, page, timeout=15)
        if auth_page:
            return auth_page

        if has_canva_transient_login_error(page):
            log("  ⚠️ Canva 返回临时报错，准备重新点击 Microsoft 帐户登录")
        elif is_canva_login_options_page(page):
            log("  ⚠️ 仍停留在 Canva 登录方式页，准备重新点击 Microsoft 帐户登录")
        else:
            log("  ⚠️ 暂未检测到 Microsoft 登录浮窗，准备重新点击")

    log("  ❌ Microsoft 登录浮窗多次未打开")
    return None


def solve_turnstile_in_open_pages(browser, pages=None, max_wait=60, api_first=True):
    pages = list(pages or [])
    try:
        for tab_id in browser.tab_ids:
            tab = browser.get_tab(tab_id)
            if tab not in pages:
                pages.append(tab)
    except Exception:
        pass

    for candidate in pages:
        try:
            if not candidate or not has_turnstile_challenge(candidate):
                continue
            log(f"  ⚠️ 检测到登录回跳页 Cloudflare 验证: {candidate.url[:80]}")
            if handle_turnstile(candidate, max_wait=max_wait, api_first=api_first):
                log("  ✅ 登录回跳页 Cloudflare 验证已处理")
                return candidate
            log("  ❌ 登录回跳页 Cloudflare 验证处理失败")
            return None
        except Exception as e:
            log(f"  ⚠️ 检查登录回跳页 Cloudflare 验证异常: {e}")
    return None


def handle_microsoft_post_password_prompt(page, skip_count: int = 0):
    """Handle Microsoft pages shown after password submit."""
    def dismiss_passkey_prompt():
        try:
            clicked = click_any_text_by_js(page, [
                "取消", "Cancel", "キャンセル",
            ], selectors=['button', 'input[type="button"]', 'input[type="submit"]', '[role="button"]'])
            if clicked:
                time.sleep(0.8)
                return True
        except Exception:
            pass
        return False

    try:
        if "fido/create" in (page.url or "").lower():
            if dismiss_passkey_prompt():
                return "dismiss-passkey-page-cancel", skip_count
    except Exception:
        pass

    try:
        allow_skip_js = "true" if skip_count < 5 else "false"
        js_code = """
        var allowSkipSecurityInfo = __ALLOW_SKIP__;
        function visible(el) {
            if (!el) return false;
            var rect = el.getBoundingClientRect();
            var style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 &&
                style.visibility !== 'hidden' &&
                style.display !== 'none' &&
                !el.disabled &&
                el.getAttribute('aria-disabled') !== 'true';
        }
        function clickEl(el) {
            el.scrollIntoView({block: 'center', inline: 'center'});
            el.click();
            return true;
        }
        function textOf(el) {
            return [
                el.innerText || '',
                el.textContent || '',
                el.value || '',
                el.getAttribute('aria-label') || '',
                el.getAttribute('title') || ''
            ].join(' ').replace(/\\s+/g, ' ').trim();
        }
        function findByText(selectors, texts) {
            var nodes = Array.from(document.querySelectorAll(selectors.join(',')));
            for (var i = 0; i < nodes.length; i++) {
                var el = nodes[i];
                if (!visible(el)) continue;
                var label = textOf(el).toLowerCase();
                for (var j = 0; j < texts.length; j++) {
                    if (label.indexOf(texts[j].toLowerCase()) >= 0) {
                        return el.closest('button,a,[role="button"],input[type="submit"]') || el;
                    }
                }
            }
            return null;
        }

        var skipTexts = [
            '暂时跳过', '暫時跳過',
            'Skip for now', 'Skip',
            '今はスキップ', 'スキップ', '今はしない', '後で',
            '後で確認する', '後で確認', '後で行う'
        ];
        var skip = document.querySelector('#iShowSkip') ||
            findByText(['a', 'button', '[role="button"]', 'span', 'div'], skipTexts);
        if (allowSkipSecurityInfo && visible(skip)) {
            clickEl(skip);
            return 'skip-security-info';
        }

        var consentTexts = [
            '接受', '允許', '允许',
            'Accept', 'Allow',
            '承諾', '同意', '同意する', '許可', '許可する', 'アクセスを許可'
        ];
        var consent = document.querySelector('[data-testid="appConsentPrimaryButton"]') ||
            findByText(['button', 'input[type="submit"]', '[role="button"]'], consentTexts);
        if (visible(consent)) {
            clickEl(consent);
            return 'accept-consent';
        }

        var bodyText = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ');
        var lower = bodyText.toLowerCase();
        var isStaySignedIn = bodyText.indexOf('保持登录状态') >= 0 ||
            bodyText.indexOf('保持登入狀態') >= 0 ||
            bodyText.indexOf('保持登入狀態?') >= 0 ||
            bodyText.indexOf('サインインの状態を維持しますか') >= 0 ||
            bodyText.indexOf('サインインしたままにしますか') >= 0 ||
            bodyText.indexOf('サインインの状態を維持しましょうか') >= 0 ||
            lower.indexOf('stay signed in') >= 0 ||
            lower.indexOf('keep me signed in') >= 0;
        if (isStaySignedIn) {
            var yesTexts = ['是', 'Yes', 'はい'];
            var primary = document.querySelector('[data-testid="primaryButton"], input[type="submit"], button[type="submit"]') ||
                findByText(['button', 'input[type="submit"]', '[role="button"]'], yesTexts);
            if (visible(primary)) {
                clickEl(primary);
                return 'stay-signed-in-yes';
            }
        }

        return '';
        """.replace("__ALLOW_SKIP__", allow_skip_js)
        result = page.run_js(js_code)
        if result == "skip-security-info":
            time.sleep(1.0)
            try:
                if "fido/create" in (page.url or "").lower():
                    if dismiss_passkey_prompt():
                        return "skip-security-info-passkey-page-cancel", skip_count + 1
            except Exception:
                pass
            if skip_count >= 5:
                return "", skip_count
            return result, skip_count + 1
        return result or "", skip_count
    except Exception:
        return "", skip_count


def complete_microsoft_login(browser, page, email_addr: str, password: str, auth_page=None):
    if not email_addr or not password:
        log("  ❌ Microsoft 登录模式需要自备邮箱和密码")
        return None

    auth_page = auth_page or wait_for_microsoft_page(browser, page, timeout=30)
    if not auth_page:
        log("  ❌ 未检测到 Microsoft 登录弹窗")
        return None

    log(f"  → Microsoft 登录页: {auth_page.url[:80]}")

    email_selectors = [
        'tag:input@@id=i0116',
        'tag:input@@name=loginfmt',
        'tag:input@@type=email',
        'tag:input@@autocomplete=username',
    ]
    email_input = wait_for_stable_input(auth_page, email_selectors, "Microsoft 邮箱", timeout=10)
    if not email_input:
        log("  ❌ 找不到 Microsoft 邮箱输入框")
        return None
    email_input = type_text_verified(
        auth_page,
        email_selectors,
        email_addr,
        "Microsoft 邮箱",
        max_attempts=3,
        fast_type=True,
        js_fallback=False,
    )
    if not email_input or get_input_value(email_input) != email_addr:
        log("  ❌ Microsoft 邮箱输入后校验仍为空或不完整，停止提交")
        return None
    log(f"  ✅ Microsoft 邮箱已输入: {email_addr}")

    if not click_first_element(auth_page, [
        'tag:input@@id=idSIButton9',
        'tag:input@@type=submit',
        'tag:button@@type=submit',
    ], timeout=3):
        email_input.input('\n')
        log("  → Microsoft 邮箱页按回车提交")
    human_delay(2.2, 3.5)

    password_selectors = [
        'tag:input@@id=passwordEntry',
        'tag:input@@id=i0118',
        'tag:input@@name=passwd',
        'tag:input@@type=password',
        'css:input[type="password"]',
    ]
    password_input = None
    start = time.time()
    while time.time() - start < 45 and not password_input:
        auth_page = wait_for_microsoft_page(browser, auth_page, timeout=3) or auth_page
        password_input = wait_for_stable_input(auth_page, password_selectors, "Microsoft 密码", timeout=4)
        if not password_input:
            time.sleep(1)
    if not password_input:
        log("  ❌ 找不到 Microsoft 密码输入框")
        return None

    password_input = type_text_verified(
        auth_page,
        password_selectors,
        password,
        "Microsoft 密码",
        max_attempts=3,
        fast_type=True,
        js_fallback=False,
    )
    if not password_input or get_input_value(password_input) != password:
        log("  ❌ Microsoft 密码输入后校验仍为空或不完整，停止提交")
        return None
    log("  ✅ Microsoft 密码已输入")

    password_submit_selectors = [
        'tag:button@@data-testid=primaryButton',
        'tag:button@@type=submit',
        'tag:input@@id=idSIButton9',
        'tag:input@@type=submit',
    ]
    password_submitted_at = None
    if click_first_element(auth_page, password_submit_selectors, timeout=3):
        password_submitted_at = time.time()
        log("  → Microsoft 密码页已点击提交")
    else:
        password_input.input('\n')
        password_submitted_at = time.time()
        log("  → Microsoft 密码页按回车提交")

    security_skip_count = 0
    post_password_deadline = password_submitted_at + 30
    password_submit_retries = 0
    next_password_submit_retry_at = password_submitted_at + 5
    post_confirm_clicks = 0
    while time.time() < post_password_deadline:
        human_delay(0.8, 1.3)
        challenged_page = solve_turnstile_in_open_pages(browser, [auth_page, page], max_wait=3, api_first=True)
        if challenged_page:
            auth_page = challenged_page
            human_delay(1.0, 2.0)

        try:
            auth_page = wait_for_microsoft_page(browser, auth_page, timeout=1) or auth_page
            retry_password_input = find_first_element(auth_page, password_selectors, timeout=0.3)
            if (
                password_submit_retries < 2
                and time.time() >= next_password_submit_retry_at
                and retry_password_input
            ):
                if click_first_element(auth_page, password_submit_selectors, timeout=1):
                    submit_retry_method = "点击"
                else:
                    retry_password_input.input('\n')
                    submit_retry_method = "回车"
                password_submit_retries += 1
                next_password_submit_retry_at = time.time() + 5
                log(f"  → Microsoft 密码页提交重试 {password_submit_retries}/2 ({submit_retry_method})")
                human_delay(1.0, 1.5)
        except Exception:
            pass

        try:
            prompt_clicked, security_skip_count = handle_microsoft_post_password_prompt(auth_page, security_skip_count)
            if prompt_clicked:
                log(f"  → Microsoft 登录后提示已处理: {prompt_clicked}")
                human_delay(1.0, 1.8)
            for tab_id in browser.tab_ids:
                tab = browser.get_tab(tab_id)
                prompt_clicked, security_skip_count = handle_microsoft_post_password_prompt(tab, security_skip_count)
                if prompt_clicked:
                    auth_page = tab
                    log(f"  → Microsoft 登录后提示已处理: {prompt_clicked}")
                    human_delay(1.0, 1.8)
                    break
        except Exception:
            pass

        identity_submitted = False
        try:
            if submit_canva_identity_confirmation(page):
                identity_submitted = True
            for tab_id in browser.tab_ids:
                tab = browser.get_tab(tab_id)
                if submit_canva_identity_confirmation(tab):
                    page = tab
                    identity_submitted = True
                    break
        except Exception:
            pass
        if identity_submitted:
            human_delay(1.0, 2.0)

        templates_page = wait_for_canva_templates_page(browser, page, timeout=1)
        if templates_page:
            log("  ✅ Microsoft 登录完成，已进入 Canva 模板页")
            return templates_page

        next_page = wait_for_canva_verification_page(browser, page, timeout=1)
        if next_page:
            log("  ✅ Microsoft 登录完成，已回到 Canva 验证码页面")
            return next_page

        try:
            if post_confirm_clicks < 2:
                auth_page = wait_for_microsoft_page(browser, auth_page, timeout=1) or auth_page
                clicked = click_any_text_by_js(auth_page, [
                    "是", "Yes", "はい",
                    "继续", "繼續", "Continue", "続行",
                    "下一步", "Next", "次へ", "次へ進む",
                    "接受", "允許", "允许", "Accept", "Allow",
                    "承諾", "同意", "同意する", "許可", "許可する", "アクセスを許可",
                    "後で確認する", "後で確認",
                ], selectors=['button', 'input[type="submit"]', 'div[role="button"]', '[data-testid]'])
                if clicked:
                    post_confirm_clicks += 1
                    log(f"  → Microsoft 后续确认已点击: {clicked} ({post_confirm_clicks}/2)")
        except Exception:
            pass

    log("  ❌ Microsoft 密码提交后 30 秒内未回到 Canva 验证码页面或模板页")
    return None

# ════════════════════════ Cloudflare Turnstile 处理 ════════════════════════

def _solve_turnstile_via_api(page_url: str, sitekey: str) -> str | None:
    """通过 YesCaptcha API 解决 Turnstile 验证（备用方案）"""
    if not YESCAPTCHA_KEY:
        log("  未配置 YesCaptcha Key，无法通过 API 解决 Turnstile")
        return None
    import httpx as _httpx
    log(f"  调用 YesCaptcha API 解决 Turnstile (sitekey: {sitekey[:20]}...)")
    try:
        client = _httpx.Client(timeout=60.0)
        # 1. 创建任务
        resp = client.post("https://api.yescaptcha.com/createTask", json={
            "clientKey": YESCAPTCHA_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            }
        })
        result = resp.json()
        if result.get("errorId", 1) != 0:
            log(f"  创建任务失败: {result.get('errorDescription', '未知错误')}")
            client.close()
            return None
        task_id = result["taskId"]
        log(f"  任务已创建: {task_id}")

        # 2. 轮询结果（最多 120s）
        for i in range(40):
            time.sleep(3)
            resp = client.post("https://api.yescaptcha.com/getTaskResult", json={
                "clientKey": YESCAPTCHA_KEY,
                "taskId": task_id,
            })
            result = resp.json()
            status = result.get("status", "")
            if status == "ready":
                token = result.get("solution", {}).get("token", "")
                log(f"  Turnstile token 已获取 ({len(token)} 字符)")
                client.close()
                return token
            elif result.get("errorId", 0) != 0:
                log(f"  查询失败: {result.get('errorDescription', '未知')}")
                client.close()
                return None
            if i % 5 == 4:
                log(f"  等待 Turnstile 解决中... ({(i+1)*3}s)")
        log("  Turnstile API 超时")
        client.close()
        return None
    except Exception as e:
        log(f"  Turnstile API 异常: {e}")
        return None


def solve_turnstile_by_api_on_page(page) -> bool:
    sitekey = None
    try:
        html = page.html
        m = re.search(r'data-sitekey=["\']([^"\']+)', html)
        if m:
            sitekey = m.group(1)
        if not sitekey:
            m = re.search(r'sitekey["\']\s*:\s*["\']([0-9x]+[A-Za-z0-9_-]+)', html)
            if m:
                sitekey = m.group(1)

        # 尝试全局搜索 0x/1x/2x/3x 开头的可能是 sitekey 的长字符串
        if not sitekey:
            try:
                keys = re.findall(r'[0-3]x[A-Za-z0-9_-]{15,}', html)
                if keys:
                    sitekey = keys[0]
            except:
                pass

        if not sitekey:
            try:
                with open(os.path.join(SCREENSHOT_DIR, "turnstile_failed.html"), "w", encoding="utf-8") as f:
                    f.write(html)
                log("  📄 已导出未找到 sitekey 的网页源码至 turnstile_failed.html")
            except:
                pass
    except:
        pass

    if not sitekey:
        log("  未找到 sitekey，无法调用 API")
        return False

    token = _solve_turnstile_via_api(page.url, sitekey)
    if not token:
        return False

    try:
        js_code = (
            'var resp = document.querySelector(\'[name="cf-turnstile-response"]\');'
            f'if (resp) {{ resp.value = "{token}"; }}'
            'var cb = document.querySelector("[data-callback]");'
            'if (cb) {'
            '  var fnName = cb.getAttribute("data-callback");'
            f'  if (window[fnName]) window[fnName]("{token}");'
            '}'
        )
        page.run_js(js_code)
        log("  Token 已注入，等待跳转...")
        time.sleep(5)
        return not has_turnstile_challenge(page)
    except Exception as e:
        log(f"  Token 注入失败: {e}")
        return False


def handle_turnstile(page, max_wait=30, api_first=False) -> bool:
    """
    检测并处理 Cloudflare Turnstile 挑战页面。
    默认先等待 YesCaptcha 扩展自动解决；api_first=True 时检测到挑战就立即调用 API。
    返回 True 表示已解决或无需解决。
    """
    if not has_turnstile_challenge(page):
        return True  # 没有 Turnstile 挑战

    log("  检测到 Cloudflare Turnstile 挑战!")

    for refresh_attempt in range(1, 3):
        try:
            log(f"  ↻ 尝试刷新页面跳过 Turnstile ({refresh_attempt}/2)")
            page.refresh()
            time.sleep(3)
            if not has_turnstile_challenge(page):
                log("  ✅ 刷新后 Turnstile 已跳过")
                time.sleep(1)
                return True
        except Exception as e:
            log(f"  ⚠️ 刷新跳过 Turnstile 失败: {e}")

    if api_first:
        log("  立即调用 YesCaptcha API 解决 Turnstile...")
        if solve_turnstile_by_api_on_page(page):
            log("  Turnstile 已通过 YesCaptcha API 解决!")
            return True
        log("  YesCaptcha API 未能立即解决，切换到自动等待兜底...")

    # Phase 1: 等待 YesCaptcha 扩展自动解决
    log(f"  等待自动解决 (最多 {max_wait}s)...")
    for i in range(max_wait):
        time.sleep(1)
        try:
            if not has_turnstile_challenge(page):
                log(f"  Turnstile 已自动解决! (耗时 {i+1}s)")
                time.sleep(2)
                return True
        except:
            pass
        # 尝试点击 Turnstile checkbox
        if i == 5 or i == 15:
            try:
                cf_iframe = page.ele('tag:iframe@@src:challenges.cloudflare.com', timeout=1)
                if cf_iframe:
                    cf_iframe.click()
                    log("  尝试点击 Turnstile checkbox")
            except:
                pass

    log("  自动解决超时，尝试 API 解决...")
    if solve_turnstile_by_api_on_page(page):
        log("  Turnstile 已通过 YesCaptcha API 解决!")
        return True

    # 最后再等一轮
    for i in range(10):
        time.sleep(1)
        try:
            if not has_turnstile_challenge(page):
                log("  Turnstile 最终已解决!")
                return True
        except:
            pass

    log("  Turnstile 未能解决")

    return False


# ════════════════════════ 主流程 ════════════════════════

def get_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_playwright_proxy_config(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    parsed = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
    if not parsed.hostname or not parsed.port:
        return None
    config = {"server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        config["username"] = unquote(parsed.username)
    if parsed.password:
        config["password"] = unquote(parsed.password)
    return config


class AuthProxyForwarder:
    def __init__(self, proxy_url: str):
        import base64
        import threading

        parsed = urlsplit(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
        if not parsed.hostname or not parsed.port:
            raise ValueError("代理地址缺少 host 或 port")
        if (parsed.scheme or "http").lower() not in ("http", "https"):
            raise ValueError(f"new-headless 暂不支持 {parsed.scheme} 认证代理")

        self.scheme = (parsed.scheme or "http").lower()
        self.host = parsed.hostname
        self.port = int(parsed.port)
        self.username = unquote(parsed.username or "")
        self.password = unquote(parsed.password or "")
        token = f"{self.username}:{self.password}".encode("utf-8")
        self.auth_header = f"Proxy-Authorization: Basic {base64.b64encode(token).decode('ascii')}\r\n"
        self._threading = threading
        self._stop_event = threading.Event()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(100)
        self.port_local = int(self._server.getsockname()[1])
        self._thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def proxy_server(self) -> str:
        return f"http://127.0.0.1:{self.port_local}"

    def start(self):
        self._thread.start()

    def close(self):
        self._stop_event.set()
        try:
            self._server.close()
        except Exception:
            pass

    def _connect_upstream(self):
        import ssl

        sock = socket.create_connection((self.host, self.port), timeout=20)
        if self.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
        return sock

    def _serve(self):
        while not self._stop_event.is_set():
            try:
                client, _ = self._server.accept()
            except OSError:
                break
            self._threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()

    def _recv_headers(self, sock):
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 1024 * 1024:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
        return data

    def _send_upstream_request(self, upstream, header_data: bytes):
        header_end = header_data.find(b"\r\n\r\n")
        if header_end < 0:
            upstream.sendall(header_data)
            return
        headers = header_data[:header_end].decode("latin1", errors="replace")
        body = header_data[header_end + 4:]
        if "proxy-authorization:" not in headers.lower():
            first, rest = headers.split("\r\n", 1)
            headers = f"{first}\r\n{self.auth_header.rstrip()}\r\n{rest}"
        upstream.sendall(headers.encode("latin1", errors="replace") + b"\r\n\r\n" + body)

    def _relay(self, left, right):
        import select

        sockets = [left, right]
        while not self._stop_event.is_set():
            try:
                readable, _, _ = select.select(sockets, [], [], 1)
            except Exception:
                break
            if not readable:
                continue
            for src in readable:
                dst = right if src is left else left
                try:
                    data = src.recv(65536)
                    if not data:
                        return
                    dst.sendall(data)
                except Exception:
                    return

    def _handle_client(self, client):
        upstream = None
        try:
            header_data = self._recv_headers(client)
            if not header_data:
                return
            first_line = header_data.split(b"\r\n", 1)[0].decode("latin1", errors="replace")
            upstream = self._connect_upstream()
            if first_line.upper().startswith("CONNECT "):
                target = first_line.split(" ", 2)[1]
                request = (
                    f"CONNECT {target} HTTP/1.1\r\n"
                    f"Host: {target}\r\n"
                    f"{self.auth_header}"
                    "Proxy-Connection: Keep-Alive\r\n\r\n"
                )
                upstream.sendall(request.encode("latin1"))
                response = self._recv_headers(upstream)
                client.sendall(response)
                if b" 200 " in response.split(b"\r\n", 1)[0]:
                    self._relay(client, upstream)
            else:
                self._send_upstream_request(upstream, header_data)
                self._relay(client, upstream)
        except Exception:
            pass
        finally:
            for sock in (client, upstream):
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass


def launch_playwright_chromium_headless(user_data_dir: str, ua: str):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("new-headless 需要 Playwright：请在运行环境安装 playwright 并执行 playwright install chromium") from exc

    import subprocess
    import urllib.request

    debug_port = get_free_local_port()
    playwright = sync_playwright().start()
    try:
        chromium_path = playwright.chromium.executable_path
    finally:
        playwright.stop()
    if not os.path.isfile(chromium_path):
        raise RuntimeError(
            f"Playwright Chromium not found: {chromium_path}. "
            "Rebuild the Docker image after running `python -m playwright install --with-deps chromium`."
        )

    args = [
        chromium_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "--headless=new",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--window-size=1280,900",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-default-apps",
        f"--user-agent={ua}",
        "about:blank",
    ]
    auth_proxy_forwarder = None
    proxy = build_proxy_string()
    if proxy:
        parsed = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
        if parsed.hostname and parsed.port:
            if parsed.username or parsed.password:
                try:
                    auth_proxy_forwarder = AuthProxyForwarder(proxy)
                    auth_proxy_forwarder.start()
                    args.insert(-1, f"--proxy-server={auth_proxy_forwarder.proxy_server}")
                    log("  🌐 new-headless 已启用带账号密码的代理认证")
                except Exception as e:
                    args.insert(-1, f"--proxy-server={parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}")
                    log(f"  ⚠️ 认证代理转发器启动失败，已仅设置代理服务器地址: {e}")
            else:
                args.insert(-1, f"--proxy-server={parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}")

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    class _PlaywrightChromiumProcess:
        def __init__(self, proc, proxy_forwarder=None):
            self.proc = proc
            self.proxy_forwarder = proxy_forwarder

        def close(self):
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            if self.proxy_forwarder:
                self.proxy_forwarder.close()

    version_url = f"http://127.0.0.1:{debug_port}/json/version"
    last_error = None
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError(f"Playwright Chromium 启动后立即退出，退出码 {process.returncode}")
        try:
            with urllib.request.urlopen(version_url, timeout=1) as resp:
                if resp.status == 200:
                    log(f"  ✅ Playwright Chromium headless 已启动，CDP: 127.0.0.1:{debug_port}")
                    return None, _PlaywrightChromiumProcess(process, auth_proxy_forwarder), debug_port
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    _PlaywrightChromiumProcess(process, auth_proxy_forwarder).close()
    raise RuntimeError(f"Playwright Chromium CDP 端口未就绪: {last_error}")


def launch_cloakbrowser_headless(user_data_dir: str):
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError as exc:
        raise RuntimeError("cloakbrowser 模式需要安装 cloakbrowser：请执行 `pip install cloakbrowser`") from exc

    import urllib.request

    debug_port = get_free_local_port()
    args = [
        f"--remote-debugging-port={debug_port}",
        "--window-size=1280,900",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]

    proxy = build_proxy_string()
    launch_kwargs = {
        "headless": True,
        "args": args,
    }
    if proxy:
        launch_kwargs["proxy"] = proxy
        launch_kwargs["geoip"] = os.getenv("CLOAKBROWSER_GEOIP", "1") == "1"

    try:
        cloak_browser = launch_persistent_context(user_data_dir, **launch_kwargs)
    except TypeError:
        launch_kwargs.pop("geoip", None)
        cloak_browser = launch_persistent_context(user_data_dir, **launch_kwargs)

    version_url = f"http://127.0.0.1:{debug_port}/json/version"
    last_error = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(version_url, timeout=1) as resp:
                if resp.status == 200:
                    log(f"  ✅ CloakBrowser headless 已启动，CDP: 127.0.0.1:{debug_port}")
                    return cloak_browser, debug_port
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    try:
        cloak_browser.close()
    except Exception:
        pass
    raise RuntimeError(f"CloakBrowser CDP 端口未就绪: {last_error}")


def run_registration(email_addr: str, mail: "TempMail") -> bool:
    """使用 DrissionPage 完成 Canva 注册流程"""

    log("━" * 50)
    if BROWSER_MODE == "new-headless":
        log("配置浏览器 (Playwright Chromium headless + DrissionPage CDP)")
    else:
        log("配置浏览器 (DrissionPage + 本地 Chrome / 比特浏览器)")

    browser_id = None
    browser = None
    playwright_instance = None
    playwright_context = None
    cloak_browser = None
    auto_created_user_data_dir = None

    if BITBROWSER_ENABLED:
        import requests
        from urllib.parse import urlparse, unquote
        log("调用比特浏览器 API...")

        def is_transient_bitbrowser_failure(result):
            msg = str(result.get("msg", "") or result.get("message", "")).lower()
            transient_markers = [
                "502", "503", "504", "500", "bad gateway", "gateway",
                "timeout", "timed out", "econnreset", "socket hang up",
                "network error", "temporarily", "try again",
            ]
            return any(marker in msg for marker in transient_markers)

        def bitbrowser_post(path, payload, *, timeout=None, retries=None, retry_delay=3):
            url = f"{BITBROWSER_URL}{path}"
            timeout = timeout or BITBROWSER_API_TIMEOUT
            retries = retries or BITBROWSER_API_RETRIES
            last_error = None
            last_result = None

            for attempt in range(1, retries + 1):
                try:
                    resp = requests.post(
                        url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=timeout,
                        proxies={"http": None, "https": None},
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    if result.get("success") is False and is_transient_bitbrowser_failure(result):
                        last_result = result
                        last_error = result.get("msg") or result
                        log(f"  ⚠️ 比特浏览器接口临时失败 {path} (第 {attempt}/{retries} 次): {last_error}")
                    else:
                        return result
                except requests.exceptions.ReadTimeout as e:
                    last_error = e
                    log(f"  ⚠️ 比特浏览器接口超时 {path} (第 {attempt}/{retries} 次，timeout={timeout}s)")
                except requests.exceptions.RequestException as e:
                    last_error = e
                    log(f"  ⚠️ 比特浏览器接口请求失败 {path} (第 {attempt}/{retries} 次): {e}")
                except ValueError as e:
                    last_error = e
                    log(f"  ⚠️ 比特浏览器接口返回非 JSON {path} (第 {attempt}/{retries} 次): {e}")

                if attempt < retries:
                    time.sleep(retry_delay * attempt)

            if last_result is not None:
                return last_result
            raise RuntimeError(f"{path} 连续 {retries} 次调用失败: {last_error}")

        # 提取代理并配置给比特浏览器
        proxy = build_proxy_string()
        proxy_type = 'noproxy'
        host = ''
        port = ''
        proxy_user = ''
        proxy_pass = ''

        if proxy:
            try:
                p = urlparse(proxy if '://' in proxy else f'http://{proxy}')
                proxy_type = p.scheme if p.scheme else 'http'
                host = p.hostname or ''
                port = str(p.port) if p.port else ''
                proxy_user = unquote(p.username) if p.username else ''
                proxy_pass = unquote(p.password) if p.password else ''
                log(f"  🌐 比特浏览器代理: {proxy_type}://{host}:{port}")
            except Exception as e:
                log(f"  ⚠️ 代理格式解析失败: {e}")

        create_data = {
            'name': f'leo-auto-{random.randint(1000, 99999)}',
            'proxyMethod': 2,
            'proxyType': proxy_type,
            'host': host,
            'port': int(port) if port else 0,  # 官方API要求 port 为 number 类型
            'proxyUserName': proxy_user,
            'proxyPassword': proxy_pass,
            'workbench': 'disable',  # 禁用工作台页面，加速启动
            'abortMedia': True,  # 禁止视频自动播放，节省VPS带宽
            'disableTranslatePopup': True,  # 禁止翻译弹窗干扰
            'disableNotifications': True,  # 禁止通知弹窗
            'clearCacheFilesBeforeLaunch': True,  # 每次启动清理缓存防止指纹关联
            'browserFingerPrint': {
                'coreVersion': '124',
                'ostype': 'PC',
                'os': 'MacIntel' if sys.platform == 'darwin' else 'Win32',
                'isIpCreateTimeZone': True,    # 基于代理IP自动生成时区
                'isIpCreatePosition': True,     # 基于代理IP自动生成地理位置
                'isIpCreateLanguage': True,     # 基于代理IP自动生成语言
                'webRTC': '3',                  # 隐私模式(替换WebRTC)
                'portScanProtect': '1',         # 关闭端口扫描保护(允许localhost WS连接)
                'canvas': '0',                  # 随机Canvas指纹
                'webGL': '0',                   # 随机WebGL指纹
                'audioContext': '0',            # 随机音频指纹
            }
        }

        try:
            res = bitbrowser_post("/browser/update", create_data, timeout=BITBROWSER_API_TIMEOUT, retries=BITBROWSER_API_RETRIES)
            if not res.get("success"):
                log(f"❌ 创建比特浏览器窗口失败: {res}")
                return False
            browser_id = res['data']['id']
            log(f"✅ 创建比特浏览器窗口成功, ID: {browser_id}")

            # 打开窗口 (使用 queue=true 排队模式，防止高并发报错)
            open_res = None
            for open_attempt in range(3):
                try:
                    open_res = bitbrowser_post(
                        "/browser/open",
                        {'id': browser_id, 'queue': True},  # queue排队模式防并发
                        timeout=max(120, BITBROWSER_API_TIMEOUT),
                        retries=1,
                    )
                    if open_res.get("success"):
                        break
                except Exception as oe:
                    log(f"  ⚠️ 打开窗口异常: {oe}")

                log(f"  ⚠️ 打开窗口失败 (第 {open_attempt+1}/3 次): {open_res.get('msg', '') if open_res else 'timeout'}")
                # 如果提示"正在打开中/关闭中"，调用 closing/reset 重置状态
                open_msg = str(open_res.get('msg', '')) if open_res else ''
                if open_res and ('打开' in open_msg or '关闭' in open_msg):
                    try:
                        bitbrowser_post("/browser/closing/reset", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                        log("  🔄 已重置窗口状态")
                    except:
                        pass
                time.sleep(3)

            if not open_res or not open_res.get("success"):
                log(f"❌ 打开比特浏览器窗口失败: {open_res}")
                # 清理：先关闭再删除
                try:
                    bitbrowser_post("/browser/close", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                    time.sleep(2)
                except: pass
                bitbrowser_post("/browser/delete", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                return False

            http_addr = open_res['data']['http']
            log(f"✅ 比特浏览器窗口已打开, 调试地址: {http_addr}")

            # 连接 DrissionPage
            co = ChromiumOptions()
            co.set_address(http_addr)

            browser = ChromiumPage(co)
            page = browser
            page.set.window.max()
            minimize_browser_window(page)

            # 注入反自动化检测脚本（隐藏 WebDriver 痕迹）
            try:
                page.run_js("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    window.chrome = { runtime: {} };
                """)
                log("  🛡️ 已注入反检测脚本")
            except:
                pass

        except Exception as e:
            log(f"❌ 比特浏览器接口调用异常: {e}")
            if browser_id:
                try:
                    bitbrowser_post("/browser/delete", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                except: pass
            return False

    else:
        co = ChromiumOptions()
        use_playwright_headless = BROWSER_MODE == "new-headless"
        use_cloakbrowser = BROWSER_MODE == "cloakbrowser"

        # 自动检测 Chrome 路径 (Docker Linux vs Windows)
        import shutil as _shutil
        import uuid
        chrome_path = None
        for candidate in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            _shutil.which("msedge"),
            _shutil.which("google-chrome-stable"),
            _shutil.which("google-chrome"),
            _shutil.which("chromium-browser"),
            _shutil.which("chromium"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]:
            if candidate and os.path.isfile(candidate):
                chrome_path = candidate
                break
        if chrome_path and not use_playwright_headless and not use_cloakbrowser:
            co.set_browser_path(chrome_path)
            log(f"  🌐 浏览器路径: {chrome_path}")

        # 使用独立 profile 避免干扰
        user_data_dir = os.getenv("USER_DATA_DIR", "")
        if not user_data_dir:
            user_data_dir = os.path.join(DATA_DIR, f"chrome_dp_{uuid.uuid4().hex[:8]}")
            auto_created_user_data_dir = user_data_dir
        co.set_user_data_path(user_data_dir)

        # 随机调试端口，避免连接到已有 Chrome 实例
        debug_port = random.randint(19200, 19999)
        co.set_local_port(debug_port)
        co.auto_port()  # 端口冲突时自动递增

        # ── 反检测参数 ──
        co.incognito(True)
        co.set_argument('--incognito')
        co.set_argument('--inprivate')
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-infobars')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1280,900')
        # 伪装为正常桌面浏览器
        co.set_argument('--disable-features=IsolateOrigins,site-per-process')
        co.set_argument('--disable-site-isolation-trials')
        co.set_argument('--disable-web-security=false')
        # 防止 WebDriver 特征泄漏
        co.set_argument('--disable-automation')
        co.set_argument('--disable-default-apps')
        # 设置正常的 User-Agent（去除 Headless 标记）
        if sys.platform == 'darwin':
            ua = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        else:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        co.set_user_agent(ua)

        # ── 加载 YesCaptcha 扩展 (自动解决 Turnstile) ──
        ext_dir = os.path.join(APP_DIR, "yescaptcha_ext")
        if use_playwright_headless or use_cloakbrowser:
            pass
        elif os.path.isdir(ext_dir) and os.path.isfile(os.path.join(ext_dir, "manifest.json")):
            # 写入 clientKey 到扩展配置
            if YESCAPTCHA_KEY:
                config_js = os.path.join(ext_dir, "config.js")
                try:
                    with open(config_js, "w", encoding="utf-8") as f:
                        f.write(f'var yescaptchaClientKey = "{YESCAPTCHA_KEY}";\n')
                except:
                    pass
            co.add_extension(ext_dir)
            log(f"  🧩 已加载 YesCaptcha 扩展")
        else:
            log(f"  ⚠️ YesCaptcha 扩展未找到 ({ext_dir})")

        # 代理
        proxy = build_proxy_string()
        if proxy and not use_playwright_headless and not use_cloakbrowser:
            import urllib.parse
            parsed = urllib.parse.urlparse(proxy)
            if parsed.username and parsed.password:
                # 账号密码代理：创建动态 Chrome 扩展
                ext_dir = os.path.join(user_data_dir, "proxy_ext")
                os.makedirs(ext_dir, exist_ok=True)
                manifest_json = '''
                {
                    "version": "1.0.0",
                    "manifest_version": 2,
                    "name": "Proxy Auth Extension",
                    "permissions": [
                        "proxy",
                        "tabs",
                        "unlimitedStorage",
                        "storage",
                        "<all_urls>",
                        "webRequest",
                        "webRequestBlocking"
                    ],
                    "background": {
                        "scripts": ["background.js"]
                    },
                    "minimum_chrome_version":"22.0.0"
                }
                '''
                background_js = f'''
                var config = {{
                        mode: "fixed_servers",
                        rules: {{
                          singleProxy: {{
                            scheme: "http",
                            host: "{parsed.hostname}",
                            port: parseInt({parsed.port})
                          }},
                          bypassList: ["localhost"]
                        }}
                      }};
                chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
                function callbackFn(details) {{
                    return {{
                        authCredentials: {{
                            username: "{urllib.parse.unquote(parsed.username)}",
                            password: "{urllib.parse.unquote(parsed.password)}"
                        }}
                    }};
                }}
                chrome.webRequest.onAuthRequired.addListener(
                            callbackFn,
                            {{urls: ["<all_urls>"]}},
                            ['blocking']
                );
                '''
                with open(os.path.join(ext_dir, "manifest.json"), "w") as f:
                    f.write(manifest_json)
                with open(os.path.join(ext_dir, "background.js"), "w") as f:
                    f.write(background_js)
                co.add_extension(ext_dir)
                log(f"  🌐 代理 (扩展模式): {parsed.hostname}:{parsed.port}")
            else:
                co.set_proxy(proxy)
                log(f"  🌐 代理: {proxy}")

        # ── 显示模式策略 ──
        # 注意：Cloudflare Turnstile 极容易检测 headless Chrome。
        # - Docker: Xvfb 虚拟显示器提供"有头"环境
        is_docker = os.path.isfile("/.dockerenv") or os.getenv("DISPLAY") == ":99"
        if use_playwright_headless or use_cloakbrowser:
            pass
        elif is_docker:
            log("  🖥️ Docker 模式: Xvfb 虚拟显示器 (有头模式)")
        elif not SHOW_BROWSER and BROWSER_MODE != "new-headless":
            co.set_argument('--headless=new')
            log("  🔇 本地模式: 无头模式 (--headless=new)")
        else:
            log("  🖥️ 本地模式: 有头浏览器 (防止 Cloudflare 检测)")

        if BROWSER_MODE == "new-headless":
            log("  🔇 new-headless: 改用 Playwright Chromium 无头模式")
            if YESCAPTCHA_KEY:
                log("  ℹ️ 无头模式不加载浏览器扩展，Turnstile 走 YesCaptcha API 方案")
            playwright_instance, playwright_context, debug_port = launch_playwright_chromium_headless(user_data_dir, ua)
            co = ChromiumOptions()
            co.set_address(f"127.0.0.1:{debug_port}")
        elif BROWSER_MODE == "cloakbrowser":
            log("  CloakBrowser: using stealth headless mode")
            if YESCAPTCHA_KEY:
                log("  CloakBrowser mode does not load browser extensions; Turnstile uses the API fallback")
            cloak_browser, debug_port = launch_cloakbrowser_headless(user_data_dir)
            co = ChromiumOptions()
            co.set_address(f"127.0.0.1:{debug_port}")

        browser = ChromiumPage(co)
        page = browser  # page 指向当前活动标签，browser 用于标签管理
        if BROWSER_MODE not in ("new-headless", "cloakbrowser"):
            page.set.window.max()
            minimize_browser_window(page)
        log("  ✅ 本地浏览器已启动")

    # 注入 JS 覆盖 WebDriver 特征（仅比特浏览器需要，本地浏览器自身就是真实环境）
    if BITBROWSER_ENABLED:
        try:
            page.run_js('''
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            ''')
        except:
            pass


    try:

        # ══ Step 1: 打开 Canva 邀请链接 ══
        log("━" * 50)
        log("Step 1: 打开 Canva 团队邀请链接")
        page.get(CANVA_INVITE_URL)
        human_delay(1.5, 2.5)  # 只等 DOM 基本渲染，不等完整加载
        log(f"  ✅ 页面已加载: {page.url[:60]}")
        if is_canva_invite_invalid_page(page):
            mark_invite_invalid("打开邀请链接后显示无访问权限，邀请可能不存在或已被使用")
            return False

        # ── 检查 Cloudflare Turnstile ──
        if not handle_turnstile(page, max_wait=45, api_first=True):
            log("  ❌ Cloudflare Turnstile 验证未通过，终止")
            return False
        log(f"  → Turnstile 检查通过: {page.url[:60]}")
        if is_canva_invite_invalid_page(page):
            mark_invite_invalid("Turnstile 后显示无访问权限，邀请可能不存在或已被使用")
            return False

        # ══ Step 2: 接受 Cookie 声明 ══
        log("━" * 50)
        log("Step 2: 尝试接受 Cookie 声明")
        try:
            cookie_btn = None
            for text in COOKIE_ACCEPT_TEXTS:
                cookie_btn = page.ele(f'text:{text}', timeout=0.5)
                if cookie_btn:
                    break
            if cookie_btn:
                cookie_btn.click()
                log("  ✅ 已点击接受 Cookie")
                human_delay(0.5, 1.0)
            else:
                log("  → 未检测到 Cookie 弹窗，跳过")
        except:
            pass

        if REGISTRATION_MODE == "microsoft":
            microsoft_login_page = None
            auth_page = None
            for microsoft_attempt in range(2):
                if microsoft_attempt:
                    log("━" * 50)
                    log(f"Microsoft 登录卡住，关闭弹窗后重试注册 {microsoft_attempt}/1")
                    close_microsoft_login_popup(browser, auth_page=auth_page, main_page=page)
                    page.get(CANVA_INVITE_URL)
                    human_delay(1.5, 2.5)
                    if not handle_turnstile(page, max_wait=45, api_first=True):
                        log("  ❌ 重试时 Cloudflare Turnstile 验证未通过，终止")
                        return False
                    try:
                        cookie_btn = None
                        for text in COOKIE_ACCEPT_TEXTS:
                            cookie_btn = page.ele(f'text:{text}', timeout=0.5)
                            if cookie_btn:
                                break
                        if cookie_btn:
                            cookie_btn.click()
                            log("  ✅ 重试时已点击接受 Cookie")
                            human_delay(0.5, 1.0)
                    except:
                        pass

                # ══ Step 3: 点击其他登录方式 ══
                log("━" * 50)
                log("Step 3: 点击其他登录方式")
                if not click_any_text_by_js(page, OTHER_LOGIN_TEXTS):
                    log("  ❌ 未找到其他登录方式入口")
                    continue
                human_delay(0.8, 1.5)

                # ══ Step 4: 点击 Microsoft 帐户登录 ══
                log("━" * 50)
                log("Step 4: 点击 Microsoft 帐户登录")
                auth_page = open_microsoft_login_with_retries(browser, page, max_retries=2)
                if not auth_page:
                    continue

                # ══ Step 5: 在 Microsoft 弹窗中登录 ══
                log("━" * 50)
                log("Step 5: 在 Microsoft 弹窗中完成帐户登录")
                microsoft_login_page = complete_microsoft_login(
                    browser,
                    page,
                    email_addr,
                    getattr(mail, "password", ""),
                    auth_page=auth_page,
                )
                if microsoft_login_page:
                    page = microsoft_login_page
                    break

            if not microsoft_login_page:
                log("  ❌ Microsoft 登录重试 1 次后仍未完成")
                return False
            human_delay(1.0, 2.0)
        else:
            # ══ Step 3: 点击邮箱登录 ══
            log("━" * 50)
            log("Step 3: 点击邮箱登录")

            # 按 ESC 关闭可能的弹窗
            try:
                page.run_js('document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));')
            except:
                pass

            # 终极解决方案：完全抛弃外部点击，直接把 JS 注入到网页里运行！
            # 让网页自己去找包含 email 的 button 然后自己点！
            email_keywords_js = json.dumps([kw.lower() for kw in EMAIL_LOGIN_KEYWORDS], ensure_ascii=False)
            js_code = """
            var keywords = __EMAIL_KEYWORDS__;
            var btns = document.querySelectorAll('button, a[role="button"], div[role="button"], [data-testid], [aria-label]');
            for(var i=0; i<btns.length; i++) {
                var text = ((btns[i].innerText || btns[i].textContent || '') + ' ' + (btns[i].getAttribute('title') || '')).toLowerCase();
                var aria = (btns[i].getAttribute('aria-label') || '').toLowerCase();
                if(keywords.some(function(keyword) {
                    return text.includes(keyword) || aria.includes(keyword);
                })) {
                    btns[i].click();
                    return true;
                }
            }
            return false;
            """.replace("__EMAIL_KEYWORDS__", email_keywords_js)

            try:
                clicked = False
                for attempt in range(2):
                    clicked = page.run_js(js_code)
                    if clicked:
                        log("  ✅ 已点击邮箱登录 (纯原生 JS 引擎执行)")
                        human_delay(0.5, 1.0)
                        break
                    else:
                        if attempt == 0:
                            log("  ⚠️ 原生 JS 没找到邮箱按钮，尝试刷新页面...")
                            page.refresh()
                            page.wait.load_start()
                            human_delay(3.0, 5.0)
                            # 再次执行消除防爬虫弹窗
                            try:
                                page.run_js('document.body.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape"}));')
                                page.run_js('document.body.dispatchEvent(new KeyboardEvent("keyup", {key: "Escape"}));')
                                human_delay(0.5, 1.0)
                            except:
                                pass
                        else:
                            log("  ❌ 原生 JS 没找到邮箱按钮 (重试后依然失败)")
                            return False
            except Exception as e:
                log(f"  ❌ JS执行失败: {e}")
                return False

            # ══ Step 4: 输入邮箱 ══
            log("━" * 50)
            log("Step 4: 输入邮箱")


            email_input = None
            # DrissionPage: 用 tag: 语法来查找 input
            for sel in [
                'tag:input@@name=email', 'tag:input@@name=username',
                'tag:input@@type=email', 'tag:input@@type=text',
            ]:
                try:
                    el = page.ele(sel, timeout=2)
                    if el:
                        email_input = el
                        break
                except:
                    continue

            if not email_input:
                log("  ❌ 找不到邮箱输入框")
                # 调试: 列出所有 input
                inputs = page.eles('tag:input')
                for inp in inputs[:10]:
                    log(f"    输入框: type={inp.attr('type')} name={inp.attr('name')} placeholder={inp.attr('placeholder')}")
                return False

            type_like_human(email_input, email_addr)

            log(f"  ✅ 邮箱输入: {email_addr}")

            # 提交 - 点击"继续"按钮
            submitted = False
            for text in CONTINUE_BUTTON_TEXTS:
                try:
                    btn = page.ele(f'tag:button@@text():{text}', timeout=1)
                    if btn:
                        try:
                            rect = btn.rect
                            cx = int(rect.midpoint[0]) + random.randint(-8, 8)
                            cy = int(rect.midpoint[1]) + random.randint(-4, 4)
                            page.actions.move_to((cx, cy))
                            human_delay(0.15, 0.4)
                            page.actions.click()
                            submitted = True
                            log(f"  ✅ 已坐标点击 [{text}] 按钮 @ ({cx},{cy})")
                            break
                        except Exception as e:
                            log(f"  ⚠️ 邮箱提交坐标点击报错 [{text}]: {e}")
                            continue
                except:
                    continue
            if not submitted:
                email_input.input('\n')
                log("  → 按回车提交")
            human_delay(1.0, 2.0)

            # ══ Step 5: 创建账号名称 ══
            log("━" * 50)
            log("Step 5: 创建账号名称（使用默认）")

            # 页面可能显示"创建账户"，名称输入框已自动填充邮箱前缀
            # 需要点击"继续"按钮提交
            try:
                # 查找名称输入框（确认存在即可，使用默认值）
                name_input = None
                for sel in ['tag:input@@name=displayName', 'tag:input@@name=name',
                            'tag:input@@type=text']:
                    try:
                        el = page.ele(sel, timeout=2)
                        if el:
                            name_input = el
                            log(f"  📝 名称: {el.value or el.attr('value') or '(默认)'}")
                            break
                    except:
                        continue

                # 立即点击"继续"按钮提交
                submitted = False
                for text in CREATE_ACCOUNT_BUTTON_TEXTS:
                    try:
                        btn = page.ele(f'tag:button@@text():{text}', timeout=1)
                        if btn:
                            try:
                                rect = btn.rect
                                cx = int(rect.midpoint[0]) + random.randint(-8, 8)
                                cy = int(rect.midpoint[1]) + random.randint(-4, 4)
                                page.actions.move_to((cx, cy))
                                human_delay(0.15, 0.4)
                                page.actions.click()
                                submitted = True
                                log(f"  ✅ 已坐标点击 [{text}] 按钮提交名称 @ ({cx},{cy})")
                                break
                            except Exception as e:
                                log(f"  ⚠️ 名称提交坐标点击报错 [{text}]: {e}")
                                continue
                    except:
                        continue

                if not submitted and name_input:
                    name_input.input('\n')
                    log("  → 按回车提交默认名称")
            except Exception as e:
                log(f"  → 名称步骤异常 (可忽略): {e}")
            human_delay(1.0, 2.0)

        canva_login_already_done = REGISTRATION_MODE == "microsoft" and is_canva_templates_page(page)
        if canva_login_already_done:
            log("━" * 50)
            log("Step 6-8: Microsoft 登录后已进入 Canva 模板页，跳过验证码流程")
            mark_verify_success("Microsoft 登录后直接进入 Canva 模板页")
        else:
            # ══ Step 6: 等待验证码 ══
            log("━" * 50)
            log("Step 6: 等待验证码邮件")

            # 检查是否有错误消息
            try:
                error_el = None
                for text in SECURITY_REASON_TEXTS:
                    error_el = page.ele(f'text:{text}', timeout=0.5)
                    if error_el:
                        break
                if error_el:
                    log(f"  🚫 安全拦截: {error_el.text[:100]}")
                    return False
            except:
                pass

            try:
                error_el = page.ele("text:There's an issue", timeout=1)
                if error_el:
                    log(f"  🚫 服务错误: {error_el.text[:100]}")
                    return False
            except:
                pass

            # 同步等待验证码 (支持重发)
            code = None
            for mail_attempt in range(2):
                wait_time = 60 if mail_attempt == 0 else 60
                code = mail.wait_for_code_sync(max_wait=wait_time, interval=5)
                if code:
                    break

                if mail_attempt == 0:
                    # 第一次没收到，尝试点击页面上的"Resend code"
                    log("  ⚠️ 未收到验证码，尝试点击重发...")
                    resent = False
                    try:
                        btn = page.ele('tag:a@@role=button@@text():重新发送验证码', timeout=1)
                        if not btn:
                            for text in RESEND_CODE_TEXTS:
                                btn = page.ele(f'text:{text}', timeout=1)
                                if btn:
                                    break

                        if btn:
                            btn.click()
                            resent = True
                            log("  🔄 已点击重发验证码按钮，等待新验证码...")
                            human_delay(2.0, 3.0)
                    except:
                        pass
                    if not resent:
                        log("  ❌ 未找到重发按钮，放弃等待")
                        break

            if not code:
                log("  ❌ 验证码等待超时 (含重发)")
                return False

            # ══ Step 7: 输入验证码 ══
            log("━" * 50)
            log("Step 7: 输入验证码")

            code_input = None
            for sel in [
                'tag:input@@name=code', 'tag:input@@name=otp',
                'tag:input@@type=tel', 'tag:input@@autocomplete=one-time-code',
                'tag:input@@maxlength=6', 'tag:input@@type=number',
            ]:
                try:
                    el = page.ele(sel, timeout=2)
                    if el:
                        code_input = el
                        break
                except:
                    continue

            if not code_input:
                log("  ❌ 找不到验证码输入框")
                inputs = page.eles('tag:input')
                for inp in inputs[:10]:
                    log(f"    输入框: type={inp.attr('type')} name={inp.attr('name')} maxlength={inp.attr('maxlength')}")
                return False

            type_code_like_human(code_input, code)
            log(f"  ✅ 验证码已输入: {code}")

            # ══ Step 8: 主动点击提交按钮并等待跳转 ══
            log("━" * 50)
            log("Step 8: 主动点击提交并等待跳转")

            # 先尝试找到提交按钮并用坐标点击
            submit_clicked = False
            for text in SUBMIT_CODE_BUTTON_TEXTS:
                try:
                    btn = page.ele(f'tag:button@@text():{text}', timeout=0.5)
                    if btn:
                        try:
                            rect = btn.rect
                            # 计算按钮中心 + 随机偏移，模拟真人点击
                            cx = int(rect.midpoint[0]) + random.randint(-8, 8)
                            cy = int(rect.midpoint[1]) + random.randint(-4, 4)
                            # 先移动鼠标过去 (需要传元组)
                            page.actions.move_to((cx, cy))
                            human_delay(0.15, 0.4)
                            # 坐标点击
                            page.actions.click()
                            submit_clicked = True
                            log(f"  ✅ 已坐标点击提交按钮 [{text}] @ ({cx},{cy})")
                            break
                        except Exception as e:
                            log(f"  ⚠️ 坐标计算或点击报错 [{text}]: {e}")
                            continue
                except Exception as e:
                    pass

            if not submit_clicked:
                clicked_text = click_text_button_by_js(page, SUBMIT_CODE_BUTTON_TEXTS)
                if clicked_text:
                    submit_clicked = True
                    log(f"  ✅ 已用 JS 兜底点击提交按钮 [{clicked_text}]")
                else:
                    log("  ⚠️ 未执行坐标点击，等待自动提交...")

            jumped = False
            start_time = time.time()
            click_count = 0
            has_security_warning_ever = False

            while True:
                elapsed = time.time() - start_time
                current_url = page.url

                # 已跳转到 Canva 主页
                if 'canva.com' in current_url and 'templates' in current_url:
                    log(f"  ✅ 已跳转: {current_url[:80]}")
                    jumped = True
                    break

                # 等待超过20秒依然未跳转，直接判定失败
                if elapsed > 20:
                    log(f"  ❌ 提交验证码后超过20秒未跳转，判定任务失败")
                    return False

                # 检查当前是否出现风控拦截
                current_warning = False
                try:
                    error_el = None
                    for text in SECURITY_REASON_TEXTS:
                        error_el = page.ele(f'text:{text}', timeout=0.5)
                        if error_el:
                            break

                    if error_el:
                        current_warning = True
                        has_security_warning_ever = True
                        text_val = error_el.text if error_el.text else ""
                        log(f"  🚫 安全拦截提示: {text_val[:80]}")
                except:
                    pass

                # 如果出现风控拦截，尝试坐标点击（最多 5 次）
                if current_warning and click_count < 5:
                    clicked_this_round = False
                    try:
                        for text in SUBMIT_CODE_BUTTON_TEXTS:
                            btn = page.ele(f'tag:button@@text():{text}', timeout=0.5)
                            if btn:
                                log(f"  ⚠️ 触发风控拦截，尝试坐标点击...")
                                try:
                                    rect = btn.rect
                                    cx = int(rect.midpoint[0]) + random.randint(-10, 10)
                                    cy = int(rect.midpoint[1]) + random.randint(-5, 5)
                                    page.actions.move_to((cx, cy))
                                    human_delay(0.3, 0.8)
                                    page.actions.click()
                                    click_count += 1
                                    clicked_this_round = True
                                    log(f"  → 已坐标点击 (第 {click_count}/5 次) @ ({cx},{cy})")
                                except:
                                    pass
                                break
                    except:
                        pass

                    if not clicked_this_round:
                        clicked_text = click_text_button_by_js(page, SUBMIT_CODE_BUTTON_TEXTS)
                        if clicked_text:
                            click_count += 1
                            log(f"  → 已用 JS 兜底点击 [{clicked_text}] (第 {click_count}/5 次)")
                        else:
                            log("  ⚠️ 已触发风控，但没有找到可点击的继续/提交按钮")

                if current_warning:
                    human_delay(2.0, 3.0)
                else:
                    human_delay(1.5, 2.5)

                # 检查二次 Turnstile
                try:
                    if "challenges.cloudflare.com" in page.html:
                        log("  ⚠️ 检测到二次 Turnstile，尝试处理...")
                        handle_turnstile(page, max_wait=20)
                except:
                    pass

            if not jumped:
                return False

            mark_verify_success("验证码提交成功")

        # ══ Step 9: 通过 Canva SSO 登录 Leonardo.Ai ══
        log("━" * 50)
        log("Step 9: 通过 Canva SSO 登录 Leonardo.Ai")

        def _check_leo_cookies(pg):
            """检查是否已经拿到了核心 Cookie"""
            all_c = pg.cookies()
            leo_c = [c for c in all_c if 'leonardo' in c.get('domain', '').lower()]
            names = [c['name'] for c in leo_c]
            has_st = "__Secure-better-auth.session_token" in names
            has_sd = any(n.startswith("__Secure-better-auth.session_data.") for n in names)
            has_cf = "CF_Access_Token" in names
            return has_st and has_sd and has_cf, leo_c

        def _is_leonardo_auth_pending(url: str) -> bool:
            url = (url or "").lower()
            try:
                host = urlsplit(url).hostname or ""
            except Exception:
                host = ""
            if host != "app.leonardo.ai":
                return False
            return (
                "app.leonardo.ai/auth/" in url
                or "app.leonardo.ai/api/auth/" in url
                or "callbackurl=" in url
            )

        def _is_leonardo_host(url: str) -> bool:
            try:
                return (urlsplit(url or "").hostname or "") == "app.leonardo.ai"
            except Exception:
                return False

        def _request_leonardo_session(pg):
            pg.get("https://app.leonardo.ai/api/auth/get-session")
            time.sleep(2)
            return _check_leo_cookies(pg)[0]

        def _wait_for_leonardo_cookies(pg, wait_seconds=30, interval=5):
            start = time.time()
            attempt = 0
            while time.time() - start < wait_seconds:
                attempt += 1
                try:
                    if _check_leo_cookies(pg)[0]:
                        return True
                    if _request_leonardo_session(pg):
                        return True
                    log(f"  → 等待 Leonardo Cookie 写入 ({attempt}, {int(time.time() - start)}s/{wait_seconds}s)")
                except Exception as e:
                    log(f"  ⚠️ 等待 Leonardo Cookie 时检查失败: {e}")
                time.sleep(interval)
            return _check_leo_cookies(pg)[0]

        def _perform_leonardo_sso(pg, attempt: int, timeout=120):
            log(f"  → Canva SSO 登录 Leonardo 尝试 {attempt}")
            pg.get("https://app.leonardo.ai/auth/canva-login")
            human_delay(3.0, 5.0)
            log(f"  → 当前URL: {pg.url[:80]}")

            oauth_start = time.time()
            while time.time() - oauth_start < timeout:
                current_url = pg.url

                # 已经拿到完整 cookie，说明 SSO 真正完成
                try:
                    cookie_ok, _ = _check_leo_cookies(pg)
                    if cookie_ok:
                        log("  ✅ OAuth 登录完成，已获取 Leonardo 核心 Cookie")
                        return pg, True
                except Exception:
                    pass

                # 已经跳到 Leonardo 正常页面，说明 SSO 授权回跳完成；Cookie 写入交给 Step 10 处理
                if _is_leonardo_host(current_url) and not _is_leonardo_auth_pending(current_url):
                    log(f"  ✅ OAuth 已自动跳转: {current_url[:80]}")
                    return pg, True

                # 还在授权页面，尝试点击允许
                if 'oauth' in current_url or 'authorize' in current_url or 'canva.com' in current_url:
                    if not click_canva_oauth_allow(pg):
                        log("  → 未找到可点击的 Canva OAuth 授权按钮，继续等待")

                # 检查是否有新标签页打开
                tabs = browser.tab_ids
                for tab_id in tabs:
                    tab = browser.get_tab(tab_id)
                    if _is_leonardo_host(tab.url) and tab_id != pg.tab_id:
                        pg = tab
                        log(f"  → 切换到 Leonardo 标签: {pg.url[:80]}")
                        break

                if _is_leonardo_host(current_url) and _is_leonardo_auth_pending(current_url):
                    log(f"  → 等待 Leonardo 授权自动跳转: {current_url[:80]}")

                human_delay(1.5, 2.5)

            log(f"  ❌ Leonardo OAuth 授权未完成自动跳转: {pg.url[:80]}")
            return pg, False

        def _handle_leonardo_onboarding(pg):
            # 处理首次登录可能出现的协议勾选和初始化按钮（快速跳过）
            try:
                checkbox = pg.ele('tag:button@@role=checkbox', timeout=2)
                if checkbox:
                    checkbox.click()
                    log("  ✅ 已勾选 I agree")
                    human_delay(0.5, 1.0)
            except:
                pass

            for text in ONBOARDING_SKIP_TEXTS:
                try:
                    btn = pg.ele(f'tag:button@@text():{text}', timeout=1)
                    if btn:
                        btn.click()
                        log(f"  ✅ 跳过初始化: [{text}]")
                        human_delay(0.5, 1.0)
                except:
                    continue

        def _hydrate_leonardo_cookies(pg, urls) -> bool:
            # 先在当前页面检查一次（OAuth 可能已经写入了 Cookie）
            if _wait_for_leonardo_cookies(pg, wait_seconds=30, interval=5):
                log("  ✅ OAuth 后已获取到完整 Cookie！")
                return True

            for url_idx, leo_url in enumerate(urls):
                log(f"  → 尝试 ({url_idx+1}/{len(urls)}): {leo_url}")
                pg.get(leo_url)
                human_delay(3.0, 5.0)

                _handle_leonardo_onboarding(pg)
                log(f"  → 当前URL: {pg.url[:80]}")

                # 强制请求 Auth API 让后端写入完整 Cookie
                if _request_leonardo_session(pg):
                    log(f"  ✅ 已获取完整 Cookie (通过 {leo_url})")
                    return True

                all_c = pg.cookies()
                leo_c = [c for c in all_c if 'leonardo' in c.get('domain', '').lower()]
                names = [c['name'] for c in leo_c]
                missing = []
                if "__Secure-better-auth.session_token" not in names: missing.append("session_token")
                if not any(n.startswith("__Secure-better-auth.session_data.") for n in names): missing.append("session_data")
                if "CF_Access_Token" not in names: missing.append("CF_Access_Token")
                log(f"  ⚠️ Cookie 不完整 (缺少: {', '.join(missing)})，尝试下一个地址...")
            return False

        # 按优先级依次尝试打开 Leonardo 页面获取 Cookie
        leo_urls = [
            "https://app.leonardo.ai/generate?model=auto-preset",
            "https://app.leonardo.ai/generate?model=motion_2.0-fast",
            "https://app.leonardo.ai",
        ]

        oauth_completed = False
        cookies_ready = False
        max_sso_attempts = 2
        for sso_attempt in range(1, max_sso_attempts + 1):
            page, oauth_completed = _perform_leonardo_sso(page, sso_attempt)
            log(f"  → OAuth 完成后URL: {page.url[:80]}")

            if not oauth_completed:
                if sso_attempt < max_sso_attempts:
                    log("  ↻ OAuth 未完成，重新打开 Canva SSO 登录 Leonardo.Ai")
                    human_delay(2.0, 4.0)
                    continue
                break

            _handle_leonardo_onboarding(page)

            # ══ Step 10: 打开 Leonardo 功能页获取 Cookie ══
            log("━" * 50)
            log("Step 10: 打开 Leonardo 功能页获取 Cookie")
            cookies_ready = _hydrate_leonardo_cookies(page, leo_urls)
            if cookies_ready:
                break

            if sso_attempt < max_sso_attempts:
                log("  ↻ Step 10 后核心 Cookie 仍不完整，重新打开 Canva SSO 登录 Leonardo.Ai")
                human_delay(2.0, 4.0)

        if not oauth_completed:
            log("  ❌ 多次 Canva SSO 后仍未完成 Leonardo OAuth，终止")
            return False

        if not cookies_ready:
            log("  ⚠️ 多次 Canva SSO + Step 10 后核心 Cookie 仍不完整，进入最终刷新检查")


        # ══ Step 15: 导出 Cookie ══
        log("━" * 50)
        log("Step 15: 导出 Cookie")

        # 循环尝试获取完整 Cookie (最多 3 次)
        required_cookies_found = False
        for attempt in range(3):


            all_cookies = page.cookies()
            leo_cookies = [c for c in all_cookies if 'leonardo' in c.get('domain', '').lower()]

            cookie_names = [c['name'] for c in leo_cookies]
            has_session_token = "__Secure-better-auth.session_token" in cookie_names
            has_session_data = any(name.startswith("__Secure-better-auth.session_data.") for name in cookie_names)
            has_cf_token = "CF_Access_Token" in cookie_names

            if has_session_token and has_session_data and has_cf_token:
                required_cookies_found = True
                break

            log(f"  ⚠️ Leonardo 核心 Cookie 不完整 (第 {attempt+1}/3 次)，尝试请求 Auth API 获取...")
            page.get("https://app.leonardo.ai/api/auth/get-session")
            time.sleep(3)

        if not required_cookies_found:
            log("  ❌ 多次刷新仍未获取到完整的核心 Cookie，判定为注册失败！")
            return False

        # 根据 leonardo-cookie-exporter 的逻辑对 Cookie 进行排序
        important_order = [
            "__Secure-better-auth.session_token",
            "__Secure-better-auth.session_data.0",
            "__Secure-better-auth.session_data.1",
            "__Secure-better-auth.session_data.2",
            "__Secure-better-auth.session_data.3",
            "CF_Access_Token"
        ]

        def get_rank(name):
            try:
                return important_order.index(name)
            except ValueError:
                if name.startswith("__Secure-better-auth.session_data."):
                    try:
                        return 100 + int(name.split('.')[-1])
                    except:
                        return 100
                return 1000

        # 对提取到的 Leonardo Cookies 进行排序
        sorted_leo_cookies = sorted(
            leo_cookies,
            key=lambda c: (get_rank(c['name']), c['name'], c.get('domain', ''), c.get('path', ''))
        )

        # 拼接成最终的 Cookie 字符串
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in sorted_leo_cookies])

        # 确保 cookies 目录存在
        cookies_dir = os.path.join(DATA_DIR, "cookies")
        os.makedirs(cookies_dir, exist_ok=True)

        cookie_id = os.getenv("COOKIE_ID", "")
        if cookie_id:
            cookie_file = os.path.join(cookies_dir, f"cookie_{cookie_id}.json")
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            cookie_file = os.path.join(cookies_dir, f"leonardo-cookie-{ts}.json")

        # 导出格式：包含 cookie 和 name（邮箱地址）
        cookie_data = {
            "name": email_addr,
            "cookie": cookie_string,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        log(f"  🍪 已导出标准格式 Cookie ({len(sorted_leo_cookies)} 项)")
        log(f"  📁 文件: {cookie_file}")

        log("╔═══════════════════════════════════════════════════╗")
        log("║              🎉 注册流程完成!                    ║")
        log("╚═══════════════════════════════════════════════════╝")
        return True

    except Exception as e:
        log(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            if browser:
                browser.quit()
        except:
            pass
        try:
            if playwright_context:
                playwright_context.close()
        except:
            pass
        try:
            if playwright_instance:
                playwright_instance.stop()
        except:
            pass
        try:
            if cloak_browser:
                cloak_browser.close()
        except:
            pass
        if BROWSER_MODE == "cloakbrowser" and auto_created_user_data_dir:
            try:
                cleanup_path = os.path.abspath(auto_created_user_data_dir)
                data_root = os.path.abspath(DATA_DIR)
                if (
                    os.path.basename(cleanup_path).startswith("chrome_dp_")
                    and os.path.commonpath([cleanup_path, data_root]) == data_root
                ):
                    shutil.rmtree(cleanup_path, ignore_errors=True)
                    log(f"🧹 已清理本次 CloakBrowser profile: {cleanup_path}")
            except Exception as e:
                log(f"⚠️ 清理 CloakBrowser profile 失败: {e}")

        if BITBROWSER_ENABLED and 'browser_id' in locals() and browser_id:
            try:
                import requests
                # 官方文档要求：调用close后等待5秒进程退出再删除
                if 'bitbrowser_post' in locals():
                    bitbrowser_post("/browser/close", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                else:
                    requests.post(f"{BITBROWSER_URL}/browser/close", json={'id': browser_id}, headers={'Content-Type': 'application/json'}, timeout=20, proxies={"http": None, "https": None})
                log(f"🧹 正在关闭比特浏览器窗口 {browser_id}，等待进程退出...")
                time.sleep(5)  # 等待5秒让进程彻底退出
                if 'bitbrowser_post' in locals():
                    bitbrowser_post("/browser/delete", {'id': browser_id}, timeout=20, retries=2, retry_delay=2)
                else:
                    requests.post(f"{BITBROWSER_URL}/browser/delete", json={'id': browser_id}, headers={'Content-Type': 'application/json'}, timeout=20, proxies={"http": None, "https": None})
                log(f"🧹 已删除比特浏览器窗口 {browser_id}")
            except Exception as e:
                log(f"⚠️ 清理比特浏览器窗口失败: {e}")


# ════════════════════════ 入口 ════════════════════════

async def main():
    if SELF_EMAIL_MODE:
        mail = SelfProvidedMail(SELF_EMAIL_ADDRESS, SELF_EMAIL_PASSWORD, SELF_EMAIL_API_URL)
    else:
        mail = TempMail()

    log("╔═══════════════════════════════════════════════════╗")
    log("║   Leonardo.Ai 自动注册 (DrissionPage 模式)       ║")
    log("╚═══════════════════════════════════════════════════╝")

    log("━" * 50)
    log("Step 0: 准备邮箱")
    try:
        email_addr = await mail.create()
    except Exception as e:
        log(f"❌ 邮箱准备失败: {e}")
        await mail.close()
        return

    try:
        success = await asyncio.to_thread(run_registration, email_addr, mail)
        if not success:
            log("❌ 注册流程未完成")
    finally:
        await mail.close()


if __name__ == "__main__":
    asyncio.run(main())
