"""
JSON 提取与处理组件

包含: JSON_EXTRACT
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..flow_engine import FlowContext, FlowEngine
from .common import _apply_filter, _json_path
from .registry import register_component

log = logging.getLogger(__name__)


# ─────────────────────────── JSON_EXTRACT ───────────────────────────


@register_component("JSON_EXTRACT")
def handle_json_extract(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    JSON 提取组件：从 JSON 数据中按路径提取字段。

    params:
        source: str = None — 数据源表达式（如 "${api_call.data}"），留空则用 ctx.records[0]
        container: str = None — 列表容器路径（如 "data.files"），留空表示整体视为单条
        mappings: list = [] — 字段映射 [{targetField, path, defaultValue}]
            path 为点分路径（如 "file_name" 或 "video.url"）
        filter: str = None — 过滤表达式（如 "fileName endsWith .mp4"）
        limit: int = None — 截取条数
    """
    # 确定数据源
    source_data = params.get("source")
    if source_data is None:
        # 默认从 step_results 中找最近的 HTTP 响应
        source_data = _find_latest_http_data(ctx)
    if source_data is None:
        raise ValueError("JSON_EXTRACT: 无数据源，请指定 source 参数或确保前序有 HTTP_REQUEST")

    # 定位容器
    container_path = params.get("container")
    if container_path:
        items = _json_path(source_data, container_path)
        if not isinstance(items, list):
            items = [items] if items is not None else []
    else:
        items = source_data if isinstance(source_data, list) else [source_data]

    # 过滤
    filter_expr = params.get("filter")
    if filter_expr:
        items = _apply_filter(items, filter_expr)

    # 字段映射
    mappings = params.get("mappings") or []
    if mappings:
        records: List[Dict[str, Any]] = []
        for item in items:
            record: Dict[str, Any] = {}
            for mapping in mappings:
                target = mapping.get("targetField")
                path = mapping.get("path", "")
                if not target:
                    continue
                value = _json_path(item, path) if path else item
                if value is None and mapping.get("defaultValue"):
                    value = mapping["defaultValue"]
                if value is not None:
                    record[target] = value
            if record:
                records.append(record)
        ctx.records = records
    else:
        # 无映射：直接把 items 作为 records
        ctx.records = [item if isinstance(item, dict) else {"value": item} for item in items]

    # 截取
    limit = params.get("limit")
    if limit and isinstance(limit, int) and limit > 0:
        ctx.records = ctx.records[:limit]

    log.debug("[flow:JSON_EXTRACT] %d 条记录", len(ctx.records))


def _find_latest_http_data(ctx: FlowContext) -> Any:
    """从 step_results 中找最近的 HTTP 响应数据"""
    for key in reversed(list(ctx.step_results.keys())):
        result = ctx.step_results[key]
        if isinstance(result, dict) and "data" in result and "statusCode" in result:
            return result["data"]
    return None
