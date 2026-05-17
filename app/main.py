"""MB Farm — FastAPI application entry point."""

import json
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import AppError
from app.core.dependencies import get_current_user
from app.routes.auth import router as auth_router
from app.routes.farm import router as farm_router
from app.routes.shop import router as shop_router
from app.routes.social import router as social_router
from app.routes.steal import router as steal_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)

# ── Jinja2 Templates Setup ───────────────────────────────────────────────────

template_dir = "templates"
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(default=True),
    enable_async=True,
)


def _tojson_filter(obj):
    """Jinja2 tojson filter that handles SQLAlchemy models."""
    if hasattr(obj, "__dict__"):
        # Convert SQLAlchemy model to dict
        data = {}
        for key, value in obj.__dict__.items():
            if key == "_sa_instance_state":
                continue
            if value is not None:
                data[key] = value
        obj = data
    return Markup(json.dumps(obj))


env.filters["tojson"] = _tojson_filter

# ── Static Files ─────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Global Exception Handler ─────────────────────────────────────────────────


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                **(exc.extra or {}),
            }
        },
    )


# ── Template Rendering Helper ────────────────────────────────────────────────


async def render_page(request: Request, template: str, context: dict | None = None):
    """Render a Jinja2 page and return an HTMLResponse."""
    ctx = context or {}
    ctx["request"] = request
    ctx["page_name"] = template.split("/")[-1].replace(".html", "").replace("_", "-")
    t = env.get_template(template)
    html = await t.render_async(**ctx)
    return HTMLResponse(content=html)


def _user_to_dict(user) -> dict:
    """Convert SQLAlchemy User model to template-safe dict."""
    return {
        "id": user.id,
        "username": user.username,
        "coins": user.coins,
        "stamina": user.stamina,
        "xp": user.xp,
        "level": user.level,
    }


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Auto-create all tables on startup (dev-only; Alembic will replace this in P1)."""
    await init_db()


# ── Page Routes (HTML) ───────────────────────────────────────────────────────


@app.get("/")
async def page_root(request: Request):
    """Redirect to farm page."""
    return RedirectResponse(url="/farm")


@app.get("/farm", response_class=HTMLResponse)
async def page_farm(
    request: Request,
    user=Depends(get_current_user),
):
    """农场首页 — 需要登录"""
    return await render_page(request, "farm.html", {"current_user": _user_to_dict(user)})


@app.get("/friend-farm", response_class=HTMLResponse)
async def page_friend_farm(
    request: Request,
    user=Depends(get_current_user),
):
    """好友农场 — 需要登录"""
    return await render_page(request, "friend_farm.html", {"current_user": _user_to_dict(user)})


@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    """登录页 — 未登录状态"""
    return await render_page(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
async def page_register(request: Request):
    """注册页 — 未登录状态"""
    return await render_page(request, "register.html")


# ── Routers (JSON API) ───────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api")
app.include_router(farm_router, prefix="/api")
app.include_router(shop_router, prefix="/api")
app.include_router(social_router, prefix="/api")
app.include_router(steal_router, prefix="/api")


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
