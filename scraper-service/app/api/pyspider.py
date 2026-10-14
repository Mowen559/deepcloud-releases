import logging
import re
from typing import Any, List, Optional
import urllib.parse

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..core import ok
from ..spider_runner import SpiderRunner
from ..spider_source_manager import SpiderSourceManager

log = logging.getLogger("scraper.pyspider")

router = APIRouter(tags=["PySpider"])


class PySpiderLoadRequest(BaseModel):
    pyPath: str
    key: Optional[str] = None
    ext: Optional[str] = ""
    isNew: Optional[bool] = False


class PySpiderInvokeRequest(BaseModel):
    key: str
    pyPath: Optional[str] = None
    method: str
    args: Optional[List[Any]] = []


class DirectorySettingRequest(BaseModel):
    path: str
    isDefault: Optional[bool] = False


class CustomSpiderRegisterRequest(BaseModel):
    name: str
    path: str


def _resolve_spider(spider_key: str):
    """根据 key 动态解析并加载对应的 Spider 实例（完全由用户设置的目录驱动）"""
    res = SpiderSourceManager.resolve_spider_path(spider_key)
    if not res:
        raise HTTPException(status_code=404, detail=f"未在配置的爬虫目录中找到匹配的源: {spider_key}")
    path, name = res
    spider = SpiderRunner.get_spider(name)
    if spider is None:
        spider = SpiderRunner.load_spider(path, key=name)
        SpiderRunner.init_spider(spider)
    return spider, name, name


@router.get("/api/v1/pyspider/health")
async def pyspider_health():
    """Python Spider 执行引擎健康探活"""
    return ok({"status": "ready", "engine": "pyspider-runner"})


@router.post("/api/v1/pyspider/load")
async def pyspider_load(req: PySpiderLoadRequest):
    """加载并初始化 Python Spider 源"""
    try:
        spider = SpiderRunner.load_spider(req.pyPath, req.key, req.isNew or False)
        SpiderRunner.set_extend_info(spider, req.ext or "")
        SpiderRunner.init_spider(spider, req.ext or "")
        return ok({
            "key": SpiderRunner.get_instance_key(req.pyPath, req.key),
            "status": "ready",
            "hasDependence": hasattr(spider, "getDependence"),
        })
    except Exception as e:
        log.error("加载 Python 爬虫源失败: %s", e, exc_info=True)
        return {"code": "500", "message": f"加载失败: {str(e)}", "data": None}


@router.post("/api/v1/pyspider/invoke")
async def pyspider_invoke(req: PySpiderInvokeRequest):
    """执行 Spider 实例方法 (homeContent, categoryContent, detailContent 等)"""
    try:
        spider = SpiderRunner.get_spider(req.key)
        if spider is None and req.pyPath:
            spider = SpiderRunner.load_spider(req.pyPath, req.key)
        if spider is None:
            return {"code": "404", "message": f"未找到爬虫实例: {req.key}", "data": None}

        result = SpiderRunner.invoke(spider, req.method, req.args or [])
        return ok(result)
    except Exception as e:
        log.error("执行 Python 爬虫方法 %s 失败: %s", req.method, e, exc_info=True)
        return {"code": "500", "message": f"调用失败: {str(e)}", "data": None}


@router.get("/api/v1/pyspider/settings")
async def pyspider_get_settings():
    """获取当前所有配置的爬虫源目录、默认路径及各目录扫描状态"""
    return ok(SpiderSourceManager.get_settings())


@router.post("/api/v1/pyspider/settings/dir")
async def pyspider_add_dir(req: DirectorySettingRequest):
    """添加或更新爬虫源目录（如果目录不存在将自动创建）"""
    res = SpiderSourceManager.add_directory(req.path, req.isDefault or False)
    return ok(res)


@router.delete("/api/v1/pyspider/settings/dir")
async def pyspider_remove_dir(path: str = Query(..., description="要移除的目录完整路径")):
    """移除指定的爬虫源扫描目录"""
    res = SpiderSourceManager.remove_directory(path)
    return ok(res)


@router.post("/api/v1/pyspider/settings/custom_spider")
async def pyspider_register_spider(req: CustomSpiderRegisterRequest):
    """独立注册外部单文件 Python 爬虫源"""
    try:
        res = SpiderSourceManager.register_custom_spider(req.name, req.path)
        return ok(res)
    except Exception as e:
        return {"code": "400", "message": str(e), "data": None}


