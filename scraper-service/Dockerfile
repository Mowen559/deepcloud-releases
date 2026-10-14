# scraper-service 镜像
#
# 【为什么是 Debian 而不是 Alpine】
# 渲染依赖 Playwright 下载的 Chromium，它只提供 glibc 构建，官方明确不支持
# Alpine 的 musl libc——在 Alpine 上装完也起不来。
FROM python:3.12-slim-bookworm

# 是否安装浏览器。设为 false 可得到一个仅支持 mode=static 的轻量镜像
# （体积从约 1.3G 降到约 250M），适合只采静态页的场景。
ARG WITH_BROWSER=true

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    SCRAPER_HOST=0.0.0.0 \
    SCRAPER_PORT=18000 \
    SCRAPER_REUSE_BROWSER=true \
    SCRAPER_MAX_PAGES=3 \
    SCRAPER_BLOCK_PRIVATE_NETWORK=true \
    SCRAPER_ADAPTIVE_DB_DIR=/data/adaptive

# 浏览器装到 /opt 而非 root 家目录：容器以非 root 用户运行，
# 装在 /root/.cache 下非 root 读不到。
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

WORKDIR /app

COPY requirements.txt .

# 注意：RUN 的续行会拼成一行 shell，行内写 # 注释会把后续命令全部吃掉，所以注释都放在指令外。
RUN pip install --no-cache-dir -r requirements.txt

# Chromium 的运行时依赖由 `scrapling install` 负责拉起（它会调 playwright install --with-deps）
RUN if [ "$WITH_BROWSER" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends ca-certificates && \
        scrapling install && \
        chmod -R a+rX /opt/ms-playwright && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/*; \
    else \
        echo "skip browser install: only mode=static will work"; \
    fi

COPY app ./app

# adaptive 的元素指纹库落在这里。必须挂 PVC——
# 不挂盘则 Pod 重启即丢指纹，选择器自愈会静默退化为「永远没有历史可匹配」。
RUN mkdir -p /data/adaptive

# 非 root 运行
RUN useradd -r -u 10001 -m -d /home/scraper scraper && \
    chown -R scraper:scraper /app /data
USER scraper

EXPOSE 18000

# 容器内跑 Chromium 通常还需放开沙箱（内核 user namespace 受限时会起不来）。
# 如果日志出现 "Failed to move to new namespace"，给 Pod 加
# securityContext.capabilities.add: ["SYS_ADMIN"] 或改用 --no-sandbox。
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:18000/health').read()" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18000"]
