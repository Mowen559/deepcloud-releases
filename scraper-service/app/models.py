"""
scraper-service 的请求/响应契约

与 engine-service 的 Java 模型一一对应（见 engine.domain.spec.FieldMapping /
SpiderJobSpec.Browser），字段名刻意保持 camelCase 与 Java 侧一致，
避免两端各写一套映射还得维护转换表。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FieldRule(BaseModel):
    """单个字段的提取规则，对应 Java 的 FieldMapping"""

    targetField: str = Field(..., description="落库后 data_json 里的 key")
    selector: Optional[str] = Field(None, description="CSS Selector 或 XPath")
    type: str = Field("CSS_SELECTOR", description="CSS_SELECTOR / XPATH / REGEX")
    extractAttr: str = Field("text", description="text / html / 或任意属性名如 href")
    regex: Optional[str] = Field(None, description="对提取结果做二次截取")
    regexGroup: int = Field(1, description="正则捕获组，0 表示整个匹配串")
    defaultValue: Optional[str] = Field(None, description="提取不到时的兜底值")
    fallbackSelectors: List[str] = Field(default_factory=list)


class BrowserOptions(BaseModel):
    """无头浏览器行为开关，对应 Java 的 SpiderJobSpec.Browser"""

    waitSelector: Optional[str] = None
    waitMs: int = 0
    networkIdle: bool = False
    solveCloudflare: bool = False
    disableResources: bool = True


class ScrapeRequest(BaseModel):
    url: str

    mode: str = Field(
        "stealthy",
        description="static=纯 HTTP（最快）| dynamic=渲染 | stealthy=渲染+指纹伪装",
    )

    container: Optional[str] = Field(
        None,
        description="列表容器选择器；留空表示整页视为单条记录（详情页场景）",
    )

    fields: List[FieldRule] = Field(default_factory=list)

    headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Optional[str] = Field(None, description="原始 Cookie 头字符串")
    proxy: Optional[str] = Field(None, description="http://user:pass@host:port")

    browser: BrowserOptions = Field(default_factory=BrowserOptions)

    timeoutMs: int = 30000

    adaptive: bool = Field(
        True,
        description="启用选择器自愈：正常路径写入元素指纹，选择器失效时按相似度重定位",
    )

    adaptiveDomain: Optional[str] = Field(
        None,
        description="站点换域名但结构沿用时，指定它以复用既有指纹库",
    )


# ─────────────────────────── 流程编排 ───────────────────────────


class FlowComponentConfig(BaseModel):
    """流程中的单个组件配置，对应老项目 ParseComponentConfig"""

    componentId: str = Field(..., description="组件唯一标识")
    componentType: str = Field(
        ...,
        description="LOAD_HTML / CSS_SELECT / ATTR_FILTER / FIELD_MAPPING / DEEP_PARSE / "
        "REGEX_FILTER / RESULT_OUTPUT / HTTP_REQUEST / JSON_EXTRACT / SET_VARIABLE / FOR_EACH",
    )
    params: Dict[str, Any] = Field(default_factory=dict, description="组件参数")
    nextComponentId: Optional[str] = Field(None, description="下一个组件 ID，为空表示链尾")
    exceptionStrategy: str = Field(
        "TERMINATE", description="TERMINATE=异常中断流程 / IGNORE=记录告警继续"
    )


class FlowEdgeConfig(BaseModel):
    """DAG 中带端口的有向边。"""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    to: str
    when: Optional[str] = None


class FlowConfig(BaseModel):
    """流程编排总配置；兼容线性链，并支持 edges DAG。"""

    flowId: Optional[str] = Field(None, description="流程唯一标识")
    components: List[FlowComponentConfig] = Field(..., description="组件列表")
    firstComponentId: str = Field(..., description="流程入口组件 ID")
    edges: List[FlowEdgeConfig] = Field(default_factory=list, description="DAG 边")


class ExecutorPipelineRequest(BaseModel):
    """Java 控制面提交给 Python 数据源执行器的稳定契约。"""

    apiVersion: str = "executor.deepcloud/v1"
    executionId: Optional[str] = None
    pipeline: FlowConfig
    input: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutorResult(BaseModel):
    """所有数据源执行计划共用的结果信封。"""

    success: bool = True
    suspended: bool = False
    outputType: str = "RECORD_SET"
    data: Any = None
    records: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    elapsedMs: int = 0
    deepResult: Optional[Dict[str, Any]] = Field(
        None, description="深度解析的嵌套结果（DEEP_PARSE 组件产出）"
    )