@router.delete("/api/v1/pyspider/settings/custom_spider")
async def pyspider_unregister_spider(name: str = Query(..., description="注册的爬虫源名称")):
    """取消独立注册的 Python 爬虫源"""
    res = SpiderSourceManager.unregister_custom_spider(name)
    return ok(res)


class LocalImportRequest(BaseModel):
    path: str


@router.post("/api/v1/pyspider/upload")
async def pyspider_upload_package(file: UploadFile = File(...)):
    """上传并导入 Python 爬虫包（支持 .py 脚本文件或 .zip / .hk小程序 压缩包）"""
    try:
        content = await file.read()
        res = SpiderSourceManager.import_spider_package(content, file.filename or "spider.py")
        return ok(res)
    except Exception as e:
        log.error("上传爬虫包失败: %s", e, exc_info=True)
        return {"code": "400", "message": f"导入失败: {str(e)}", "data": None}


@router.post("/api/v1/pyspider/import_local")
async def pyspider_import_local(req: LocalImportRequest):
    """直接从本机文件路径导入 .py 或 .zip 爬虫包（支持 Electron 原生秒级导入）"""
    try:
        import os
        if not os.path.exists(req.path):
            raise FileNotFoundError(f"本地文件不存在: {req.path}")
        with open(req.path, "rb") as f:
            content = f.read()
        res = SpiderSourceManager.import_spider_package(content, os.path.basename(req.path))
        return ok(res)
    except Exception as e:
        log.error("本地导入爬虫包失败: %s", e, exc_info=True)
        return {"code": "400", "message": f"导入失败: {str(e)}", "data": None}


@router.get("/api/v1/pyspider/sources")
async def pyspider_sources(request: Request):
    """列出所有支持的 Python 爬虫源及其聚阅一键配置信息（全量动态扫描用户目录）"""
    client_host = request.headers.get("host") or "127.0.0.1:18000"
    scheme = request.url.scheme or "http"
    base_url = f"{scheme}://{client_host}"

    all_spiders = SpiderSourceManager.scan_all_spiders()
    result = [
        {
            "key": "all",
            "name": "🌟 全源动态合集 (手机端免重复导入，自动识别新增源)",
            "filename": "multi-source-aggregate",
            "group": "全源聚合",
            "path": "聚合用户配置的所有扫描目录",
            "dir": "全目录动态聚合",
            "maccms_api": f"{base_url}/api.php/provide/vod?spider=all",
            "juyue_rule_url": f"{base_url}/api/v1/pyspider/juyue_rule?spider=all",
        }
    ]
    for s in all_spiders:
        k = s["key"]
        result.append({
            "key": k,
            "name": s["name"],
            "filename": s["filename"],
            "group": s["group"],
            "path": s["path"],
            "dir": s["dir"],
            "maccms_api": f"{base_url}/api.php/provide/vod?spider={urllib.parse.quote(k)}",
            "juyue_rule_url": f"{base_url}/api/v1/pyspider/juyue_rule?spider={urllib.parse.quote(k)}",
        })
    return ok(result)


