from fastapi import APIRouter

from .ai import router as ai_router
from .datasources import router as datasources_router
from .jobs import router as jobs_router
from .mcp import router as mcp_router
from .pipelines import router as pipelines_router
from .pyspider import router as pyspider_router
from .webapps import router as webapps_router

api_router = APIRouter()
api_router.include_router(jobs_router)
api_router.include_router(datasources_router)
api_router.include_router(webapps_router)
api_router.include_router(pipelines_router)
api_router.include_router(ai_router)
api_router.include_router(mcp_router)
api_router.include_router(pyspider_router)

__all__ = [
    "api_router",
    "jobs_router",
    "datasources_router",
    "webapps_router",
    "pipelines_router",
    "ai_router",
    "mcp_router",
    "pyspider_router",
]
