import asyncio
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..fetcher import ScraperEngine
    from ..flow_engine import FlowEngine
    from ..job_service import JobService
    from ..scheduler import LocalScheduler
    from ..webapp_service import DataSourceService, WebAppService


class AppState:
    """引擎全局运行时状态与核心单例容器"""

    def __init__(self) -> None:
        self.engine: Optional["ScraperEngine"] = None
        self.flow_engine: Optional["FlowEngine"] = None
        self.job_service: Optional["JobService"] = None
        self.scheduler: Optional["LocalScheduler"] = None
        self.ds_service: Optional["DataSourceService"] = None
        self.webapp_service: Optional["WebAppService"] = None
        self.active_executions: Dict[str, asyncio.Task] = {}


state = AppState()
