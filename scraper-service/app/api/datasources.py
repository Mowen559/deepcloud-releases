from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from ..core import ok, state

router = APIRouter(prefix="/api/v1/engine/datasources", tags=["DataSources"])


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_data_sources(
    pageNum: int = Query(1, alias="pageNum"),
    pageSize: int = Query(20, alias="pageSize"),
    keyword: Optional[str] = Query(None, alias="keyword"),
    sourceType: Optional[str] = Query(None, alias="sourceType"),
):
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return ok(state.ds_service.page_data_sources(pageNum, pageSize, keyword, sourceType))


@router.get("/{ds_id}")
async def get_data_source(ds_id: int):
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    ds = state.ds_service.get_data_source(ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return ok(ds)


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def create_data_source(data: Dict[str, Any] = Body(...)):
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    new_id = state.ds_service.create_data_source(data)
    return ok({"id": new_id})


@router.put("/{ds_id}")
async def update_data_source(ds_id: int, data: Dict[str, Any] = Body(...)):
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.ds_service.update_data_source(ds_id, data)
    return ok(None)


@router.delete("/{ds_id}")
async def delete_data_source(ds_id: int):
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.ds_service.delete_data_source(ds_id)
    return ok(None)


@router.post("/from-job")
async def create_datasource_from_job(data: Dict[str, Any] = Body(...)):
    """从采集任务一键逆向生成数据源"""
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    job_id = data.get("jobId")
    if not job_id:
        raise HTTPException(status_code=400, detail="缺少 jobId")
    source_code = data.get("sourceCode") or f"ds_job_{job_id}"
    source_name = data.get("sourceName") or ""
    try:
        new_id = state.ds_service.create_from_job(int(job_id), source_code, source_name)
        return ok({"id": new_id})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{ds_id}/query")
async def query_data_source_records(ds_id: int, params: Dict[str, Any] = Body(default={})):
    """执行数据源查询 (供低代码设计器与运行时消费)"""
    if not state.ds_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        res = state.ds_service.query_data_source(ds_id, params)
        return ok(res)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
