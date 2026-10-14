---
spec_id: "SCRAPER-FLOWDSL-001"
title: "FlowDSL 声明式工作流语法、标准组件库与自愈提取规范"
domain: "scraper"
status: "accepted"
version: "1.0.0"
created_at: "2026-10-14"
updated_at: "2026-10-14"
---

# FlowDSL 声明式工作流语法、标准组件库与自愈提取规范 (FlowDSL Spec)

> **规范定位**：定义 DeepCloud Engine 低代码工作流的数据交换契约、DAG 节点编排规范、官方组件生态协议与自适应选择器自愈算法契约。

---

## 1. FlowDSL 语法与 JSON Schema

### 1.1 核心结构
FlowDSL 是强类型的 JSON/YAML 声明式语法，任何合规的流水线定义必须遵循以下顶层 Schema：

```json
{
  "$schema": "https://deepcloud.org/schemas/flowdsl-v1.json",
  "flowId": "unique_flow_identifier",
  "name": "电商商品列表及详情采集流水线",
  "version": "1.0.0",
  "firstComponentId": "node_load_page",
  "components": [
    {
      "componentId": "node_load_page",
      "componentType": "LOAD_HTML",
      "params": {
        "url": "${input.target_url}",
        "mode": "static",
        "timeout": 30
      },
      "nextComponentId": "node_select_cards",
      "exceptionStrategy": "TERMINATE"
    }
  ]
}
```

### 1.2 节点字段契约 (Component Anatomy)
| 字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `componentId` | `string` | 是 | 流水线内节点唯一标识符（字母、数字与下划线）。 |
| `componentType` | `string` | 是 | 注册在组件注册中心的组件类型名称（见第 2 节）。 |
| `params` | `object` | 是 | 传递给组件的具体参数字典，支持 `${context.var}` 插值语法。 |
| `nextComponentId`| `string \| null`| 是 | 下一节点 ID。若为 `null` 则表示当前分支终止。 |
| `exceptionStrategy`| `enum` | 是 | 节点异常处理策略：`TERMINATE` (熔断终止)、`IGNORE` (忽略继续)、`RETRY` (重试)。 |

---

## 2. 官方标准组件库规范 (Component Registry)

任何被引擎支持的标准组件必须继承自 `BaseComponent`，并实现统一的生命周期接口：`execute(context: PipelineContext) -> ComponentResult`。

### 2.1 网络与加载组件 (Network / Loading)
1. **`LOAD_HTML`**：
   - 职责：抓取目标网页并挂载至 `context.html`；
   - 关键参数：
     - `url` (`string`): 目标地址；
     - `mode` (`enum`): `"static"` (curl_cffi/httpx 极速模式), `"dynamic"` (Playwright 动态渲染模式)；
     - `wait_for_selector` (`string` 可选): 动态渲染等待就绪的 CSS 选择器。
2. **`HTTP_REQUEST`**：
   - 职责：发起结构化 REST/GraphQL API 请求；
   - 关键参数：`method`, `headers`, `body`, `proxy`。

### 2.2 解析与抽取组件 (Parsing / Extraction)
1. **`CSS_SELECT` / `XPATH_SELECT`**：
   - 职责：从当前上下文提取 DOM 节点或属性列表；
   - 关键参数：
     - `selector` (`string`): CSS 或 XPath 表达式；
     - `adaptive` (`boolean` 默认 `false`): **开启 Scrapling 选择器自愈**；
     - `attribute` (`string` 可选): 提取属性名（如 `href`、`src`，默认提取 `text`）。
2. **`JSON_PATH`**：
   - 职责：针对 API 响应执行 JSONPath 查询（如 `$.data.items[*]`）。
3. **`REGEX_EXTRACT`**：
   - 职责：正规表达式捕获组提取与字段映射。

### 2.3 流程控制组件 (Control Flow)
1. **`LOOP_LIST` (循环组件)**：
   - 职责：遍历输入数组（如商品卡片列表），对每个子项执行嵌套子流水线（`subFlow`）；
   - 参数：`listVariable` (迭代源数组名), `itemAlias` (单项迭代变量名), `subFlow`。
