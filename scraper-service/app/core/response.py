import time
from typing import Any, Dict


def ok(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """标准前端响应包裹，code 严格为字符串 '200' 以满足前端拦截器契约"""
    return {
        "code": "200",
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
