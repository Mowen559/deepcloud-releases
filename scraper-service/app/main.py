"""
deepcloud-engine：纯 Python 独立数据采集与页面适配引擎

集控制面（任务管理、声明式 Spec 校验、本地 SQLite 存储、APScheduler 调度）
与执行面（Scrapling 自适应自愈、Playwright 浏览器自动化、curl_cffi、FlowEngine DAG）于一体。

启动：
    uvicorn app.main:app --host 0.0.0.0 --port 18000
或打包后直接运行 deepcloud-engine.exe（见 build-exe.ps1）
"""

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .api import api_router
from .api.mcp import auto_register_to_hub
from .core import (
    ADAPTIVE_DB_DIR,
    BROWSER_IDLE_TIMEOUT,
    HEADLESS,
    MAX_PAGES,
    REUSE_BROWSER,
    SCRAPER_HOST,
    SCRAPER_LOG_LEVEL,
    SCRAPER_PORT,
    assert_safe_url,
    _assert_safe_url,
    ok,
    state,
)
from .database import init_db
from .fetcher import ScraperEngine
from .flow_engine import FlowEngine
from .job_service import JobService
from .scheduler import LocalScheduler
from .webapp_service import DataSourceService, WebAppService

logging.basicConfig(
    level=SCRAPER_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scraper")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 1. 初始化本地 SQLite
    init_db()

    # 2. 初始化自适应指纹库目录
    if ADAPTIVE_DB_DIR:
        os.makedirs(ADAPTIVE_DB_DIR, exist_ok=True)
        os.chdir(ADAPTIVE_DB_DIR)
        log.info("[scraper] adaptive 指纹库目录: %s", ADAPTIVE_DB_DIR)

    # 3. 初始化抓取与流程引擎单例
    state.engine = ScraperEngine(
        reuse_browser=REUSE_BROWSER,
        max_pages=MAX_PAGES,
        headless=HEADLESS,
        idle_timeout_seconds=BROWSER_IDLE_TIMEOUT,
    )
    state.flow_engine = FlowEngine(scraper_engine=state.engine, url_validator=assert_safe_url)
    state.job_service = JobService(flow_engine=state.flow_engine)
    state.ds_service = DataSourceService()
    state.webapp_service = WebAppService()

    # 4. 启动本地定时调度器
    state.scheduler = LocalScheduler(job_service=state.job_service, check_interval_seconds=15)
    await state.scheduler.start()

    # 5. 向 Hub.rs 异步宣告注册插件能力
    asyncio.create_task(auto_register_to_hub())

    log.info(
        "[scraper] deepcloud-engine (纯 Python) 启动就绪: reuse_browser=%s max_pages=%s idle_timeout=%.1fs",
        REUSE_BROWSER,
        MAX_PAGES,
        BROWSER_IDLE_TIMEOUT,
    )

    try:
        yield
    finally:
        if state.scheduler:
            await state.scheduler.stop()
        if state.engine is not None:
            await state.engine.close()
        log.info("[scraper] deepcloud-engine 已平稳关闭")


app = FastAPI(
    title="deepcloud-engine",
    description="DeepCloud 纯 Python 独立数据采集与页面适配引擎",
    version="2.0.0",
    lifespan=lifespan,
)

# 允许桌面端跨域通信
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    scraplingVersion: str
    reuseBrowser: bool
    maxPages: int


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查接口"""
    try:
        import scrapling

        v = getattr(scrapling, "__version__", "unknown")
    except Exception:
        v = "unknown"

    return HealthResponse(
        status="UP",
        scraplingVersion=v,
        reuseBrowser=REUSE_BROWSER,
        maxPages=MAX_PAGES,
    )


# 挂载各领域拆分路由
app.include_router(api_router)


# ----------------------------------------------------------------------
# 模块向后兼容代理（满足测试与遗留引用）
# ----------------------------------------------------------------------
def __getattr__(name: str) -> Any:
    if hasattr(state, name):
        return getattr(state, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def main() -> None:
    """打包执行入口"""
    import uvicorn

    uvicorn.run(
        app,
        host=SCRAPER_HOST,
        port=SCRAPER_PORT,
        log_level=SCRAPER_LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
