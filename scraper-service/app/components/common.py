"""
组件通用工具函数
"""

from __future__ import annotations

import re
from typing import Any, List


def _json_path(data: Any, path: str) -> Any:
    """
    简易点分路径解析（不引入额外依赖）。

    支持：
      - "data.files" → data["files"]
      - "data.list[0].title" → data["list"][0]["title"]
      - "$.data.files" → 忽略 $. 前缀
    """
    if not path:
        return data
    # 去掉 $. 前缀
    if path.startswith("$."):
        path = path[2:]
    elif path == "$":
        return data

    current = data
    for segment in path.split("."):
        if current is None:
            return None
        # 处理 "list[0]" 这种
        m = re.match(r"^(\w+)\[(\d+)]$", segment)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if isinstance(current, dict):
                current = current.get(key)
            if isinstance(current, (list, tuple)) and idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(segment)
            else:
                return None
    return current


def _apply_filter(items: List[Any], filter_expr: Any) -> List[Any]:
    """
    简易过滤表达式。

    支持：
      - "fieldName endsWith .mp4"  — 后缀匹配
      - "fieldName startsWith prefix" — 前缀匹配
      - "fieldName contains text"  — 包含
      - "fieldName equals value"   — 相等
    """
    if isinstance(filter_expr, dict):
        field_name = str(filter_expr.get("field", ""))
        operator = str(filter_expr.get("op", "equals")).lower()
        value = str(filter_expr.get("value", ""))
    elif isinstance(filter_expr, str):
        parts = filter_expr.split(None, 2)
        if len(parts) < 3:
            return items
        field_name, operator, value = parts[0], parts[1].lower(), parts[2]
    else:
        return items

    operator = {
        "eq": "equals",
        "equals": "equals",
        "startswith": "startswith",
        "endswith": "endswith",
    }.get(operator, operator)
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        field_val = str(item.get(field_name, ""))
        if operator == "endswith" and field_val.lower().endswith(value.lower()):
            result.append(item)
        elif operator == "startswith" and field_val.lower().startswith(value.lower()):
            result.append(item)
        elif operator == "contains" and value.lower() in field_val.lower():
            result.append(item)
        elif operator == "equals" and field_val == value:
            result.append(item)
    return result
