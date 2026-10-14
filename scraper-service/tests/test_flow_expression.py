"""快速验证表达式引擎 + JSON_EXTRACT + SET_VARIABLE"""
import sys
sys.path.insert(0, ".")

from app.flow_engine import FlowContext, resolve_expressions
from app.flow_components import handle_json_extract, handle_set_variable, _json_path, _apply_filter

# ─── 表达式引擎 ───────────────────────────────────────────
ctx = FlowContext()
ctx.step_results["search"] = {
    "records": [{"title": "test", "url": "http://example.com/1"}],
    "page": True, "elements_count": 5, "deep_result": None,
}
ctx.variables["token"] = "abc123"
ctx.current_item = {"fileId": "f001", "name": "video.mp4"}

assert resolve_expressions("${search.records[0].title}", ctx) == "test"
assert resolve_expressions("${vars.token}", ctx) == "abc123"
assert resolve_expressions("${item.fileId}", ctx) == "f001"
assert resolve_expressions("Bearer ${vars.token}", ctx) == "Bearer abc123"
assert resolve_expressions("${index}", ctx) == 0

# 嵌套 dict/list 参数
params = {"url": "http://api.com/${item.fileId}", "headers": {"Auth": "${vars.token}"}}
resolved = resolve_expressions(params, ctx)
assert resolved["url"] == "http://api.com/f001"
assert resolved["headers"]["Auth"] == "abc123"

print("[PASS] Expression engine")

# ─── _json_path ───────────────────────────────────────────
data = {"data": {"files": [{"name": "a.mp4", "id": 1}, {"name": "b.txt", "id": 2}]}}
assert _json_path(data, "data.files") == data["data"]["files"]
assert _json_path(data, "$.data.files[0].name") == "a.mp4"
assert _json_path(data, "data.files[1].id") == 2
assert _json_path(data, "") == data

print("[PASS] _json_path")

# ─── _apply_filter ────────────────────────────────────────
items = [{"fileName": "a.mp4"}, {"fileName": "b.txt"}, {"fileName": "c.mkv"}]
assert len(_apply_filter(items, "fileName endsWith .mp4")) == 1
assert len(_apply_filter(items, "fileName endsWith .mp4")) == 1
assert len(_apply_filter(items, "fileName contains .")) == 3

print("[PASS] _apply_filter")

# ─── JSON_EXTRACT 组件 ────────────────────────────────────
ctx2 = FlowContext()
ctx2.step_results["api"] = {
    "statusCode": 200,
    "data": {"code": 0, "data": {"files": [
        {"file_name": "ep01.mp4", "fid": "f1", "size": 100},
        {"file_name": "ep02.mp4", "fid": "f2", "size": 200},
        {"file_name": "readme.txt", "fid": "f3", "size": 10},
    ]}},
}

params_extract = {
    "source": "${api.data}",
    "container": "data.files",
    "filter": "file_name endsWith .mp4",
    "mappings": [
        {"targetField": "name", "path": "file_name"},
        {"targetField": "fileId", "path": "fid"},
    ],
}
# 先 resolve source
resolved_params = resolve_expressions(params_extract, ctx2)
handle_json_extract(resolved_params, ctx2, None)
assert len(ctx2.records) == 2
assert ctx2.records[0]["name"] == "ep01.mp4"
assert ctx2.records[1]["fileId"] == "f2"

print("[PASS] JSON_EXTRACT")

# ─── SET_VARIABLE 组件 ────────────────────────────────────
ctx3 = FlowContext()
ctx3.records = [{"share_url": "https://pan.quark.cn/s/xxx"}]
ctx3.step_results["extract"] = {"records": ctx3.records}

params_var = {"variables": {"url": "${extract.records[0].share_url}"}}
resolved_var = resolve_expressions(params_var, ctx3)
handle_set_variable(resolved_var, ctx3, None)
assert ctx3.variables["url"] == "https://pan.quark.cn/s/xxx"

print("[PASS] SET_VARIABLE")

print("\n=== ALL TESTS PASSED ===")
