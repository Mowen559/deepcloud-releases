"""端到端验证：HTTP_REQUEST → JSON_EXTRACT 通过统一执行面接口。

默认 pytest 不启动外部服务、不访问公网；显式设置 RUN_SCRAPER_E2E=1 后才执行。
"""
import os
import httpx
import pytest

flow = {
    "flowId": "test_http_json",
    "firstComponentId": "fetch_posts",
    "components": [
        {
            "componentId": "fetch_posts",
            "componentType": "HTTP_REQUEST",
            "params": {
                "url": "https://jsonplaceholder.typicode.com/posts",
                "method": "GET",
                "storeAs": "api_result",
            },
            "nextComponentId": "extract",
        },
        {
            "componentId": "extract",
            "componentType": "JSON_EXTRACT",
            "params": {
                "source": "${api_result.data}",
                "container": "",
                "mappings": [
                    {"targetField": "title", "path": "title"},
                    {"targetField": "id", "path": "id"},
                ],
                "limit": 3,
            },
            "nextComponentId": None,
        },
    ],
}


@pytest.mark.skipif(
    os.getenv("RUN_SCRAPER_E2E") != "1",
    reason="需要先启动 scraper-service，并显式设置 RUN_SCRAPER_E2E=1",
)
def test_http_request_to_json_extract_through_live_service():
    resp = httpx.post(
        "http://127.0.0.1:18000/internal/api/v1/executor/pipelines:execute",
        json={"pipeline": flow, "input": {}, "metadata": {}},
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["total"] == 3
