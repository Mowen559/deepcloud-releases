"""
入口安全校验测试

重点是 SSRF：本服务按外部传入的 URL 发起请求，部署在集群内时若不阻断内网地址，
调用方就能借它访问 iam-service 等内部服务。
"""

import pytest
from fastapi import HTTPException

from app.main import _assert_safe_url


class TestSchemeWhitelist:

    def test_拒绝file协议以防任意文件读取(self):
        with pytest.raises(HTTPException) as e:
            _assert_safe_url("file:///etc/passwd")
        assert e.value.status_code == 400
        assert "只允许 http/https" in e.value.detail

    @pytest.mark.parametrize("url", [
        "ftp://example.com/x",
        "data:text/html,<h1>x",
        "gopher://example.com",
    ])
    def test_拒绝其他非网络协议(self, url):
        with pytest.raises(HTTPException):
            _assert_safe_url(url)

    def test_缺少主机名时拒绝(self):
        with pytest.raises(HTTPException) as e:
            _assert_safe_url("http://")
        assert "缺少主机名" in e.value.detail


class TestSSRF:

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1:8080/actuator/health",
        "http://localhost:8081/internal/users",
        "http://10.0.0.5/admin",
        "http://192.168.1.4:30848/nacos",
        "http://172.16.0.1/",
        # 云环境的元数据服务，泄露即等于泄露凭据
        "http://169.254.169.254/latest/meta-data/",
    ])
    def test_阻断内网与环回地址(self, url):
        with pytest.raises(HTTPException) as e:
            _assert_safe_url(url)
        assert e.value.status_code == 400

    def test_报错信息指出关闭开关的方式(self):
        # 确有内网采集需求时，用户要能从报错里知道怎么放行
        with pytest.raises(HTTPException) as e:
            _assert_safe_url("http://127.0.0.1:9999/")
        assert "SCRAPER_BLOCK_PRIVATE_NETWORK" in e.value.detail

    def test_放行公网地址(self):
        # 不应误伤正常目标；example.com 是 IANA 保留的稳定域名
        _assert_safe_url("https://example.com/list?page=1")
        _assert_safe_url("http://example.com")
