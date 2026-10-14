"""
FastAPI REST 接口集成测试 (验证与前端契约 code=="200" 严格对齐)
"""

import os
import shutil
import tempfile
import unittest

TEST_TMP_DIR = tempfile.mkdtemp(prefix="deepcloud_api_test_")
os.environ["DEEPCLOUD_ENGINE_DB"] = os.path.join(TEST_TMP_DIR, "test_api_engine.db")

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


class TestEngineAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)

    def test_health_check(self):
        with TestClient(app) as client:
            resp = client.get("/health")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "UP")

    def test_jobs_api_contract(self):
        """测试 /api/v1/engine/jobs 的全链路与前端拦截器契约 (code=="200")"""
        with TestClient(app) as client:
            # 1. 创建任务
            create_payload = {
                "jobName": "api_test_job",
                "source": "contract_test",
                "description": "契约测试任务",
                "loaderType": "HTTP_CLIENT",
                "spec": {
                    "loader": {"url": "https://example.com/items"},
                    "container": "div.item",
                    "fieldMappings": [
                        {"targetField": "title", "selector": "h1", "type": "CSS_SELECTOR"}
                    ]
                }
            }
            res = client.post("/api/v1/engine/jobs", json=create_payload)
            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertEqual(body["code"], "200")  # 铁律：code 必须为字符串 "200"
            job_id = body["data"]["id"]
            self.assertIsInstance(job_id, int)

            # 2. 获取任务详情
            get_res = client.get(f"/api/v1/engine/jobs/{job_id}")
            self.assertEqual(get_res.status_code, 200)
            get_body = get_res.json()
            self.assertEqual(get_body["code"], "200")
            self.assertEqual(get_body["data"]["jobName"], "api_test_job")
            self.assertEqual(get_body["data"]["spec"]["loader"]["url"], "https://example.com/items")

            # 3. 分页查询
            page_res = client.get("/api/v1/engine/jobs?pageNum=1&pageSize=10")
            self.assertEqual(page_res.status_code, 200)
            page_body = page_res.json()
            self.assertEqual(page_body["code"], "200")
            self.assertGreaterEqual(page_body["data"]["total"], 1)

            # 4. 状态启停
            status_res = client.patch(f"/api/v1/engine/jobs/{job_id}/status?status=1")
            self.assertEqual(status_res.status_code, 200)
            self.assertEqual(status_res.json()["code"], "200")

            # 5. 更新任务
            update_payload = {
                "jobName": "api_test_job_renamed",
                "spec": {"loader": {"url": "https://example.com/updated"}}
            }
            update_res = client.put(f"/api/v1/engine/jobs/{job_id}", json=update_payload)
            self.assertEqual(update_res.status_code, 200)
            self.assertEqual(update_res.json()["code"], "200")

            # 6. 删除任务
            del_res = client.delete(f"/api/v1/engine/jobs/{job_id}")
            self.assertEqual(del_res.status_code, 200)
            self.assertEqual(del_res.json()["code"], "200")


if __name__ == "__main__":
    unittest.main()
