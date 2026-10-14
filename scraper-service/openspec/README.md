# DeepCloud Engine (Scraper Engine) 开源规范体系

> **项目代号**：`deepcloud-engine` / `open-scraper-engine`  
> **开源愿景**：打造下一代轻量级、声明式、具备自愈与 AI 增强能力的单文件边缘数据采集与页面适配引擎。  
> **设计哲学**：**端侧第一 (Edge-First)**、**声明式工作流 (Declarative FlowDSL)**、**多阶弹性抓取 (Multi-Tier Fetching)**、**开箱即用零依赖 (Zero-Dependency Standalone)**。

---

## 一、为什么独立开源？

现代数据采集与网页抽取面临三大严峻痛点：
1. **云端采集易触发封禁**：云厂商机房 IP 容易被各大站点风控高频拦截；
2. **私有凭据上云风险**：个人用户或企业的特定登录态（Cookie、Token、私钥）上传到公有云服务端存在严重数据泄露隐患；
3. **前端反爬与 DOM 频繁变动**：传统 XPath/CSS 规则一旦页面微调就彻底失效，维护成本极高。

**DeepCloud Engine 的破局解法**：
- **纯端侧单文件运行**：凭据、Cookie 与中间抓取数据 100% 留存在本地 SQLite，绝不上云；
- **自适应选择器自愈**：深度集成 [Scrapling](https://github.com/D4Vinci/Scrapling) 算法，页面改版时基于相似度指纹库自动修正选择器；
- **FlowEngine 低代码 DAG 编排**：无需编写 Python 脚本，通过清晰的声明式 JSON/YAML 流水线串联加载、交互、解析、循环与 AI 处理；
- **跨平台独立二进制分发**：支持直接打包为单个轻量可执行文件（`.exe` / Linux 二进制），内置 Web 服务与调度器，用户免装 Python 环境双击即跑。

---

## 二、开源规范目录组织

本规范体系完全自包含在引擎目录下，随引擎代码一同独立版本化与开源：

```text
scraper-service/
├── SPECIFICATION.md                 # 规范总导航入口
├── openspec/
│   ├── README.md                    # 本文件：开源愿景、架构全景与规范总览
│   ├── engine-core.spec.md          # 引擎微内核：进程模型、任务状态机、并发管理与本地存储契约
│   ├── flow-dsl.spec.md             # FlowDSL 规范：声明式工作流语法、标准组件库与自愈提取协议
│   └── standalone-runtime.spec.md   # 便携运行规范：单文件构建、安全沙箱、环回接口与 MCP 协议契约
```

---

## 三、四层混合抓取体系 (Multi-Tier Fetching Architecture)

引擎内置分层降级与弹性切换机制，依据目标站点的防护等级自适应选择最佳算力与资源消耗方案：

```mermaid
flowchart TD
    Req[数据采集请求 FlowDSL] --> Tier1{Tier 1: 静态 HTTP / TLS 伪装}
    Tier1 -->|成功 (低消耗, 10~50ms)| Parse[数据解析与提取]
    Tier1 -->|遇到 Cloudflare/TLS指纹风控| Tier2{Tier 2: curl_cffi 模拟浏览器指纹}
    Tier2 -->|成功 (中消耗, 100~300ms)| Parse
    Tier2 -->|遇到复杂 JS 混淆 / 动态 DOM / 验证码| Tier3{Tier 3: Playwright 动态无头浏览器池}
    Tier3 -->|成功 (高消耗, 1~3s)| Parse
    
    Parse --> SelectorEngine{选择器提取}
    SelectorEngine -->|常规提取命中| Finish[输出标准 RecordSet]
    SelectorEngine -->|DOM 改版失效| Tier4[Tier 4: Scrapling 自愈算法 / LLM 语义抽取]
    Tier4 --> Finish
```

---

## 四、开源许可证与治理协议

1. **开源协议建议**：Apache License 2.0（允许商用、专利授权、支持二次分发）；
2. **所有权隔离原则**：引擎内部核心算法与 FlowDSL 规范绝对不引入对特定业务云端的硬编码依赖，保持 100% 独立可运行；
3. **版本号遵循**：严格遵循 [SemVer 2.0.0](https://semver.org/) 规范（`MAJOR.MINOR.PATCH`）。
