"""
本地 SQLite 数据库访问层 (Pure Python & Zero Dependency)

管理 local_spider_job, local_raw_data, local_job_log 等表，
数据默认存储于 ~/.deepcloud/engine.db，支持环境变量 DEEPCLOUD_ENGINE_DB 自定义。
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("scraper.db")

DEFAULT_DB_DIR = Path.home() / ".deepcloud"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "engine.db"


def get_db_path() -> Path:
    custom_path = os.getenv("DEEPCLOUD_ENGINE_DB")
    if custom_path:
        path = Path(custom_path)
    else:
        path = DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库表结构"""
    db_path = get_db_path()
    log.info("[db] 初始化本地 SQLite 数据库: %s", db_path)
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 本地采集任务表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_spider_job (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name        TEXT NOT NULL UNIQUE,
            source          TEXT NOT NULL,
            description     TEXT,
            loader_type     TEXT DEFAULT 'HTTP_CLIENT',
            spec_json       TEXT NOT NULL,
            cron_expression TEXT,
            auth_secret     TEXT,
            proxy_policy    TEXT,
            status          INTEGER DEFAULT 0, -- 0: 停止/待机, 1: 启用中, 2: 运行中
            phase           TEXT DEFAULT 'IDLE',
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. 原始采集记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_raw_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL,
            job_name        TEXT NOT NULL,
            source          TEXT,
            data_key        TEXT,
            data_json       TEXT NOT NULL,
            batch_no        TEXT,
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_job ON local_raw_data(job_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_data_key ON local_raw_data(data_key);")
        
        # 3. 执行日志表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_job_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL,
            job_name        TEXT NOT NULL,
            trigger_type    TEXT DEFAULT 'MANUAL', -- SCHEDULE / MANUAL / PREVIEW
            status          INTEGER DEFAULT 0,     -- 0: 成功, 1: 失败, 2: 跳过
            fetched_count   INTEGER DEFAULT 0,
            stored_count    INTEGER DEFAULT 0,
            page_count      INTEGER DEFAULT 0,
            message         TEXT,
            error_msg       TEXT,
            cost_ms         INTEGER DEFAULT 0,
            exec_time       DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_log_job ON local_job_log(job_id);")

        # 4. 本地数据源表 (Low-Code Data Source)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_data_source (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_code     TEXT NOT NULL UNIQUE,
            source_name     TEXT NOT NULL,
            source_type     TEXT DEFAULT 'SPIDER_JOB',
            access_mode     TEXT DEFAULT 'SNAPSHOT',
            driver_config   TEXT NOT NULL,
            param_specs     TEXT DEFAULT '[]',
            field_schemas   TEXT DEFAULT '[]',
            cache_policy    TEXT DEFAULT '{}',
            status          INTEGER DEFAULT 1,
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 5. 本地 WebApp 低代码应用表 (Low-Code App)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_web_app (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            app_key         TEXT NOT NULL UNIQUE,
            title           TEXT NOT NULL,
            description     TEXT,
            icon            TEXT,
            revision        INTEGER DEFAULT 1,
            status          TEXT DEFAULT 'DRAFT',
            package_spec    TEXT NOT NULL,
            current_version INTEGER DEFAULT 0,
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 6. 本地 WebApp 版本快照表 (Published Immutables)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_web_app_version (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id          INTEGER NOT NULL,
            app_key         TEXT NOT NULL,
            version         INTEGER NOT NULL,
            package_spec    TEXT NOT NULL,
            changelog       TEXT,
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(app_id, version)
        );
        """)

        # 7. 本地规则模板表 (Rule Template)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_rule_template (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name   TEXT NOT NULL,
            category        TEXT DEFAULT 'GENERAL',
            base_url        TEXT,
            rule_type       TEXT DEFAULT 'XPATH',
            group_name      TEXT,
            description     TEXT,
            spec_json       TEXT NOT NULL,
            create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 8. 引擎智能体 AI 配置表 (AI Agent Engine Config)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_ai_config (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key      TEXT NOT NULL UNIQUE,
            provider        TEXT DEFAULT 'openai',
            api_base        TEXT DEFAULT 'http://127.0.0.1:3001/v1',
            api_key         TEXT DEFAULT '',
            model           TEXT DEFAULT 'deepseek-chat',
            temperature     REAL DEFAULT 0.7,
            max_tokens      INTEGER DEFAULT 2048,
            system_prompt   TEXT,
            is_enabled      INTEGER DEFAULT 1,
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # 默认初始化一条 default 配置项
        cursor.execute("""
        INSERT OR IGNORE INTO local_ai_config (id, config_key, provider, api_base, api_key, model, is_enabled)
        VALUES (1, 'default', 'openai', 'http://127.0.0.1:3001/v1', '', 'deepseek-chat', 1);
        """)
        conn.commit()
    log.info("[db] 本地 SQLite 初始化完成")

