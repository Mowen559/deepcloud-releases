"""
DeepCloud PC 端 TVBox / Drpy Python Spider 运行时与驱动引擎
负责动态加载、隔离执行 TVBox 与 Drpy 的 Python 爬虫源（spider.py）
"""

import importlib.util
import json
import logging
import os
import sys
import threading
import traceback
from typing import Any, Dict, List, Optional

log = logging.getLogger("scraper.pyspider")

# 爬虫实例缓存与线程锁
_instances: Dict[str, Any] = {}
_modules: Dict[str, Any] = {}
_lock = threading.RLock()


def _ensure_libs_path():
    """将常见的爬虫依赖目录注入 sys.path"""
    # 1. 尝试注入当前工作区可能存在的第三方/本地规则运行库
    app_data = os.getenv("APPDATA", "")
    candidates = [
        os.path.join(app_data, "deepcloud", "hk_files", "rules", "DrpyHiker", "plugins", "chaquopy", "libs_py"),
        os.path.join(app_data, "deepcloud", "hk_files", "data", "DrpyHiker", "libs_py"),
        os.path.join(os.path.dirname(__file__), "pyspider_libs"),
    ]
    for c in candidates:
        if os.path.exists(c) and c not in sys.path:
            sys.path.insert(0, c)


def _ensure_builtin_base_spider():
    """
    内置注入 TVBox 标准 base.spider.Spider 基类到 sys.modules。
    当用户本地仅存放独立的 .py 爬虫脚本而未携带 base/spider.py 目录时，
    确保 `from base.spider import Spider` 零配置直接可用。
    """
    try:
        import base.spider  # type: ignore
        return
    except ImportError:
        pass

    import re
    import types
    import urllib.parse
    import urllib.request
    import ssl

    class _FallbackResponse:
        def __init__(self, content: bytes, status_code: int = 200, headers: Optional[Dict[str, str]] = None, url: str = ""):
            self.content = content or b""
            self.status_code = status_code
            self.headers = headers or {}
            self.url = url
            self.encoding = "utf-8"

        @property
        def text(self) -> str:
            try:
                return self.content.decode(self.encoding or "utf-8", errors="replace")
            except Exception:
                return self.content.decode("utf-8", errors="replace")

        def json(self) -> Any:
            return json.loads(self.text)

    class BaseSpider:
        def init(self, extend: Any = ""):
            pass

        def getName(self) -> str:
            return self.__class__.__name__

        def getDependence(self) -> List[str]:
            return []

        def setExtendInfo(self, extend: Any):
            self.extend = extend

        def isVideoFormat(self, url: str) -> bool:
            if not url:
                return False
            return bool(re.search(r"\.(?:m3u8|mp4|flv|mkv|avi|ts|mov|webm|mp3|m4a)(?:[?#]|$)", str(url), re.I))

        def manualVideoCheck(self) -> bool:
            return False

        def destroy(self):
            pass

        def homeContent(self, filter: bool) -> Dict[str, Any]:
            return {"class": [], "list": []}

        def homeVideoContent(self) -> Dict[str, Any]:
            return {"list": []}

        def categoryContent(self, tid: str, pg: Any, filter: bool, extend: Dict[str, Any]) -> Dict[str, Any]:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 20, "total": 0}

        def detailContent(self, ids: List[Any]) -> Dict[str, Any]:
            return {"list": []}

        def searchContent(self, key: str, quick: bool, pg: Any = "1") -> Dict[str, Any]:
            return {"list": []}

        def searchContentPage(self, key: str, quick: bool, pg: Any = "1") -> Dict[str, Any]:
            return self.searchContent(key, quick, pg)

        def playerContent(self, flag: str, id: str, vipFlags: List[str]) -> Dict[str, Any]:
            return {"parse": 0, "playUrl": "", "url": str(id or ""), "header": ""}

        def localProxy(self, param: Dict[str, Any]) -> List[Any]:
            return [200, "text/plain", ""]

        def fetch(
            self,
            url: str,
            params: Optional[Dict[str, Any]] = None,
            cookies: Optional[Dict[str, str]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = 10,
            verify: bool = False,
            stream: bool = False,
            allow_redirects: bool = True,
        ) -> Any:
            try:
                import requests  # type: ignore
                import urllib3  # type: ignore
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                return requests.get(
                    url,
                    params=params,
                    cookies=cookies,
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                    stream=stream,
                    allow_redirects=allow_redirects,
                )
            except ImportError:
                full_url = url
                if params:
                    qs = urllib.parse.urlencode(params, doseq=True)
                    full_url += ("&" if "?" in full_url else "?") + qs
                req_headers = dict(headers or {})
                if "User-Agent" not in req_headers and "user-agent" not in req_headers:
                    req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                if cookies:
                    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
                    req_headers["Cookie"] = cookie_str
                req = urllib.request.Request(full_url, headers=req_headers, method="GET")
                ctx = ssl._create_unverified_context()
                try:
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                        return _FallbackResponse(resp.read(), resp.status, dict(resp.headers), resp.geturl())
                except Exception as e:
                    log.warning(f"Fallback fetch error for {full_url}: {e}")
                    return _FallbackResponse(b"", 500, {}, full_url)

        def post(
            self,
            url: str,
            params: Optional[Dict[str, Any]] = None,
            data: Any = None,
            json: Any = None,
            cookies: Optional[Dict[str, str]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = 10,
            verify: bool = False,
            stream: bool = False,
            allow_redirects: bool = True,
        ) -> Any:
            try:
                import requests  # type: ignore
                import urllib3  # type: ignore
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                return requests.post(
                    url,
                    params=params,
                    data=data,
                    json=json,
                    cookies=cookies,
                    headers=headers,
                    timeout=timeout,
                    verify=verify,
                    stream=stream,
                    allow_redirects=allow_redirects,
                )
            except ImportError:
                import json as _json
                full_url = url
                if params:
                    qs = urllib.parse.urlencode(params, doseq=True)
                    full_url += ("&" if "?" in full_url else "?") + qs
                req_headers = dict(headers or {})
                if "User-Agent" not in req_headers and "user-agent" not in req_headers:
                    req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
                if cookies:
                    req_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
                body_bytes: Optional[bytes] = None
                if json is not None:
                    body_bytes = _json.dumps(json).encode("utf-8")
                    req_headers.setdefault("Content-Type", "application/json")
                elif isinstance(data, dict):
                    body_bytes = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
                    req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
                elif isinstance(data, str):
                    body_bytes = data.encode("utf-8")
                elif isinstance(data, bytes):
                    body_bytes = data
                req = urllib.request.Request(full_url, data=body_bytes, headers=req_headers, method="POST")
                ctx = ssl._create_unverified_context()
                try:
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                        return _FallbackResponse(resp.read(), resp.status, dict(resp.headers), resp.geturl())
                except Exception as e:
                    log.warning(f"Fallback post error for {full_url}: {e}")
                    return _FallbackResponse(b"", 500, {}, full_url)

        def html(self, content: str) -> Any:
            try:
                from lxml import etree  # type: ignore
                return etree.HTML(content or "")
            except ImportError:
                return None

        def str2json(self, s: str) -> Any:
            return json.loads(s)

        def json2str(self, obj: Any) -> str:
            return json.dumps(obj, ensure_ascii=False)

        def regStr(self, reg: str, src: str, group: int = 1) -> str:
            try:
                m = re.search(reg, str(src or ""))
                return m.group(group) if m else ""
            except Exception:
                return ""

        def cleanText(self, src: str) -> str:
            return re.sub(r"[\r\n\t\s]+", " ", str(src or "")).strip()

        def removeHtmlTags(self, src: str) -> str:
            return re.sub(r"<[^>]+>", "", str(src or ""))

        def getProxyUrl(self, local: bool = True) -> str:
            return "http://127.0.0.1:18000/api/v1/pyspider/proxy"

        def log(self, msg: Any):
            log.info(f"[Spider] {msg}")

    base_mod = types.ModuleType("base")
    base_mod.__path__ = []
    spider_mod = types.ModuleType("base.spider")
    setattr(spider_mod, "Spider", BaseSpider)
    setattr(spider_mod, "BaseSpider", BaseSpider)
    setattr(base_mod, "spider", spider_mod)
    sys.modules.setdefault("base", base_mod)
    sys.modules.setdefault("base.spider", spider_mod)


_ensure_libs_path()
_ensure_builtin_base_spider()


class SpiderRunner:
    @classmethod
    def get_instance_key(cls, py_path: str, key: Optional[str] = None) -> str:
        return key or py_path

    @classmethod
    def _normalize_py_path(cls, py_path: str) -> str:
        raw = str(py_path or "").strip()
        if raw.startswith("file://"):
            raw = raw[len("file://"):]
            if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
                raw = raw[1:]
        return os.path.normpath(raw)

    @classmethod
    def load_spider(cls, py_path: str, key: Optional[str] = None, is_new: bool = False) -> Any:
        with _lock:
            inst_key = cls.get_instance_key(py_path, key)
            if not is_new and inst_key in _instances:
                return _instances[inst_key]

            # 规范化路径
            norm_path = cls._normalize_py_path(py_path)
            if not os.path.exists(norm_path):
                raise FileNotFoundError(f"Python 爬虫源文件不存在: {norm_path}")

            # 动态加载模块
            mod_name = f"pyspider_{abs(hash(norm_path))}"
            spec = importlib.util.spec_from_file_location(mod_name, norm_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法为目标脚本创建 spec: {norm_path}")

            # 将脚本所在目录临时加入 sys.path，支持脚本内部同级 import
            script_dir = os.path.dirname(norm_path)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            _modules[inst_key] = module

            # 查找 Spider 类（跳过从 base.spider 导入的基类本身）
            base_spider_cls = getattr(sys.modules.get("base.spider"), "Spider", None)
            spider_cls = getattr(module, "Spider", None)
            if spider_cls is None or spider_cls is base_spider_cls:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name, None)
                    if (
                        isinstance(attr, type)
                        and attr is not base_spider_cls
                        and (attr_name in ("Spider", "spider", "PySpider", "Main") or (base_spider_cls and issubclass(attr, base_spider_cls)))
                    ):
                        spider_cls = attr
                        break

            if spider_cls is None:
                raise AttributeError(f"目标脚本未导出 Spider 类: {norm_path}")

            instance = spider_cls()
            _instances[inst_key] = instance
            log.info(f"成功加载 Python 爬虫源: {inst_key} (class: {spider_cls.__name__})")
            return instance

    @classmethod
    def get_spider(cls, key: str) -> Optional[Any]:
        with _lock:
            return _instances.get(key)

    @classmethod
    def set_extend_info(cls, spider: Any, ext: str = ""):
        if hasattr(spider, "setExtendInfo"):
            try:
                spider.setExtendInfo(ext)
            except Exception as e:
                log.warning(f"setExtendInfo 调用异常: {e}")
        elif hasattr(spider, "extend"):
            setattr(spider, "extend", ext)

    @classmethod
    def init_spider(cls, spider: Any, extend: Any = ""):
        if hasattr(spider, "init"):
            try:
                spider.init(extend)
            except Exception as e:
                log.warning(f"spider.init 调用异常: {e}")

    @classmethod
    def invoke(cls, spider: Any, method_name: str, args: List[Any]) -> Any:
        if not hasattr(spider, method_name):
            raise AttributeError(f"Spider 实例缺少指定方法: {method_name}")

        method = getattr(spider, method_name)
        if not callable(method):
            return method

        # 调用方法
        result = method(*args)

        # 若返回的是 JSON 字符串，尝试解析为 dict 方便网络层统一序列化
        if isinstance(result, str):
            s = result.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    return json.loads(s)
                except Exception:
                    pass
        return result


def _run_cli():
    """支持沙箱在本地引擎未启动时通过 CLI 子进程直接调用单个 Spider 方法"""
    try:
        if len(sys.argv) < 3 or sys.argv[1] != "--cli":
            sys.stdout.write(json.dumps({"code": "400", "message": "Invalid CLI arguments"}))
            return
        payload = json.loads(sys.argv[2])
        py_path = payload.get("pyPath") or payload.get("key") or ""
        key = payload.get("key") or py_path
        method = payload.get("method") or ""
        args = payload.get("args") or []
        extend = payload.get("extend") or ""

        spider = SpiderRunner.load_spider(py_path, key=key, is_new=False)
        if method != "init":
            try:
                 deps = SpiderRunner.invoke(spider, "getDependence", []) if hasattr(spider, "getDependence") else []
            except Exception:
                deps = []
            SpiderRunner.init_spider(spider, extend if extend else (deps if deps else ""))
        data = SpiderRunner.invoke(spider, method, args)
        sys.stdout.write(json.dumps({"code": "200", "message": "success", "data": data}, ensure_ascii=False))
    except Exception as e:
        sys.stdout.write(json.dumps({"code": "500", "message": str(e), "trace": traceback.format_exc()}, ensure_ascii=False))


if __name__ == "__main__":
    _run_cli()