@router.get("/api.php/provide/vod")
@router.get("/api/v1/pyspider/vod")
async def maccms_vod_api(
    request: Request,
    spider: str = Query("hongguo", description="爬虫标识"),
    ac: Optional[str] = Query(None, description="动作: list, detail"),
    t: Optional[str] = Query(None, description="分类ID"),
    pg: Optional[str] = Query("1", description="页码"),
    wd: Optional[str] = Query(None, description="搜索关键字"),
    ids: Optional[str] = Query(None, description="视频ID列表，逗号分隔"),
):
    """
    MacCMS v10 标准 JSON 采集接口适配器
    供 聚阅小程序、海阔视界、TVBox 等第三方客户端无缝对接。
    """
    try:
        client_host = request.headers.get("host") or "127.0.0.1:18000"
        scheme = request.url.scheme or "http"
        base_origin = f"{scheme}://{client_host}"

        # -------------------------------------------------------------
        # 全源动态合集模式: spider == "all"
        # -------------------------------------------------------------
        if (spider or "").strip().lower() == "all":
            all_spiders = SpiderSourceManager.scan_all_spiders()

            # 1. 详情查询
            if ids:
                first_id = str(ids).split(",")[0].strip()
                if "@@" in first_id:
                    target_sp, actual_id = first_id.split("@@", 1)
                    return await maccms_vod_api(request, spider=target_sp, ac=ac, t=None, pg=None, wd=None, ids=actual_id)
                elif all_spiders:
                    return await maccms_vod_api(request, spider=all_spiders[0]["key"], ac=ac, t=None, pg=None, wd=None, ids=ids)

            # 2. 搜索查询 (并发聚合前 4 个源)
            if wd:
                aggregated_list = []
                for s_item in all_spiders[:4]:
                    try:
                        s_inst, s_k, _ = _resolve_spider(s_item["key"])
                        s_res = SpiderRunner.invoke(s_inst, "searchContent", [wd, False, str(pg or "1")])
                        for it in (s_res.get("list", []) if isinstance(s_res, dict) else []):
                            it_copy = dict(it)
                            it_copy["vod_id"] = f"{s_k}@@{it_copy.get('vod_id', '')}"
                            it_copy["vod_name"] = f"[{s_item['name']}] {it_copy.get('vod_name', '')}"
                            aggregated_list.append(it_copy)
                    except Exception:
                        pass
                return {
                    "code": 1,
                    "msg": "全源聚合搜索",
                    "page": int(pg) if str(pg).isdigit() else 1,
                    "pagecount": 1,
                    "limit": len(aggregated_list),
                    "total": len(aggregated_list),
                    "list": aggregated_list,
                }

            # 3. 分类查询 (分类 ID 对应某个源的 key 时切换到对应源)
            if t:
                res_t = SpiderSourceManager.resolve_spider_path(str(t))
                if res_t:
                    _, resolved_name = res_t
                    sub_res = await maccms_vod_api(request, spider=resolved_name, ac=ac, t=None, pg=pg, wd=None, ids=None)
                    raw_sub_list = sub_res.get("list", [])
                    for it in raw_sub_list:
                        it["vod_id"] = f"{resolved_name}@@{it.get('vod_id', '')}"
                    sub_res["list"] = raw_sub_list
                    return sub_res
                elif all_spiders:
                    return await maccms_vod_api(request, spider=all_spiders[0]["key"], ac=ac, t=t, pg=pg, wd=None, ids=None)

            # 4. 默认首页: 将所有爬虫源作为顶级分类（聚阅进入即可分类切源）
            classes = [
                {"type_id": s["key"], "type_name": s["name"]}
                for s in all_spiders
            ]
            mixed_list = []
            for s_item in all_spiders[:3]:
                try:
                    s_inst, s_k, _ = _resolve_spider(s_item["key"])
                    h_res = SpiderRunner.invoke(s_inst, "homeContent", [True])
                    for it in (h_res.get("list", []) if isinstance(h_res, dict) else [])[:10]:
                        it_copy = dict(it)
                        it_copy["vod_id"] = f"{s_k}@@{it_copy.get('vod_id', '')}"
                        mixed_list.append(it_copy)
                except Exception:
                    pass

            return {
                "code": 1,
                "msg": "全源动态合集",
                "page": 1,
                "pagecount": 1,
                "limit": len(mixed_list),
                "total": len(mixed_list),
                "class": classes,
                "list": mixed_list,
            }

        spider_inst, s_key, s_name = _resolve_spider(spider)

        # 1. 详情查询 (ids 存在 或 ac=detail 且未带分类/搜索)
        if ids or (ac == "detail" and not t and not wd):
            if not ids and ac == "detail":
                # 获取首页视频推荐列表（无具体 id 时）
                home_data = SpiderRunner.invoke(spider_inst, "homeContent", [True])
                vlist = home_data.get("list", []) if isinstance(home_data, dict) else []
                return {
                    "code": 1,
                    "msg": "数据列表",
                    "page": 1,
                    "pagecount": 1,
                    "limit": len(vlist),
                    "total": len(vlist),
                    "list": vlist,
                }

            id_list = [i.strip() for i in str(ids).split(",") if i.strip()]
            detail_res = SpiderRunner.invoke(spider_inst, "detailContent", [id_list])
            raw_list = detail_res.get("list", []) if isinstance(detail_res, dict) else []

            # 动态改写播放直链里的 localProxy 地址与非 http 播放 ID
            rewritten_list = []
            for item in raw_list:
                item_copy = dict(item)
                play_from_str = str(item_copy.get("vod_play_from", "默认线路"))
                from_parts = play_from_str.split("$$$")
                play_url_str = str(item_copy.get("vod_play_url", ""))
                url_groups = play_url_str.split("$$$")

                new_url_groups = []
                for g_idx, u_group in enumerate(url_groups):
                    cur_from = from_parts[g_idx] if g_idx < len(from_parts) else "默认"
                    new_episodes = []
                    for ep in u_group.split("#"):
                        if not ep.strip():
                            continue
                        parts = ep.split("$")
                        ep_title = parts[0]
                        ep_target = parts[1] if len(parts) > 1 else ep_title

                        # 如果是自定义 episode ID（非 http/https），包装为 /api/v1/pyspider/play 动态解析端点
                        if not ep_target.startswith("http://") and not ep_target.startswith("https://"):
                            ep_target = f"{base_origin}/api/v1/pyspider/play?spider={s_key}&flag={urllib.parse.quote(cur_from)}&id={urllib.parse.quote(ep_target)}"
                        else:
                            if "127.0.0.1:18000" in ep_target or "localhost:18000" in ep_target:
                                ep_target = ep_target.replace("http://127.0.0.1:18000", base_origin).replace("http://localhost:18000", base_origin)
                            if "/api/v1/pyspider/proxy" in ep_target and "spider=" not in ep_target:
                                ep_target = re.sub(r"(/api/v1/pyspider/proxy\?)", rf"\1spider={s_key}&", ep_target)

                        new_episodes.append(f"{ep_title}${ep_target}")
                    new_url_groups.append("#".join(new_episodes))

                item_copy["vod_play_url"] = "$$$".join(new_url_groups)
                rewritten_list.append(item_copy)

            return {
                "code": 1,
                "msg": "数据列表",
                "page": 1,
                "pagecount": 1,
                "limit": len(rewritten_list),
                "total": len(rewritten_list),
                "list": rewritten_list,
            }

        # 2. 搜索查询 (wd 存在)
        if wd:
            search_res = SpiderRunner.invoke(spider_inst, "searchContent", [wd, False, str(pg or "1")])
            vlist = search_res.get("list", []) if isinstance(search_res, dict) else []
            return {
                "code": 1,
                "msg": "搜索结果",
                "page": int(pg) if str(pg).isdigit() else 1,
                "pagecount": int(search_res.get("pagecount", 1)) if isinstance(search_res, dict) else 1,
                "limit": int(search_res.get("limit", 20)) if isinstance(search_res, dict) else 20,
                "total": int(search_res.get("total", len(vlist))) if isinstance(search_res, dict) else len(vlist),
                "list": vlist,
            }

        # 3. 分类筛选查询 (t 存在)
        if t:
            cat_res = SpiderRunner.invoke(spider_inst, "categoryContent", [str(t), str(pg or "1"), True, {}])
            vlist = cat_res.get("list", []) if isinstance(cat_res, dict) else []
            return {
                "code": 1,
                "msg": "分类列表",
                "page": int(cat_res.get("page", pg or 1)) if isinstance(cat_res, dict) else 1,
                "pagecount": int(cat_res.get("pagecount", 1)) if isinstance(cat_res, dict) else 1,
                "limit": int(cat_res.get("limit", 20)) if isinstance(cat_res, dict) else 20,
                "total": int(cat_res.get("total", len(vlist))) if isinstance(cat_res, dict) else len(vlist),
                "list": vlist,
            }

        # 4. 默认主页（分类导航与推荐数据）
        home_res = SpiderRunner.invoke(spider_inst, "homeContent", [True])
        classes = home_res.get("class", []) if isinstance(home_res, dict) else []
        vlist = home_res.get("list", []) if isinstance(home_res, dict) else []
        return {
            "code": 1,
            "msg": "数据列表",
            "page": 1,
            "pagecount": 1,
            "limit": len(vlist) if vlist else 20,
            "total": len(vlist) if vlist else 0,
            "class": classes,
            "list": vlist,
        }
    except Exception as e:
        log.error("MacCMS VOD 处理异常: %s", e, exc_info=True)
        return {
            "code": 0,
            "msg": f"接口异常: {str(e)}",
            "page": 1,
            "pagecount": 1,
            "limit": 0,
            "total": 0,
            "list": [],
        }


