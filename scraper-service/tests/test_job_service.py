"""
纯 Python 引擎 JobService 与 SQLite 持久化、调度校验测试
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# 指定测试临时数据库
TEST_TMP_DIR = tempfile.mkdtemp(prefix="deepcloud_test_")
os.environ["DEEPCLOUD_ENGINE_DB"] = os.path.join(TEST_TMP_DIR, "test_engine.db")

from app.database import init_db, get_connection
from app.job_service import JobService, spec_to_flow_config
from app.scheduler import is_cron_due
from app.models import ExecutorResult


class TestPurePythonEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)

    def setUp(self):
        self.mock_flow_engine = MagicMock()
        self.job_service = JobService(flow_engine=self.mock_flow_engine)

    def test_spec_to_flow_config_conversion(self):
        """测试声明式 SpiderJobSpec 转换为 FlowEngine 组件树"""
        spec = {
            "loader": {
                "type": "HTTP_CLIENT",
                "url": "https://example.com/jobs?p={{page}}",
            },
            "container": "div.job-item",
            "fieldMappings": [
                {
                    "targetField": "title",
                    "selector": "h3.title",
                    "type": "CSS_SELECTOR",
                    "extractAttr": "text"
                },
                {
                    "targetField": "salary",
                    "selector": "span.salary",
                    "type": "CSS_SELECTOR",
                    "extractAttr": "text"
                }
            ],
            "filterConditions": [
                {
                    "field": "title",
                    "op": "NOT_EMPTY"
                }
            ]
        }

        flow = spec_to_flow_config(spec, page=2)
        self.assertEqual(flow.firstComponentId, "step_load")
        self.assertEqual(len(flow.components), 5)
        # 验证 URL 占位符替换
        load_comp = next(c for c in flow.components if c.componentId == "step_load")
        self.assertEqual(load_comp.params["url"], "https://example.com/jobs?p=2")

    def test_job_crud_lifecycle(self):
        """测试任务创建、详情查询、更新、状态变更与删除"""
        job_data = {
            "jobName": "test_crawler",
            "source": "example",
            "description": "测试任务",
            "loaderType": "HTTP_CLIENT",
            "spec": {"loader": {"url": "https://example.com"}},
            "cronExpression": "0 0 * * *",
            "status": 0,
        }

        # 1. 创建
        job_id = self.job_service.create_job(job_data)
        self.assertIsInstance(job_id, int)

        # 2. 查询
        detail = self.job_service.get_job(job_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["jobName"], "test_crawler")
        self.assertEqual(detail["spec"]["loader"]["url"], "https://example.com")
        self.assertEqual(detail["status"], 0)

        # 3. 更新
        self.job_service.update_job(job_id, {"description": "已更新描述", "status": 1})
        updated = self.job_service.get_job(job_id)
        self.assertEqual(updated["description"], "已更新描述")
        self.assertEqual(updated["status"], 1)

        # 4. 启停
        self.job_service.change_status(job_id, 0)
        self.assertEqual(self.job_service.get_job(job_id)["status"], 0)

        # 5. 分页查询
        page_res = self.job_service.page_jobs(page_num=1, page_size=10, job_name="test_crawler")
        self.assertEqual(page_res["total"], 1)
        self.assertEqual(len(page_res["records"]), 1)

        # 6. 删除
        self.job_service.delete_job(job_id)
        self.assertIsNone(self.job_service.get_job(job_id))

    def test_cron_matcher(self):
        """测试 Cron 表达式匹配器"""
        # 测试每 5 分钟
        dt1 = datetime(2026, 9, 30, 10, 15, 0)
        dt2 = datetime(2026, 9, 30, 10, 16, 0)
        self.assertTrue(is_cron_due("*/5 * * * *", dt1))
        self.assertFalse(is_cron_due("*/5 * * * *", dt2))

        # 测试指定分钟
        self.assertTrue(is_cron_due("15 10 * * *", dt1))
        self.assertFalse(is_cron_due("20 10 * * *", dt1))


if __name__ == "__main__":
    unittest.main()
