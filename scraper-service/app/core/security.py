import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

from .config import BLOCK_PRIVATE_NETWORK


def assert_safe_url(url: str) -> None:
    """
    目标地址安全校验

    两项防护：
    1. 只允许 http/https 协议——阻断 file://、gopher:// 等本地协议；
    2. 默认阻断内网/环回地址——防止借助爬虫引擎探测集群内网服务（SSRF 防护）。
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail=f"只允许 http/https，实际为 {parsed.scheme or '(空)'}",
        )

    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail=f"URL 缺少主机名: {url}")

    if not BLOCK_PRIVATE_NETWORK:
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail=f"域名解析失败: {host} ({e})") from e

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"目标解析到内网地址 {ip}，已阻断以防 SSRF；"
                    "确需采集内网请设置 SCRAPER_BLOCK_PRIVATE_NETWORK=false"
                ),
            )


# 保持向后兼容命名
_assert_safe_url = assert_safe_url
