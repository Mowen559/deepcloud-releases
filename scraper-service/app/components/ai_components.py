"""
FlowEngine 智能体 AI 流程组件

注册组件:
1. AI_EXTRACT: 从 HTML 或文本中通过大模型直接抽取结构化数据 (无需繁琐的选择器);
2. AI_ENRICH: 对已采集的 records 进行批量语义扩充 (摘要、分类、情感分析、打标);
3. AI_FILTER: 基于自然语言语义条件的智能记录过滤器。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from ..flow_engine import FlowContext, FlowEngine
from ..ai_service import AiService
from .registry import register_component

log = logging.getLogger("scraper.components.ai")


def _run_async(coro):
    """在同步组件执行环境中安全运行异步协同程序"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # 如果事件循环已在运行，使用独立的新循环或 thread executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return loop.run_until_complete(coro)


@register_component("AI_EXTRACT")
def handle_ai_extract(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    AI 智能抽取组件
    从当前上下文中的 HTML 或纯文本直接智能识别并抽取结构化记录

    params:
        fields: List[str] 或 Dict[str, str] — 需要提取的字段清单及其语义含义
        instruction: str (可选) — 附加指导说明
        maxRecords: int (可选，默认 10) — 限制单次提取的最大条数
    """
    fields = params.get("fields", ["title", "content"])
    instruction = params.get("instruction", "从页面中提取高质量数据列表")
    max_records = int(params.get("maxRecords", 10))

    html_content = ctx.html_content or ""
    if not html_content and ctx.variables:
        html_content = str(ctx.variables.get("latest_data", ""))

    if not html_content:
        log.warning("[AI_EXTRACT] 上下文中缺少 HTML 或文本内容，跳过抽取")
        return

    prompt = (
        f"请从以下文本/网页源码中抽取最多 {max_records} 条结构化记录。\n"
        f"抽取字段清单: {fields}\n"
        f"特别要求: {instruction}\n"
        "请严格输出一个 JSON 数组，数组中每个元素包含指定的字段。\n"
        f"内容样例 (截取):\n{html_content[:5000]}"
    )

    async def _extract():
        res = await AiService.call_llm(prompt, json_mode=True)
        try:
            # 清理可能的 Markdown 反引号
            import re
            clean = re.sub(r"^```(?:json)?\s*", "", res.strip(), flags=re.MULTILINE)
            clean = re.sub(r"\s*```$", "", clean.strip(), flags=re.MULTILINE)
            data = json.loads(clean)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 寻找内部的 list
                for val in data.values():
                    if isinstance(val, list):
                        return val
                return [data]
        except Exception as e:
            log.warning("[AI_EXTRACT] LLM 输出反序列化异常: %s", e)
            return []

    extracted = _run_async(_extract())
    if extracted:
        ctx.records.extend(extracted)
        log.info("[AI_EXTRACT] 智能体成功抽取 %d 条结构化记录", len(extracted))


@register_component("AI_ENRICH")
def handle_ai_enrich(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    AI 语义扩充与数据增强组件
    对当前 ctx.records 中已有的数据进行深层次理解并追加智能体字段

    params:
        instruction: str (必填) — 增强指令 (如: "根据标题和描述提取核心技术标签和情感倾向")
        targetField: str (可选) — 写入的目标新字段名，若不填则打平成顶层属性
    """
    if not ctx.records:
        log.info("[AI_ENRICH] 当前上下文中记录为空，无需增强")
        return

    instruction = params.get("instruction", "对数据进行语义增强，提炼核心关键词与分类")
    
    async def _enrich():
        return await AiService.enrich_records(ctx.records, instruction=instruction)

    enriched = _run_async(_enrich())
    if enriched:
        ctx.records = enriched
        log.info("[AI_ENRICH] 智能体成功增强 %d 条记录", len(enriched))


@register_component("AI_FILTER")
def handle_ai_filter(params: Dict[str, Any], ctx: FlowContext, engine: FlowEngine) -> None:
    """
    AI 语义条件过滤器组件
    根据自然语言条件让大模型判断每条记录是否保留

    params:
        condition: str (必填) — 筛选条件 (如: "只保留关于人工智能、芯片或云计算的科技内容")
    """
    if not ctx.records:
        return

    condition = params.get("condition", "判断内容是否符合高质量规范")

    async def _filter():
        kept = []
        for rec in ctx.records:
            prompt = (
                f"筛选条件: {condition}\n"
                f"当前数据记录: {json.dumps(rec, ensure_ascii=False)}\n"
                "请判断该记录是否符合上述筛选条件。\n"
                "请严格输出 JSON: {\"keep\": true} 或 {\"keep\": false, \"reason\": \"原因\"}。"
            )
            res = await AiService.call_llm(prompt, json_mode=True)
            try:
                import re
                clean = re.sub(r"^```(?:json)?\s*", "", res.strip(), flags=re.MULTILINE)
                clean = re.sub(r"\s*```$", "", clean.strip(), flags=re.MULTILINE)
                judgement = json.loads(clean)
                if judgement.get("keep") is True:
                    kept.append(rec)
            except Exception:
                # 容错：默认保留
                kept.append(rec)
        return kept

    survived = _run_async(_filter())
    before_count = len(ctx.records)
    ctx.records = survived
    log.info("[AI_FILTER] 语义过滤完成: 原始 %d 条 -> 留存 %d 条", before_count, len(survived))