@router.get("/api/v1/pyspider/play")
async def pyspider_play(
    request: Request,
    spider: str = Query("hongguo"),
    flag: str = Query(""),
    id: str = Query(""),
):
    """
    通用播放地址解析中继（调用 spider.playerContent 并 302 重定向到流媒体播放地址）
    """
    try:
        target_spider = spider
        actual_id = id
        if "@@" in id:
            parts = id.split("@@", 1)
            target_spider = parts[0]
            actual_id = parts[1]

        spider_inst, s_key, _ = _resolve_spider(target_spider)
        client_host = request.headers.get("host") or "127.0.0.1:18000"
        scheme = request.url.scheme or "http"
        base_origin = f"{scheme}://{client_host}"

        play_res = SpiderRunner.invoke(spider_inst, "playerContent", [flag, actual_id, []])
        play_url = play_res.get("url", "") if isinstance(play_res, dict) else str(play_res or "")

        if "127.0.0.1:18000" in play_url or "localhost:18000" in play_url:
            play_url = play_url.replace("http://127.0.0.1:18000", base_origin).replace("http://localhost:18000", base_origin)
        if "/api/v1/pyspider/proxy" in play_url and "spider=" not in play_url:
            play_url = re.sub(r"(/api/v1/pyspider/proxy\?)", rf"\1spider={s_key}&", play_url)

        if not play_url:
            raise HTTPException(status_code=404, detail="未解析到有效播放地址")

        return RedirectResponse(url=play_url, status_code=302)
    except Exception as e:
        log.error("播放解析异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"播放解析异常: {str(e)}")


@router.get("/api/v1/pyspider/proxy")
async def pyspider_proxy(request: Request, spider: str = Query("hongguo")):
    """
    Python Spider 本地流媒体解密转发代理
    专门处理各类逆向防盗链视频流（如红果短剧的 CENC 动态分片流与头伪装）
    """
    try:
        spider_inst, _, _ = _resolve_spider(spider)
        params = dict(request.query_params)
        params.pop("spider", None)

        res = SpiderRunner.invoke(spider_inst, "localProxy", [params])
        if not isinstance(res, (list, tuple)) or len(res) < 3:
            raise HTTPException(status_code=502, detail="Invalid proxy response from spider")

        status_code = int(res[0])
        media_type = str(res[1])
        body = res[2]

        if isinstance(body, str):
            body = body.encode("utf-8")

        headers = {
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Content-Length": str(len(body)),
        }
        return Response(content=body, status_code=status_code, media_type=media_type, headers=headers)
    except Exception as e:
        log.error("Spider 代理流异常: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")


@router.get("/api/v1/pyspider/juyue_rule")
async def pyspider_juyue_rule(request: Request, spider: str = Query("hongguo")):
    """
    动态生成可直接导入聚阅小程序的原生 JS 规则脚本
    包含自动主页推荐、分类二级、多选集线路展示、搜索与无缝免嗅探播放
    """
    _, s_key, s_name = _resolve_spider(spider)
    client_host = request.headers.get("host") or "127.0.0.1:18000"
    scheme = request.url.scheme or "http"
    base_url = f"{scheme}://{client_host}"

    js_template = f"""// 聚阅完整规则 - {s_name}
// 来源: DeepCloud 边缘引擎 MacCMS 桥接器
let parse = {{
    作者: "DeepCloud",
    版本: "1.0",
    host: "{base_url}",
    spider: "{s_key}",
    频道: {{
        包含页: ["分类"]
    }},
    主页: function() {{
        let d = [];
        let url = this.host + "/api.php/provide/vod?spider=" + this.spider + "&ac=detail";
        let res = JSON.parse(fetch(url) || "{{}}");
        (res.list || []).forEach(it => {{
            d.push({{
                title: it.vod_name,
                url: it.vod_id,
                img: it.vod_pic,
                desc: it.vod_remarks || "",
                col_type: "movie_3"
            }});
        }});
        return d;
    }},
    二级: function(id) {{
        let url = this.host + "/api.php/provide/vod?spider=" + this.spider + "&ac=detail&ids=" + id;
        let res = JSON.parse(fetch(url) || "{{}}");
        let item = (res.list && res.list[0]) || {{}};
        let playList = [];
        let fromList = (item.vod_play_from || "默认线路").split("$$$");
        let urlList = (item.vod_play_url || "").split("$$$");

        fromList.forEach((fromName, idx) => {{
            let epStr = urlList[idx] || "";
            let episodes = epStr.split("#").filter(Boolean).map(ep => {{
                let parts = ep.split("$");
                return {{
                    title: parts[0] || "播放",
                    url: parts[1] || parts[0]
                }};
            }});
            playList.push(episodes);
        }});

        return {{
            title: item.vod_name,
            desc: item.vod_remarks || "",
            content: item.vod_content || item.vod_name,
            img: item.vod_pic,
            line: fromList,
            list: playList
        }};
    }},
    搜索: function(wd) {{
        let d = [];
        let url = this.host + "/api.php/provide/vod?spider=" + this.spider + "&wd=" + encodeURIComponent(wd);
        let res = JSON.parse(fetch(url) || "{{}}");
        (res.list || []).forEach(it => {{
            d.push({{
                title: it.vod_name,
                url: it.vod_id,
                img: it.vod_pic,
                desc: it.vod_remarks || ""
            }});
        }});
        return d;
    }}
}};
"""
    return Response(content=js_template, media_type="application/javascript; charset=utf-8")
