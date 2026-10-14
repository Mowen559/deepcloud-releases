"""
测试低代码平台端到端全链路闭环 (Pure Python 引擎内真实运行)

测试链路：
1. 创建采集任务 -> 模拟数据抓取入库
2. 采集数据大盘接口 (/api/v1/engine/jobs/data) 正常查询
3. 从任务一键生成数据源 (/api/v1/engine/datasources/from-job)
4. 数据源查询测试 (/api/v1/engine/datasources/{id}/query)
5. 创建低代码应用 (/api/v1/engine/webapps)
6. 组装页面组件树资源 (PageDefinition via PageVisualEditor)
7. 校验规范并发布不可变运行版本 (/publish)
8. 低代码运行时装配测试 (/api/v1/engine/webapps/{app}/pages/_entry)
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app


def run_full_lowcode_lifecycle(client):
    # 1. 创建采集任务
    job_payload = {
        "jobName": "bilibili_hot_videos",
        "source": "bilibili",
        "description": "B站热门视频排行采集",
        "loaderType": "HTTP_CLIENT",
        "spec": {
            "entryUrl": "https://api.bilibili.com/x/web-interface/ranking/v2",
            "fields": [
                {"name": "bvid", "selector": "bvid", "extractType": "JSONPATH"},
                {"name": "title", "selector": "title", "extractType": "JSONPATH"},
                {"name": "pic", "selector": "pic", "extractType": "JSONPATH"},
                {"name": "owner", "selector": "owner.name", "extractType": "JSONPATH"},
            ]
        }
    }
    r = client.post("/api/v1/engine/jobs", json=job_payload)
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    job_id = res["data"]["id"]

    # 2. 模拟数据入库 (直接向 local_raw_data 插入样本)
    from app.database import get_connection
    sample_records = [
        {"bvid": "BV1xx411c7X1", "title": "【4K珍藏】极致视觉盛宴", "pic": "https://img.bili.com/1.jpg", "owner": "影视飓风"},
        {"bvid": "BV2yy411c7X2", "title": "十分钟带你精通 Python 爬虫与低代码", "pic": "https://img.bili.com/2.jpg", "owner": "极客学院"},
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO local_raw_data (job_id, job_name, source, data_key, data_json, batch_no)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [job_id, "bilibili_hot_videos", "bilibili", "batch_001", json.dumps(sample_records, ensure_ascii=False), "B001"])
        conn.commit()

    # 3. 验证采集数据大盘接口 (/api/v1/engine/jobs/data)
    r = client.get("/api/v1/engine/jobs/data", params={"jobId": job_id})
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    assert res["data"]["total"] >= 1

    # 4. 从任务一键逆向生成数据源 (/api/v1/engine/datasources/from-job)
    ds_payload = {
        "jobId": job_id,
        "sourceCode": "ds_bili_hot",
        "sourceName": "B站热门数据源",
    }
    r = client.post("/api/v1/engine/datasources/from-job", json=ds_payload)
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    ds_id = res["data"]["id"]

    # 5. 数据源查询测试 (/api/v1/engine/datasources/{id}/query)
    r = client.post(f"/api/v1/engine/datasources/{ds_id}/query", json={})
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    records = res["data"]["records"]
    assert len(records) == 2
    assert records[0]["title"] == "【4K珍藏】极致视觉盛宴"

    # 6. 创建 WebApp 低代码应用
    app_payload = {
        "packageSpec": {
            "apiVersion": "webapp.deepcloud/v1",
            "kind": "WebAppPackage",
            "metadata": {
                "name": "bili-video-app",
                "title": "B站热门精选",
                "description": "基于低代码组装的视频聚合展示应用",
            }
        }
    }
    r = client.post("/api/v1/engine/webapps", json=app_payload)
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    app_id = res["data"]["id"]

    # 7. 组装页面组件树资源 (模拟 PageVisualEditor 保存带有数据源绑定的组件树)
    page_resource = {
        "apiVersion": "webapp.deepcloud/v1",
        "kind": "PageDefinition",
        "metadata": {"name": "_entry", "version": 1},
        "spec": {
            "route": "/",
            "title": "热门视频首页",
            "componentTree": {
                "type": "Page",
                "props": {"title": "热门视频聚合"},
                "children": [
                    {
                        "type": "SearchBar",
                        "props": {"placeholder": "搜索全站视频..."},
                        "events": {"onSearch": {"type": "NAVIGATE", "url": "/search"}}
                    },
                    {
                        "type": "VideoGrid",
                        "props": {},
                        "dataSourceBinding": {
                            "dataSourceRef": "ds_bili_hot",
                            "fieldMapping": {
                                "title": "title",
                                "cover": "pic",
                                "desc": "owner",
                                "url": "bvid"
                            }
                        }
                    }
                ]
            }
        }
    }
    r = client.put(f"/api/v1/engine/webapps/{app_id}/resources/page/_entry", json={
        "revision": 1,
        "resource": page_resource,
    })
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"

    # 8. 校验规范并发布版本
    r = client.post(f"/api/v1/engine/webapps/{app_id}:validate")
    assert r.status_code == 200
    assert r.json()["data"]["valid"] is True

    r = client.post(f"/api/v1/engine/webapps/{app_id}:publish")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "PUBLISHED"
    assert r.json()["data"]["version"] == 1

    # 9. 低代码运行时装配测试 (/webapp-runtime?app=bili-video-app&page=_entry)
    r = client.get("/api/v1/engine/webapps/bili-video-app/pages/_entry")
    assert r.status_code == 200
    res = r.json()
    assert res["code"] == "200"
    runtime_data = res["data"]
    assert runtime_data["appSlug"] == "bili-video-app"
    component_tree = runtime_data["node"]
    assert component_tree["type"] == "Page"
    children = component_tree["children"]
    assert len(children) == 2
    assert children[0]["type"] == "SearchBar"
    assert children[1]["type"] == "VideoGrid"
    assert children[1]["dataSourceBinding"]["dataSourceRef"] == "ds_bili_hot"


class TestLowcodeFlow(unittest.TestCase):
    def test_flow(self):
        init_db()
        with TestClient(app) as client:
            run_full_lowcode_lifecycle(client)


if __name__ == "__main__":
    unittest.main()