2. **`BRANCH_CONDITION` (条件分支)**：
   - 职责：基于表达式动态计算并路由到不同的 `nextComponentId`；
   - 参数：`expression`（支持 Python 安全子集表达式，如 `len(records) > 0`）。

### 2.4 AI 增强组件 (AI Augmented)
1. **`AI_EXTRACT`**：
   - 职责：在零规则或复杂非标 HTML 场景下，借助大语言模型直接提取指定 JSON 结构的记录；
   - 参数：`schema` (目标结构定义), `prompt` (提示词), `model` (模型名)。

---

## 3. 上下文变量与插值表达式契约 (Pipeline Context)

### 3.1 变量作用域层级
1. **全局输入层 (`input.*`)**：发起任务时传入的初始参数（如 `input.keyword`、`input.page`）；
2. **流程全局层 (`vars.*`)**：在整个流水线生命周期中累加的变量；
3. **局部循环层 (`item.*`)**：在 `LOOP_LIST` 内迭代的局部对象；
4. **输出记录池 (`records`)**：最终对外交付的标准结构化数据集。

### 3.2 变量解析协议 (Interpolation Engine)
引擎内置双重插值求值器：
- 字符串宏替换：`${input.url}` 自动替换为上下文中变量字符串；
- 类型直通表达式：`${records}` 在参数期待数组时直接传递原始 Python 对象，严禁强制降级为字符串。

---

## 4. Scrapling 自适应选择器自愈算法契约 (Adaptive Selector Healing)

### 4.1 背景与自愈原理
网站前端频繁发版（如将 `.item-title` 重命名为 `.product-name_2x`）会导致传统爬虫大面积报错。
当节点配置 `"adaptive": true` 时，引擎启动自适应纠错管线：

```mermaid
flowchart TD
    RunSelector[执行原始选择器] --> HasResult{能否提取到有效内容?}
    HasResult -->|是| SaveFingerprint[计算/更新 DOM 结构特征指纹库]
    SaveFingerprint --> Success[正常产出结果]
    
    HasResult -->|否 (DOM发生偏移)| LoadFingerprint[加载历史有效指纹]
    LoadFingerprint --> SimilarityCalc[遍历候选节点并计算相似度]
    SimilarityCalc --> Matched{相似度 >= 0.85?}
    Matched -->|是| AutoHeal["✨ 自动采用最优候选节点，<br/>并生成日志提示选择器自愈"]
    AutoHeal --> Success
    Matched -->|否| Fail[判定为页面大改版，抛出结构破坏异常]
```

### 4.2 约束与红线
- **RULE-ADAPT-01**：自适应特征指纹库必须持久化在本地 SQLite 或专用指纹文件目录（`ADAPTIVE_DB_DIR`），保证跨次运行能够继承自愈能力；
- **RULE-ADAPT-02**：自愈相似度硬性阈值不得低于 `0.85`，防止页面彻底改版时产生“张冠李戴”的脏数据提取。

---

## 5. 验收准则与测试矩阵

### 5.1 验收基准
1. **DAG 依赖合规验收**：包含分支、循环的复合 FlowDSL，能够严格按照图拓扑序列正确消费和生产变量；
2. **自愈有效性验证**：针对类名被篡改但结构保留的模拟 HTML，开启 `adaptive=true` 后能够 100% 成功自愈提取正确字段；
3. **跨语言契约验收**：Java 控制面（engine-service）生成的规范包传入本 Python 引擎执行后，输出的 RecordSet 字段与类型无任何丢失漂移。

### 5.2 关联自动化测试
- DAG 与低代码编排测试：`pytest tests/test_lowcode_flow.py`、`pytest tests/test_flow_dag.py`
- 选择器与自愈算法测试：`pytest tests/test_extractor.py`
- 端到端 Flow 契约测试：`pytest tests/test_flow_contract.py`
