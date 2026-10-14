# scraper-service

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 的解析服务。对 engine-service 暴露一个
HTTP 接口：**入参是采集规则，出参是结构化记录**。渲染、反爬、字段提取、选择器自愈都在这一侧完成。

## 为什么是独立服务，以及为什么连提取一起做

engine-service 跑在 JVM 上，Scrapling 是 Python 库，没法像 Jsoup 那样直接 import——中间必然有一道进程边界。

而边界划在哪里决定了能拿到什么：

- 若只让它返回渲染后的 HTML、回到 Java 用 Jsoup 提取，那 Scrapling 的招牌能力
  **adaptive（选择器自愈）就完全用不上**——它只能在 Scrapling 自己的 Selector 上生效，
  而自愈恰恰是引入它的主要理由。
- 所以边界划在「规则进、记录出」：本服务吃 `container` + `fields`，直接吐 records。

字段转换（Aviator 表达式）与去重键仍留在 Java 侧的下游环节，因此换 `loaderType`
不会让同一份规则的落库行为漂移。

## 接口

### `POST /internal/api/v1/executor/pipelines:execute`

```json
{
  "apiVersion": "executor.deepcloud/v1",
  "executionId": "exec-01",
  "input": { "selection": { "id": 7 }, "page": 1 },
  "metadata": { "jobId": 12, "stage": "list" },
  "pipeline": {
    "flowId": "list_flow",
    "firstComponentId": "load",
    "components": [
      {
        "componentId": "load",
        "componentType": "LOAD_HTML",
        "params": { "url": "https://example.com", "mode": "static" },
        "nextComponentId": "select",
        "exceptionStrategy": "TERMINATE"
      },
      {
        "componentId": "select",
        "componentType": "CSS_SELECT",
        "params": { "selector": "article" },
        "nextComponentId": null,
        "exceptionStrategy": "TERMINATE"
      }
    ]
  }
}
```

响应：

```json
{
  "success": true,
  "outputType": "RECORD_SET",
  "data": [{ "title": "Java 工程师", "url": "https://example.com/job/1" }],
  "records": [{ "title": "Java 工程师", "url": "https://example.com/job/1" }],
  "total": 1,
  "artifacts": [],
  "warnings": [],
  "elapsedMs": 640,
  "metadata": { "jobId": 12, "stage": "list" }
}
```

失败一律用 HTTP 状态码表达（`400` 规则/入参问题，`502` 目标站点或渲染失败），
调用方不必解包业务码。旧 `/api/v1/scrape` 与 `/api/v1/flow` 已删除，避免两套契约继续漂移。

`firstComponentId` 指向入口，每个组件通过 `nextComponentId` 串联；组件参数可用
`${input.xxx}`、`${stepId.records[0].field}`、`${vars.name}`、`${item}`、`${index}`
引用前序输出或循环上下文。

Java 在模板入库前会校验入口、组件 ID、断链/循环/不可达节点、必填参数与异常策略。
`DRIVE_RESOLVE` 走独立的网盘解析路由，必须单独构成终结 flow，不能与普通抓取组件串联。

内置组件：`LOAD_HTML`、`CSS_SELECT`、`ATTR_FILTER`、`FIELD_MAPPING`、
`DEEP_PARSE`、`REGEX_FILTER`、`RESULT_OUTPUT`、`HTTP_REQUEST`、`JSON_EXTRACT`、
`SET_VARIABLE`、`FOR_EACH`。`FOR_EACH.components` 支持同步和异步子组件。
所有实际出网地址（包括表达式解析后的 HTTP 请求与深度链接）都在请求前经过同一套 SSRF 校验。

### `GET /health`

回报存活状态与 `scraplingVersion`——排查「本地能跑容器不能跑」时先看这个。

## 三种模式

| mode | 用什么 | 何时用 |
|---|---|---|
| `static` | 纯 HTTP（curl_cffi，带 TLS 指纹模拟） | 内容在初始 HTML 里就有，最快 |
| `dynamic` | 真浏览器渲染 | 内容靠 JS 渲染出来 |
| `stealthy` | 渲染 + 指纹伪装（默认） | 上面两种被反爬拦下 |

## 选择器自愈（adaptive）

