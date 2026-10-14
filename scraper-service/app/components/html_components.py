"""
HTML 加载与解析组件

包含: LOAD_HTML, CSS_SELECT, ATTR_FILTER, FIELD_MAPPING, DEEP_PARSE
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..extractor import Extractor
from ..flow_engine import FlowContext, FlowEngine
from ..models import FieldRule
from .registry import register_component

log = logging.getLogger(__name__)


# ─────────────────────────── LOAD_HTML ───────────────────────────


@register_component("LOAD_HTML")
async def handle_load_html(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    加载 HTML 页面

    params:
        url: str (必填)
        mode: str = "stealthy" (static/dynamic/stealthy)
        headers: dict = {}
        cookies: str = None
        proxy: str = None
        timeout: int = 30000 (ms)
    """
    url = params.get("url")
    if not url:
        raise ValueError("LOAD_HTML: 缺少 url 参数")
    engine.validate_url(url)

    scraper = engine.scraper_engine
    if scraper is None:
        raise RuntimeError("LOAD_HTML: ScraperEngine 未初始化")

    mode = params.get("mode", "stealthy")
    mode = {"fetch": "static", "browser": "dynamic"}.get(mode, mode)
    
    # M5 深挂载: 自动继承 Session 与 Proxy
    metadata = ctx.metadata or {}
    session_tpl = metadata.get("sessionTemplate", {})
    proxy_meta = metadata.get("proxy", {})

    headers = dict(params.get("headers", {}))
    if "headers" in session_tpl:
        for k, v in session_tpl["headers"].items():
            headers.setdefault(k, v)
            
    cookies = params.get("cookies") or session_tpl.get("cookies")
    proxy = params.get("proxy") or proxy_meta.get("url")
    timeout_ms = params.get("timeout", 30000)

    # 构造 ScrapeRequest 复用现有 fetch 逻辑
    from ..models import BrowserOptions, ScrapeRequest

    req = ScrapeRequest(
        url=url,
        mode=mode,
        headers=headers,
        cookies=cookies,
        proxy=proxy,
        timeoutMs=timeout_ms,
        browser=BrowserOptions(
            waitSelector=params.get("waitSelector"),
            waitMs=params.get("waitMs", 0),
            networkIdle=params.get("networkIdle", False),
            solveCloudflare=params.get("solveCloudflare", False),
            disableResources=params.get("disableResources", True),
        ),
        adaptive=params.get("adaptive", True),
    )

    page = await scraper.fetch(req)
    ctx.page = page
    ctx.base_url = url
    ctx.adaptive = req.adaptive
    log.info("[flow:LOAD_HTML] 已加载 %s (mode=%s)", url, mode)


# ─────────────────────────── CSS_SELECT ───────────────────────────


