from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime
import httpx
import asyncio
import logging
import os
import re
from dotenv import load_dotenv
from urllib.parse import unquote

load_dotenv()

# Ensure Playwright can find its browsers
_pw_browsers = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
if _pw_browsers:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _pw_browsers

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

app = FastAPI(title="Cookie Checker API", version="1.0.0")

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
    cookie_bundles: List[dict] = []
    cookie_count: int = 0
    tokens: List[dict] = []
    token_count: int = 0
    bundle_count: int = 0

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
    accounts: List[dict] = []
    account_count: int = 0
    bundle_count: int = 0
    checked_cookie_count: int = 0

LARGE_IMPORT_ACCOUNT_LOOKUP_THRESHOLD = 20

# Cookie Parsing Functions
COMPACT_NETFLIX_COOKIE_NAMES = (
    "netflix-sans-normal-3-loaded",
    "netflix-sans-bold-3-loaded",
    "OptanonConsent",
    "SecureNetflixId",
    "profilesNewSession",
    "NetflixId",
    "nfvdid",
    "flwssn",
    "gsid",
    "dscatrue",
    "memclid",
    "cl2",
    "cL",
    "ftl",
    "lhpu",
    "nfg",
    "nfxp",
)

COMPACT_NETFLIX_PREFIX = re.compile(
    r"^(?P<domain>\.?(?:[A-Za-z0-9-]+\.)*netflix\.com)"
    r"(?P<include_subdomains>TRUE|FALSE)(?P<path>/)"
    r"(?P<secure>TRUE|FALSE)(?P<expires>\d{10,13})(?P<data>.+)$",
    re.IGNORECASE,
)

COMPACT_NETFLIX_RECORD_START = re.compile(
    r"(?=\.?(?:[A-Za-z0-9-]+\.)*netflix\.com"
    r"(?:TRUE|FALSE)/(?:TRUE|FALSE)\d{10,13})",
    re.IGNORECASE,
)


def _split_compact_netflix_records(line: str) -> List[str]:
    """Split delimiter-free Netscape records using their repeated domain prefix."""
    starts = [match.start() for match in COMPACT_NETFLIX_RECORD_START.finditer(line)]
    if not starts:
        return []

    return [
        line[start:end]
        for start, end in zip(starts, starts[1:] + [len(line)])
        if line[start:end].strip()
    ]


def _split_compact_cookie_data(data: str) -> tuple[Optional[str], Optional[str]]:
    """Split a compact name/value pair using known Netflix cookie names."""
    lowered = data.lower()
    for name in sorted(COMPACT_NETFLIX_COOKIE_NAMES, key=len, reverse=True):
        if lowered.startswith(name.lower()):
            return name, data[len(name):]

    # Preserve support for compact records that still contain a normal '='.
    if "=" in data:
        name, value = data.split("=", 1)
        if re.fullmatch(r"[A-Za-z0-9_!-]+", name):
            return name, value

    return None, None


def _parse_compact_netflix_record(record: str) -> Optional[Cookie]:
    match = COMPACT_NETFLIX_PREFIX.match(record)
    if not match:
        return None

    name, value = _split_compact_cookie_data(match.group("data"))
    if not name or value is None:
        return None

    return Cookie(
        name=name,
        value=value,
        domain=match.group("domain"),
        path=match.group("path"),
        expires=match.group("expires"),
        secure=match.group("secure").upper() == "TRUE",
    )


def parse_netscape_cookies(text: str) -> tuple[List[Cookie], List[str]]:
    """Parse Netscape format cookies (from browser dev tools)"""
    cookies = []
    errors = []
    
    for line in text.strip().split('\n'):
        line = line.strip()
        if line.startswith('#') or not line or re.fullmatch(r"=+", line):
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
                continue

            compact_records = _split_compact_netflix_records(line)
            if compact_records:
                parsed_any = False
                for record in compact_records:
                    cookie = _parse_compact_netflix_record(record)
                    if cookie:
                        cookies.append(cookie)
                        parsed_any = True
                if not parsed_any:
                    errors.append("Could not identify a cookie name in a compact Netflix record.")
                continue

            if '=' in line:
                # Fallback for simple key=value pairs
                for pair in line.split(';'):
                    pair = pair.strip()
                    if '=' in pair:
                        k, _, v = pair.partition('=')
                        cookies.append(Cookie(name=k.strip(), value=v.strip()))
        except Exception as e:
            errors.append(f"Failed to parse line: {line}. Error: {str(e)}")
    
    return cookies, errors

