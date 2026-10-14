import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from ..core import ok, state

router = APIRouter(prefix="/api/v1/engine/jobs", tags=["Jobs"])


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_jobs(
    pageNum: int = Query(1, alias="pageNum"),
    pageSize: int = Query(20, alias="pageSize"),
    jobName: Optional[str] = Query(None, alias="jobName"),
    source: Optional[str] = Query(None, alias="source"),
    status: Optional[int] = Query(None, alias="status"),
    phase: Optional[str] = Query(None, alias="phase"),
):
    """任务分页查询"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    result = state.job_service.page_jobs(
        page_num=pageNum,
        page_size=pageSize,
        job_name=jobName,
        source=source,
        status=status,
        phase=phase,
    )
    return ok(result)


@router.get("/logs")
async def list_job_logs(
    pageNum: int = Query(1, alias="pageNum"),
    pageSize: int = Query(20, alias="pageSize"),
    jobId: Optional[int] = Query(None, alias="jobId"),
    status: Optional[int] = Query(None, alias="status"),
):
    """执行日志分页查询"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    result = state.job_service.page_job_logs(
        page_num=pageNum,
        page_size=pageSize,
        job_id=jobId,
        status=status,
    )
    return ok(result)


@router.get("/data")
@router.get("/raw-data")
async def list_raw_data(
    pageNum: int = Query(1, alias="pageNum"),
    pageSize: int = Query(20, alias="pageSize"),
    jobId: Optional[int] = Query(None, alias="jobId"),
    jobName: Optional[str] = Query(None, alias="jobName"),
    batchNo: Optional[str] = Query(None, alias="batchNo"),
    dataKey: Optional[str] = Query(None, alias="dataKey"),
):
    """原始采集数据分页查询"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    result = state.job_service.page_raw_data(
        page_num=pageNum,
        page_size=pageSize,
        job_id=jobId,
        job_name=jobName,
        data_key=dataKey,
    )
    return ok(result)


@router.get("/{job_id}")
async def get_job(job_id: int):
    """获取任务详情 (含结构化 spec)"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    job = state.job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ok(job)


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def create_job(data: Dict[str, Any] = Body(...)):
    """创建采集任务"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    new_id = state.job_service.create_job(data)
    return ok({"id": new_id})


@router.put("/{job_id}")
async def update_job(job_id: int, data: Dict[str, Any] = Body(...)):
    """更新采集任务"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.job_service.update_job(job_id, data)
    return ok(None)


@router.patch("/{job_id}/status")
async def change_job_status(job_id: int, status: int = Query(...)):
    """启用/停用任务"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.job_service.change_status(job_id, status)
    return ok(None)


@router.post("/{job_id}/run")
async def run_job(job_id: int):
    """手动触发任务运行一次 (异步后台执行)"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    asyncio.create_task(state.job_service.run_job(job_id, trigger_type="MANUAL"))
    return ok(None)


@router.delete("/{job_id}")
async def delete_job(job_id: int):
    """删除任务及关联数据"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.job_service.delete_job(job_id)
    return ok(None)


@router.delete("/{job_id}/data")
async def reset_job_data(job_id: int):
    """清空任务已采集数据"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.job_service.reset_job_data(job_id)
    return ok(None)


@router.post("/preview")
async def preview_rule(data: Dict[str, Any] = Body(...)):
    """规则预览 (同步执行单页，不落库)"""
    if not state.job_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    result = await state.job_service.preview_rule(data)
    return ok(result)
