---
spec_id: "SCRAPER-STANDALONE-001"
title: "单文件打包、零依赖便携运行、SSRF安全沙箱与MCP协议集成规范"
domain: "scraper"
status: "accepted"
version: "1.0.0"
created_at: "2026-10-14"
updated_at: "2026-10-14"
---

# 单文件打包、零依赖便携运行、SSRF安全沙箱与MCP协议集成规范 (Standalone Runtime Spec)

> **规范定位**：定义 DeepCloud Engine 跨平台单文件二进制发布标准、零依赖便携运行时行为、企业级安全沙箱守卫与 AI Agent (MCP) 协议集成契约。

---

## 1. 单文件跨平台二进制交付架构 (Single-Binary Packaging)

### 1.1 交付目标
- **零 Python 环境依赖**：宿主机器无需安装 Python 解释器、无需配置虚拟环境或安装任何 pip 包；
- **单可执行文件**：
  - Windows：`deepcloud-engine.exe`（自解压单文件，含嵌入式资源）；
  - Linux / macOS：`deepcloud-engine`（独立二进制）；
- **双击即行**：双击启动后，自动初始化本地 SQLite 数据库、启动 Uvicorn 并侦听本地安全端口，打印启动横幅。

### 1.2 运行时工作区自动规整 (Directory Self-Healing)
单文件引擎启动时，必须自动探测并自愈以下本地目录结构（不存在则自动创建）：
```text
./ (运行工作目录)
├── data/
│   ├── scraper_engine.db           # 本地 SQLite 任务与数据存储
│   └── adaptive_fingerprints/      # Scrapling DOM 相似度指纹库
├── logs/
│   └── engine.log                  # 本地滚动运行日志
└── browsers/                       # 内嵌或便携式 Chromium 浏览器核心
```

---

## 2. 企业级安全沙箱与合规守卫 (Security Sandbox)

> [!CAUTION]
> 爬虫引擎具备发起任意 HTTP 请求的能力，若缺乏严格的沙箱防御，极易被利用进行内网探测（SSRF）或凭据泄露。

### 2.1 SSRF 深度防御红线 (RULE-SEC-01)
引擎在执行任何网络请求（静态抓取或无头浏览器导航）之前，**必须**调用 `assert_safe_url(url)` 进行网络层白名单与内网阻断校验：
- **强制拦截内网 IP 段**：
  - 本地保留地址：`127.0.0.0/8`, `localhost`（除受控回环接口外）；
  - 私有 A/B/C 类局域网：`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`；
  - 链路本地地址：`169.254.0.0/16`（特别是云厂商元数据端点 `169.254.169.254`，坚决拦截！）；
  - 广播与组播地址：`224.0.0.0/4`, `255.255.255.255`。
- **协议白名单**：仅放行 `http://` 与 `https://`，坚决拦截 `file://`、`gopher://`、`ftp://` 等危险协议方案。

### 2.2 凭据零泄露原则 (RULE-SEC-02: Zero-Cloud Token Leakage)
- 用户私有 Cookie、网站 Token、账号密码等高敏感数据，**仅允许保存在客户端本地 SQLite 的加密字段中**；
- 在任何向外部（包括云端协同中心、日志收集服务或对外 REST 响应）返回数据时，必须执行脱敏过滤（如 `Cookie: ***`），杜绝因数据采集导致账号被盗。

---

## 3. Model Context Protocol (MCP) 标准 AI 协议集成

### 3.1 协议定位
DeepCloud Engine 原生支持 Anthropic 发起的 **MCP (Model Context Protocol)** 协议，使引擎能够直接被任何支持 MCP 的现代 AI Agent（如 Claude Desktop、Cursor、Antigravity、OpenCode）无缝调用，充当 AI 的“视觉与网页实时抽取器官”。

### 3.2 暴露的标准 MCP Tools 契约
1. **`scrape_and_extract`**：
   - 描述：输入 URL 与所需抽取的字段描述，引擎自动抓取并返回结构化 JSON；
   - 载荷参数：
     ```json
     {
       "url": "https://news.ycombinator.com",
       "fields": {
         "title": "css:.titleline > a",
         "score": "css:.score"
       },
       "adaptive": true
     }
     ```
2. **`run_flow`**：
   - 描述：执行一段 FlowDSL 低代码声明式工作流；
3. **`execute_sql` (只读查询)**：
   - 描述：向本地 SQLite 执行只读聚合查询，提取历史采集的本地离线数据。

---

## 4. 构建与发布流程 (Build & Release Automation)

### 4.1 构建命令
在 `scraper-service/` 目录下执行标准化构建：
```powershell
# 执行单文件打包 (基于 PyInstaller 与 spec 规则)
.\build-exe.ps1
```

### 4.2 产物校验基准
- [ ] 产物独立性：在无 Python 环境的纯净 Windows 10/11 虚拟机中，双击 `deepcloud-engine.exe` 能够成功在 3 秒内启动并响应 `GET http://127.0.0.1:18000/health`；
- [ ] 大小控制：单文件压缩包体积收敛在合理区间（不含 Chromium < 50MB）；
- [ ] 自动化测试全部 PASS：运行 `pytest tests/test_security.py` 验证 SSRF 拦截 100% 生效。