官方的两阶段模型：正常能选中时写入元素指纹，选不中时按相似度重定位。本服务的策略是
**先常规选，选不中再自愈**——常规路径顺带维护指纹库，只有真失效时才付相似度计算的开销。

自愈成功会往 `warnings` 里记一条。**这条必须让用户看到**：自愈能救一次，但页面已经改版，
规则终究得更新；否则自愈会一直掩盖问题，直到某天连相似度都匹配不上才暴露。

> ⚠️ **指纹库必须持久化**。它是 SQLite，位置由 `SCRAPER_ADAPTIVE_DB_DIR` 指定。
> 容器部署不挂盘的话，Pod 一重启指纹全丢，自愈就永远等于「没有历史可匹配」——
> 功能开着但从不生效，比明确关掉更难排查。K8s manifest 里已挂 PVC。

## 配置（全部走环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SCRAPER_HOST` / `SCRAPER_PORT` | `0.0.0.0` / `18000` | 监听地址 |
| `SCRAPER_REUSE_BROWSER` | `true` | 复用浏览器实例。**这是服务化的主要收益**：实测不复用每请求 6.5s，复用后稳态 0.64s |
| `SCRAPER_MAX_PAGES` | `3` | 并发标签页上限。调大必须同步调大内存 limit，否则 OOMKilled |
| `SCRAPER_HEADLESS` | `true` | 无头模式 |
| `SCRAPER_BLOCK_PRIVATE_NETWORK` | `true` | 阻断内网目标，见下 |
| `SCRAPER_ADAPTIVE_DB_DIR` | 空 | 指纹库目录，留空则用当前工作目录 |
| `SCRAPER_LOG_LEVEL` | `INFO` | 日志级别 |

## 安全

本服务**按调用方给的 URL 发起请求**，这本身就是 SSRF 的形状，所以每个出网点都有两道校验：

1. 只允许 `http`/`https`——放行 `file://` 等于把任意本地文件读取做成功能；
2. 默认阻断内网/环回/链路本地地址（含 `169.254.169.254` 这类云元数据地址）。
   否则部署在集群内就等于给出一个能探测 `iam-service` 等内部服务的跳板。

注意第 2 条只解析一次 DNS，对 DNS rebinding 无效；真正的隔离应由 NetworkPolicy
或出网网关承担。确有内网采集需求时才设 `SCRAPER_BLOCK_PRIVATE_NETWORK=false`。

## 本地运行

```bash
pip install -r requirements.txt
scrapling install                 # 首次：下载浏览器
uvicorn app.main:app --host 127.0.0.1 --port 18000
```

## 测试

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q
```

单测只覆盖纯逻辑（提取规则、SSRF 校验），不联网、不启浏览器。真实抓取用运行中的服务验证。

## 打包成 exe

```powershell
.\build-exe.ps1 -Clean
```

产出 `dist/scraper-service.exe`（约 70 MB）。

> ⚠️ **exe 不包含浏览器**，目标机器还需两步，缺任一步 `mode=static` 仍可用但
> `dynamic`/`stealthy` 会返回 502：
>
> ```powershell
> pip install scrapling; scrapling install          # 1. 落地浏览器
> $env:PLAYWRIGHT_BROWSERS_PATH="$env:LOCALAPPDATA\ms-playwright"   # 2. 告诉 exe 它在哪
> ```
>
> 第 2 步容易被忽略但是必需的：打包后 patchright 会去 PyInstaller 的临时解包目录
> （`_MEIxxxx\patchright\driver\...`）找浏览器，那里永远不会有。

## 已知限制

- **单副本**。指纹库是 SQLite + ReadWriteOnce 卷，多副本既挂不上同一个卷，
  SQLite 也不适合跨节点并发写。要更高吞吐先调 `SCRAPER_MAX_PAGES`；
  再不够就改 StatefulSet 让每副本各带一份指纹库（代价是指纹不共享，自愈命中率下降）。
- **并发未压测**。`MAX_PAGES` 默认取保守值 3，实际上限需按目标站点与内存实测。
- **容器内 Chromium 沙箱**。多数托管集群的默认 seccomp 会拦下 user namespace，
  表现为 `Failed to move to new namespace`；manifest 里已加 `SYS_ADMIN` capability，
  集群策略不允许时需改为给浏览器传 `--no-sandbox`。
