from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ..core import ok, state

router = APIRouter(prefix="/api/v1/engine/webapps", tags=["WebApps"])


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=False)
async def list_webapps(
    pageNum: int = Query(1, alias="pageNum"),
    pageSize: int = Query(20, alias="pageSize"),
    keyword: Optional[str] = Query(None, alias="keyword"),
    status: Optional[str] = Query(None, alias="status"),
):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return ok(state.webapp_service.page_web_apps(pageNum, pageSize, keyword, status))


@router.get("/{app_id}")
async def get_webapp(app_id: int):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    app_detail = state.webapp_service.get_web_app(app_id)
    if not app_detail:
        raise HTTPException(status_code=404, detail="WebApp 不存在")
    return ok(app_detail)


@router.post("", include_in_schema=True)
@router.post("/", include_in_schema=False)
async def create_webapp(data: Dict[str, Any] = Body(...)):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    pkg = data.get("packageSpec") or data
    res = state.webapp_service.create_web_app(pkg)
    return ok(res)


@router.put("/{app_id}")
async def update_webapp(app_id: int, data: Dict[str, Any] = Body(...)):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    revision = data.get("revision", 1)
    pkg = data.get("packageSpec") or data
    res = state.webapp_service.update_web_app(app_id, revision, pkg)
    return ok(res)


@router.delete("/{app_id}")
async def delete_webapp(app_id: int):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    state.webapp_service.delete_web_app(app_id)
    return ok(None)


@router.post("/{app_id}:validate")
async def validate_webapp(app_id: int):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    res = state.webapp_service.validate_web_app(app_id)
    return ok(res)


@router.post("/{app_id}:publish")
async def publish_webapp(app_id: int):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    res = state.webapp_service.publish_web_app(app_id)
    return ok(res)


@router.get("/{app_id}/versions")
async def list_webapp_versions(app_id: int):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return ok(state.webapp_service.list_versions(app_id))


@router.get("/{app_id}/resources/{kind}")
async def list_webapp_resources(app_id: int, kind: str):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return ok(state.webapp_service.list_resources(app_id, kind))


@router.post("/{app_id}/resources/{kind}")
async def create_webapp_resource(app_id: int, kind: str, data: Dict[str, Any] = Body(...)):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    revision = data.get("revision", 1)
    resource = data.get("resource") or {}
    key = resource.get("metadata", {}).get("name") or "_entry"
    res = state.webapp_service.save_resource(app_id, kind, key, revision, resource)
    return ok(res)


@router.put("/{app_id}/resources/{kind}/{resource_key:path}")
async def update_webapp_resource(app_id: int, kind: str, resource_key: str, data: Dict[str, Any] = Body(...)):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    revision = data.get("revision", 1)
    resource = data.get("resource") or {}
    res = state.webapp_service.save_resource(app_id, kind, resource_key, revision, resource)
    return ok(res)


@router.delete("/{app_id}/resources/{kind}/{resource_key:path}")
async def delete_webapp_resource(app_id: int, kind: str, resource_key: str, revision: int = Query(1)):
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    res = state.webapp_service.delete_resource(app_id, kind, resource_key, revision)
    return ok(res)


@router.get("/{app_slug}/pages/{page_name}")
async def get_webapp_runtime_page(app_slug: str, page_name: str = "_entry", request: Request = None):
    """WebApp 运行时入口：渲染已发布的低代码页面"""
    if not state.webapp_service:
        raise HTTPException(status_code=503, detail="服务未就绪")
    query_params = dict(request.query_params) if request else {}
    try:
        page_data = state.webapp_service.get_runtime_page(app_slug, page_name, query_params)
        return ok(page_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