def _cookies_from_json_data(data: object) -> List[Cookie]:
    cookies = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cookies.append(Cookie(
                    name=item.get('name', ''),
                    value=item.get('value', ''),
                    domain=item.get('domain'),
                    path=item.get('path', '/'),
                    expires=item.get('expires'),
                    secure=item.get('secure', False),
                    httponly=item.get('httpOnly', False),
                    samesite=item.get('sameSite')
                ))
    elif isinstance(data, dict):
        for k, v in data.items():
            cookies.append(Cookie(name=k, value=str(v)))

    return cookies


def _extract_bracketed_json_arrays(text: str) -> List[list]:
    """Extract complete JSON arrays from newline- or bracket-separated input."""
    decoder = json.JSONDecoder()
    arrays = []
    search_from = 0

    while search_from < len(text):
        start = text.find('[', search_from)
        if start == -1:
            break

        try:
            data, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            search_from = start + 1
            continue

        if isinstance(data, list):
            arrays.append(data)
        search_from = end

    return arrays


def parse_json_cookies(text: str) -> tuple[List[Cookie], List[str]]:
    """Parse standard JSON or newline-delimited bracketed JSON cookie arrays."""
    try:
        data = json.loads(text)
        return _cookies_from_json_data(data), []
    except json.JSONDecodeError as json_error:
        arrays = _extract_bracketed_json_arrays(text)
        if not arrays:
            return [], [f"Invalid JSON: {str(json_error)}"]

        cookies = []
        errors = []
        for index, data in enumerate(arrays, 1):
            bundle_cookies = _cookies_from_json_data(data)
            if bundle_cookies:
                cookies.extend(bundle_cookies)
            else:
                errors.append(f"Bracketed JSON bundle #{index} contains no cookie objects.")

        return cookies, errors

def parse_cookies_auto(text: str) -> tuple[List[Cookie], List[str]]:
    """Auto-detect and parse cookies"""
    text = text.strip()
    
    if text.startswith('[') or text.startswith('{'):
        cookies, errors = parse_json_cookies(text)
        if cookies:
            return cookies, errors
    
    return parse_netscape_cookies(text)