@register_component("CSS_SELECT")
def handle_css_select(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    CSS 选择器筛选元素

    params:
        selector: str (必填) — CSS 选择器
        scope: str = "page" — "page" 从整页选 / "elements" 从当前元素列表的子级选
    """
    selector = params.get("selector")
    if not selector:
        raise ValueError("CSS_SELECT: 缺少 selector 参数")

    scope = params.get("scope", "page")

    if scope == "elements" and ctx.elements:
        # 从已有元素的子级中选择
        matched = []
        for el in ctx.elements:
            try:
                children = el.css(selector)
                if children:
                    matched.extend(children if isinstance(children, list) else [children])
            except Exception as e:
                log.warning("[flow:CSS_SELECT] 子元素选择失败: %s", e)
        ctx.elements = matched
    else:
        # 从整页选择
        if ctx.page is None:
            raise ValueError("CSS_SELECT: 当前无页面内容（需先执行 LOAD_HTML）")
        try:
            elements = ctx.page.css(selector)
            ctx.elements = list(elements) if elements else []
        except Exception as e:
            raise RuntimeError(f"CSS_SELECT 失败 (selector='{selector}'): {e}") from e

    log.debug("[flow:CSS_SELECT] 匹配到 %d 个元素 (selector='%s')", len(ctx.elements), selector)


# ─────────────────────────── ATTR_FILTER ───────────────────────────


@register_component("ATTR_FILTER")
def handle_attr_filter(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    按属性过滤元素

    params:
        attr: str (必填) — 属性名（如 "class", "data-type", "href"）
        pattern: str (必填) — 正则匹配表达式
        invert: bool = False — 是否反向匹配
    """
    attr = params.get("attr")
    pattern = params.get("pattern")
    if not attr or not pattern:
        raise ValueError("ATTR_FILTER: 缺少 attr 或 pattern 参数")

    invert = params.get("invert", False)
    compiled = re.compile(pattern)

    filtered = []
    for el in ctx.elements:
        # Scrapling 元素的属性获取方式
        val = None
        try:
            val = el.attrib.get(attr, "")
        except Exception:
            try:
                val = str(getattr(el, attr, ""))
            except Exception:
                pass

        if val is not None:
            matched = bool(compiled.search(str(val)))
            if matched != invert:
                filtered.append(el)

    ctx.elements = filtered
    log.debug("[flow:ATTR_FILTER] 过滤后剩余 %d 个元素", len(ctx.elements))


# ─────────────────────────── FIELD_MAPPING ───────────────────────────


@register_component("FIELD_MAPPING")
def handle_field_mapping(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    字段映射：将每个元素提取为一条字典记录

    params:
        fields: dict (必填) — {字段名: {selector, extract, attr, default, regex, ...}}
    """
    fields_def = params.get("fields")
    if not fields_def or not isinstance(fields_def, dict):
        raise ValueError("FIELD_MAPPING: 缺少 fields 配置")

    # 转为 FieldRule 对象列表
    rules = []
    for name, f_cfg in fields_def.items():
        if isinstance(f_cfg, dict):
            rules.append(FieldRule(name=name, **f_cfg))
        elif isinstance(f_cfg, str):
            # 简写：{"title": "h2 a::text"}
            rules.append(FieldRule(name=name, selector=f_cfg))

    if not ctx.elements and ctx.page is not None:
        # 没有通过 CSS_SELECT 预选元素，直接从页面提取单条记录
        record = Extractor.extract_item(ctx.page, rules)
        ctx.records = [record]
    elif ctx.elements:
        # 从每个元素提取一条记录
        ctx.records = Extractor.extract_items_from_elements(ctx.elements, rules)
    else:
        ctx.records = []

    log.debug("[flow:FIELD_MAPPING] 提取到 %d 条记录", len(ctx.records))


def _get_text(element: Any) -> Optional[str]:
    """提取元素文本"""
    try:
        if hasattr(element, "text"):
            t = element.text
            return t.strip() if t else ""
        if hasattr(element, "get_all_text"):
            t = element.get_all_text()
            return t.strip() if t else ""
        return str(element).strip()
    except Exception:
        return ""


def _get_html(element: Any) -> Optional[str]:
    """提取元素 HTML"""
    try:
        if hasattr(element, "html"):
            return element.html
        return str(element)
    except Exception:
        return ""


# ─────────────────────────── DEEP_PARSE ───────────────────────────


@register_component("DEEP_PARSE")
def handle_deep_parse(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    深度解析：支持树形/嵌套结构提取

    params:
        rules: list (必填) — 树形规则定义列表
    """
    rules = params.get("rules")
    if not rules or not isinstance(rules, list):
        raise ValueError("DEEP_PARSE: 缺少 rules 配置")

    source = ctx.page
    if source is None:
        raise ValueError("DEEP_PARSE: 当前无页面内容")

    ctx.deep_result = _execute_deep_rules(source, rules, ctx, engine)
    log.info("[flow:DEEP_PARSE] 深度解析完成")


def _execute_deep_rules(
    current_scope: Any,
    rules: List[Dict[str, Any]],
    ctx: FlowContext,
    engine: FlowEngine,
) -> Dict[str, Any]:
    """递归执行深度解析规则树"""
    result: Dict[str, Any] = {}

    for rule in rules:
        name = rule.get("name")
        selector = rule.get("selector")
        rule_type = rule.get("type", "field")
        children = rule.get("children", [])

        if not name or not selector:
            continue

        elements = _select_elements(current_scope, selector)

        if rule_type == "list":
            items = []
            for el in elements:
                if children:
                    item_data = _execute_deep_rules(el, children, ctx, engine)
                    items.append(item_data)
                else:
                    items.append(_get_text(el))
            result[name] = items

        elif rule_type == "link":
            if elements:
                result[name] = _execute_link_rule(elements[0], rule, ctx, engine)
            else:
                result[name] = None

        else:  # "field"
            if elements:
                extract_type = rule.get("extract", "TEXT")
                extract_attr = rule.get("attr", "")
                result[name] = _extract_value(elements[0], extract_type, extract_attr)
            else:
                result[name] = rule.get("default", None)

    return result


def _select_elements(scope: Any, selector: str) -> List[Any]:
    """在指定作用域中用 CSS 选择器选元素"""
    try:
        elements = scope.css(selector)
        return list(elements) if elements else []
    except Exception:
        try:
            return [scope]
        except Exception:
            return []


def _execute_link_rule(
    element: Any,
    rule: Dict[str, Any],
    ctx: FlowContext,
    engine: FlowEngine,
) -> Any:
    """二级链接深入采集（同步阻塞请求）"""
    attr = rule.get("attr", "href")
    try:
        link_url = element.attrib.get(attr, "")
    except Exception:
        link_url = ""

    if not link_url:
        return None

    # 补全相对路径
    from urllib.parse import urljoin
    if ctx.base_url:
        link_url = urljoin(ctx.base_url, link_url)

    engine.validate_url(link_url)

    # 用 requests 同步抓取（轻量）
    import requests
    try:
        resp = requests.get(link_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()

        # 转为 Selector 解析
        from scrapling import Selector
        sub_page = Selector(resp.text)

        children = rule.get("children", [])
        if children:
            return _execute_deep_rules(sub_page, children, ctx, engine)
        return {"url": link_url, "text": sub_page.get_all_text()[:500] if hasattr(sub_page, "get_all_text") else ""}
    except Exception as e:
        return {"url": link_url, "error": str(e)}


def _extract_value(element: Any, extract_type: str, extract_attr: str) -> Any:
    """提取单个值"""
    if extract_type == "HTML":
        return _get_html(element)
    elif extract_type == "ATTR":
        attr = extract_attr or "href"
        try:
            return element.attrib.get(attr, "")
        except Exception:
            return ""
    else:  # TEXT
        return _get_text(element)
