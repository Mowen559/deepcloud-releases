import asyncio
import logging

from fastapi import APIRouter, HTTPException

from ..core import state
from ..models import ExecutorPipelineRequest, ExecutorResult

log = logging.getLogger("scraper.pipelines")

router = APIRouter(tags=["Pipelines"])


@router.post(
    "/internal/api/v1/executor/pipelines:execute",
    response_model=ExecutorResult,
)
async def execute_pipeline(req: ExecutorPipelineRequest) -> ExecutorResult:
    """统一执行 HTML、浏览器和 JSON/API 流水线计划"""
    if state.flow_engine is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")

    execution_id = req.executionId or (req.metadata.get("executionId") if req.metadata else None)
    task = asyncio.create_task(state.flow_engine.execute(req.pipeline, req.input, req.metadata))
    if execution_id:
        state.active_executions[execution_id] = task

    try:
        result = await task
    except asyncio.CancelledError:
        log.info("[flow] 流程执行被取消: %s", execution_id)
        raise HTTPException(status_code=400, detail="流程执行被取消")
    except Exception as e:
        log.exception("[flow] 流程执行异常")
        raise HTTPException(status_code=400, detail=f"流程执行失败: {e}") from e
    finally:
        if execution_id:
            state.active_executions.pop(execution_id, None)

    if not result.success and not result.records:
        raise HTTPException(
            status_code=400,
            detail="; ".join(result.warnings) if result.warnings else "流程执行失败",
        )

    return result


@router.post("/internal/api/v1/executor/pipelines/{execution_id}:cancel")
async def cancel_pipeline(execution_id: str):
    """取消正在执行的流程"""
    task = state.active_executions.get(execution_id)
    if task:
        task.cancel()
        log.info("[flow] 收到取消请求，已下发取消信号: %s", execution_id)
        return {"status": "cancelled"}
    raise HTTPException(status_code=404, detail="执行不存在或已结束")
