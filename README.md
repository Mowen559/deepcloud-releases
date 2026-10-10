<div align="center">

# 🚀 DeepCloud Desktop Releases

<p align="center">
  <strong>DeepCloud 桌面客户端官方发行版、更新分发与软件使用指南</strong>
</p>

<p align="center">
  <a href="https://github.com/Mowen559/deepcloud-releases/releases/latest"><img src="https://img.shields.io/github/v/release/Mowen559/deepcloud-releases?color=brightgreen&label=Latest%20Version" alt="Latest Release"></a>
  <a href="https://github.com/Mowen559/deepcloud-releases/releases"><img src="https://img.shields.io/badge/Platform-Windows%20x64-blue.svg" alt="Platform"></a>
  <a href="https://github.com/Mowen559/deepcloud-releases/releases"><img src="https://img.shields.io/badge/Arch-x64-lightgrey.svg" alt="Arch"></a>
  <a href="https://github.com/Mowen559/deepcloud-releases/releases"><img src="https://img.shields.io/badge/Security-Bytenode%20V8%20Protected-success.svg" alt="Bytenode Protected"></a>
  <a href="#-开源协议"><img src="https://img.shields.io/badge/License-MIT-orange.svg" alt="License"></a>
</p>

<p align="center">
  <a href="#-最新版本下载-v0211">最新版本下载</a> •
  <a href="#-校验和与完整性验证">哈希校验</a> •
  <a href="#-微内核插件化架构解析">插件化架构解析</a> •
  <a href="#-软件详细使用指引">软件使用指引</a>
</p>

</div>

---

## 📥 最新版本下载 (v0.2.12)

