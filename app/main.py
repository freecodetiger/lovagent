"""
FastAPI 应用入口
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import wecom


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的初始化逻辑
    print(f"🚀 恋爱 Agent 启动中...")
    print(f"📍 服务地址: http://{settings.server_host}:{settings.server_port}")
    print(f"🔗 企业微信回调地址: http://100.100.191.48:{settings.server_port}/wecom/callback")

    yield

    # 关闭时的清理逻辑
    print("👋 恋爱 Agent 关闭中...")


app = FastAPI(
    title="恋爱 Agent",
    description="通过企业微信接入个人微信的恋爱伴侣 Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(wecom.router, prefix="/wecom", tags=["企业微信"])


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