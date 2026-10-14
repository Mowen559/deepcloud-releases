"""
HTTP 网络请求组件

包含: HTTP_REQUEST
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..flow_engine import FlowContext, FlowEngine
from .registry import register_component

log = logging.getLogger(__name__)


# ─────────────────────────── HTTP_REQUEST ───────────────────────────


@register_component("HTTP_REQUEST")
async def handle_http_request(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    通用 HTTP 请求组件：发起 HTTP/HTTPS 请求，响应存入上下文。

    params:
        url: str (必填) — 请求地址（支持 ${} 表达式）
        method: str = "GET" — GET / POST / PUT / DELETE
        headers: dict = {} — 请求头
        body: dict|str = None — 请求体（dict 自动序列化为 JSON）
        timeout: int = 30000 — 超时（毫秒）
        proxy: str = None — 代理地址
        storeAs: str = None — 将响应存入 step_results 的自定义 key（默认用 componentId）
        parseJson: bool = True — 是否自动解析 JSON 响应
    """
    from curl_cffi.requests import AsyncSession

    url = params.get("url")
    if not url:
        raise ValueError("HTTP_REQUEST: 缺少 url 参数")
    engine.validate_url(url)

    method = (params.get("method") or "GET").upper()
    
    # M5 深挂载: 自动继承 Session 与 Proxy
    metadata = ctx.metadata or {}
    session_tpl = metadata.get("sessionTemplate", {})
    proxy_meta = metadata.get("proxy", {})

    headers = dict(params.get("headers") or {})
    if "headers" in session_tpl:
        for k, v in session_tpl["headers"].items():
            headers.setdefault(k, v)
    if "cookies" in session_tpl and "Cookie" not in [k.title() for k in headers.keys()]:
        headers["Cookie"] = session_tpl["cookies"]

    body = params.get("body")
    timeout_s = (params.get("timeout") or 30000) / 1000.0
    proxy = params.get("proxy") or proxy_meta.get("url")
    parse_json = params.get("parseJson", True)

    kwargs: Dict[str, Any] = {
        "timeout": timeout_s,
        "headers": headers,
        "impersonate": "chrome",
        # Do not follow an unchecked redirect into a private network.
        "allow_redirects": False,
    }
    if proxy:
        kwargs["proxy"] = proxy

    # 请求体
    if body is not None:
        if isinstance(body, dict):
            import json as json_mod
            kwargs["data"] = json_mod.dumps(body, ensure_ascii=False).encode("utf-8")
            if "Content-Type" not in headers:
                kwargs["headers"]["Content-Type"] = "application/json; charset=utf-8"
        elif isinstance(body, str):
            kwargs["data"] = body.encode("utf-8")

    async with AsyncSession() as session:
        response = await session.request(method, url, **kwargs)

    # 存储原始响应信息
    result: Dict[str, Any] = {
        "statusCode": response.status_code,
        "headers": dict(response.headers) if response.headers else {},
    }

    content_type = result["headers"].get("Content-Type", "")
    is_binary = any(t in content_type for t in ["image/", "video/", "audio/", "application/pdf", "application/zip", "application/octet-stream"])
    store_as_artifact = params.get("storeAsArtifact", False) or is_binary
    
    if store_as_artifact and metadata.get("artifactStore"):
        import hashlib
        import os
        from pathlib import Path
        file_hash = hashlib.md5(response.content).hexdigest()
        
        # 尝试根据 Content-Type 推导扩展名
        ext = ""
        if "image/jpeg" in content_type:
            ext = ".jpg"
        elif "image/png" in content_type:
            ext = ".png"
        elif "image/webp" in content_type:
            ext = ".webp"
        elif "application/pdf" in content_type:
            ext = ".pdf"
        elif "video/mp4" in content_type:
            ext = ".mp4"
        elif "audio/mpeg" in content_type:
            ext = ".mp3"

        # 真实持久化到本地工作区 Artifact 存储目录
        storage_dir = Path(os.getenv("ARTIFACT_STORAGE_DIR", "./data/artifacts"))
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = storage_dir / f"{file_hash}{ext}"
        with open(file_path, "wb") as f:
            f.write(response.content)

        base_url = os.getenv("ARTIFACT_BASE_URL", "http://127.0.0.1:8000/artifacts").rstrip("/")
        artifact_url = f"{base_url}/{file_hash}{ext}"

        result["artifactId"] = f"art-{file_hash}"
        result["artifactUrl"] = artifact_url
        result["artifactPath"] = str(file_path.resolve())
        result["data"] = {
            "artifactId": result["artifactId"],
            "url": result["artifactUrl"],
            "path": result["artifactPath"],
            "bytes": len(response.content),
        }
        ctx.records = [result["data"]]
    elif parse_json and not is_binary:
        try:
            result["data"] = response.json()
        except Exception:
            result["data"] = response.text
    else:
        # 如果没有要求存为 artifact 但又是二进制，转 Base64 防崩溃
        if is_binary:
            import base64
            result["data"] = base64.b64encode(response.content).decode("utf-8")
        else:
            result["data"] = response.text

    # 存入上下文：后续组件可通过 ${storeAs.data.xxx} 引用
    store_key = params.get("storeAs") or "_http_response"
    ctx.step_results[store_key] = result

    # 如果响应是 JSON 且包含列表，自动设入 records 以便下游使用
    data = result.get("data")
    if isinstance(data, list):
        ctx.records = data
    elif isinstance(data, dict):
        ctx.records = [data]

    log.info("[flow:HTTP_REQUEST] %s %s → %d", method, url, response.status_code)
