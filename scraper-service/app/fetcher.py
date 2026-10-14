"""
Scrapling 封装：三种抓取模式 + 浏览器实例复用

服务化相对「每次起子进程」的主要收益就在这里——浏览器可以常驻复用，
省掉每次约 1~3 秒的 Python 解释器 + Chromium 启动开销。
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from .models import ScrapeRequest

log = logging.getLogger(__name__)

MODE_STATIC = "static"
MODE_DYNAMIC = "dynamic"
MODE_STEALTHY = "stealthy"
VALID_MODES = (MODE_STATIC, MODE_DYNAMIC, MODE_STEALTHY)


class BrowserPool:
    """
    常驻无头浏览器与 Context 复用池 (Browser Context Pool)

    并发控制与生命周期管理：
    - ``max_pages``：通过 asyncio.Semaphore(max_pages) 限制最大并发标签页租借，避免无节制开 Tab 导致 OOM；
    - 并发指标：追踪活跃租借数 active_leases、历史租借总量 total_acquired、峰值并发 peak_concurrent；
    - 空闲超时回收 (Idle Eviction)：通过后台协程 _scavenger_loop 定期检查，当 active_leases == 0 且
      空闲时长超过 idle_timeout_seconds 时，自动优雅关闭 Chromium 进程释放内存；
    - 透明重建：新抓取请求到达时通过双检锁透明重建浏览器，兼顾高吞吐与空闲期系统资源节约。
    """

    def __init__(self, mode: str, max_pages: int, headless: bool = True,
                 idle_timeout_seconds: float = 300.0):
        self._mode = mode
        self._max_pages = max_pages
        self._headless = headless
        self._idle_timeout_seconds = idle_timeout_seconds
        self._session: Optional[Any] = None
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(max_pages)

        # 监控指标与时标
        self._active_leases: int = 0
        self._total_acquired: int = 0
        self._total_released: int = 0
        self._total_errors: int = 0
        self._peak_concurrent: int = 0
        self._last_active_at: float = time.time()
        self._created_at: Optional[float] = None
        self._scavenger_task: Optional[asyncio.Task] = None

    async def fetch(self, url: str, **kwargs: Any) -> Any:
        async with self._sem:
            async with self._lock:
                self._active_leases += 1
                self._total_acquired += 1
                if self._active_leases > self._peak_concurrent:
                    self._peak_concurrent = self._active_leases
                self._last_active_at = time.time()

            try:
                session = await self._ensure_session()
                return await session.fetch(url, **kwargs)
            except Exception:
                async with self._lock:
                    self._total_errors += 1
                # 会话可能已崩溃，丢弃让下次重建；异常继续上抛由调用方决定降级
                await self._discard()
                raise
            finally:
                async with self._lock:
                    self._active_leases = max(0, self._active_leases - 1)
                    self._total_released += 1
                    self._last_active_at = time.time()

    async def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session

        # 双检 + 锁：并发首请求下只建一个浏览器
        async with self._lock:
            if self._session is not None:
                return self._session

            session_cls = self._session_class()
            session = session_cls(
                headless=self._headless,
                max_pages=self._max_pages,
            )
            await session.__aenter__()
            self._session = session
            self._created_at = time.time()
            self._last_active_at = time.time()
            log.info("[scraper] 已启动常驻浏览器会话 mode=%s max_pages=%s idle_timeout=%.1fs",
                     self._mode, self._max_pages, self._idle_timeout_seconds)

            # 启动空闲超时巡检协程
            if self._scavenger_task is None or self._scavenger_task.done():
                self._scavenger_task = asyncio.create_task(self._scavenger_loop())

            return session

    def _session_class(self):
        from scrapling.fetchers import AsyncDynamicSession, AsyncStealthySession

        return AsyncStealthySession if self._mode == MODE_STEALTHY else AsyncDynamicSession

    async def _scavenger_loop(self) -> None:
        """后台空闲超时巡检协程：当无活跃租借且空闲超过设定秒数时，回收 Chromium 进程"""
        check_interval = max(0.05, min(30.0, self._idle_timeout_seconds / 4))
        try:
            while True:
                await asyncio.sleep(check_interval)
                async with self._lock:
                    if self._session is not None and self._active_leases == 0:
                        idle_duration = time.time() - self._last_active_at
                        if idle_duration >= self._idle_timeout_seconds:
                            log.info("[scraper] 浏览器会话空闲超过 %.1fs (阈值 %.1fs)，自动回收进程释放内存: mode=%s",
                                     idle_duration, self._idle_timeout_seconds, self._mode)
                            session, self._session = self._session, None
                            self._created_at = None
                            if session is not None:
                                try:
                                    await session.__aexit__(None, None, None)
                                except Exception as e:
                                    log.warning("[scraper] 空闲回收关闭会话时报错（已忽略）: %s", e)
                            break
        except asyncio.CancelledError:
            pass

    async def _discard(self) -> None:
        async with self._lock:
            session, self._session = self._session, None
            self._created_at = None
        if session is None:
            return
        try:
            await session.__aexit__(None, None, None)
        except Exception as e:
            log.warning("[scraper] 关闭失效会话时报错（已忽略）: %s", e)

    def get_stats(self) -> Dict[str, Any]:
        """获取当前复用池指标与状态"""
        now = time.time()
        is_alive = self._session is not None
        idle_seconds = round(now - self._last_active_at, 1) if (is_alive and self._active_leases == 0) else 0.0
        uptime_seconds = round(now - self._created_at, 1) if (is_alive and self._created_at) else 0.0

        return {
            "mode": self._mode,
            "maxPages": self._max_pages,
            "activeLeases": self._active_leases,
            "totalAcquired": self._total_acquired,
            "totalReleased": self._total_released,
            "totalErrors": self._total_errors,
            "peakConcurrent": self._peak_concurrent,
            "isSessionAlive": is_alive,
            "uptimeSeconds": uptime_seconds,
            "idleSeconds": idle_seconds,
            "idleTimeoutSeconds": self._idle_timeout_seconds,
        }

    async def close(self) -> None:
        if self._scavenger_task and not self._scavenger_task.done():
            self._scavenger_task.cancel()
        await self._discard()


class ScraperEngine:
    """按请求选择抓取方式，并把 Scrapling 的响应对象交给上层提取"""

    def __init__(self, reuse_browser: bool = True, max_pages: int = 3,
                 headless: bool = True, idle_timeout_seconds: float = 300.0):
        self._reuse_browser = reuse_browser
        self._pools: Dict[str, BrowserPool] = {}
        if reuse_browser:
            self._pools = {
                MODE_DYNAMIC: BrowserPool(MODE_DYNAMIC, max_pages, headless, idle_timeout_seconds),
                MODE_STEALTHY: BrowserPool(MODE_STEALTHY, max_pages, headless, idle_timeout_seconds),
            }
        self._headless = headless

    def get_pool_stats(self) -> Dict[str, Any]:
        return {mode: pool.get_stats() for mode, pool in self._pools.items()}

    async def close(self) -> None:
        for pool in self._pools.values():
            await pool.close()

    async def fetch(self, req: ScrapeRequest) -> Any:
        mode = (req.mode or MODE_STEALTHY).strip().lower()
        if mode not in VALID_MODES:
            raise ValueError(f"mode 只能是 {VALID_MODES} 之一，实际为 {mode!r}")

        if mode == MODE_STATIC:
            return await self._fetch_static(req)
        return await self._fetch_browser(req, mode)

    # ─────────────────────────── static ───────────────────────────

    async def _fetch_static(self, req: ScrapeRequest) -> Any:
        from scrapling.fetchers import AsyncFetcher

        kwargs: Dict[str, Any] = {
            "timeout": req.timeoutMs / 1000.0,  # 静态 Fetcher 的 timeout 单位是秒
            "stealthy_headers": True,
            "selector_config": self._selector_config(req),
        }
        headers = self._merged_headers(req)
        if headers:
            kwargs["headers"] = headers
        if req.proxy:
            kwargs["proxy"] = req.proxy

        return await AsyncFetcher.get(req.url, **kwargs)

    # ─────────────────────────── browser ───────────────────────────

    async def _fetch_browser(self, req: ScrapeRequest, mode: str) -> Any:
        kwargs = self._browser_kwargs(req, mode)

        pool = self._pools.get(mode) if self._reuse_browser else None
        if pool is not None:
            try:
                return await pool.fetch(req.url, **kwargs)
            except Exception as e:
                # 复用会话失败：降级为一次性 fetch，保证本次请求仍有机会成功
                log.warning("[scraper] 复用会话失败，降级为一次性抓取: %s", e)

        return await self._fetch_once(req, mode, kwargs)

    async def _fetch_once(self, req: ScrapeRequest, mode: str,
                          kwargs: Dict[str, Any]) -> Any:
        from scrapling.fetchers import DynamicFetcher, StealthyFetcher

        fetcher = StealthyFetcher if mode == MODE_STEALTHY else DynamicFetcher
        return await fetcher.async_fetch(req.url, headless=self._headless, **kwargs)

    def _browser_kwargs(self, req: ScrapeRequest, mode: str) -> Dict[str, Any]:
        browser = req.browser
        kwargs: Dict[str, Any] = {
            # 浏览器系 fetcher 的 timeout 单位是毫秒（与静态 Fetcher 的秒不同，易错）
            "timeout": req.timeoutMs,
            "network_idle": browser.networkIdle,
            "disable_resources": browser.disableResources,
            "selector_config": self._selector_config(req),
        }
        if browser.waitSelector:
            kwargs["wait_selector"] = browser.waitSelector
        if browser.waitMs and browser.waitMs > 0:
            kwargs["wait"] = browser.waitMs
        if req.proxy:
            kwargs["proxy"] = req.proxy

        headers = self._merged_headers(req)
        if headers:
            kwargs["extra_headers"] = headers

        # solve_cloudflare 仅 Stealthy 系列支持，传给 Dynamic 会因未知参数报错
        if mode == MODE_STEALTHY and browser.solveCloudflare:
            kwargs["solve_cloudflare"] = True

        return kwargs

    # ─────────────────────────── 公共 ───────────────────────────

    def _selector_config(self, req: ScrapeRequest) -> Dict[str, Any]:
        """
        开启选择器自愈所需的配置

        必须走 ``selector_config`` 逐请求传，不能用类级的 ``Fetcher.configure(adaptive=True)``：

        1. 类级 configure 对 Session 实例无效——实测下会报
           "Argument ``auto_save`` will be ignored because ``adaptive`` wasn't enabled"，
           也就是自愈静默失效；
        2. 类级 configure 是全局可变状态，并发请求会互相覆盖对方的 adaptive 设置。

        selector_config 会被透传给 Selector 构造（其中 adaptive_domain 被特殊处理为替换 url）。
        """
        config: Dict[str, Any] = {"adaptive": req.adaptive}
        if req.adaptiveDomain:
            config["adaptive_domain"] = req.adaptiveDomain
        return config

    def _merged_headers(self, req: ScrapeRequest) -> Dict[str, str]:
        """把 cookies 合进请求头：上游 engine-service 传的是原始 Cookie 头字符串"""
        headers = dict(req.headers or {})
        if req.cookies:
            headers.setdefault("Cookie", req.cookies)
        return headers
