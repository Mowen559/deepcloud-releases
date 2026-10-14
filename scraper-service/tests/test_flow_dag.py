import asyncio

from app.flow_engine import FlowContext, FlowEngine
from app.models import FlowConfig


def test_dag_branches_are_isolated_and_joined_in_one_execution():
    engine = FlowEngine()

    def seed(params, ctx: FlowContext, _engine):
        ctx.records = [{"value": 1}]

    def branch(params, ctx: FlowContext, _engine):
        ctx.records[0]["branch"] = params["name"]

    engine.register("TEST_SEED", seed)
    engine.register("TEST_BRANCH", branch)
    config = FlowConfig.model_validate({
        "flowId": "dag-test",
        "firstComponentId": "seed",
        "components": [
            {"componentId": "seed", "componentType": "TEST_SEED"},
            {"componentId": "left", "componentType": "TEST_BRANCH", "params": {"name": "L"}},
            {"componentId": "right", "componentType": "TEST_BRANCH", "params": {"name": "R"}},
            {"componentId": "join", "componentType": "JOIN", "params": {"output": {
                "left": "${nodes.left.records[0]}",
                "right": "${nodes.right.records[0]}"
            }}},
            {"componentId": "result", "componentType": "RESULT_BUILD", "params": {
                "type": "STRUCTURED", "data": "${nodes.join.output}"
            }},
        ],
        "edges": [
            {"from": "seed.records", "to": "left.records"},
            {"from": "seed.records", "to": "right.records"},
            {"from": "left.records", "to": "join.left"},
            {"from": "right.records", "to": "join.right"},
            {"from": "join.output", "to": "result.data"},
        ],
    })

    result = asyncio.run(engine.execute(config))

    assert result.success
    assert result.deepResult == {
        "type": "STRUCTURED",
        "data": {
            "left": {"value": 1, "branch": "L"},
            "right": {"value": 1, "branch": "R"},
        },
    }
    assert [run["status"] for run in result.metadata["nodeRuns"]] == ["SUCCEEDED"] * 5


def test_switch_only_executes_the_matching_terminal_branch():
    engine = FlowEngine()
    config = FlowConfig.model_validate({
        "firstComponentId": "route",
        "components": [
            {"componentId": "route", "componentType": "SWITCH", "params": {
                "expression": "input.requestedResult == 'DOWNLOAD' ? 'download' : 'play'"
            }},
            {"componentId": "play", "componentType": "RESULT_BUILD",
             "params": {"type": "PLAY"}},
            {"componentId": "download", "componentType": "RESULT_BUILD",
             "params": {"type": "DOWNLOAD"}},
        ],
        "edges": [
            {"from": "route.play", "to": "play.input", "when": "route == 'play'"},
            {"from": "route.download", "to": "download.input", "when": "route == 'download'"},
        ],
    })

    result = asyncio.run(engine.execute(config, {"requestedResult": "PLAY"}))

    assert result.success
    assert result.deepResult == {"type": "PLAY"}
    statuses = {run["nodeId"]: run["status"] for run in result.metadata["nodeRuns"]}
    assert statuses == {"route": "SUCCEEDED", "download": "SKIPPED", "play": "SUCCEEDED"}
