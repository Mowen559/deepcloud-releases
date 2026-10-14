import json
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from ..ai_service import AiService
from ..core import ok, state

router = APIRouter(prefix="/api/v1/engine/ai", tags=["AI"])


@router.get("/config")
async def get_ai_config():
    """获取引擎智能体 AI 配置"""
    return ok(AiService.get_config())


@router.put("/config")
@router.post("/config")
async def update_ai_config(data: Dict[str, Any] = Body(...)):
    """更新引擎智能体 AI 配置"""
    res = AiService.update_config(data)
    return ok(res)


@router.post("/generate-spec")
async def ai_generate_spec(data: Dict[str, Any] = Body(...)):
    """智能体生成采集规约 (Natural Language / HTML -> SpiderJobSpec)"""
    intent = data.get("intent") or data.get("prompt") or ""
    if not intent:
        raise HTTPException(status_code=400, detail="需求意图 (intent) 不能为空")
    entry_url = data.get("entryUrl") or data.get("url")
    html_sample = data.get("htmlSample") or data.get("html")
    spec = await AiService.generate_spider_spec(intent, entry_url=entry_url, html_sample=html_sample)
    return ok(spec)


@router.post("/enrich-data")
async def ai_enrich_data(data: Dict[str, Any] = Body(...)):
    """智能体批量语义清洗与数据增强"""
    records = data.get("records")
    instruction = data.get("instruction", "提取核心标签、情感正负向与20字摘要")

    # 支持按 jobId 自动拉取原始数据
    job_id = data.get("jobId")
    if not records and job_id and state.job_service:
        raw_res = state.job_service.page_raw_data(page_num=1, page_size=20, job_id=job_id)
        raw_items = raw_res.get("records", [])
        records = []
        for item in raw_items:
            try:
                parsed = json.loads(item["dataJson"])
                if isinstance(parsed, list):
                    records.extend(parsed)
                elif isinstance(parsed, dict):
                    records.append(parsed)
            except Exception:
                pass

    if not records:
        return ok([])

    enriched = await AiService.enrich_records(records, instruction=instruction)
    return ok(enriched)


@router.post("/diagnose")
async def ai_diagnose(data: Dict[str, Any] = Body(...)):
    """采集异常智能诊断与自愈建议"""
    job_name = data.get("jobName", "采集任务")
    error_msg = data.get("errorMsg") or data.get("error") or "未知错误"
    snippet = data.get("snippet")
    res = await AiService.diagnose_failure(job_name, error_msg, response_snippet=snippet)
    return ok(res)


@router.post("/chat")
async def ai_chat(data: Dict[str, Any] = Body(...)):
    """采集引擎与工作流智能体对话交互"""
    prompt = data.get("prompt") or data.get("message") or ""
    system_prompt = data.get("systemPrompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="提问内容不能为空")
    reply = await AiService.call_llm(prompt, system_prompt=system_prompt)
    return ok({"reply": reply})
