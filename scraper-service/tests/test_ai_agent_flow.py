"""
测试采集引擎原生智能体 AI 生态能力接入 (Engine Native AI Agent Test Suite)

测试范围:
1. 智能体配置读取与更新 (/api/v1/engine/ai/config)
2. 智能采集规约生成 (/api/v1/engine/ai/generate-spec)
3. 智能数据清洗与语义增强 (/api/v1/engine/ai/enrich-data)
4. 异常反爬诊断与自愈建议 (/api/v1/engine/ai/diagnose)
5. 智能体问答交互 (/api/v1/engine/ai/chat)
6. FlowEngine DAG 内置 AI 组件 (AI_EXTRACT, AI_ENRICH, AI_FILTER) 真实管线执行
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.database import init_db
from app.main import app
from app.models import FlowComponentConfig, FlowConfig
from app.flow_engine import FlowEngine, FlowContext


class TestAiAgentFlow(unittest.TestCase):
    def setUp(self):
        init_db()
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        self._client_cm.__exit__(None, None, None)


    def test_01_ai_config_crud(self):
        """测试 AI 智能体配置读写"""
        # 读取配置
        r = self.client.get("/api/v1/engine/ai/config")
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        self.assertIn("api_base", res["data"])

        # 更新配置
        update_payload = {
            "model": "deepseek-v3",
            "temperature": 0.5,
            "maxTokens": 4096
        }
        r = self.client.post("/api/v1/engine/ai/config", json=update_payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        self.assertEqual(res["data"]["model"], "deepseek-v3")
        self.assertEqual(res["data"]["temperature"], 0.5)

    def test_02_ai_generate_spec(self):
        """测试自然语言智能生成爬虫规约"""
        payload = {
            "intent": "帮我采集科技新闻列表，需要包含文章标题、原文链接、发布作者与阅读量",
            "entryUrl": "https://tech.example.com/news",
            "htmlSample": "<div class='list-item'><a class='title' href='/n/1'>大模型新突破</a><span class='author'>张三</span></div>"
        }
        r = self.client.post("/api/v1/engine/ai/generate-spec", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        spec = res["data"]
        self.assertIn("fields", spec)
        self.assertIn("pipeline", spec)
        field_names = [f["name"] for f in spec["fields"]]
        self.assertIn("title", field_names)
        self.assertIn("url", field_names)

    def test_03_ai_enrich_data(self):
        """测试批量数据 AI 语义清洗与增强"""
        sample_records = [
            {"title": "OpenAI 推出全新 o3 系列推理模型", "category": "tech"},
            {"title": "春季家常菜谱大全做法分享", "category": "food"}
        ]
        payload = {
            "records": sample_records,
            "instruction": "提取核心标签、情感正负向与20字摘要"
        }
        r = self.client.post("/api/v1/engine/ai/enrich-data", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        enriched = res["data"]
        self.assertEqual(len(enriched), 2)
        for item in enriched:
            self.assertIn("ai_tags", item)
            self.assertIn("ai_sentiment", item)

    def test_04_ai_diagnose(self):
        """测试采集反爬智能诊断"""
        payload = {
            "jobName": "电商秒杀采集",
            "errorMsg": "HTTP 403 Forbidden: Cloudflare Turnstile verification required",
            "snippet": "<html><title>Just a moment...</title></html>"
        }
        r = self.client.post("/api/v1/engine/ai/diagnose", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        diag = res["data"]
        self.assertIn("cause", diag)
        self.assertIn("recommended_action", diag)

    def test_05_ai_chat(self):
        """测试采集智能体交互问答"""
        payload = {
            "prompt": "如果目标网站存在动态无限瀑布流加载，推荐采用什么样的抓取策略？"
        }
        r = self.client.post("/api/v1/engine/ai/chat", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        self.assertIn("reply", res["data"])
        self.assertTrue(len(res["data"]["reply"]) > 0)

    def test_06_flow_engine_ai_components(self):
        """测试 FlowEngine DAG 流程原生运行 AI 组件 (AI_ENRICH 语义增强)"""
        import asyncio
        engine = FlowEngine()
        
        flow_config = FlowConfig(
            firstComponentId="c1",
            components=[
                FlowComponentConfig(
                    componentId="c1",
                    componentType="AI_ENRICH",
                    params={"instruction": "对科技内容提取核心语义标签"},
                    nextComponentId="c2"
                ),
                FlowComponentConfig(
                    componentId="c2",
                    componentType="RESULT_OUTPUT",
                    params={},
                    nextComponentId=None
                )
            ]
        )

        initial_metadata = {
            "flowContext": {
                "records": [
                    {"title": "DeepCloud 架构演进全纪录", "summary": "纯 Python 引擎与 AI 智能体生态接入"}
                ]
            }
        }

        result = asyncio.run(engine.execute(flow_config, metadata=initial_metadata))
        self.assertTrue(result.success)
        self.assertEqual(len(result.records), 1)
        first_rec = result.records[0]
        self.assertIn("title", first_rec)
        self.assertIn("ai_tags", first_rec)

    def test_07_mcp_registration_and_invoke(self):
        """测试向 Hub 宣告能力清单以及响应 Hub 的动态工具回调"""
        # 1. 验证能力清单 Manifest
        r = self.client.get("/api/v1/engine/mcp/manifest")
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertEqual(res["code"], "200")
        manifest = res["data"]
        self.assertEqual(manifest["service_name"], "scraper_engine")
        self.assertEqual(len(manifest["tools"]), 4)

        # 2. 模拟 Hub.rs 发起 engine_create_and_run_job 调用
        invoke_payload = {
            "tool": "engine_create_and_run_job",
            "arguments": {
                "jobName": "copilot_bilibili_test",
                "source": "bilibili",
                "description": "由 Copilot 伴随智能体创建",
                "spec": {
                    "entryUrl": "https://api.bilibili.com/x/web-interface/ranking/v2",
                    "fields": [{"name": "title", "selector": "title"}]
                }
            }
        }
        r = self.client.post("/api/v1/engine/mcp/invoke", json=invoke_payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertTrue(res["success"])
        self.assertIn("jobId", res["result"])
        self.assertEqual(res["clientAction"]["type"], "REFRESH_VIEW")
        self.assertEqual(res["clientAction"]["target"], "job_table")

        # 3. 模拟 Hub.rs 发起 engine_query_raw_data 调用
        query_payload = {
            "tool": "engine_query_raw_data",
            "arguments": {"limit": 5}
        }
        r = self.client.post("/api/v1/engine/mcp/invoke", json=query_payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertTrue(res["success"])
        self.assertIn("records", res["result"])


if __name__ == "__main__":
    unittest.main()

