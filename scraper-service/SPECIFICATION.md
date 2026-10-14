# DeepCloud Engine 规范与开发架构总则 (Engine Specifications)

> **开源声明**：本目录（`scraper-service/`）设计为完全自包含的独立项目架构，后续将以 `deepcloud-engine`（或 `open-scraper-engine`）为名独立开源发布。
> 任何对本模块的架构改进、功能扩展与 Bug 修复，必须遵守本规范体系。

---

## 规范总览导航 (OpenSpec Directory)

| 规范文件 | 规范标识 | 核心定位与治理范围 |
|---|---|---|
| [**`openspec/README.md`**](./openspec/README.md) | `SCRAPER-META` | 开源愿景、多阶弹性抓取体系（HTTP -> curl_cffi -> Playwright -> Scrapling 自愈）与开源许可证准则 |
| [**`openspec/engine-core.spec.md`**](./openspec/engine-core.spec.md) | `SCRAPER-ENGINE-001` | 微内核架构、任务状态机、浏览器池生命周期与本地嵌入式 SQLite 存储契约 |
| [**`openspec/flow-dsl.spec.md`**](./openspec/flow-dsl.spec.md) | `SCRAPER-FLOWDSL-001` | FlowDSL 低代码声明式工作流语法、官方标准组件库契约与自适应选择器自愈算法 |
| [**`openspec/standalone-runtime.spec.md`**](./openspec/standalone-runtime.spec.md) | `SCRAPER-STANDALONE-001` | 单文件跨平台二进制打包、零依赖便携运行、SSRF 企业级安全沙箱与 MCP 协议规范 |

---

## 核心架构铁律速查 (Core Golden Rules)

1. **凭据安全绝对留端 (RULE-SEC-02)**：用户私有 Cookie、Token 与采集明细数据仅保存在客户端本地 SQLite，绝不向任何外部公有云端回传；
2. **SSRF 全量网络防御 (RULE-SEC-01)**：所有抓取与加载请求必须强制通过 `assert_safe_url` 拦截内网 IP 段（`10.*`、`192.168.*`、`169.254.169.254` 等），杜绝内网探测风险；
3. **无头浏览器严格资源回收 (RULE-POOL-02/04)**：页面打开必须处于 `try...finally` 保护下，闲置超过 120 秒自动彻底释放 Chromium 内存；
4. **选择器自愈相似度守卫 (RULE-ADAPT-02)**：Scrapling 自愈算法仅在结构相似度 $\ge 0.85$ 时才自动纠错，杜绝由于改版产生张冠李戴的数据污染。

---

## 快速运行与测试

```bash
# 1. 安装开发依赖
pip install -r requirements.txt -r requirements-dev.txt

# 2. 运行全量单元测试与规范断言
pytest tests/

# 3. 本地开发启动
uvicorn app.main:app --host 127.0.0.1 --port 18000 --reload

# 4. 单文件二进制打包 (Windows)
powershell ./build-exe.ps1
```
