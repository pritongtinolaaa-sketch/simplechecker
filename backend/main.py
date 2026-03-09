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

    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])

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

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.post(
                'https://android13.prod.ftl.netflix.com/graphql',
                headers=nft_headers,
                json=payload
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data and data['data'] and 'createAutoLoginToken' in data['data']:
                    token = data['data']['createAutoLoginToken']
                    return True, token, None
                elif 'errors' in data:
                    return False, None, f"API Error: {json.dumps(data.get('errors', []))}"
                else:
                    return False, None, "Unexpected response"
            else:
                return False, None, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, None, str(e)

async def get_netflix_account_info(cookies: dict) -> tuple[bool, Optional[dict], Optional[str]]:
    """Extract Netflix account information from cookies"""
    # Normalize cookie names
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v

    netflix_id = norm.get('NetflixId') or norm.get('netflixid')
    secure_id = norm.get('SecureNetflixId') or norm.get('securenetflixid')

    if not netflix_id or not secure_id:
        return False, None, "Missing required cookies (NetflixId, SecureNetflixId)"

    cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Origin': 'https://www.netflix.com',
        'Referer': 'https://www.netflix.com/',
        'Cookie': cookie_str
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Try to get account info from the Netflix API
            resp = await http_client.get(
                'https://www.netflix.com/api/shakti/v1e9e8b93/pathEvaluator?withSize=true&materialize=true&model=harris',
                headers=headers,
                params={
                    'path': json.dumps([
                        ['accountInfo', ['email', 'countryOfSignup', 'membershipStatus', 'createdDate']],
                        ['currentAccount', ['planName', 'planType', 'maxStreamingQuality', 'maxUserLimit']],
                        ['paymentData', ['lastPaymentDate', 'nextPaymentDate', 'billingMethod', 'paymentMethods']]
                    ])
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                account_info = {}
                
                # Extract account information from the response
                try:
                    if 'jsonGraph' in data:
                        json_graph = data['jsonGraph']
                        
                        # Extract email and account details
                        if 'accountInfo' in json_graph:
                            acc_info = json_graph['accountInfo']
                            if 'email' in acc_info and 'value' in acc_info['email']:
                                account_info['email'] = acc_info['email']['value']
                            if 'countryOfSignup' in acc_info and 'value' in acc_info['countryOfSignup']:
                                account_info['country'] = acc_info['countryOfSignup']['value']
                            if 'membershipStatus' in acc_info and 'value' in acc_info['membershipStatus']:
                                account_info['subscription_status'] = acc_info['membershipStatus']['value']
                            if 'createdDate' in acc_info and 'value' in acc_info['createdDate']:
                                # Format date if it's a timestamp
                                created = acc_info['createdDate']['value']
                                if isinstance(created, (int, float)):
                                    from datetime import datetime
                                    created = datetime.utcfromtimestamp(created / 1000).strftime('%Y-%m-%d')
                                account_info['account_created_date'] = str(created)
                        
                        # Extract plan and streaming quality info
                        if 'currentAccount' in json_graph:
                            curr_acc = json_graph['currentAccount']
                            if 'planName' in curr_acc and 'value' in curr_acc['planName']:
                                account_info['plan'] = curr_acc['planName']['value']
                            elif 'planType' in curr_acc and 'value' in curr_acc['planType']:
                                account_info['plan'] = curr_acc['planType']['value']
                            if 'maxStreamingQuality' in curr_acc and 'value' in curr_acc['maxStreamingQuality']:
                                account_info['streaming_quality'] = curr_acc['maxStreamingQuality']['value']
                        
                        # Extract payment info
                        if 'paymentData' in json_graph:
                            payment = json_graph['paymentData']
                            if 'nextPaymentDate' in payment and 'value' in payment['nextPaymentDate']:
                                next_payment = payment['nextPaymentDate']['value']
                                if isinstance(next_payment, (int, float)):
                                    from datetime import datetime
                                    next_payment = datetime.utcfromtimestamp(next_payment / 1000).strftime('%Y-%m-%d')
                                account_info['billing_date'] = str(next_payment)
                            if 'paymentMethods' in payment and 'value' in payment['paymentMethods']:
                                methods = payment['paymentMethods']['value']
                                if isinstance(methods, list) and len(methods) > 0:
                                    method = methods[0]
                                    if isinstance(method, dict):
                                        method_type = method.get('type', 'Unknown')
                                        last4 = method.get('last4', '')
                                        if last4:
                                            account_info['payment_method'] = f"{method_type} ****{last4}"
                                        else:
                                            account_info['payment_method'] = method_type
                    
                    # Try alternate API endpoint if first one didn't work
                    if not account_info:
                        resp2 = await http_client.get(
                            'https://www.netflix.com/AccountSettings',
                            headers=headers
                        )
                        
                        if resp2.status_code == 200:
                            # Try to parse from HTML/JSON if available
                            # This is a fallback - the API endpoint should work better
                            pass
                    
                    # Get profile information
                    resp_profiles = await http_client.get(
                        'https://www.netflix.com/api/shakti/v1e9e8b93/profiles',
                        headers=headers
                    )
                    
                    if resp_profiles.status_code == 200:
                        profiles_data = resp_profiles.json()
                        if 'profiles' in profiles_data:
                            account_info['profiles'] = [
                                {
                                    'name': p.get('firstName', 'Unknown'),
                                    'isKids': p.get('isKids', False),
                                    'guid': p.get('guid', '')
                                }
                                for p in profiles_data['profiles']
                            ]
                    
                    if account_info:
                        return True, account_info, None
                    else:
                        return False, None, "Could not extract account information from response"
                        
                except Exception as parse_error:
                    return False, None, f"Error parsing account data: {str(parse_error)}"
            else:
                return False, None, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, None, f"Request error: {str(e)}"

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
