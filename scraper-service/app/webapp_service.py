"""
WebApp & DataSource 服务层 (纯 Python 本地独立实现)

承载低代码平台核心领域用例：
1. DataSource 管理、从任务一键逆向提取、运行时查询与字段映射；
2. WebAppSpec 草稿多资源管理 (PageDefinition / ActionDefinition / Schema)；
3. WebApp 校验、版本发布与快照归档；
4. WebApp 运行时装配 (给 /webapp-runtime 页面提供直接渲染所需的数据与组件树)。
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import get_connection

log = logging.getLogger("scraper.webapp")


class DataSourceService:
    """本地数据源管理"""

    def page_data_sources(
        self,
        page_num: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        offset = (page_num - 1) * page_size
        where_clauses = ["1=1"]
        params: List[Any] = []

        if keyword:
            where_clauses.append("(source_code LIKE ? OR source_name LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if source_type:
            where_clauses.append("source_type = ?")
            params.append(source_type)

        where_sql = " AND ".join(where_clauses)

        with get_connection() as conn:
            cursor = conn.cursor()
            count_res = cursor.execute(f"SELECT COUNT(*) FROM local_data_source WHERE {where_sql}", params).fetchone()
            total = count_res[0] if count_res else 0

            rows = cursor.execute(f"""
                SELECT * FROM local_data_source
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id": r["id"],
                    "sourceCode": r["source_code"],
                    "sourceName": r["source_name"],
                    "sourceType": r["source_type"],
                    "accessMode": r["access_mode"],
                    "driverConfig": json.loads(r["driver_config"]) if r["driver_config"] else {},
                    "paramSpecs": json.loads(r["param_specs"]) if r["param_specs"] else [],
                    "fieldSchemas": json.loads(r["field_schemas"]) if r["field_schemas"] else [],
                    "cachePolicy": json.loads(r["cache_policy"]) if r["cache_policy"] else {},
                    "status": r["status"],
                    "createTime": r["create_time"],
                    "updateTime": r["update_time"],
                })

        return {
            "records": records,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }

    def get_data_source(self, ds_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            r = cursor.execute("SELECT * FROM local_data_source WHERE id = ?", [ds_id]).fetchone()
            if not r:
                return None
            return {
                "id": r["id"],
                "sourceCode": r["source_code"],
                "sourceName": r["source_name"],
                "sourceType": r["source_type"],
                "accessMode": r["access_mode"],
                "driverConfig": json.loads(r["driver_config"]) if r["driver_config"] else {},
                "paramSpecs": json.loads(r["param_specs"]) if r["param_specs"] else [],
                "fieldSchemas": json.loads(r["field_schemas"]) if r["field_schemas"] else [],
                "cachePolicy": json.loads(r["cache_policy"]) if r["cache_policy"] else {},
                "status": r["status"],
                "createTime": r["create_time"],
                "updateTime": r["update_time"],
            }

    def create_data_source(self, data: Dict[str, Any]) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_code = data.get("sourceCode") or f"ds_{int(time.time())}"
        source_name = data.get("sourceName") or source_code
        source_type = data.get("sourceType") or "SPIDER_JOB"
        access_mode = data.get("accessMode") or "SNAPSHOT"
        driver_config = json.dumps(data.get("driverConfig") or {}, ensure_ascii=False)
        param_specs = json.dumps(data.get("paramSpecs") or [], ensure_ascii=False)
        field_schemas = json.dumps(data.get("fieldSchemas") or [], ensure_ascii=False)
        cache_policy = json.dumps(data.get("cachePolicy") or {}, ensure_ascii=False)
        status = data.get("status", 1)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO local_data_source (
                    source_code, source_name, source_type, access_mode,
                    driver_config, param_specs, field_schemas, cache_policy,
                    status, create_time, update_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                source_code, source_name, source_type, access_mode,
                driver_config, param_specs, field_schemas, cache_policy,
                status, now, now
            ])
            conn.commit()
            return cursor.lastrowid

    def update_data_source(self, ds_id: int, data: Dict[str, Any]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE local_data_source SET
                    source_name = coalesce(?, source_name),
                    source_type = coalesce(?, source_type),
                    access_mode = coalesce(?, access_mode),
                    driver_config = coalesce(?, driver_config),
                    param_specs = coalesce(?, param_specs),
                    field_schemas = coalesce(?, field_schemas),
                    cache_policy = coalesce(?, cache_policy),
                    status = coalesce(?, status),
                    update_time = ?
                WHERE id = ?
            """, [
                data.get("sourceName"),
                data.get("sourceType"),
                data.get("accessMode"),
                json.dumps(data["driverConfig"]) if "driverConfig" in data else None,
                json.dumps(data["paramSpecs"]) if "paramSpecs" in data else None,
                json.dumps(data["fieldSchemas"]) if "fieldSchemas" in data else None,
                json.dumps(data["cachePolicy"]) if "cachePolicy" in data else None,
                data.get("status"),
                now,
                ds_id,
            ])
            conn.commit()

    def delete_data_source(self, ds_id: int) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_data_source WHERE id = ?", [ds_id])
            conn.commit()

    def create_from_job(self, job_id: int, source_code: str, source_name: str) -> int:
        """从采集任务自动逆向推导出数据源契约"""
        with get_connection() as conn:
            cursor = conn.cursor()
            job = cursor.execute("SELECT * FROM local_spider_job WHERE id = ?", [job_id]).fetchone()
            if not job:
                raise ValueError("采集任务不存在")

            field_schemas = []
            if job["spec_json"]:
                try:
                    spec = json.loads(job["spec_json"])
                    for field in spec.get("fields", []):
                        name = field.get("name")
                        semantic = "TEXT"
                        lower = name.lower()
                        if "title" in lower or "name" in lower:
                            semantic = "TITLE"
                        elif "img" in lower or "pic" in lower or "cover" in lower or "poster" in lower:
                            semantic = "IMAGE"
                        elif "url" in lower or "href" in lower or "link" in lower:
                            semantic = "URL"
                        elif "price" in lower:
                            semantic = "PRICE"

                        field_schemas.append({
                            "name": name,
                            "type": "STRING",
                            "title": name,
                            "semantic": semantic,
                        })
                except Exception:
                    pass

            driver_config = {"jobId": job_id, "jobName": job["job_name"]}
            return self.create_data_source({
                "sourceCode": source_code,
                "sourceName": source_name or f"{job['job_name']} 数据源",
                "sourceType": "SPIDER_JOB",
                "accessMode": "SNAPSHOT",
                "driverConfig": driver_config,
                "fieldSchemas": field_schemas,
            })

    def query_data_source(self, ds_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据源查询：从本地采集数据提取记录并返回给低代码组件"""
        ds = self.get_data_source(ds_id)
        if not ds:
            raise ValueError("数据源不存在")

        driver_config = ds.get("driverConfig") or {}
        job_id = driver_config.get("jobId")

        with get_connection() as conn:
            cursor = conn.cursor()
            if job_id:
                rows = cursor.execute(
                    "SELECT data_json FROM local_raw_data WHERE job_id = ? ORDER BY id DESC LIMIT 50",
                    [job_id]
                ).fetchall()
            else:
                rows = cursor.execute(
                    "SELECT data_json FROM local_raw_data ORDER BY id DESC LIMIT 50"
                ).fetchall()

            records = []
            for r in rows:
                try:
                    parsed = json.loads(r["data_json"])
                    if isinstance(parsed, list):
                        records.extend(parsed)
                    elif isinstance(parsed, dict):
                        records.append(parsed)
                except Exception:
                    continue

        return {
            "sourceCode": ds["sourceCode"],
            "records": records[:50],
            "total": len(records),
            "timestamp": int(time.time() * 1000),
        }


class WebAppService:
    """本地 WebApp 低代码应用管理"""

    def page_web_apps(
        self,
        page_num: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        offset = (page_num - 1) * page_size
        where_clauses = ["1=1"]
        params: List[Any] = []

        if keyword:
            where_clauses.append("(app_key LIKE ? OR title LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if status:
            where_clauses.append("status = ?")
            params.append(status)

        where_sql = " AND ".join(where_clauses)

        with get_connection() as conn:
            cursor = conn.cursor()
            count_res = cursor.execute(f"SELECT COUNT(*) FROM local_web_app WHERE {where_sql}", params).fetchone()
            total = count_res[0] if count_res else 0

            rows = cursor.execute(f"""
                SELECT * FROM local_web_app
                WHERE {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id": r["id"],
                    "appKey": r["app_key"],
                    "title": r["title"],
                    "description": r["description"],
                    "icon": r["icon"],
                    "revision": r["revision"],
                    "status": r["status"],
                    "currentVersion": r["current_version"],
                    "createTime": r["create_time"],
                    "updateTime": r["update_time"],
                })

        return {
            "records": records,
            "total": total,
            "pageNum": page_num,
            "pageSize": page_size,
        }

    def get_web_app(self, app_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            r = cursor.execute("SELECT * FROM local_web_app WHERE id = ?", [app_id]).fetchone()
            if not r:
                return None
            pkg = json.loads(r["package_spec"]) if r["package_spec"] else {}
            return {
                "id": r["id"],
                "appKey": r["app_key"],
                "title": r["title"],
                "description": r["description"],
                "icon": r["icon"],
                "revision": r["revision"],
                "status": r["status"],
                "packageSpec": pkg,
                "currentVersion": r["current_version"],
                "createTime": r["create_time"],
                "updateTime": r["update_time"],
            }

    def create_web_app(self, package_spec: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = package_spec.get("metadata") or {}
        app_key = metadata.get("name") or f"app_{int(time.time())}"
        title = metadata.get("title") or app_key
        description = metadata.get("description", "")
        icon = metadata.get("icon", "")

        # 初始化空资源包骨架
        if "pages" not in package_spec:
            package_spec["pages"] = {
                "_entry": {
                    "apiVersion": "webapp.deepcloud/v1",
                    "kind": "PageDefinition",
                    "metadata": {"name": "_entry", "version": 1},
                    "spec": {
                        "route": "/",
                        "title": title,
                        "componentTree": {
                            "type": "Page",
                            "props": {"title": title},
                            "children": [
                                {
                                    "type": "VideoGrid",
                                    "props": {},
                                    "dataSourceBinding": {}
                                }
                            ]
                        }
                    }
                }
            }

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO local_web_app (
                    app_key, title, description, icon, revision,
                    status, package_spec, current_version, create_time, update_time
                ) VALUES (?, ?, ?, ?, 1, 'DRAFT', ?, 0, ?, ?)
            """, [
                app_key, title, description, icon,
                json.dumps(package_spec, ensure_ascii=False),
                now, now
            ])
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "revision": 1,
                "status": "DRAFT",
            }

    def update_web_app(self, app_id: int, revision: int, package_spec: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata = package_spec.get("metadata") or {}
        new_rev = revision + 1

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE local_web_app SET
                    title = coalesce(?, title),
                    description = coalesce(?, description),
                    icon = coalesce(?, icon),
                    revision = ?,
                    package_spec = ?,
                    update_time = ?
                WHERE id = ?
            """, [
                metadata.get("title"),
                metadata.get("description"),
                metadata.get("icon"),
                new_rev,
                json.dumps(package_spec, ensure_ascii=False),
                now,
                app_id
            ])
            conn.commit()
            return {
                "id": app_id,
                "revision": new_rev,
                "status": "DRAFT",
            }

    def delete_web_app(self, app_id: int) -> None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM local_web_app WHERE id = ?", [app_id])
            cursor.execute("DELETE FROM local_web_app_version WHERE app_id = ?", [app_id])
            conn.commit()

    def validate_web_app(self, app_id: int) -> Dict[str, Any]:
        """校验 WebAppSpec 完整性"""
        app = self.get_web_app(app_id)
        if not app:
            return {"valid": False, "errors": ["应用不存在"]}
        pkg = app.get("packageSpec") or {}
        errors = []
        if not pkg.get("pages"):
            errors.append("应用缺少至少一个可执行 PageDefinition")
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    def publish_web_app(self, app_id: int) -> Dict[str, Any]:
        """发布 WebApp 为不可变运行快照"""
        app = self.get_web_app(app_id)
        if not app:
            raise ValueError("应用不存在")

        new_version = (app.get("currentVersion") or 0) + 1
        pkg = app.get("packageSpec") or {}
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_connection() as conn:
            cursor = conn.cursor()
            # 1. 存入版本快照
            cursor.execute("""
                INSERT INTO local_web_app_version (
                    app_id, app_key, version, package_spec, changelog, create_time
                ) VALUES (?, ?, ?, ?, '发布新版本', ?)
            """, [app_id, app["appKey"], new_version, json.dumps(pkg, ensure_ascii=False), now])

            # 2. 更新主表状态
            cursor.execute("""
                UPDATE local_web_app SET
                    status = 'PUBLISHED',
                    current_version = ?,
                    update_time = ?
                WHERE id = ?
            """, [new_version, now, app_id])
            conn.commit()

        return {
            "id": app_id,
            "version": new_version,
            "status": "PUBLISHED",
        }

    def list_versions(self, app_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT * FROM local_web_app_version
                WHERE app_id = ?
                ORDER BY version DESC
            """, [app_id]).fetchall()
            return [{
                "version": r["version"],
                "changelog": r["changelog"],
                "createTime": r["create_time"],
            } for r in rows]

    def list_resources(self, app_id: int, kind: str) -> List[Dict[str, Any]]:
        app = self.get_web_app(app_id)
        if not app:
            return []
        pkg = app.get("packageSpec") or {}
        plural_kind = f"{kind}s" if not kind.endswith("s") else kind
        res_map = pkg.get(plural_kind) or {}
        return list(res_map.values()) if isinstance(res_map, dict) else []

    def save_resource(
        self,
        app_id: int,
        kind: str,
        key: str,
        revision: int,
        resource: Dict[str, Any],
    ) -> Dict[str, Any]:
        """更新设计态的组件树或动作资源"""
        app = self.get_web_app(app_id)
        if not app:
            raise ValueError("应用不存在")

        pkg = app.get("packageSpec") or {}
        plural_kind = f"{kind}s" if not kind.endswith("s") else kind
        if plural_kind not in pkg or not isinstance(pkg[plural_kind], dict):
            pkg[plural_kind] = {}

        actual_key = key or resource.get("metadata", {}).get("name") or "_entry"
        pkg[plural_kind][actual_key] = resource

        res = self.update_web_app(app_id, revision, pkg)
        return {
            "id": app_id,
            "revision": res["revision"],
            "resourceKey": actual_key,
        }

    def delete_resource(self, app_id: int, kind: str, key: str, revision: int) -> Dict[str, Any]:
        app = self.get_web_app(app_id)
        if not app:
            raise ValueError("应用不存在")

        pkg = app.get("packageSpec") or {}
        plural_kind = f"{kind}s" if not kind.endswith("s") else kind
        if plural_kind in pkg and isinstance(pkg[plural_kind], dict):
            pkg[plural_kind].pop(key, None)

        res = self.update_web_app(app_id, revision, pkg)
        return {
            "id": app_id,
            "revision": res["revision"],
        }

    def get_runtime_page(self, app_slug: str, page_name: str = "_entry", query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        低代码运行时入口：根据 app_slug 与 page_name 组装已发布的渲染树
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            app_row = cursor.execute("SELECT * FROM local_web_app WHERE app_key = ?", [app_slug]).fetchone()
            if not app_row:
                raise ValueError(f"WebApp '{app_slug}' 不存在")

            # 优先读已发布的最新快照
            ver_row = cursor.execute("""
                SELECT package_spec FROM local_web_app_version
                WHERE app_key = ? ORDER BY version DESC LIMIT 1
            """, [app_slug]).fetchone()

            raw_spec = ver_row["package_spec"] if ver_row else app_row["package_spec"]
            pkg = json.loads(raw_spec) if raw_spec else {}

            pages = pkg.get("pages") or {}
            # 找到指定页面或第一个页面
            target_page = pages.get(page_name) or next(iter(pages.values()), None)
            if not target_page:
                raise ValueError(f"页面 '{page_name}' 不存在")

            node = target_page.get("spec", {}).get("componentTree") or {
                "type": "Page",
                "props": {"title": app_row["title"]},
                "children": []
            }

            return {
                "appSlug": app_slug,
                "pageName": page_name,
                "node": node,
                "pageInput": query or {},
                "actionResult": {},
            }
