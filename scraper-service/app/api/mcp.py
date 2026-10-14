import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Body
import httpx

from ..ai_service import AiService
from ..core import ok, state
from ..core.config import HUB_REGISTER_URL, SCRAPER_PORT

log = logging.getLogger("scraper.mcp")

router = APIRouter(prefix="/api/v1/engine/mcp", tags=["MCP"])

SCRAPER_CAPABILITIES_MANIFEST = {
    "service_name": "scraper_engine",
    "callback_url": f"http://127.0.0.1:{SCRAPER_PORT}/api/v1/engine/mcp/invoke",
    "display_name": "网页采集与逆向分析引擎",
    "description": "提供全网网页自动化采集、HTML/JSON 解析、任务调度与原始数据查询能力",
    "tools": [
        {
            "name": "engine_generate_spider_spec",
            "description": "根据自然语言需求、入口 URL 或 HTML 片段，智能推导结构化的采集规则与字段映射",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "description": "采集需求意图描述"},
                    "entryUrl": {"type": "string", "description": "目标入口网站 URL"},
                    "htmlSample": {"type": "string", "description": "目标网页的 HTML 片段 (可选)"},
                },
                "required": ["intent"],
            },
        },
        {
            "name": "engine_create_and_run_job",
            "description": "根据采集规约创建任务并立即执行一次，并可向前端发送局部视图刷新指令",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "jobName": {"type": "string", "description": "任务唯一标识名称"},
                    "source": {"type": "string", "description": "来源标识，如 bilibili, weibo, custom"},
                    "description": {"type": "string", "description": "任务描述"},
                    "loaderType": {"type": "string", "description": "HTTP_CLIENT 或 HEADLESS_BROWSER"},
                    "spec": {"type": "object", "description": "符合 SpiderJobSpec 规范的规则对象"},
                },
                "required": ["jobName", "spec"],
            },
        },
        {
            "name": "engine_query_raw_data",
            "description": "查询指定任务已抓取沉淀的原始数据大盘",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "jobId": {"type": "integer", "description": "任务 ID (可选，不传查全部)"},
                    "limit": {"type": "integer", "default": 10, "description": "查询记录条数"},
                },
            },
        },
        {
            "name": "engine_diagnose_failure",
            "description": "分析采集失败的原因（如 403、反爬盾牌、选择器失效）并提供自愈方案",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "jobName": {"type": "string", "description": "任务名称"},
                    "errorMsg": {"type": "string", "description": "捕获到的错误信息"},
                    "snippet": {"type": "string", "description": "响应 HTML 片段 (可选)"},
                },
                "required": ["errorMsg"],
            },
        },
    ],
    "context_hints": {
        "applicable_routes": ["/engine/job", "/engine/data", "/engine/webapp"],
        "quick_prompts": [
            "帮我为当前目标网站生成采集规则",
            "查询最新一次采集任务的数据沉淀",
            "诊断当前采集异常与反爬特征",
        ],
    },
}


async def auto_register_to_hub():
    """在后台异步向 Hub 宣告注册能力，具备弹性重试机制"""
    for _ in range(5):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(HUB_REGISTER_URL, json=SCRAPER_CAPABILITIES_MANIFEST)
                if res.status_code == 200:
                    log.info("[hub] 爬虫引擎成功向 Hub (3001) 注册 4 项原子能力！")
                    return
        except Exception:
            pass
        await asyncio.sleep(2)
    log.info("[hub] Hub 暂未启动或离线，注册宣告将在 Hub 就绪后由微内核或触发器拉起。")


@router.get("/manifest")
async def get_mcp_manifest():
    """获取爬虫引擎已注册的能力清单 (Manifest)"""
    return ok(SCRAPER_CAPABILITIES_MANIFEST)


@router.post("/register-to-hub")
async def manual_register_to_hub():
    """手动触发向 Hub 注册"""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.post(HUB_REGISTER_URL, json=SCRAPER_CAPABILITIES_MANIFEST)
            return ok({
                "status": "registered" if res.status_code == 200 else "failed",
                "hubStatus": res.status_code,
                "manifest": SCRAPER_CAPABILITIES_MANIFEST,
            })
    except Exception as e:
        return ok({
            "status": "hub_offline",
            "message": f"连接 Hub (3001) 失败: {e}",
            "manifest": SCRAPER_CAPABILITIES_MANIFEST,
        })


@router.post("/invoke")
async def mcp_invoke(req: Dict[str, Any] = Body(...)):
    """Hub.rs 调用爬虫引擎的通用 MCP 执行回调接口"""
    tool_name = req.get("tool")
    arguments = req.get("arguments", {})
    log.info("[mcp] 收到 Hub 智能体工具调用指令: %s, 参数: %s", tool_name, arguments)

    # 1. 智能生成采集规则
    if tool_name == "engine_generate_spider_spec":
        intent = arguments.get("intent") or arguments.get("prompt") or ""
        entry_url = arguments.get("entryUrl") or arguments.get("url")
        html_sample = arguments.get("htmlSample")
        spec = await AiService.generate_spider_spec(intent, entry_url=entry_url, html_sample=html_sample)
        return {
            "success": True,
            "tool": tool_name,
            "result": spec,
            "message": "已成功生成采集规约与字段映射",
            "clientAction": {
                "type": "SET_FORM_SPEC",
                "spec": spec,
            },
        }

    # 2. 创建并立即运行采集任务
    elif tool_name == "engine_create_and_run_job":
        if not state.job_service:
            return {"success": False, "error": "采集引擎服务尚未就绪"}
        job_payload = {
            "jobName": arguments.get("jobName"),
            "source": arguments.get("source", "custom"),
            "description": arguments.get("description", "由 Hub 智能体 Copilot 自动生成创建"),
            "loaderType": arguments.get("loaderType", "HTTP_CLIENT"),
            "spec": arguments.get("spec", {}),
        }
        new_id = state.job_service.create_job(job_payload)
        asyncio.create_task(state.job_service.run_job(new_id, trigger_type="COPILOT"))
        return {
            "success": True,
            "tool": tool_name,
            "result": {"jobId": new_id, "jobName": job_payload["jobName"]},
            "message": f"任务 [{job_payload['jobName']}] (ID: {new_id}) 已创建并启动执行！",
            "clientAction": {
                "type": "REFRESH_VIEW",
                "target": "job_table",
                "highlightId": new_id,
            },
        }

    # 3. 查询原始采集数据
    elif tool_name == "engine_query_raw_data":
        if not state.job_service:
            return {"success": False, "error": "采集引擎服务尚未就绪"}
        job_id = arguments.get("jobId")
        limit = int(arguments.get("limit", 10))
        res = state.job_service.page_raw_data(page_num=1, page_size=limit, job_id=job_id)
        return {
            "success": True,
            "tool": tool_name,
            "result": res,
            "clientAction": {
                "type": "REFRESH_VIEW",
                "target": "raw_data_table",
            },
        }

    # 4. 采集异常诊断
    elif tool_name == "engine_diagnose_failure":
        job_name = arguments.get("jobName", "采集任务")
        error_msg = arguments.get("errorMsg", "未知异常")
        snippet = arguments.get("snippet")
        diag = await AiService.diagnose_failure(job_name, error_msg, response_snippet=snippet)
        return {
            "success": True,
            "tool": tool_name,
            "result": diag,
        }

    return {"success": False, "error": f"不支持或未知的工具名称: {tool_name}"}
