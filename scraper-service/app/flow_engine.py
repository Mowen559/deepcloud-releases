"""
流程编排引擎

参照老项目 ParseEngine 架构：按 FlowConfig 定义的组件链顺序执行，
组件间通过 FlowContext 共享状态。所有组件逻辑在 Python 侧完成。

数据绑定：组件参数中的 ${stepId.path.to.value} 表达式会在执行前自动解析，
引用前序步骤的输出或全局变量，实现多步请求间的自动联动。
"""

import logging
import re
import asyncio
import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .models import ExecutorResult, FlowComponentConfig, FlowConfig

log = logging.getLogger(__name__)

# 匹配 ${...} 表达式的正则
_EXPR_PATTERN = re.compile(r"\$\{([^}]+)}")


class SuspendExecution(Exception):
    """用于挂起流程的特殊异常"""
    pass


@dataclass
class FlowContext:
    """组件间共享的执行上下文"""

    page: Any = None  # Scrapling Selector（当前页面）
    elements: List[Any] = field(default_factory=list)  # 当前筛选出的元素列表
    records: List[Dict[str, Any]] = field(default_factory=list)  # 最终结构化记录
    warnings: List[str] = field(default_factory=list)
    deep_result: Optional[Dict[str, Any]] = None  # 深度解析嵌套结果
    base_url: str = ""  # 当前页面 URL（用于链接补全）

    # ─── 多步编排扩展 ───────────────────────────────────────────
    # 每个组件执行后，其输出以 componentId 为 key 存入 step_results，
    # 后续组件可通过 ${componentId.records[0].field} 引用。
    step_results: Dict[str, Any] = field(default_factory=dict)
    # 全局变量（SET_VARIABLE 组件写入），可通过 ${vars.name} 引用。
    variables: Dict[str, Any] = field(default_factory=dict)
    # 当前循环项（FOR_EACH 组件设入），可通过 ${item} / ${item.field} 引用。
    current_item: Any = None
    current_index: int = 0
    input_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    adaptive: bool = True