> [!TIP]
> 推荐直接访问 **[GitHub Releases 官方发布页](https://github.com/Mowen559/deepcloud-releases/releases/latest)** 获取最新构建资产。

| 发行资产 (Asset) | 适用场景 | 说明 | 直接下载 |
| :--- | :--- | :--- | :--- |
| **`deepcloud-ui Setup 0.2.12.exe`** | **全量安装** | 首次使用请下载此安装包，支持自定义路径并自动创建桌面快捷方式 | [立即下载](https://github.com/Mowen559/deepcloud-releases/releases/download/v0.2.12/deepcloud-ui.Setup.0.2.12.exe) |
| **`deepcloud-update-v0.2.12.asar`** | **增量热更新** | 针对已有安装用户的轻量热更新补丁包（V8 字节码加固，秒级生效） | [立即下载](https://github.com/Mowen559/deepcloud-releases/releases/download/v0.2.12/deepcloud-update-v0.2.12.asar) |
| **`app.asar`** | **核心包替换** | 完整核心二进制归档，可直接覆盖安装目录 `resources/app.asar` | [立即下载](https://github.com/Mowen559/deepcloud-releases/releases/download/v0.2.12/app.asar) |
| **`hub-windows-amd64.zip`** | **AI 智能体服务** | Hub 智能体与视觉处理中台守护进程绿色包（内含 `hub.exe`，支持自动解压热加载） | [立即下载](https://github.com/Mowen559/deepcloud-releases/releases/download/v0.2.11/hub-windows-amd64.zip) |
| **`hub.exe`** | **智能体独立程序** | Hub 智能体服务端单文件独立可执行程序 | [立即下载](https://github.com/Mowen559/deepcloud-releases/releases/download/v0.2.11/hub.exe) |

---

## 🔒 校验和与完整性验证

在 PowerShell 终端中执行以下命令核验下载文件的完整性：

```powershell
Get-FileHash -Path ".\deepcloud-ui Setup 0.2.12.exe" -Algorithm SHA256
```

### 官方发布哈希标准基线 (v0.2.12)：
- **`deepcloud-ui Setup 0.2.12.exe`**：`d43eb98aab86c9da1c62a3c9b97737967525e35deafa4eee85015b931cba0fac`
- **`deepcloud-update-v0.2.12.asar`**：`a81cde8342c771647733707e81958b88b1c3a746e53d6c4b1cca5c76a5dee0e6`
- **`app.asar`**：`a81cde8342c771647733707e81958b88b1c3a746e53d6c4b1cca5c76a5dee0e6`
- **`hub-windows-amd64.zip`**：`76733eb125d2109f46736c434fe2b547ba47f214913b1f472b679b5b8fd96729`
- **`hub.exe`**：`e4c1e380b5ea3afaec987723d9e1d3eec557fcdfb9027a9d1f9bd8ce6688f588`

---

## 🧩 微内核插件化架构解析 (Plugin Architecture)

DeepCloud 桌面端基于 **微内核操作系统容器架构 (WebOS V3.0)** 构建，实现了**内核极简、能力外挂、声明驱动、安全隔离**的现代化设计：

### 1. 核心设计原则
- **宿主无感知 (Host-Agnostic) 与零特判**：
  宿主内核专注于窗口调度、统一动作总线（`ActionBus`）、安全能力沙箱与扩展点分发。严禁在主流程中编写针对具体应用的 `if-else` 分支，所有功能组件平等挂载。
- **声明式清单契约 (AppManifest)**：
  每个插件通过标准的 `manifest.json` 声明自身的入口路径、权限集合、后台守护进程参数模板以及 UI 贡献插槽（如顶栏小部件、上下文菜单、斜杠命令）。
- **设置就地内聚铁律 (Local High Cohesion)**：
  系统级设置（`/settings`）仅维护全系统共用状态（开发者模式、外观主题、系统语言、更新源等）；所有插件的私有业务参数必须就地内聚在其自身面板中，绝不污染系统主设置。

### 2. 四级插件分类体系

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      DeepCloud WebOS 微内核容器                         │
├─────────────────┬─────────────────┬──────────────────┬─────────────────┤
│ Core_Shortcut   │Deep_Integration │Static_Integration│Browser_Extension│
│ 系统快捷应用    │深度集成 (Sidecar)│静态 Web 沙箱     │浏览器原生扩展   │
│                 │                 │                  │                 │
│ • 系统全局设置  │ • AList 多网盘  │ • 离线 Web 工具  │ • Chrome MV3    │
│ • 媒体中心      │ • Rclone 存储   │ • 第三方 H5 页面 │   扩展插件      │
│ • 在线会话      │ • 本地单文件爬虫│ • 独立轻应用     │ • 网页脚本/拦截 │
│                 │ • 本地大模型    │                  │                 │
│ (共享宿主上下文)│ (参数宏/守护进程)│ (严格隔离原生IPC)│ (Crx Runtime)   │
└─────────────────┴─────────────────┴──────────────────┴─────────────────┘
```

### 3. V8 原生字节码加固体系 (Bytenode Enterprise Shield)
- **100% 二进制化交付**：主进程入口及 `native/` 目录下 170 个核心业务模块、数据库操作层与规则运行时全部编译为原生 `.jsc` 字节码，无明文 JavaScript 源码暴露；
- **智能 Loader 路由 Hook**：内置 Bootstrap Loader 透明拦截模块请求并重定向至字节码，兼顾卓越运行效率与企业级知识产权安全。

### 4. 海阔视界 (Hiker View) 规则引擎演进
- **JSON 安全代理作用域收敛**：建立属性容器精准白名单（`isContainerProp`），普通未声明字段严格遵循 ECMAScript 原生布尔语义，彻底根治 Proxy 代理劫持导致的条件误杀；
- **原生 Assets 虚拟协议**：统一支持 `hiker://assets/` 虚拟协议与纯 JS 跨平台加解密降级；
- **多线路播放自愈**：飞鱼4K初始化死锁自愈、HLS流无缝降级与视频选集生命周期治理。

### 5. 弹幕与播放扩展生态
- **弹弹play 官方 API v2 开放平台**：基于 16MB 流式哈希精准识别剧集正名，自动抓取多源弹幕；
- **即时发射与上报**：控制条内置弹幕胶囊与调色板，自发弹幕秒级上屏高亮显示，并自动异步上报官方弹幕库。

---

## 📖 软件详细使用指引 (User Guide)

### 1. 软件安装与自动更新

#### 首次安装
1. 下载 `deepcloud-ui Setup 0.2.11.exe`；
2. 双击运行安装程序，可自选安装盘符，安装完成将自动生成桌面快捷图标。

#### 客户端内一键热更新
1. 打开客户端，点击左下角 **「设置」 -> 「通用设置」**；
2. 确认更新源为 `Mowen559/deepcloud-releases`，点击 **「检查更新」**；
3. 检测到新版本后，点击 **「一键热更新」**，客户端将在后台自动下载差分补丁，完成后提示重启即可生效。

---

### 2. 影音播放器沉浸体验

#### 全网多源搜索与选集
1. 点击左侧主导航 **「海阔视界」**；
2. 顶部搜索框输入影片关键词，系统自动调动多个规则源并发检索并聚合呈现；
3. 点击剧集卡片进入播放页，可自由切换播放源线路与集数。

#### 快捷键操作清单

| 快捷键 | 功能 |
| :--- | :--- |
| <kbd>Space</kbd> | 播放 / 暂停 |
| <kbd>←</kbd> / <kbd>→</kbd> | 快退 5 秒 / 快进 5 秒 |
| <kbd>↑</kbd> / <kbd>↓</kbd> | 音量递增 5% / 递减 5% |
| <kbd>F</kbd> | 进入 / 退出全屏幕模式 |
| <kbd>M</kbd> | 静音 / 恢复音量 |
| <kbd>D</kbd> | 显示 / 隐藏弹幕 |
| <kbd>[</kbd> / <kbd>]</kbd> | 上一集 / 下一集 |

#### 全屏沉浸式菜单穿透 (W3C Top Layer)
- 在全屏播放模式下，点击底栏菜单（画质、音轨、设置、DLNA 投屏）会自动向上展开，菜单弹层完美穿透全屏层级，绝不被视频画面遮挡；
- 展开菜单时悬浮条保持常驻，调节参数时自动屏蔽键盘播放快捷键防误触。

#### 弹幕发射与视觉定制
- **发射弹幕**：底栏中央输入框输入弹幕内容，回车直接发送；支持切换滚动/顶部/底部弹幕及 8 种高频预设颜色；
- **视觉设置**：在播放设置面板中可自由滑动调节字号大小（12px~48px）、不透明度与滚动速度；
- **避让字幕**：开启「避让字幕区域」后，弹幕自动避开底部 18% 区域，保证不挡字幕。

---

### 3. 海阔规则导入与管理

- **口令导入**：复制包含 `hiker://` 的口令，打开客户端将自动识别并弹出导入确认；
- **文件导入**：在「海阔视界」右上角点击「导入规则」，选择本地 `.json` 文件；
- **订阅链接**：粘贴 HTTP/HTTPS 规则订阅地址，自动拉取并保持定时更新。

---

### 4. AList 多网盘挂载与流式播放 (Sidecar)

1. 前往 **「插件市场」** 启用 **AList** 插件；
2. Sidecar 进程管理器将在后台自动调度 `alist.exe` 守护进程；
3. 进入 AList 面板绑定阿里云盘、百度网盘、夸克网盘、115网盘等；
4. 网盘中的视频资源将自动挂载至 **「媒体中心」**，支持原画直连秒播。

---

### 5. 桌面悬浮视窗与 AI 智能体 (Super-Agent)

- **悬浮视窗**：使用全局热键唤出屏幕悬浮工具栏；
- **离线 OCR 与翻译**：支持一键矩形框选，内置离线 PaddleOCR 识别文字与多引擎翻译；
- **AI 助手**：文字一键带入智能体对话框，支持多厂商大模型问答与要点提炼。

---

## 📜 开源协议

本项目采用 [MIT License](LICENSE) 授权。
如有任何使用问题或功能建议，欢迎前往 [Issue 反馈](https://github.com/Mowen559/deepcloud-releases/issues)。
