"""
组件注册表与自动发现机制

支持通过装饰器 @register_component("NAME") 注册流程组件，
实现组件的完全解耦与横向扩展（OCP 开闭原则）。
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any, Callable, Dict

log = logging.getLogger(__name__)

ComponentHandler = Callable[..., Any]

# 全局组件注册表
COMPONENT_REGISTRY: Dict[str, ComponentHandler] = {}


def register_component(name: str) -> Callable[[ComponentHandler], ComponentHandler]:
    """
    组件注册装饰器
    用法:
        @register_component("LOAD_HTML")
        async def handle_load_html(params, ctx, engine):
            ...
    """
    def decorator(handler: ComponentHandler) -> ComponentHandler:
        if name in COMPONENT_REGISTRY:
            log.warning("[ComponentRegistry] 组件 %s 已存在，将被覆盖", name)
        COMPONENT_REGISTRY[name] = handler
        return handler

    return decorator


def get_registry() -> Dict[str, ComponentHandler]:
    """获取当前已注册的组件映射"""
    return dict(COMPONENT_REGISTRY)


def auto_discover_components(package_name: str = "app.components") -> None:
    """
    自动扫描当前包下的所有子模块，触发组件注册
    支持新增文件放入 components/ 目录即可自动加载，无需修改核心代码。
    """
    try:
        package = importlib.import_module(package_name)
    except Exception as e:
        log.error("[ComponentRegistry] 无法导入包 %s: %s", package_name, e)
        return

    if not hasattr(package, "__path__"):
        return

    for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
        if not is_pkg and not module_name.startswith("_") and module_name != "registry":
            full_module_name = f"{package.__name__}.{module_name}"
            try:
                importlib.import_module(full_module_name)
                log.debug("[ComponentRegistry] 已加载组件模块 %s", full_module_name)
            except Exception as e:
                log.error("[ComponentRegistry] 自动加载组件模块 %s 失败: %s", full_module_name, e)