def parse_cookie_bundles(
    text: str,
    format_type: str,
) -> tuple[List[tuple[List[Cookie], List[str]]], List[str]]:
    """Parse cookie sets separately when an export includes separator lines."""
    format_type = format_type.lower()

    if format_type == "json" or (format_type == "auto" and text.lstrip().startswith(("[", "{"))):
        try:
            data = json.loads(text)
            cookies = _cookies_from_json_data(data)
            return ([(cookies, [])] if cookies else []), []
        except json.JSONDecodeError as json_error:
            arrays = _extract_bracketed_json_arrays(text)
            if arrays:
                bundles = []
                all_errors = []
                for index, data in enumerate(arrays, 1):
                    bundle_cookies = _cookies_from_json_data(data)
                    if bundle_cookies:
                        bundles.append((bundle_cookies, []))
                    else:
                        all_errors.append(
                            f"Bracketed JSON bundle #{index} contains no cookie objects."
                        )
                return bundles, all_errors

            cookies, errors = parse_json_cookies(text)
            if not cookies:
                errors.insert(0, f"Invalid JSON: {str(json_error)}")
            return ([(cookies, errors)] if cookies else []), errors

    if format_type not in ("auto", "netscape"):
        raise ValueError("Invalid format_type. Must be 'netscape', 'json', or 'auto'")

    raw_bundles = re.split(r"(?m)^\s*=+\s*$", text)
    if len(raw_bundles) == 1:
        cookies, errors = parse_netscape_cookies(text)
        return ([(cookies, errors)] if cookies else []), errors

    bundles = []
    all_errors = []
    for raw_bundle in raw_bundles:
        if not raw_bundle.strip():
            continue
        cookies, errors = parse_netscape_cookies(raw_bundle)
        if cookies:
            bundles.append((cookies, errors))
        all_errors.extend(errors)

    return bundles, all_errors

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
    """Generate an NFTOKEN using the same account endpoint as the checker."""
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v

    netflix_id = norm.get('NetflixId') or norm.get('netflixid')

    if not netflix_id:
        return False, None, "Missing required cookie (NetflixId)"

    api_url = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    query_params = {
        "appVersion": "15.48.1",
        "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","sharksEnabled":"true"}',
        "device_type": "NFAPPL-02-",
        "esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
        "idiom": "phone",
        "iosVersion": "15.8.5",
        "isTablet": "false",
        "languages": "en-US",
        "locale": "en-US",
        "maxDeviceWidth": "375",
        "model": "saget",
        "modelType": "IPHONE8-1",
        "odpAware": "true",
        "path": '["account","token","default"]',
        "pathFormat": "graph",
        "pixelDensity": "2.0",
        "progressive": "false",
        "responseFormat": "json",
    }

    nft_headers = {
        "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
        "x-netflix.request.attempt": "1",
        "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
        "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
        "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
        "x-netflix.context.app-version": "15.48.1",
        "x-netflix.argo.translated": "true",
        "x-netflix.context.form-factor": "phone",
        "x-netflix.context.sdk-version": "2012.4",
        "x-netflix.client.appversion": "15.48.1",
        "x-netflix.context.max-device-width": "375",
        "x-netflix.client.type": "argo",
        "x-netflix.context.locales": "en-US",
        "x-netflix.client.iosversion": "15.8.5",
        "x-netflix.context.os-version": "15.8.5",
        "x-netflix.context.ui-flavor": "argo",
        "x-netflix.context.pixel-density": "2.0",
        "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
        "x-netflix.context.ab-tests": "",
        "x-netflix.argo.abtests": "",
        "x-netflix.argo.nfnsm": "9",
        "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
        "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
        "x-netflix.request.client.context": '{"appState":"foreground"}',
        "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
        "x-netflix.request.client.timezoneid": "Asia/Dhaka",
        "accept-language": "en-US;q=1",
        "Cookie": f"NetflixId={unquote(str(netflix_id))}",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, http2=False) as http_client:
            resp = await http_client.get(
                api_url,
                params=query_params,
                headers=nft_headers,
            )

            if resp.status_code != 200:
                return False, None, f"HTTP {resp.status_code} from Netflix token endpoint"

            data = resp.json()
            token_data = (
                (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
                or {}
            )
            token = token_data.get("token") if isinstance(token_data, dict) else None
            logger.info(
                "Netflix token response shape: top_level=%s value=%s account=%s "
                "token_default=%s token_type=%s token_length=%s",
                sorted(data.keys()) if isinstance(data, dict) else type(data).__name__,
                sorted((data.get("value") or {}).keys()) if isinstance(data, dict) and isinstance(data.get("value"), dict) else type((data.get("value") if isinstance(data, dict) else None)).__name__,
                sorted(((data.get("value") or {}).get("account") or {}).keys()) if isinstance(data, dict) and isinstance((data.get("value") or {}).get("account"), dict) else type(((data.get("value") or {}).get("account") if isinstance(data, dict) else None)).__name__,
                sorted(token_data.keys()) if isinstance(token_data, dict) else type(token_data).__name__,
                type(token).__name__,
                len(token) if isinstance(token, str) else None,
            )

            if not isinstance(token, str) or not token.strip():
                return False, None, "Netflix returned no usable token"

            return True, token, None
    except Exception as e:
        return False, None, str(e)


def normalize_netflix_plan(value: object) -> Optional[str]:
    """Normalize Netflix plan metadata while preserving ad-supported variants."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    normalized = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    tier = next(
        (name for name in ("Premium", "Standard", "Basic") if name.lower() in normalized),
        None,
    )
    if not tier:
        return raw

    has_ads = (
        " ads" in f" {normalized}"
        or "ad supported" in normalized
        or "withadvert" in normalized.replace(" ", "")
    )
    return f"{tier} with Ads" if has_ads else tier


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
                    metadata_plan = (
                        _falcor_val(curr.get('planName'))
                        or _falcor_val(curr.get('planType'))
                    )
                    if metadata_plan:
                        account_info['plan'] = normalize_netflix_plan(metadata_plan)
                    if max_streams is not None:
                        try:
                            n = int(max_streams)
                            account_info['max_streams'] = n
                        except (ValueError, TypeError):
                            pass
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
                                account_info['plan'] = normalize_netflix_plan(
                                    _falcor_val(model_data[pk])
                                )
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
                                account_info['plan'] = normalize_netflix_plan(
                                    _falcor_val(ya_jg[pk])
                                )
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
                                    account_info['plan'] = normalize_netflix_plan(txt)
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

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "message": "Cookie Checker API",
        "version": "1.0.0"
    }

@app.post("/api/check-cookies", response_model=CookieCheckResponse)
async def check_cookies(
    request: CookieCheckRequest
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
    file: UploadFile = File(...)
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
    request: NetflixTokenRequest
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
        
        bundles, bundle_errors = parse_cookie_bundles(request.cookies_text, format_type)
        if not bundles:
            return NetflixTokenResponse(
                success=False,
                error="No cookie bundles parsed from input"
            )

        async def generate_bundle_token(bundle_number: int, bundle_cookies: List[Cookie]) -> dict:
            cookies_dict = {cookie.name: cookie.value for cookie in bundle_cookies}
            has_netflix_id = any(name.lower() == "netflixid" for name in cookies_dict)
            if not has_netflix_id:
                return {
                    "bundle_number": bundle_number,
                    "success": False,
                    "error": "Missing required cookie (NetflixId)",
                    "cookie_count": len(bundle_cookies),
                }

            # Playwright is useful for a single partial export, but launching a
            # browser for every bundle would make large imports impractical.
            if request.use_playwright and len(bundles) == 1:
                logger.info("Using Playwright to get full cookie header...")
                browser_cookies, playwright_error = await get_browser_cookies_with_playwright(cookies_dict)
                if not playwright_error:
                    cookies_dict = browser_cookies
                else:
                    logger.warning(f"Playwright error: {playwright_error}")

            success, token, error = await generate_nftoken(cookies_dict)
            return {
                "bundle_number": bundle_number,
                "success": success,
                "nftoken": token,
                "error": error,
                "cookie_count": len(bundle_cookies),
            }

        token_results = await asyncio.gather(*[
            generate_bundle_token(index, bundle_cookies)
            for index, (bundle_cookies, _) in enumerate(bundles, 1)
        ])
        successful_tokens = [
            result for result in token_results
            if result.get("success") and result.get("nftoken")
        ]
        cookie_bundles = [
            {
                "bundle_number": index,
                "cookies": [cookie.model_dump() for cookie in bundle_cookies],
            }
            for index, (bundle_cookies, _) in enumerate(bundles, 1)
        ]
        first_token = successful_tokens[0] if successful_tokens else {}
        total_cookies = sum(len(bundle_cookies) for bundle_cookies, _ in bundles)
        error = None
        if not successful_tokens:
            error = "No usable Netflix tokens were generated from the cookie bundles."
            if bundle_errors:
                error = bundle_errors[0]
        
        return NetflixTokenResponse(
            success=bool(successful_tokens),
            nftoken=first_token.get("nftoken"),
            error=error,
            cookies=cookies,
            cookie_bundles=cookie_bundles,
            cookie_count=total_cookies,
            tokens=token_results,
            token_count=len(successful_tokens),
            bundle_count=len(bundles),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating token: {str(e)}")

@app.post("/api/get-account-info", response_model=NetflixAccountInfo)
async def get_account_info(
    request: CookieCheckRequest
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
        
        bundles, bundle_errors = parse_cookie_bundles(request.cookies_text, format_type)
        if not bundles:
            return NetflixAccountInfo(
                success=False,
                error="No cookie bundles parsed from input"
            )

        if len(bundles) > LARGE_IMPORT_ACCOUNT_LOOKUP_THRESHOLD:
            total_cookies = sum(len(bundle_cookies) for bundle_cookies, _ in bundles)
            account_results = [
                {
                    "bundle_number": index,
                    "cookie_count": len(bundle_cookies),
                    "success": False,
                    "error": (
                        "Account details skipped for this large import; "
                        "live status is determined by token validation."
                    ),
                }
                for index, (bundle_cookies, _) in enumerate(bundles, 1)
            ]
            return NetflixAccountInfo(
                success=False,
                error=(
                    "Account details were skipped for this large import. "
                    "Live status is determined by token validation."
                ),
                accounts=account_results,
                account_count=len(account_results),
                bundle_count=len(bundles),
                checked_cookie_count=total_cookies,
            )

        lookup_semaphore = asyncio.Semaphore(4)

        async def lookup_bundle(bundle_number: int, bundle_cookies: List[Cookie]) -> dict:
            result = {
                "bundle_number": bundle_number,
                "cookie_count": len(bundle_cookies),
                "success": False,
            }
            cookies_dict = {cookie.name: cookie.value for cookie in bundle_cookies}
            if not any(name.lower() == "netflixid" for name in cookies_dict):
                result["error"] = "Missing required cookie (NetflixId)"
                return result

            async with lookup_semaphore:
                try:
                    success, account_info, error = await asyncio.wait_for(
                        get_netflix_account_info(cookies_dict),
                        timeout=60,
                    )
                except asyncio.TimeoutError:
                    success, account_info, error = (
                        False,
                        None,
                        "Account lookup timed out",
                    )

            result["success"] = success and bool(account_info)
            if account_info:
                result.update({
                    "email": account_info.get("email"),
                    "country": account_info.get("country"),
                    "plan": account_info.get("plan"),
                    "subscription_status": account_info.get("subscription_status"),
                    "billing_date": account_info.get("billing_date"),
                    "account_created_date": account_info.get("account_created_date"),
                    "payment_method": account_info.get("payment_method"),
                    "streaming_quality": account_info.get("streaming_quality"),
                    "profiles": account_info.get("profiles"),
                })
            if error:
                result["error"] = error
            return result

        account_results = await asyncio.gather(*[
            lookup_bundle(index, bundle_cookies)
            for index, (bundle_cookies, _) in enumerate(bundles, 1)
        ])
        successful_accounts = [
            result for result in account_results if result.get("success")
        ]
        first_account = successful_accounts[0] if successful_accounts else {}
        total_cookies = sum(len(bundle_cookies) for bundle_cookies, _ in bundles)
        error = None
        if not successful_accounts:
            error = "Could not extract account information from the cookie bundles."
            if bundle_errors:
                error = bundle_errors[0]

        return NetflixAccountInfo(
            success=bool(successful_accounts),
            email=first_account.get("email"),
            country=first_account.get("country"),
            plan=first_account.get("plan"),
            subscription_status=first_account.get("subscription_status"),
            billing_date=first_account.get("billing_date"),
            account_created_date=first_account.get("account_created_date"),
            payment_method=first_account.get("payment_method"),
            streaming_quality=first_account.get("streaming_quality"),
            profiles=first_account.get("profiles"),
            error=error,
            accounts=account_results,
            account_count=len(account_results),
            bundle_count=len(bundles),
            checked_cookie_count=total_cookies,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting account info: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
