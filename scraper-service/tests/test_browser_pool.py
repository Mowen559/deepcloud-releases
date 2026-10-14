"""
BrowserPool 浏览器复用池并发与空闲超时回收单元测试 (基于 unittest.IsolatedAsyncioTestCase)
"""

import asyncio
import unittest
from app.fetcher import BrowserPool, ScraperEngine, MODE_DYNAMIC, MODE_STEALTHY


class MockSession:
    def __init__(self, mode="dynamic", **kwargs):
        self.mode = mode
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exited = True

    async def fetch(self, url, **kwargs):
        await asyncio.sleep(0.05)
        return f"<html>Mock content for {url}</html>"


class TestBrowserPool(unittest.IsolatedAsyncioTestCase):

    async def test_browser_pool_concurrency_and_metrics(self):
        pool = BrowserPool(mode=MODE_DYNAMIC, max_pages=2, headless=True, idle_timeout_seconds=60.0)
        # Mock _session_class to return MockSession
        pool._session_class = lambda: MockSession

        self.assertFalse(pool.get_stats()["isSessionAlive"])
        self.assertEqual(pool.get_stats()["activeLeases"], 0)

        # 并发发起 3 个 fetch 请求（max_pages 为 2）
        tasks = [
            asyncio.create_task(pool.fetch(f"https://example.com/page{i}"))
            for i in range(3)
        ]

        # 等待执行过程中检查活跃租借数与峰值并发
        await asyncio.sleep(0.02)
        stats = pool.get_stats()
        self.assertTrue(stats["isSessionAlive"])
        self.assertLessEqual(stats["peakConcurrent"], 2)

        results = await asyncio.gather(*tasks)
        self.assertEqual(len(results), 3)

        # 完成后活跃租借归 0，统计量正确
        stats_after = pool.get_stats()
        self.assertEqual(stats_after["activeLeases"], 0)
        self.assertEqual(stats_after["totalAcquired"], 3)
        self.assertEqual(stats_after["totalReleased"], 3)
        self.assertEqual(stats_after["totalErrors"], 0)
        self.assertEqual(stats_after["peakConcurrent"], 2)

        await pool.close()
        self.assertFalse(pool.get_stats()["isSessionAlive"])

    async def test_browser_pool_idle_timeout_eviction(self):
        # 设置快速空闲超时 0.2 秒
        pool = BrowserPool(mode=MODE_STEALTHY, max_pages=3, headless=True, idle_timeout_seconds=0.2)
        mock_inst = MockSession()
        pool._session_class = lambda: (lambda **kwargs: mock_inst)

        # 触发首次请求建立 session
        res = await pool.fetch("https://example.com/test")
        self.assertIn("Mock content", res)
        self.assertTrue(pool.get_stats()["isSessionAlive"])
        self.assertTrue(mock_inst.entered)
        self.assertFalse(mock_inst.exited)

        # 等待空闲超时触发 (0.2s + 巡检间隔)
        await asyncio.sleep(0.6)

        # 巡检后应已自动回收 session
        stats = pool.get_stats()
        self.assertFalse(stats["isSessionAlive"])
        self.assertTrue(mock_inst.exited)

        # 再次请求应透明重新启动 session
        mock_inst2 = MockSession()
        pool._session_class = lambda: (lambda **kwargs: mock_inst2)
        res2 = await pool.fetch("https://example.com/test2")
        self.assertIn("Mock content", res2)
        self.assertTrue(pool.get_stats()["isSessionAlive"])
        self.assertTrue(mock_inst2.entered)

        await pool.close()

    async def test_scraper_engine_pool_stats(self):
        engine = ScraperEngine(reuse_browser=True, max_pages=4, headless=True, idle_timeout_seconds=120.0)
        stats = engine.get_pool_stats()

        self.assertIn(MODE_DYNAMIC, stats)
        self.assertIn(MODE_STEALTHY, stats)
        self.assertEqual(stats[MODE_DYNAMIC]["maxPages"], 4)
        self.assertEqual(stats[MODE_STEALTHY]["idleTimeoutSeconds"], 120.0)

        await engine.close()


if __name__ == "__main__":
    unittest.main()
