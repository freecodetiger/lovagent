"""
FastAPI 应用入口
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.models.database import init_db
from app.routers import admin, setup, wecom
from app.services.napcat_service import napcat_service
from app.services.proactive_chat_service import proactive_chat_service
from app.services.public_media_service import PUBLIC_MEDIA_DIR, PUBLIC_MEDIA_ROUTE
from app.services.tunnel_service import (
    is_invalid_autodetected_tunnel_url,
    is_quick_tunnel_url,
    tunnel_service,
)


BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_DIST_DIR = BASE_DIR / "admin-ui" / "dist"
ADMIN_INDEX_PATH = ADMIN_DIST_DIR / "index.html"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    tunnel_service.ensure_started()
    tunnel_status = tunnel_service.get_status()
    callback_base_url = tunnel_status["public_url"]
    configured_public_base_url = settings.public_base_url.strip().rstrip("/")
    if not callback_base_url and configured_public_base_url:
        if not is_quick_tunnel_url(configured_public_base_url) and not is_invalid_autodetected_tunnel_url(
            configured_public_base_url
        ):
            callback_base_url = configured_public_base_url
    callback_url = (
        f"{callback_base_url}/wecom/callback"
        if callback_base_url
        else f"http://{settings.server_host}:{settings.server_port}/wecom/callback"
    )
    logger.info("恋爱 Agent 启动中...")
    logger.info("服务地址: http://%s:%s", settings.server_host, settings.server_port)
    logger.info("企业微信回调地址: %s", callback_url)

    await napcat_service.start()
    proactive_scheduler_task = asyncio.create_task(proactive_chat_service.scheduler_loop())

    yield

    proactive_scheduler_task.cancel()
    try:
        await proactive_scheduler_task
    except asyncio.CancelledError:
        pass
    await napcat_service.stop()
    logger.info("恋爱 Agent 关闭中...")


app = FastAPI(
    title="恋爱 Agent",
    description="通过企业微信接入个人微信的恋爱伴侣 Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_dev_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.resolved_admin_session_secret,
    session_cookie=settings.admin_cookie_name,
    https_only=False,
    same_site="lax",
)

app.include_router(wecom.router, prefix="/wecom", tags=["企业微信"])
app.include_router(admin.router)
app.include_router(setup.router)

if ADMIN_DIST_DIR.exists():
    app.mount("/admin-static", StaticFiles(directory=ADMIN_DIST_DIR), name="admin_static")

PUBLIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount(PUBLIC_MEDIA_ROUTE, StaticFiles(directory=PUBLIC_MEDIA_DIR), name="public_media")


@app.get("/")
async def root():
    """根路由"""
    return {
        "name": "恋爱 Agent",
        "version": "0.1.0",
        "status": "running",
        "message": "你的数字伴侣正在运行中~",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/admin", include_in_schema=False)
async def admin_index():
    """管理后台首页。"""
    if not ADMIN_INDEX_PATH.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "Admin UI is not built yet. Run `npm install && npm run build` in admin-ui."},
        )
    return FileResponse(ADMIN_INDEX_PATH)


@app.get("/setup", include_in_schema=False)
async def setup_index():
    """首次安装向导页面。"""
    if not ADMIN_INDEX_PATH.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "Admin UI is not built yet. Run `npm install && npm run build` in admin-ui."},
        )
    return FileResponse(ADMIN_INDEX_PATH)
