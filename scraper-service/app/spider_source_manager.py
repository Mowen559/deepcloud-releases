"""
DeepCloud 爬虫源目录与路径管理服务
支持用户自主配置、动态扫描、多目录聚合与持久化管理。
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("scraper.spider_manager")

CONFIG_FILE = Path.home() / ".deepcloud" / "spider_sources.json"
DEFAULT_SPIDERS_DIR = Path.home() / ".deepcloud" / "spiders"


class SpiderSourceManager:
    @classmethod
    def _ensure_init(cls) -> Dict[str, Any]:
        """确保配置目录与默认爬虫目录存在"""
        DEFAULT_SPIDERS_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not CONFIG_FILE.exists():
            initial_dirs = [str(DEFAULT_SPIDERS_DIR)]

            # 检测环境自定义变量
            env_dir = os.getenv("SPIDERS_DIR")
            if env_dir and os.path.exists(env_dir) and env_dir not in initial_dirs:
                initial_dirs.append(os.path.normpath(env_dir))

            # 检测当前用户的历史目录作为初始选项
            qq_dir = "D:/QQ/Download/短剧影视源码合集"
            if os.path.exists(qq_dir) and qq_dir not in initial_dirs:
                initial_dirs.append(os.path.normpath(qq_dir))

            data = {
                "default_dir": str(DEFAULT_SPIDERS_DIR),
                "directories": initial_dirs,
                "custom_spiders": {},
            }
            cls._save_config(data)
            return data

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("读取爬虫源配置异常，重置配置: %s", e)
            return {
                "default_dir": str(DEFAULT_SPIDERS_DIR),
                "directories": [str(DEFAULT_SPIDERS_DIR)],
                "custom_spiders": {},
            }

    @classmethod
    def _save_config(cls, data: Dict[str, Any]) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("保存爬虫源配置失败: %s", e)

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        config = cls._ensure_init()
        dir_details = []
        for d in config.get("directories", []):
            exists = os.path.exists(d)
            py_count = 0
            if exists:
                try:
                    py_count = len([f for f in os.listdir(d) if f.endswith(".py") and " (1)" not in f])
                except Exception:
                    pass
            dir_details.append({
                "path": os.path.normpath(d),
                "exists": exists,
                "spider_count": py_count,
                "is_default": os.path.normpath(d) == os.path.normpath(config.get("default_dir", "")),
            })

        # 自动识别本机局域网 IPv4 地址列表，方便手机聚阅接入
        lan_ips = []
        try:
            import socket
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if not ip.startswith("127.") and not ip.startswith("169.254."):
                    lan_ips.append(ip)
            lan_ips.sort(key=lambda x: (not x.startswith("192.16"), not x.startswith("172."), not x.startswith("10."), x))
        except Exception:
            pass
        if not lan_ips:
            lan_ips = ["127.0.0.1"]

        return {
            "default_dir": config.get("default_dir", str(DEFAULT_SPIDERS_DIR)),
            "directories": dir_details,
            "custom_spiders": config.get("custom_spiders", {}),
            "config_file": str(CONFIG_FILE),
            "lan_ips": lan_ips,
            "engine_port": 18000,
        }

    @classmethod
    def add_directory(cls, dir_path: str, set_as_default: bool = False) -> Dict[str, Any]:
        config = cls._ensure_init()
        norm = os.path.normpath(dir_path.strip())
        if not os.path.exists(norm):
            os.makedirs(norm, exist_ok=True)

        dirs = [os.path.normpath(d) for d in config.get("directories", [])]
        if norm not in dirs:
            dirs.append(norm)
            config["directories"] = dirs

        if set_as_default:
            config["default_dir"] = norm

        cls._save_config(config)
        return cls.get_settings()

    @classmethod
    def remove_directory(cls, dir_path: str) -> Dict[str, Any]:
        config = cls._ensure_init()
        norm = os.path.normpath(dir_path.strip())
        dirs = [os.path.normpath(d) for d in config.get("directories", []) if os.path.normpath(d) != norm]
        config["directories"] = dirs

        if os.path.normpath(config.get("default_dir", "")) == norm:
            config["default_dir"] = str(DEFAULT_SPIDERS_DIR)

        cls._save_config(config)
        return cls.get_settings()

    @classmethod
    def set_default_directory(cls, dir_path: str) -> Dict[str, Any]:
        config = cls._ensure_init()
        norm = os.path.normpath(dir_path.strip())
        config["default_dir"] = norm
        dirs = [os.path.normpath(d) for d in config.get("directories", [])]
        if norm not in dirs:
            dirs.append(norm)
            config["directories"] = dirs
        cls._save_config(config)
        return cls.get_settings()

    @classmethod
    def register_custom_spider(cls, name: str, file_path: str) -> Dict[str, Any]:
        config = cls._ensure_init()
        norm = os.path.normpath(file_path.strip())
        if not os.path.exists(norm):
            raise FileNotFoundError(f"文件不存在: {norm}")
        custom = config.get("custom_spiders", {})
        custom[name.strip()] = norm
        config["custom_spiders"] = custom
        cls._save_config(config)
        return cls.get_settings()

    @classmethod
    def unregister_custom_spider(cls, name: str) -> Dict[str, Any]:
        config = cls._ensure_init()
        custom = config.get("custom_spiders", {})
        custom.pop(name.strip(), None)
        config["custom_spiders"] = custom
        cls._save_config(config)
        return cls.get_settings()

    @classmethod
    def scan_all_spiders(cls) -> List[Dict[str, Any]]:
        """扫描所有已配置目录与自定义注册的爬虫"""
        config = cls._ensure_init()
        spiders: Dict[str, Dict[str, Any]] = {}

        # 1. 扫描配置的各个目录
        for d in config.get("directories", []):
            if not os.path.exists(d):
                continue
            try:
                for f in os.listdir(d):
                    if f.endswith(".py") and " (1)" not in f:
                        full_p = os.path.normpath(os.path.join(d, f))
                        pure_name = os.path.splitext(f)[0]
                        group = "短剧" if any(x in pure_name for x in ["短剧", "红果", "剧场"]) else "影视"
                        clean_key = pure_name.replace("🐬", "").replace("py", "").strip()
                        spiders[clean_key] = {
                            "key": clean_key,
                            "name": pure_name,
                            "filename": f,
                            "group": group,
                            "path": full_p,
                            "dir": os.path.normpath(d),
                        }
            except Exception as e:
                log.warning("扫描爬虫目录 %s 异常: %s", d, e)

        # 2. 合并单文件自定义注册项
        for name, full_p in config.get("custom_spiders", {}).items():
            if os.path.exists(full_p):
                spiders[name] = {
                    "key": name,
                    "name": name,
                    "filename": os.path.basename(full_p),
                    "group": "自定义注册",
                    "path": os.path.normpath(full_p),
                    "dir": os.path.dirname(os.path.normpath(full_p)),
                }

        return list(spiders.values())

    @classmethod
    def resolve_spider_path(cls, spider_key: str) -> Optional[Tuple[str, str]]:
        """
        根据 key 解析并返回 (full_path, spider_name)
        """
        all_spiders = cls.scan_all_spiders()
        key_raw = (spider_key or "").strip()
        key_lower = key_raw.lower()

        # 1. 精确匹配 key、name 或 filename
        for s in all_spiders:
            if s["key"].lower() == key_lower or s["name"].lower() == key_lower or s["filename"].lower() == key_lower:
                return s["path"], s["name"]

        # 2. 模糊包含匹配
        for s in all_spiders:
            if key_lower in s["key"].lower() or key_lower in s["name"].lower() or s["key"].lower() in key_lower:
                return s["path"], s["name"]

        # 3. 别名与快捷映射
        aliases = {
            "hongguo": ["红果", "新红果"],
            "nuanqiu": ["暖秋", "晚秋"],
            "daishu": ["袋鼠"],
            "yingtan": ["影探"],
            "jinpai": ["金牌"],
        }
        for alias_key, keywords in aliases.items():
            if key_lower == alias_key or any(k in key_lower for k in keywords):
                for s in all_spiders:
                    if any(k in s["name"] for k in keywords):
                        return s["path"], s["name"]

        # 4. 直接传入本地文件路径
        if os.path.exists(key_raw) and key_raw.endswith(".py"):
            return os.path.normpath(key_raw), os.path.splitext(os.path.basename(key_raw))[0]

        return None

    @classmethod
    def import_spider_package(cls, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        导入 .py 脚本文件或包含 .py 的 .zip 压缩包
        自动解压/保存至默认爬虫目录，并返回导入的脚本列表
        """
        import zipfile
        import io

        default_dir = Path(cls.get_default_directory())
        default_dir.mkdir(parents=True, exist_ok=True)

        imported_files = []
        lower_name = filename.lower()

        if lower_name.endswith(".py"):
            clean_base = os.path.basename(filename) or "spider.py"
            target_path = default_dir / clean_base
            with open(target_path, "wb") as f:
                f.write(file_bytes)
            imported_files.append({
                "filename": clean_base,
                "path": str(target_path),
                "size": len(file_bytes),
            })
        elif lower_name.endswith(".zip") or lower_name.endswith(".hk小程序"):
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for name in z.namelist():
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        continue
                    if name.lower().endswith(".py"):
                        content = z.read(name)
                        clean_base = os.path.basename(name)
                        if clean_base:
                            target_path = default_dir / clean_base
                            with open(target_path, "wb") as f:
                                f.write(content)
                            imported_files.append({
                                "filename": clean_base,
                                "path": str(target_path),
                                "size": len(content),
                            })
                    elif name.lower() == "data.zip":
                        try:
                            inner_data = z.read(name)
                            with zipfile.ZipFile(io.BytesIO(inner_data)) as inner_z:
                                for inner_name in inner_z.namelist():
                                    if inner_name.lower().endswith(".py"):
                                        c = inner_z.read(inner_name)
                                        b = os.path.basename(inner_name)
                                        if b:
                                            target_path = default_dir / b
                                            with open(target_path, "wb") as f:
                                                f.write(c)
                                            imported_files.append({
                                                "filename": b,
                                                "path": str(target_path),
                                                "size": len(c),
                                            })
                        except Exception as e:
                            log.warning("解压嵌套 data.zip 异常: %s", e)
        else:
            raise ValueError(f"不支持的文件格式: {filename}，仅支持 .py 脚本或 .zip / .hk小程序 压缩包")

        return {
            "imported_count": len(imported_files),
            "imported_files": imported_files,
            "target_dir": str(default_dir),
            "all_spiders": cls.scan_all_spiders(),
        }
