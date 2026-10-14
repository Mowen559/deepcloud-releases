"""
流程编排与控制组件

包含: SWITCH, SET_VARIABLE, WAIT_USER, FOR_EACH
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from ..flow_engine import FlowContext, FlowEngine, SuspendExecution
from .registry import register_component

log = logging.getLogger(__name__)


# ─────────────────────────── SWITCH ───────────────────────────


@register_component("SWITCH")
def handle_switch(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """计算受控二元条件并把 route 暴露给条件边。"""
    expression = str(params.get("expression") or "").strip()
    match = re.fullmatch(
        r"([\w.]+)\s*==\s*['\"]([^'\"]*)['\"]\s*\?\s*['\"]([^'\"]*)['\"]\s*:\s*['\"]([^'\"]*)['\"]",
        expression,
    )
    if not match:
        raise ValueError(f"SWITCH: 不支持的表达式 {expression}")
    path, expected, matched, fallback = match.groups()
    current: Any = {"input": ctx.input_data, "vars": ctx.variables}
    for segment in path.split("."):
        current = current.get(segment) if isinstance(current, dict) else None
    ctx.deep_result = {"route": matched if str(current) == expected else fallback}


# ─────────────────────────── SET_VARIABLE ───────────────────────────


@register_component("SET_VARIABLE")
def handle_set_variable(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    变量赋值组件：从上下文/前序步骤中取值存入全局变量。

    params:
        variables: dict (必填) — {变量名: 值或表达式}
            值已经在引擎层被 resolve_expressions 解析过，
            所以这里直接存入即可。

    示例：
        {"variables": {"share_url": "${extract_share.records[0].share_url}"}}
        执行后：ctx.variables["share_url"] = "https://pan.quark.cn/s/xxx"
        后续组件可用 ${vars.share_url} 引用。
    """
    variables = params.get("variables")
    if not variables and params.get("name"):
        variables = {params["name"]: params.get("value")}
    if not variables or not isinstance(variables, dict):
        raise ValueError("SET_VARIABLE: 缺少 variables 参数")

    for key, value in variables.items():
        ctx.variables[key] = value

    log.debug("[flow:SET_VARIABLE] 设置 %d 个变量: %s", len(variables), list(variables.keys()))


# ─────────────────────────── WAIT_USER ───────────────────────────


@register_component("WAIT_USER")
def handle_wait_user(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    等待用户交互组件：抛出挂起信号，中断流程执行，保留上下文以供恢复。
    """
    raise SuspendExecution("等待用户交互: " + str(params.get("reason", "")))


# ─────────────────────────── FOR_EACH ───────────────────────────


@register_component("FOR_EACH")
async def handle_for_each(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    循环组件：对列表中的每一项执行子组件链。

    params:
        source: list — 要遍历的列表（已经被表达式引擎解析）
        itemAs: str = "item" — 循环项变量名（可通过 ${item} 引用）
        maxIterations: int = 20 — 最大循环次数（防止规则配错拖垂服务）
        components: list — 子组件链 [{componentType, params, exceptionStrategy}]
        collectField: str = None — 每轮循环后从 ctx.records 中取哪个字段收集
        collectAs: str = "results" — 收集结果存入 variables 的 key

    注意：子组件是同步顺序执行的简化链（不支持 nextComponentId 跳转），
    每个子组件执行后 ctx.records 会被重置。
    """
    source = params.get("source", params.get("list"))
    if not source or not isinstance(source, list):
        ctx.warnings.append("FOR_EACH: source 不是列表，跳过")
        return

    max_iter = params.get("maxIterations", 20)
    sub_components = params.get("components") or params.get("subComponents") or []
    collect_field = params.get("collectField")
    collect_as = params.get("collectAs", "results")

    collected: List[Any] = []
    items = source[:max_iter]

    for idx, item in enumerate(items):
        ctx.current_item = item
        ctx.current_index = idx
        ctx.records = []  # 每轮重置

        for sub_comp in sub_components:
            comp_type = (sub_comp.get("componentType") or "").upper()
            sub_params = sub_comp.get("params") or {}
            # 解析子组件参数中的表达式
            from ..flow_engine import resolve_expressions
            resolved = resolve_expressions(sub_params, ctx)

            handler = engine._registry.get(comp_type)
            if handler is None:
                ctx.warnings.append(f"FOR_EACH: 不支持的子组件类型 {comp_type}")
                continue
            try:
                result = handler(resolved, ctx, engine)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                strategy = (sub_comp.get("exceptionStrategy") or "IGNORE").upper()
                msg = f"FOR_EACH[{idx}] {comp_type} 失败: {e}"
                if strategy == "TERMINATE":
                    raise RuntimeError(msg) from e
                ctx.warnings.append(msg)

        # 收集每轮结果
        if collect_field and ctx.records:
            val = ctx.records[0].get(collect_field) if ctx.records else None
            if val is not None:
                collected.append(val)
        elif ctx.records:
            collected.extend(ctx.records)

    # 清理循环状态
    ctx.current_item = None
    ctx.current_index = 0

    # 存入变量
    ctx.variables[collect_as] = collected
    ctx.records = collected if collected and isinstance(collected[0], dict) else [{"value": v} for v in collected]

    log.info("[flow:FOR_EACH] 循环 %d 次，收集 %d 条结果", len(items), len(collected))
