import secrets as secrets_module
from typing import Optional

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import settings
from services.vault import Vault

router = APIRouter(prefix="/settings", tags=["settings"])

# Vault instance pointing to configured path
vault = Vault(settings.VAULT_FILE)

# Templates
templates = Jinja2Templates(directory="templates")

# In-memory session store: session_token -> master_password
active_sessions: dict[str, str] = {}


def get_master_password(request: Request) -> Optional[str]:
    """Retrieve the master password for the active session, if valid."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return active_sessions.get(token)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def get_settings(request: Request):
    """Render the Settings & API Key Manager page."""
    is_initialized = vault.is_initialized()
    master_pwd = get_master_password(request)
    is_unlocked = False

    if is_initialized and master_pwd:
        is_unlocked = vault.verify_master_password(master_pwd)

    providers = vault.list_providers() if is_initialized else []

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "is_initialized": is_initialized,
            "is_unlocked": is_unlocked,
            "providers": providers,
            "app_name": settings.APP_NAME,
        },
    )


@router.post("/setup-password", response_class=HTMLResponse)
async def setup_password(
    request: Request,
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Initialize the master password and activate session."""
    if len(password) < 8:
        return HTMLResponse(
            """<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3.5 text-sm text-red-400">
                Master password must be at least 8 characters long.
            </div>"""
        )

    if password != confirm_password:
        return HTMLResponse(
            """<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3.5 text-sm text-red-400">
                Passwords do not match. Please verify and try again.
            </div>"""
        )

    vault.setup_master_password(password)

    # Establish active session
    token = secrets_module.token_hex(32)
    active_sessions[token] = password

    response = HTMLResponse(
        """<div class="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3.5 text-sm text-emerald-400">
            Vault successfully initialized! Unlocking...
        </div>""",
        headers={"HX-Redirect": "/settings"},
    )
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/unlock", response_class=HTMLResponse)
async def unlock_vault(
    request: Request,
    master_password: str = Form(...),
):
    """Verify master password and store in session."""
    if not vault.verify_master_password(master_password):
        return HTMLResponse(
            """<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3.5 text-sm text-red-400">
                Incorrect master password. Please try again.
            </div>"""
        )

    token = secrets_module.token_hex(32)
    active_sessions[token] = master_password

    response = HTMLResponse(
        """<div class="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3.5 text-sm text-emerald-400">
            Vault unlocked successfully! Refreshing...
        </div>""",
        headers={"HX-Redirect": "/settings"},
    )
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/lock", response_class=HTMLResponse)
async def lock_vault(request: Request):
    """Clear active session and lock the vault."""
    token = request.cookies.get("session_token")
    if token and token in active_sessions:
        del active_sessions[token]

    response = HTMLResponse(
        """<div class="rounded-lg border border-slate-700 bg-slate-800 p-3.5 text-sm text-slate-300">
            Vault locked.
        </div>""",
        headers={"HX-Redirect": "/settings"},
    )
    response.delete_cookie(key="session_token")
    return response


@router.post("/add-key", response_class=HTMLResponse)
async def add_key(
    request: Request,
    provider: str = Form(...),
    api_key: str = Form(...),
    master_password: Optional[str] = Form(None),
):
    """Encrypt and store an API key in the vault."""
    pwd = master_password or get_master_password(request)
    if not pwd or not vault.verify_master_password(pwd):
        return HTMLResponse(
            """<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                Vault is locked or invalid password. Please unlock first.
            </div>"""
        )

    try:
        vault.store_secret(pwd, provider, api_key)
    except Exception as e:
        return HTMLResponse(
            f"""<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                Failed to store key: {str(e)}
            </div>"""
        )

    providers = vault.list_providers()
    return templates.TemplateResponse(
        request=request,
        name="partials/key_list.html",
        context={"providers": providers},
    )


@router.post("/delete-key", response_class=HTMLResponse)
async def delete_key(
    request: Request,
    provider: str = Form(...),
    master_password: Optional[str] = Form(None),
):
    """Delete an API key from the vault."""
    pwd = master_password or get_master_password(request)
    if not pwd or not vault.verify_master_password(pwd):
        return HTMLResponse(
            """<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                Vault is locked or invalid password. Please unlock first.
            </div>"""
        )

    try:
        vault.delete_secret(pwd, provider)
    except Exception as e:
        return HTMLResponse(
            f"""<div class="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                Failed to delete key: {str(e)}
            </div>"""
        )

    providers = vault.list_providers()
    return templates.TemplateResponse(
        request=request,
        name="partials/key_list.html",
        context={"providers": providers},
    )
