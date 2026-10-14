"""
本地采集任务管理与执行编排服务 (JobService)

承接原 Java engine-service 的控制面核心用例：
1. 任务的增删改查与状态流转；
2. 规则预览 (previewRule)：构造临时流水线并在内存执行，返回样本；
3. 任务执行 (runJob)：执行流水线，将记录落库至 local_raw_data，并记录 local_job_log；
4. 采集日志与原始数据分页查询。
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .database import get_connection
from .flow_engine import FlowEngine
from .models import FlowComponentConfig, FlowConfig

log = logging.getLogger("scraper.job_service")


def spec_to_flow_config(spec: Dict[str, Any], page: int = 1) -> FlowConfig:
    """
    将前端 SpiderJobSpec 声明式规范转换为 FlowEngine 的 DAG 流水线组件树
    """
    loader = spec.get("loader") or {}
    url_template = loader.get("url", "")
    url = url_template.replace("{{page}}", str(page)).replace("{page}", str(page))
    
    loader_type = loader.get("type", "HTTP_CLIENT")
    mode = "static"
    if loader_type == "HEADLESS_BROWSER":
        mode = "stealthy"
    
    browser_opts = spec.get("browser") or {}
    container = spec.get("container")
    field_mappings = spec.get("fieldMappings") or []
    filter_conditions = spec.get("filterConditions") or []

    components: List[FlowComponentConfig] = []
    
    # 1. 网页/接口加载组件
    components.append(
        FlowComponentConfig(
            componentId="step_load",
            componentType="LOAD_HTML",
            params={
                "url": url,
                "mode": mode,
                "headers": loader.get("headers") or {},
                "cookies": loader.get("cookies"),
                "proxy": loader.get("proxy"),
                "browser": {
                    "waitSelector": browser_opts.get("waitSelector"),
                    "waitMs": browser_opts.get("waitMs", 0),
                    "networkIdle": browser_opts.get("networkIdle", False),
                    "solveCloudflare": browser_opts.get("solveCloudflare", False),
                    "disableResources": browser_opts.get("disableResources", True),
                }
            },
            nextComponentId="step_select" if container else "step_extract",
            exceptionStrategy="TERMINATE",
        )
    )

    # 2. 容器选择器组件 (可选)
    if container:
        components.append(
            FlowComponentConfig(
                componentId="step_select",
                componentType="CSS_SELECT",
                params={"selector": container},
                nextComponentId="step_extract",
                exceptionStrategy="TERMINATE",
            )
        )

    # 3. 字段映射提取组件
    fields_payload = []
    for fm in field_mappings:
        fields_payload.append({
            "targetField": fm.get("targetField") or "field",
            "selector": fm.get("selector"),
            "type": fm.get("type", "CSS_SELECTOR"),
            "extractAttr": fm.get("extractAttr", "text"),
            "regex": fm.get("regex"),
            "regexGroup": fm.get("regexGroup", 1),
            "defaultValue": fm.get("defaultValue"),
        })

    components.append(
        FlowComponentConfig(
            componentId="step_extract",
            componentType="FIELD_MAPPING",
            params={"fields": fields_payload},
            nextComponentId="step_filter" if filter_conditions else "step_output",
            exceptionStrategy="IGNORE",
        )
    )

    # 4. 过滤条件 (可选)
    if filter_conditions:
        components.append(
            FlowComponentConfig(
                componentId="step_filter",
                componentType="ATTR_FILTER",
                params={"filters": filter_conditions},
                nextComponentId="step_output",
                exceptionStrategy="IGNORE",
            )
        )

    # 5. 结果输出组件
    components.append(
        FlowComponentConfig(
            componentId="step_output",
            componentType="RESULT_OUTPUT",
            params={},
            nextComponentId=None,
            exceptionStrategy="TERMINATE",
        )
    )

    return FlowConfig(
        flowId=f"flow_{uuid.uuid4().hex[:8]}",
        components=components,
        firstComponentId="step_load",
    )


class JobService:
    def __init__(self, flow_engine: FlowEngine):
        self.flow_engine = flow_engine

    def page_jobs(
        self,
        page_num: int = 1,
        page_size: int = 20,
        job_name: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[int] = None,
        phase: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分页获取本地采集任务"""
        offset = (page_num - 1) * page_size
        where_clauses = ["1=1"]
        params: List[Any] = []

        if job_name:
            where_clauses.append("job_name LIKE ?")
            params.append(f"%{job_name}%")
        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if phase:
            where_clauses.append("phase = ?")
            params.append(phase)

        where_sql = " AND ".join(where_clauses)

        with get_connection() as conn:
            cursor = conn.cursor()
            count_res = cursor.execute(f"SELECT COUNT(*) FROM local_spider_job WHERE {where_sql}", params).fetchone()
            total = count_res[0] if count_res else 0

            query_sql = f"""
                SELECT id, job_name, source, description, loader_type, cron_expression,
                       auth_secret, proxy_policy, status, phase, create_time, update_time
                FROM local_spider_job
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """
            rows = cursor.execute(query_sql, params + [page_size, offset]).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id": r["id"],
                    "jobName": r["job_name"],
                    "source": r["source"],
                    "description": r["description"],
                    "loaderType": r["loader_type"],
                    "cronExpression": r["cron_expression"],
                    "authSecret": r["auth_secret"],
                    "proxyPolicy": r["proxy_policy"],
                    "status": r["status"],
                    "phase": r["phase"],
                    "createTime": r["create_time"],
                    "updateTime": r["update_time"],
                })

        return {
            "records": records,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """获取单个任务详情 (包含反序列化的 spec)"""
        with get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT * FROM local_spider_job WHERE id = ?", [job_id]).fetchone()
            if not row:
                return None

            spec = {}
            if row["spec_json"]:
                try:
                    spec = json.loads(row["spec_json"])
                except Exception:
                    spec = {}

            return {
                "id": row["id"],
                "jobName": row["job_name"],
                "source": row["source"],
                "description": row["description"],
                "loaderType": row["loader_type"],
                "spec": spec,
                "cronExpression": row["cron_expression"],
                "authSecret": row["auth_secret"],
                "proxyPolicy": row["proxy_policy"],
                "status": row["status"],
                "phase": row["phase"],
                "createTime": row["create_time"],
                "updateTime": row["update_time"],
            }

    def create_job(self, data: Dict[str, Any]) -> int:
        """创建本地采集任务"""
        job_name = data.get("jobName") or f"job_{int(time.time())}"
        source = data.get("source") or "default"
        description = data.get("description", "")
        loader_type = data.get("loaderType") or "HTTP_CLIENT"
        spec = data.get("spec") or {}
        cron_expression = data.get("cronExpression")
        auth_secret = data.get("authSecret")
        proxy_policy = data.get("proxyPolicy")
        status = data.get("status", 0)

        spec_json = json.dumps(spec, ensure_ascii=False)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO local_spider_job (
                    job_name, source, description, loader_type, spec_json,
                    cron_expression, auth_secret, proxy_policy, status, phase,
                    create_time, update_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IDLE', ?, ?)
            """, [
                job_name, source, description, loader_type, spec_json,
                cron_expression, auth_secret, proxy_policy, status, now, now
            ])
            conn.commit()
            return cursor.lastrowid

    def update_job(self, job_id: int, data: Dict[str, Any]) -> None:
        """更新本地采集任务"""
        job_name = data.get("jobName")
        source = data.get("source")
        description = data.get("description")
        loader_type = data.get("loaderType")
        spec = data.get("spec")
        cron_expression = data.get("cronExpression")
        auth_secret = data.get("authSecret")
        proxy_policy = data.get("proxyPolicy")
        status = data.get("status")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        fields = ["update_time = ?"]
        values: List[Any] = [now]

        if job_name is not None:
            fields.append("job_name = ?")
            values.append(job_name)
        if source is not None:
            fields.append("source = ?")
            values.append(source)
        if description is not None:
            fields.append("description = ?")
            values.append(description)
        if loader_type is not None:
            fields.append("loader_type = ?")
            values.append(loader_type)
        if spec is not None:
            fields.append("spec_json = ?")
            values.append(json.dumps(spec, ensure_ascii=False))
        if cron_expression is not None:
            fields.append("cron_expression = ?")
            values.append(cron_expression)
        if auth_secret is not None:
            fields.append("auth_secret = ?")
            values.append(auth_secret)
        if proxy_policy is not None:
            fields.append("proxy_policy = ?")
            values.append(proxy_policy)
        if status is not None:
            fields.append("status = ?")
            values.append(status)

        values.append(job_id)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE local_spider_job SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

    def change_status(self, job_id: int, status: int) -> None:
        """启停任务"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE local_spider_job SET status = ?, update_time = ? WHERE id = ?",
                [status, now, job_id]
            )
            conn.commit()

    def delete_job(self, job_id: int) -> None:
        """删除任务及关联数据"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_spider_job WHERE id = ?", [job_id])
            cursor.execute("DELETE FROM local_raw_data WHERE job_id = ?", [job_id])
            cursor.execute("DELETE FROM local_job_log WHERE job_id = ?", [job_id])
            conn.commit()

    def reset_job_data(self, job_id: int) -> None:
        """清空某任务的采集记录"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_raw_data WHERE job_id = ?", [job_id])
            conn.commit()

    async def preview_rule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        规则预览：同步单页执行，不落库，直接返回样本 records
        """
        spec = data.get("spec") or {}
        flow_config = spec_to_flow_config(spec, page=1)
        
        start_time = time.time()
        try:
            result = await self.flow_engine.execute(
                pipeline=flow_config,
                input_data={},
                metadata={"mode": "PREVIEW"}
            )
            cost_ms = int((time.time() - start_time) * 1000)
            
            samples = result.records or []
            return {
                "outcome": "SUCCESS" if result.success else "FAILED",
                "fetchedCount": len(samples),
                "storedCount": 0,
                "newCount": 0,
                "pageCount": 1,
                "costMs": cost_ms,
                "samples": samples[:50],  # 最多返回 50 条样本
                "warnings": result.warnings,
            }
        except Exception as e:
            cost_ms = int((time.time() - start_time) * 1000)
            log.exception("[job_service] 预览执行异常")
            return {
                "outcome": "FAILED",
                "fetchedCount": 0,
                "storedCount": 0,
                "pageCount": 0,
                "costMs": cost_ms,
                "errorMsg": str(e),
                "samples": [],
                "warnings": [f"执行异常: {e}"],
            }

    async def run_job(self, job_id: int, trigger_type: str = "MANUAL") -> Dict[str, Any]:
        """
        运行采集任务并持久化产出
        """
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"任务不存在: id={job_id}")

        spec = job.get("spec") or {}
        pagination = spec.get("pagination") or {}
        is_paging = pagination.get("enabled", False)
        start_page = int(pagination.get("startPage", 1))
        max_pages = int(pagination.get("maxPages", 1)) if is_paging else 1
        stop_on_empty = pagination.get("stopOnEmpty", True)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        batch_no = f"batch_{uuid.uuid4().hex[:12]}"
        
        # 标记运行中状态
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE local_spider_job SET phase = 'RUNNING' WHERE id = ?", [job_id])
            conn.commit()

        start_time = time.time()
        total_fetched = 0
        total_stored = 0
        pages_run = 0
        error_msg = None

        try:
            for page in range(start_page, start_page + max_pages):
                pages_run += 1
                flow_config = spec_to_flow_config(spec, page=page)
                res = await self.flow_engine.execute(
                    pipeline=flow_config,
                    input_data={"page": page},
                    metadata={"jobId": job_id, "batchNo": batch_no}
                )
                
                records = res.records or []
                total_fetched += len(records)

                if records:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        for rec in records:
                            # 提取去重键
                            data_key = str(rec.get("id") or rec.get("url") or uuid.uuid4().hex)
                            data_json = json.dumps(rec, ensure_ascii=False)
                            cursor.execute("""
                                INSERT INTO local_raw_data (
                                    job_id, job_name, source, data_key, data_json, batch_no, create_time, update_time
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, [
                                job_id, job["jobName"], job["source"], data_key, data_json, batch_no, now_str, now_str
                            ])
                            total_stored += 1
                        conn.commit()

                if not records and stop_on_empty:
                    log.info("[job_service] 第 %d 页无数据，触发 stopOnEmpty 停止抓取", page)
                    break

            cost_ms = int((time.time() - start_time) * 1000)
            status_code = 0  # 成功

        except Exception as e:
            cost_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            status_code = 1  # 失败
            log.exception("[job_service] 任务执行失败: %s", job["jobName"])

        finally:
            # 记录执行日志并复位 phase
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO local_job_log (
                        job_id, job_name, trigger_type, status, fetched_count,
                        stored_count, page_count, message, error_msg, cost_ms, exec_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    job_id, job["jobName"], trigger_type, status_code,
                    total_fetched, total_stored, pages_run,
                    f"抓取完成，共 {total_stored} 条数据入库", error_msg, cost_ms, now_str
                ])
                cursor.execute("UPDATE local_spider_job SET phase = 'IDLE' WHERE id = ?", [job_id])
                conn.commit()

        return {
            "jobId": job_id,
            "status": "SUCCESS" if status_code == 0 else "FAILED",
            "fetchedCount": total_fetched,
            "storedCount": total_stored,
            "pageCount": pages_run,
            "costMs": cost_ms,
            "errorMsg": error_msg,
        }

    def page_job_logs(
        self,
        page_num: int = 1,
        page_size: int = 20,
        job_id: Optional[int] = None,
        status: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行日志分页"""
        offset = (page_num - 1) * page_size
        where_clauses = ["1=1"]
        params: List[Any] = []

        if job_id is not None:
            where_clauses.append("job_id = ?")
            params.append(job_id)
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)

        where_sql = " AND ".join(where_clauses)

        with get_connection() as conn:
            cursor = conn.cursor()
            count_res = cursor.execute(f"SELECT COUNT(*) FROM local_job_log WHERE {where_sql}", params).fetchone()
            total = count_res[0] if count_res else 0

            rows = cursor.execute(f"""
                SELECT * FROM local_job_log
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id": r["id"],
                    "jobId": r["job_id"],
                    "jobName": r["job_name"],
                    "triggerType": r["trigger_type"],
                    "status": r["status"],
                    "fetchedCount": r["fetched_count"],
                    "storedCount": r["stored_count"],
                    "pageCount": r["page_count"],
                    "message": r["message"],
                    "errorMsg": r["error_msg"],
                    "costMs": r["cost_ms"],
                    "execTime": r["exec_time"],
                })

        return {
            "records": records,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }

    def page_raw_data(
        self,
        page_num: int = 1,
        page_size: int = 20,
        job_id: Optional[int] = None,
        job_name: Optional[str] = None,
        data_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """原始采集数据分页"""
        offset = (page_num - 1) * page_size
        where_clauses = ["1=1"]
        params: List[Any] = []

        if job_id is not None:
            where_clauses.append("job_id = ?")
            params.append(job_id)
        if job_name:
            where_clauses.append("job_name LIKE ?")
            params.append(f"%{job_name}%")
        if data_key:
            where_clauses.append("data_key LIKE ?")
            params.append(f"%{data_key}%")

        where_sql = " AND ".join(where_clauses)

        with get_connection() as conn:
            cursor = conn.cursor()
            count_res = cursor.execute(f"SELECT COUNT(*) FROM local_raw_data WHERE {where_sql}", params).fetchone()
            total = count_res[0] if count_res else 0

            rows = cursor.execute(f"""
                SELECT * FROM local_raw_data
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id": r["id"],
                    "jobId": r["job_id"],
                    "jobName": r["job_name"],
                    "source": r["source"],
                    "dataKey": r["data_key"],
                    "dataJson": r["data_json"],
                    "batchNo": r["batch_no"],
                    "createTime": r["create_time"],
                    "updateTime": r["update_time"],
                })

        return {
            "records": records,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }
