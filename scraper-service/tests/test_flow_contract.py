"""前端 Flow 编辑器与 Python FlowEngine 的跨语言契约回归测试。"""

import asyncio

from scrapling import Selector

from app.flow_components import (
    handle_attr_filter,
    handle_field_mapping,
    handle_for_each,
    handle_load_html,
    handle_regex_filter,
    handle_set_variable,
)
from app.flow_engine import FlowContext, FlowEngine
from app.main import _assert_safe_url
from app.models import ExecutorPipelineRequest, FlowComponentConfig, FlowConfig


class _CaptureScraper:
    def __init__(self):
        self.request = None

    async def fetch(self, request):
        self.request = request
        return Selector("<html><body></body></html>", url=request.url)


def test_load_html_accepts_editor_mode_aliases():
    scraper = _CaptureScraper()
    engine = FlowEngine(scraper_engine=scraper)

    asyncio.run(handle_load_html(
        {"url": "https://example.com", "mode": "fetch", "waitSelector": ".ready"},
        FlowContext(),
        engine,
    ))

    assert scraper.request.mode == "static"
    assert scraper.request.browser.waitSelector == ".ready"


def test_editor_legacy_component_params_remain_compatible():
    page = Selector('<div class="item" data-kind="video"><a href="/1">Episode 12</a></div>',
                    url="https://example.com")
    ctx = FlowContext(page=page, base_url="https://example.com")
    ctx.elements = list(page.css(".item"))
    engine = FlowEngine()

    handle_attr_filter({"field": "data-kind", "op": "EQ", "value": "video"}, ctx, engine)
    assert len(ctx.elements) == 1

    handle_field_mapping({"mappings": [
        {"targetField": "title", "path": "a", "extractType": "TEXT"},
    ]}, ctx, engine)
    assert ctx.records == [{"title": "Episode 12"}]

    handle_regex_filter({"field": "title", "pattern": r"(\d+)"}, ctx, engine)
    assert ctx.records[0]["title"] == "12"

    handle_set_variable({"name": "items", "value": ["a", "b"]}, ctx, engine)
    assert ctx.variables["items"] == ["a", "b"]

    asyncio.run(handle_for_each(
        {"list": ["a", "b"], "subComponents": [], "collectAs": "seen"},
        ctx,
        engine,
    ))
    assert ctx.variables["seen"] == []


def test_http_request_dynamic_url_is_checked_before_network_access():
    flow = FlowConfig(
        flowId="ssrf",
        firstComponentId="request",
        components=[FlowComponentConfig(
            componentId="request",
            componentType="HTTP_REQUEST",
            params={"url": "http://169.254.169.254/latest/meta-data/"},
        )],
    )

    result = asyncio.run(FlowEngine(url_validator=_assert_safe_url).execute(flow))

    assert result.success is False
    assert any("已阻断以防 SSRF" in warning for warning in result.warnings)


def test_executor_contract_resolves_typed_input_without_java_string_replacement():
    flow = FlowConfig(
        flowId="input-contract",
        firstComponentId="capture",
        components=[FlowComponentConfig(
            componentId="capture",
            componentType="CAPTURE",
            params={"selected": "${input.selection}", "page": "${input.page}"},
        )],
    )
    request = ExecutorPipelineRequest(
        executionId="exec-1",
        pipeline=flow,
        input={"selection": {"id": 7}, "page": 2},
    )
    engine = FlowEngine()

    def capture(params, ctx, _engine):
        ctx.records = [params]

    engine.register("CAPTURE", capture)
    result = asyncio.run(engine.execute(request.pipeline, request.input, request.metadata))

    assert result.success is True
    assert result.outputType == "RECORD_SET"
    assert result.records == [{"selected": {"id": 7}, "page": 2}]
    assert result.data == result.records


def test_field_mapping_accepts_canonical_java_selector_shape():
    page = Selector('<article><a class="play" href="/ep/1">第一集</a></article>',
                    url="https://example.com/list")
    ctx = FlowContext(page=page, base_url="https://example.com/list")

    handle_field_mapping({"mappings": [{
        "targetField": "url",
        "type": "CSS_SELECTOR",
        "selector": "a.play",
        "extractAttr": "href",
    }]}, ctx, FlowEngine())

    assert ctx.records == [{"url": "https://example.com/ep/1"}]


def test_action_pipeline_expression_filter_and_dedupe_contract():
    flow = FlowConfig(
        flowId="action-contract",
        firstComponentId="capture",
        components=[
            FlowComponentConfig(
                componentId="capture",
                componentType="CAPTURE",
                params={"url": "https://example.com?q=${urlEncode(input.keyword)}"},
                nextComponentId="filter",
            ),
            FlowComponentConfig(
                componentId="filter",
                componentType="RECORD_FILTER",
                params={"conditions": [{"path": "title", "op": "NOT_EMPTY"}]},
                nextComponentId="dedupe",
            ),
            FlowComponentConfig(
                componentId="dedupe",
                componentType="DEDUPE",
                params={"keys": ["url"]},
            ),
        ],
    )
    engine = FlowEngine()

    def capture(params, ctx, _engine):
        assert params["url"] == "https://example.com?q=%E7%A7%91%E5%B9%BB%20%E7%89%87"
        ctx.records = [
            {"title": "第一集", "url": "/1"},
            {"title": "第一集重复", "url": "/1"},
            {"title": "", "url": "/2"},
        ]

    engine.register("CAPTURE", capture)
    result = asyncio.run(engine.execute(flow, {"keyword": "科幻 片"}))

    assert result.records == [{"title": "第一集", "url": "/1"}]
