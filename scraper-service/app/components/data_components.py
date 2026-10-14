"""
数据处理与转换组件

包含: REGEX_FILTER, RECORD_FILTER, DEDUPE, JOIN, RESULT_BUILD, RESULT_OUTPUT
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from ..flow_engine import FlowContext, FlowEngine
from .common import _json_path
from .registry import register_component

log = logging.getLogger(__name__)


# ─────────────────────────── REGEX_FILTER ───────────────────────────


@register_component("REGEX_FILTER")
def handle_regex_filter(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    正则过滤：对已有记录的字段做正则提取/替换

    params:
        field: str (必填) — 要操作的字段名
        pattern: str (必填) — 正则表达式
        action: str = "match" — "match" (只保留匹配到的内容) / "replace" (替换) / "drop" (不匹配则丢弃整条记录)
        replacement: str = "" — action="replace" 时的替换文本
        group: int = 0 — action="match" 时取哪个捕获组
    """
    field_name = params.get("field")
    pattern = params.get("pattern")
    if not field_name or not pattern:
        raise ValueError("REGEX_FILTER: 缺少 field 或 pattern 参数")

    action = params.get("action", "match")
    replacement = params.get("replacement", "")
    group = params.get("group", 0)
    compiled = re.compile(pattern)

    survived = []
    for record in ctx.records:
        val = str(record.get(field_name, ""))

        if action == "match":
            m = compiled.search(val)
            record[field_name] = m.group(group) if m else ""
            survived.append(record)

        elif action == "replace":
            record[field_name] = compiled.sub(replacement, val)
            survived.append(record)

        elif action == "drop":
            if compiled.search(val):
                survived.append(record)

    ctx.records = survived
    log.debug("[flow:REGEX_FILTER] 过滤后剩余 %d 条记录 (field='%s', action='%s')",
              len(ctx.records), field_name, action)


# ─────────────────────────── RECORD_FILTER ───────────────────────────


@register_component("RECORD_FILTER")
def handle_record_filter(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """按声明式条件过滤 records；支持 ActionPipeline 的常用比较操作。"""
    conditions = params.get("conditions") or []
    logic = str(params.get("logic") or "AND").upper()
    if not conditions:
        return

    def matches(record: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        value = _json_path(record, str(condition.get("path") or condition.get("field") or ""))
        expected = condition.get("value")
        op = str(condition.get("op") or "EQ").upper()
        if op == "NOT_EMPTY":
            return value is not None and str(value).strip() != ""
        if op == "EMPTY":
            return value is None or str(value).strip() == ""
        if op in ("EQ", "EQUALS"):
            return value == expected or str(value) == str(expected)
        if op in ("NE", "NOT_EQUALS"):
            return value != expected and str(value) != str(expected)
        if op == "CONTAINS":
            return str(expected) in str(value or "")
        if op == "REGEX":
            return re.search(str(expected or ""), str(value or "")) is not None
        raise ValueError(f"RECORD_FILTER: 不支持的操作符 {op}")

    filtered = []
    for record in ctx.records:
        results = [matches(record, condition) for condition in conditions]
        if (all(results) if logic == "AND" else any(results)):
            filtered.append(record)
    ctx.records = filtered


# ─────────────────────────── DEDUPE ───────────────────────────


@register_component("DEDUPE")
def handle_dedupe(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """按一个或多个字段组合去重，保持首次出现顺序。"""
    keys = params.get("keys") or []
    if isinstance(keys, str):
        keys = [keys]
    if not keys:
        return
    seen = set()
    result = []
    for record in ctx.records:
        marker = tuple(str(_json_path(record, key)) for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(record)
    ctx.records = result


# ─────────────────────────── JOIN ───────────────────────────


@register_component("JOIN")
def handle_join(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """汇聚所有已完成前驱；output 中的 nodes 表达式已由引擎解析。"""
    output = params.get("output", params)
    ctx.deep_result = output
    ctx.records = [output] if isinstance(output, dict) else []


# ─────────────────────────── RESULT_BUILD ───────────────────────────


@register_component("RESULT_BUILD")
def handle_result_build(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """构造 PAGE/API/BATCH 的最终结果结构。"""
    ctx.deep_result = params
    ctx.records = [params] if isinstance(params, dict) else []


# ─────────────────────────── RESULT_OUTPUT ───────────────────────────


@register_component("RESULT_OUTPUT")
def handle_result_output(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    结果输出控制：字段重命名、剔除、去重、条数限制

    params:
        fields: list[str] = None — 只保留指定字段
        rename: dict = {} — {原名: 新名}
        dedupeBy: str = None — 按某个字段去重
        limit: int = None — 最大条数
    """
    rename = params.get("rename", {})
    keep_fields = params.get("fields")
    dedupe_by = params.get("dedupeBy")
    limit = params.get("limit")

    for record in ctx.records:
        # 重命名
        for old_name, new_name in rename.items():
            if old_name in record:
                record[new_name] = record.pop(old_name)

        # 字段过滤
        if keep_fields:
            to_remove = [k for k in record if k not in keep_fields]
            for k in to_remove:
                del record[k]

    # 去重
    if dedupe_by:
        seen = set()
        deduped = []
        for record in ctx.records:
            val = record.get(dedupe_by)
            if val in seen:
                continue
            seen.add(val)
            deduped.append(record)
        ctx.records = deduped

    if limit and isinstance(limit, int) and limit > 0:
        ctx.records = ctx.records[:limit]
