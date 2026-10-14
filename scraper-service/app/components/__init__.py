"""
流程组件模块

遵循 OCP 开闭原则：
- 所有内置组件通过 @register_component 自动注册
- 新增组件只需在当前目录下新增 .py 文件并使用 @register_component 标记，即可被 auto_discover_components 自动加载，零侵入原有代码。
"""

from .common import _apply_filter, _json_path
from .control_components import (
    handle_for_each,
    handle_set_variable,
    handle_switch,
    handle_wait_user,
)
from .data_components import (
    handle_dedupe,
    handle_join,
    handle_record_filter,
    handle_regex_filter,
    handle_result_build,
    handle_result_output,
)
from .html_components import (
    _execute_deep_rules,
    _execute_link_rule,
    _extract_value,
    _get_html,
    _get_text,
    _select_elements,
    handle_attr_filter,
    handle_css_select,
    handle_deep_parse,
    handle_field_mapping,
    handle_load_html,
)
from .http_components import handle_http_request
from .json_components import _find_latest_http_data, handle_json_extract
from .ai_components import (
    handle_ai_extract,
    handle_ai_enrich,
    handle_ai_filter,
)
from .registry import (
    COMPONENT_REGISTRY,
    auto_discover_components,
    get_registry,
    register_component,
)


# 触发外部/动态扩展组件自动发现
auto_discover_components("app.components")

__all__ = [
    "COMPONENT_REGISTRY",
    "register_component",
    "get_registry",
    "auto_discover_components",
    # 工具函数
    "_json_path",
    "_apply_filter",
    "_get_text",
    "_get_html",
    "_execute_deep_rules",
    "_select_elements",
    "_execute_link_rule",
    "_extract_value",
    "_find_latest_http_data",
    # 处理函数
    "handle_load_html",
    "handle_css_select",
    "handle_attr_filter",
    "handle_field_mapping",
    "handle_deep_parse",
    "handle_regex_filter",
    "handle_record_filter",
    "handle_dedupe",
    "handle_join",
    "handle_result_build",
    "handle_result_output",
    "handle_http_request",
    "handle_json_extract",
    "handle_set_variable",
    "handle_switch",
    "handle_wait_user",
    "handle_for_each",
    "handle_ai_extract",
    "handle_ai_enrich",
    "handle_ai_filter",
]