def resolve_expressions(value: Any, ctx: FlowContext) -> Any:
    """
    递归解析参数中的 ${...} 表达式。

    支持的引用路径：
      - ${stepId.records[0].fieldName}  — 引用前序步骤的输出
      - ${vars.key}                     — 引用全局变量
      - ${item}                         — 当前循环项（FOR_EACH 内）
      - ${item.field}                   — 当前循环项的字段
      - ${index}                        — 当前循环索引
      - ${input}                        — 流程入口输入（由 engine-service 替换，此处兜底）

    若整个值就是单个表达式（如 "${step.records}"），返回原始类型（dict/list）；
    若值中混合了文本和表达式（如 "Bearer ${vars.token}"），返回拼接字符串。
    """
    if isinstance(value, str):
        return _resolve_string(value, ctx)
    if isinstance(value, dict):
        return {k: resolve_expressions(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_expressions(item, ctx) for item in value]
    return value


def _resolve_string(text: str, ctx: FlowContext) -> Any:
    """解析字符串中的表达式"""
    # 整个字符串就是单个表达式 → 返回原始类型
    m = _EXPR_PATTERN.fullmatch(text.strip())
    if m:
        return _eval_path(m.group(1).strip(), ctx)

    # 混合文本 → 字符串替换
    def _replacer(match: re.Match) -> str:
        result = _eval_path(match.group(1).strip(), ctx)
        return str(result) if result is not None else ""

    return _EXPR_PATTERN.sub(_replacer, text)


def _eval_path(path: str, ctx: FlowContext) -> Any:
    """
    按点分路径从上下文中取值。

    示例路径：
      - "step1.records[0].title"
      - "vars.token"
      - "item.fileId"
      - "index"
    """
    # 受控内置函数；只接受路径参数，不执行任意 Python。
    function_match = re.fullmatch(r"urlEncode\((.+)\)", path)
    if function_match:
        from urllib.parse import quote
        value = _eval_path(function_match.group(1).strip(), ctx)
        return quote("" if value is None else str(value), safe="")

    # 特殊快捷引用
    if path == "item":
        return ctx.current_item
    if path == "index":
        return ctx.current_index
    if path == "input":
        return ctx.input_data

    # 确定根对象
    parts = _split_path(path)
    if not parts:
        return None

    root_key = parts[0]
    if root_key == "vars":
        current: Any = ctx.variables
        parts = parts[1:]
    elif root_key == "input":
        current = ctx.input_data
        parts = parts[1:]
    elif root_key == "nodes":
        current = ctx.step_results
        parts = parts[1:]
    elif root_key == "runtime":
        current = ctx.metadata
        parts = parts[1:]
    elif root_key == "item":
        current = ctx.current_item
        parts = parts[1:]
    elif root_key in ctx.step_results:
        current = ctx.step_results[root_key]
        parts = parts[1:]
    else:
        # 尝试从最近的 records 中取（兼容简写 ${fieldName}）
        if ctx.records and len(ctx.records) == 1:
            current = ctx.records[0]
        else:
            return None

    # 逐层深入
    for part in parts:
        current = _access(current, part)
        if current is None:
            return None
    return current


def _split_path(path: str) -> List[str]:
    """拆分点分路径，保留数组下标：'a.b[0].c' → ['a', 'b', '[0]', 'c']"""
    tokens: List[str] = []
    for segment in path.split("."):
        # 处理 "records[0]" 这种
        bracket_match = re.match(r"^(\w+)\[(\d+)]$", segment)
        if bracket_match:
            tokens.append(bracket_match.group(1))
            tokens.append(f"[{bracket_match.group(2)}]")
        else:
            tokens.append(segment)
    return tokens


def _access(obj: Any, key: str) -> Any:
    """从对象中取一个层级"""
    if obj is None:
        return None
    # 数组下标
    if key.startswith("[") and key.endswith("]"):
        idx = int(key[1:-1])
        if isinstance(obj, (list, tuple)) and idx < len(obj):
            return obj[idx]
        return None
    # dict
    if isinstance(obj, dict):
        return obj.get(key)
    # 对象属性
    return getattr(obj, key, None)


# 组件处理函数签名：(params, context, engine_ref) -> None
ComponentHandler = Callable[[Dict[str, Any], FlowContext, "FlowEngine"], None]


class FlowEngine:
    """
    流程编排引擎

    按 FlowConfig 中定义的组件链（first_component_id → next_component_id）
    顺序执行各组件，组件通过 FlowContext 传递状态。
    """

    def __init__(
        self,
        scraper_engine: Any = None,
        url_validator: Optional[Callable[[str], None]] = None,
    ):
        self._registry: Dict[str, ComponentHandler] = {}
        self._scraper_engine = scraper_engine
        self._url_validator = url_validator
        self._register_builtin_components()

    def register(self, component_type: str, handler: ComponentHandler) -> None:
        """注册组件处理器"""
        self._registry[component_type.upper()] = handler

    async def execute(
        self,
        config: Optional[FlowConfig] = None,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        pipeline: Optional[FlowConfig] = None,
    ) -> ExecutorResult:
        """执行流程；edges 非空时按 DAG 拓扑执行，否则兼容旧线性链。"""
        actual_config = config or pipeline
        if not actual_config:
            raise ValueError("Either 'config' or 'pipeline' must be provided to FlowEngine.execute()")
        config = actual_config
        started = time.monotonic()
        context = FlowContext(input_data=input_data or {}, metadata=metadata or {})

        # 恢复挂起/中断的上下文
        if metadata and "flowContext" in metadata:
            fc = metadata["flowContext"]
            context.step_results = fc.get("step_results", {})
            context.variables = fc.get("variables", {})
            context.records = fc.get("records", [])
            context.deep_result = fc.get("deep_result")
            context.base_url = fc.get("base_url", "")
            
            # 如果是交互恢复，把用户输入合并到 variables 里，方便后续组件取值
            if "userInput" in metadata:
                context.variables.update(metadata["userInput"])

        # 找出之前已完成的节点，用于跳过
        finished_nodes = set()
        if metadata and "nodeRuns" in metadata:
            for nr in metadata["nodeRuns"]:
                if nr.get("status") in ("SUCCEEDED", "SKIPPED"):
                    finished_nodes.add(nr["nodeId"])

        # 构建组件索引
        component_map: Dict[str, FlowComponentConfig] = {
            comp.componentId: comp for comp in config.components
        }

        # 校验入口
        if config.firstComponentId not in component_map:
            return ExecutorResult(
                success=False,
                warnings=[f"入口组件 '{config.firstComponentId}' 不存在于组件列表中"],
                elapsedMs=int((time.monotonic() - started) * 1000),
            )

        if config.edges:
            return await self._execute_dag(config, component_map, context, started, finished_nodes)

        # 旧契约链式执行
        current_id: Optional[str] = config.firstComponentId
        visited: set = set()
        node_runs: List[Dict[str, Any]] = []

        while current_id:
            if current_id in visited:
                context.warnings.append(f"检测到组件循环引用: {current_id}")
                break
            visited.add(current_id)

            comp = component_map.get(current_id)
            if comp is None:
                context.warnings.append(f"组件 '{current_id}' 未定义，流程中断")
                break
                
            if current_id in finished_nodes:
                # 节点已在前次执行成功完成，直接跳过执行，保持上下文即可（恢复时已经反序列化了 step_results 等）
                current_id = comp.nextComponentId
                continue

            handler = self._registry.get(comp.componentType.upper())
            node_started = time.monotonic()
            if handler is None:
                msg = f"不支持的组件类型: {comp.componentType}"
                node_runs.append({"nodeId": comp.componentId, "capability": comp.componentType,
                                  "status": "FAILED", "elapsedMs": 0})
                if comp.exceptionStrategy.upper() == "TERMINATE":
                    return ExecutorResult(
                        success=False,
                        records=context.records,
                        total=len(context.records),
                        warnings=context.warnings + [msg],
                        metadata={**context.metadata, "nodeRuns": node_runs},
                        elapsedMs=int((time.monotonic() - started) * 1000),
                        deepResult=context.deep_result,
                    )
                context.warnings.append(msg)
                current_id = comp.nextComponentId
                continue

            try:
                # 执行前解析参数中的 ${...} 表达式
                resolved_params = resolve_expressions(comp.params, context)
                result = handler(resolved_params, context, self)
                # 支持异步组件（LOAD_HTML / HTTP_REQUEST）
                if hasattr(result, "__await__"):
                    await result
            except SuspendExecution as exc:
                # WAIT_USER 组件触发挂起，序列化当前上下文等待恢复
                log.info("[flow] 组件 %s 触发挂起: %s", comp.componentId, exc)
                node_runs.append({"nodeId": comp.componentId, "capability": comp.componentType,
                                  "status": "SUSPENDED",
                                  "elapsedMs": int((time.monotonic() - node_started) * 1000)})
                context.step_results[comp.componentId] = {
                    "records": context.records,
                    "page": context.page is not None,
                    "elements_count": len(context.elements),
                    "deep_result": context.deep_result,
                    "output": context.deep_result,
                }
                return ExecutorResult(
                    success=True,
                    suspended=True,
                    records=context.records,
                    total=len(context.records),
                    warnings=context.warnings + [f"等待用户交互: {exc}"],
                    metadata={**context.metadata, "nodeRuns": node_runs},
                    elapsedMs=int((time.monotonic() - started) * 1000),
                    deepResult=context.deep_result,
                )
            except Exception as e:
                msg = f"组件 {comp.componentId}({comp.componentType}) 执行失败: {e}"
                log.warning("[flow] %s", msg, exc_info=True)
                node_runs.append({"nodeId": comp.componentId, "capability": comp.componentType,
                                  "status": "FAILED",
                                  "elapsedMs": int((time.monotonic() - node_started) * 1000)})
                if comp.exceptionStrategy.upper() == "TERMINATE":
                    return ExecutorResult(
                        success=False,
                        records=context.records,
                        total=len(context.records),
                        warnings=context.warnings + [msg],
                        metadata={**context.metadata, "nodeRuns": node_runs},
                        elapsedMs=int((time.monotonic() - started) * 1000),
                        deepResult=context.deep_result,
                    )
                context.warnings.append(msg)
            else:
                node_runs.append({"nodeId": comp.componentId, "capability": comp.componentType,
                                  "status": "SUCCEEDED",
                                  "elapsedMs": int((time.monotonic() - node_started) * 1000)})

            # 存储步骤输出，供后续组件通过 ${componentId.xxx} 引用
            # 注意：HTML Page 不可序列化，这里只存标识
            context.step_results[comp.componentId] = {
                "records": context.records,
                "page": context.page is not None,
                "elements_count": len(context.elements),
                "deep_result": context.deep_result,
                "output": context.deep_result,
            }

            current_id = comp.nextComponentId

        return ExecutorResult(
            success=True,
            records=context.records,
            total=len(context.records),
            warnings=context.warnings,
            data=context.deep_result if context.deep_result is not None else context.records,
            metadata={**context.metadata, "nodeRuns": node_runs},
            elapsedMs=int((time.monotonic() - started) * 1000),
            deepResult=context.deep_result,
        )

    async def _execute_dag(
        self,
        config: FlowConfig,
        component_map: Dict[str, FlowComponentConfig],
        root: FlowContext,
        started: float,
        finished_nodes: set
    ) -> ExecutorResult:
        """DAG 并发执行引擎，只适用于纯 API / 无头无状态模式。"""
        incoming: Dict[str, List[Any]] = {node_id: [] for node_id in component_map}
        outgoing: Dict[str, List[Any]] = {node_id: [] for node_id in component_map}
        indegree: Dict[str, int] = {node_id: 0 for node_id in component_map}
        for edge in config.edges:
            source = self._endpoint_node(edge.from_)
            target = self._endpoint_node(edge.to)
            if source not in component_map or target not in component_map:
                return self._dag_failure(root, started, f"DAG 边引用未知节点: {source} -> {target}")
            outgoing[source].append(edge)
            incoming[target].append(edge)
            indegree[target] += 1

        ready = [node_id for node_id in component_map if indegree[node_id] == 0]
        if len(ready) != 1:
            return self._dag_failure(root, started, "DAG 必须只有一个入口")

        states: Dict[str, FlowContext] = {}
        node_runs: List[Dict[str, Any]] = []
        completed: List[str] = []
        enabled: Dict[str, bool] = {node_id: False for node_id in component_map}
        enabled[ready[0]] = True
        while ready:
            wave = ready
            ready = []
            results = await asyncio.gather(*[
                self._execute_dag_node(node_id, component_map[node_id], incoming[node_id],
                                       states, root, finished_nodes)
                for node_id in wave
            ])
            terminate = False
            for node_id, comp, ctx, status, node_run in results:
                root.step_results[node_id] = {
                    "records": ctx.records,
                    "page": ctx.page is not None,
                    "elements_count": len(ctx.elements),
                    "deep_result": ctx.deep_result,
                    "output": ctx.deep_result,
                }
                states[node_id] = ctx
                completed.append(node_id)
                node_runs.append(node_run)
                terminate = terminate or (
                    status == "FAILED" and comp.exceptionStrategy.upper() == "TERMINATE"
                ) or (status == "SUSPENDED")
            if terminate:
                metadata = dict(root.metadata)
                metadata["nodeRuns"] = node_runs
                metadata["flowContext"] = {
                    "step_results": root.step_results,
                    "variables": root.variables,
                    "records": root.records,
                    "deep_result": root.deep_result,
                    "base_url": root.base_url
                }
                return ExecutorResult(
                    success=False,
                    suspended=(status == "SUSPENDED"),
                    warnings=root.warnings,
                    metadata=metadata,
                    elapsedMs=int((time.monotonic() - started) * 1000),
                )
            for node_id, _, _, _, _ in results:
                for edge in outgoing[node_id]:
                    target = self._endpoint_node(edge.to)
                    indegree[target] -= 1
                    if self._edge_active(edge.when, states[node_id]):
                        enabled[target] = True
                    if indegree[target] == 0:
                        if enabled[target]:
                            ready.append(target)
                        else:
                            self._skip_dag_branch(target, component_map, outgoing, indegree,
                                                  enabled, states, completed, node_runs, root, ready)

        if len(completed) != len(component_map):
            return self._dag_failure(root, started, "DAG 存在循环或不可达节点", node_runs)

        sinks = [node_id for node_id, edges in outgoing.items() if not edges]
        statuses = {run["nodeId"]: run["status"] for run in node_runs}
        successful_sinks = [node_id for node_id in sinks if statuses.get(node_id) == "SUCCEEDED"]
        if not successful_sinks:
            return self._dag_failure(root, started, "DAG 没有成功的终态节点", node_runs)
        final = states[successful_sinks[-1]]
        metadata = dict(root.metadata)
        metadata["nodeRuns"] = node_runs
        return ExecutorResult(
            success=True,
            records=final.records,
            total=len(final.records),
            warnings=root.warnings,
            data=final.deep_result if final.deep_result is not None else final.records,
            metadata=metadata,
            elapsedMs=int((time.monotonic() - started) * 1000),
            deepResult=final.deep_result,
        )

    async def _execute_dag_node(
        self,
        node_id: str,
        comp: FlowComponentConfig,
        incoming: List[Any],
        states: Dict[str, FlowContext],
        root: FlowContext,
        finished_nodes: set,
    ) -> Any:
        node_started = time.monotonic()
        
        # 恢复状态下，如果本节点之前已经执行完毕
        if node_id in finished_nodes:
            # 伪造一个已完成的返回值，context 的内容在 resume 时已经装载进 root.step_results，这里做个浅拷贝即可。
            ctx = FlowContext(input_data=root.input_data, metadata=root.metadata)
            if node_id in root.step_results:
                sr = root.step_results[node_id]
                ctx.records = sr.get("records", [])
                ctx.deep_result = sr.get("deep_result")
            status = "SUCCEEDED"
            node_run = {
                "nodeId": node_id,
                "capability": comp.componentType,
                "status": status,
                "elapsedMs": 0,
            }
            return node_id, comp, ctx, status, node_run

        ctx = self._dag_context(node_id, incoming, states, root)
        status = "SUCCEEDED"
        try:
            handler = self._registry.get(comp.componentType.upper())
            if handler is None:
                raise ValueError(f"不支持的组件类型: {comp.componentType}")
            resolved_params = resolve_expressions(comp.params, ctx)
            result = handler(resolved_params, ctx, self)
            if hasattr(result, "__await__"):
                await result
        except SuspendExecution as exc:
            status = "SUSPENDED"
            msg = str(exc)
            log.info("[flow:dag] %s", msg)
            ctx.warnings.append(msg)
        except Exception as exc:
            status = "FAILED"
            msg = f"组件 {comp.componentId}({comp.componentType}) 执行失败: {exc}"
            log.warning("[flow:dag] %s", msg, exc_info=True)
            ctx.warnings.append(msg)
        node_run = {
            "nodeId": node_id,
            "capability": comp.componentType,
            "status": status,
            "elapsedMs": int((time.monotonic() - node_started) * 1000),
        }
        return node_id, comp, ctx, status, node_run

    def _edge_active(self, expression: Optional[str], source: FlowContext) -> bool:
        if not expression:
            return True
        match = re.fullmatch(r"\s*([\w.-]+)\s*(==|!=)\s*['\"]([^'\"]*)['\"]\s*", expression)
        if not match:
            raise ValueError(f"不支持的条件边表达式: {expression}")
        path, operator, expected = match.groups()
        current: Any = source.deep_result
        for segment in path.split("."):
            current = _access(current, segment)
        return (str(current) == expected) if operator == "==" else (str(current) != expected)

    def _skip_dag_branch(
        self, node_id: str, component_map: Dict[str, FlowComponentConfig],
        outgoing: Dict[str, List[Any]], indegree: Dict[str, int], enabled: Dict[str, bool],
        states: Dict[str, FlowContext], completed: List[str], node_runs: List[Dict[str, Any]],
        root: FlowContext, ready: List[str],
    ) -> None:
        if node_id in completed:
            return
        states[node_id] = self._clone_context(root)
        completed.append(node_id)
        node_runs.append({"nodeId": node_id, "capability": component_map[node_id].componentType,
                          "status": "SKIPPED", "elapsedMs": 0})
        for edge in outgoing[node_id]:
            target = self._endpoint_node(edge.to)
            indegree[target] -= 1
            if indegree[target] == 0:
                if enabled[target]:
                    ready.append(target)
                else:
                    self._skip_dag_branch(target, component_map, outgoing, indegree, enabled,
                                          states, completed, node_runs, root, ready)

    def _dag_context(
        self,
        node_id: str,
        edges: List[Any],
        states: Dict[str, FlowContext],
        root: FlowContext,
    ) -> FlowContext:
        if not edges:
            return self._clone_context(root)
        first = states[self._endpoint_node(edges[0].from_)]
        ctx = self._clone_context(first)
        for edge in edges:
            source_id = self._endpoint_node(edge.from_)
            source_port = self._endpoint_port(edge.from_)
            target_port = self._endpoint_port(edge.to)
            source = states[source_id]
            self._bind_port(ctx, target_port, source_port, source)
        return ctx

    def _clone_context(self, source: FlowContext) -> FlowContext:
        return FlowContext(
            page=source.page,
            elements=list(source.elements),
            records=copy.deepcopy(source.records),
            warnings=source.warnings,
            deep_result=copy.deepcopy(source.deep_result),
            base_url=source.base_url,
            step_results=source.step_results,
            variables=copy.deepcopy(source.variables),
            input_data=source.input_data,
            metadata=source.metadata,
            adaptive=source.adaptive,
        )

    def _bind_port(self, target: FlowContext, target_port: str,
                   source_port: str, source: FlowContext) -> None:
        if target_port in ("dom", "page") or source_port in ("response", "dom", "page"):
            target.page = source.page
            target.base_url = source.base_url
        if target_port == "elements" or source_port == "elements":
            target.elements = list(source.elements)
        if target_port in ("records", "items") or source_port == "records":
            target.records = copy.deepcopy(source.records)

    def _snapshot(self, ctx: FlowContext) -> Dict[str, Any]:
        return {
            "records": copy.deepcopy(ctx.records),
            "page": ctx.page is not None,
            "elements_count": len(ctx.elements),
            "deep_result": copy.deepcopy(ctx.deep_result),
            "output": copy.deepcopy(ctx.deep_result),
        }

    def _dag_failure(self, root: FlowContext, started: float, message: str,
                     node_runs: Optional[List[Dict[str, Any]]] = None) -> ExecutorResult:
        metadata = dict(root.metadata)
        metadata["nodeRuns"] = node_runs or []
        return ExecutorResult(success=False, warnings=root.warnings + [message], metadata=metadata,
                              elapsedMs=int((time.monotonic() - started) * 1000))

    def _endpoint_node(self, endpoint: str) -> str:
        return endpoint.split(".", 1)[0]

    def _endpoint_port(self, endpoint: str) -> str:
        parts = endpoint.split(".", 1)
        return parts[1] if len(parts) == 2 else ""

    @property
    def scraper_engine(self) -> Any:
        return self._scraper_engine

    def validate_url(self, url: str) -> None:
        """Validate every resolved outbound URL immediately before it is used."""
        if self._url_validator is not None:
            self._url_validator(url)

    def _register_builtin_components(self) -> None:
        """注册内置组件（基于注册表自动注册，对扩展开放，对修改封闭）"""
        from .components import COMPONENT_REGISTRY
        for comp_type, handler in COMPONENT_REGISTRY.items():
            self.register(comp_type, handler)
