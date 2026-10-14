"""
字段提取：把渲染后的页面按 container + fields 规则变成结构化记录

这里是 Scrapling 相对 Jsoup 的核心增量所在——adaptive 选择器自愈。
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .models import FieldRule

log = logging.getLogger(__name__)


class Extractor:
    """
    规则驱动的提取器

    adaptive 的用法遵循官方两阶段模型（见 Scrapling 文档 parsing/adaptive.md）：

    1. Save 阶段：正常能选中时带 ``auto_save=True``，把元素指纹写进 SQLite；
    2. Match 阶段：选不中时改用 ``adaptive=True``，按相似度重定位。

    所以这里的策略是「先常规选，选不中再自愈」，而不是一上来就 adaptive：
    - 常规路径顺带维护指纹库，为将来改版做准备；
    - 只有真失效时才付相似度计算的开销；
    - 自愈成功会记一条 warning——**规则已经过期了，用户需要知道**，
      否则自愈会掩盖问题，直到某天连相似度都匹配不上才暴露。
    """

    def extract(
        self,
        page: Any,
        container: Optional[str],
        fields: List[FieldRule],
        adaptive: bool,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        warnings: List[str] = []

        containers = self._select_containers(page, container, adaptive, warnings)
        if not containers:
            return [], warnings

        return self.extract_elements(containers, fields, adaptive, warnings), warnings

    def extract_elements(
        self,
        elements: List[Any],
        fields: List[FieldRule],
        adaptive: bool,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        """从已选中的容器提取字段，供 Flow 的 FIELD_MAPPING 复用。"""
        records: List[Dict[str, Any]] = []
        for element in elements:
            record = self._extract_one(element, fields, adaptive, warnings)
            # 丢弃全空记录：容器匹配到了但一个字段都没取到，落库只会得到空行。
            # （只要有任何一个字段有值或配了兜底值，记录就会保留）
            if record:
                records.append(record)

        return records

    def select(
        self,
        node: Any,
        selector: str,
        adaptive: bool,
        warnings: List[str],
        label: str,
        xpath: bool = False,
    ) -> List[Any]:
        """Flow 组件使用的自愈选择入口。"""
        return self._select(node, selector, adaptive, warnings, label, xpath)

    # ─────────────────────────── 容器 ───────────────────────────

    def _select_containers(
        self,
        page: Any,
        container: Optional[str],
        adaptive: bool,
        warnings: List[str],
    ) -> List[Any]:
        # 容器留空：整页当作一条记录，用于详情页采集
        if not container:
            return [page]

        elements = self._select(page, container, adaptive, warnings, label="容器")
        if not elements:
            warnings.append(
                f"容器选择器 '{container}' 未匹配到任何元素，"
                "请检查规则是否失效或页面是否被反爬拦截"
            )
        return list(elements)

    # ─────────────────────────── 字段 ───────────────────────────

    def _extract_one(
        self,
        element: Any,
        fields: List[FieldRule],
        adaptive: bool,
        warnings: List[str],
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {}

        for rule in fields:
            value = self._extract_field(element, rule, adaptive, warnings)

            if value is None and rule.defaultValue is not None:
                value = rule.defaultValue

            # 提取不到且无兜底值时不落 key，让 data_json 里「没有」与「空值」可区分
            if value is not None:
                record[rule.targetField] = value

        return record

    def _extract_field(
        self,
        element: Any,
        rule: FieldRule,
        adaptive: bool,
        warnings: List[str],
    ) -> Optional[str]:
        rule_type = (rule.type or "CSS_SELECTOR").upper()

        # REGEX 类型不需要选择器，直接对容器全文匹配
        if rule_type == "REGEX":
            return self._apply_regex(self._text_of(element), rule)

        selectors = [rule.selector] + list(rule.fallbackSelectors or [])
        found: List[Any] = []
        for selector in filter(None, selectors):
            try:
                found = self._select(
                    element, selector, adaptive, warnings,
                    label=f"字段 {rule.targetField}", xpath=(rule_type == "XPATH"),
                )
            except Exception as e:
                warnings.append(f"字段 {rule.targetField} 的选择器执行出错: {e}")
            if found:
                break

        if not found:
            return None

        raw = self._value_of(found[0], rule.extractAttr)
        if raw is None:
            return None

        return self._apply_regex(raw, rule) if rule.regex else raw

    # ─────────────────────────── 选择与自愈 ───────────────────────────

    def _select(
        self,
        node: Any,
        selector: str,
        adaptive: bool,
        warnings: List[str],
        label: str,
        xpath: bool = False,
    ) -> List[Any]:
        """常规选择；失败且开启 adaptive 时尝试自愈"""
        method = node.xpath if xpath else node.css

        # auto_save 只在 CSS 选择时可用（xpath 同样支持，但 adaptive 的 identifier 取选择器串）
        try:
            found = method(selector, auto_save=True) if adaptive else method(selector)
        except TypeError:
            # 某些节点类型（如整页 Selector 之外的包装对象）不接受 auto_save
            found = method(selector)

        if found or not adaptive:
            return list(found) if found else []

        # ── 自愈路径 ──
        try:
            recovered = method(selector, adaptive=True)
        except Exception as e:
            log.debug("adaptive 重定位失败 %s: %s", selector, e)
            return []

        if recovered:
            warnings.append(
                f"{label} 的选择器 '{selector}' 已失效，本次由 adaptive 按相似度重定位成功——"
                "页面结构已改版，请尽快更新规则（自愈依赖历史指纹，不能长期替代正确的选择器）"
            )
            return list(recovered)

        return []

    # ─────────────────────────── 取值 ───────────────────────────

    def _value_of(self, element: Any, extract_attr: str) -> Optional[str]:
        attr = (extract_attr or "text").strip()

        if attr in ("text", ""):
            return self._text_of(element)

        if attr == "html":
            return self._html_of(element)

        # 其余一律当作 HTML 属性名（href/src/data-id...）
        try:
            value = element.attrib.get(attr)
        except Exception:
            value = None

        if value is None:
            return None

        # 链接类属性补全为绝对地址：站点里大量是相对路径，
        # 落库后若不补全，下游拿到 /job/1 这种值无法直接使用
        if attr in ("href", "src") and hasattr(element, "urljoin"):
            try:
                return element.urljoin(value)
            except Exception:
                return value
        return value

    def _text_of(self, element: Any) -> Optional[str]:
        """
        取文本

        先用 ``.text``（只含直接文本节点，对叶子元素最精确、不带子元素噪音）；
        为空时回退到 ``get_all_text()``。回退是必需的：容器类元素的 ``.text``
        应为空串（文字都在后代节点里），而用户写 ``div.title`` 而文字在内层
        ``<span>`` 里是极常见的写法——不回退就会变成「明明有文字却取不到」。
        REGEX 类型对容器全文匹配也依赖这个回退。
        """
        try:
            text = element.text
        except Exception:
            text = None

        if text is not None and str(text).strip():
            return str(text).strip()

        try:
            if hasattr(element, "get_all_text"):
                all_text = element.get_all_text()
                if all_text and str(all_text).strip():
                    return str(all_text).strip()
        except Exception:
            return None

        return None

    def _html_of(self, element: Any) -> Optional[str]:
        for prop in ("html_content", "body"):
            if hasattr(element, prop):
                value = getattr(element, prop)
                if value:
                    return str(value)
        return None

    # ─────────────────────────── 正则 ───────────────────────────

    def _apply_regex(self, raw: Optional[str], rule: FieldRule) -> Optional[str]:
        if raw is None or not rule.regex:
            return raw
        try:
            match = re.search(rule.regex, raw)
        except re.error:
            # 正则本身写错：返回原值而非抛错，规则问题由 warning 体现
            return raw
        if not match:
            return None

        group = rule.regexGroup if rule.regexGroup is not None else 1
        try:
            return match.group(group)
        except IndexError:
            # 组序号越界（规则写错）：退而返回整个匹配串，比直接丢弃数据有用
            return match.group(0)
