## DeepCloud Desktop v0.2.21 (Windows x64)

### 🚀 核心更新与自愈特性 (Changelog)

#### 1. 插件市场与社区规则生态全闭环 (Tri-Source Market & Rule Hub)
- **三位一体插件中心架构**：全面落地内置、社区、云端三位一体插件中心架构，支持多源规则自由检索与一键装载；
- **规则多版本自由切换与回退**：插件卡片原生支持多历史版本直接切换与远程动态拉取；更新小程序时自动安全备份原程序至回收站，提供后悔药一键版本回退机制；
- **社区规则免登录一键发起 PR**：接入官方 Cloudflare Worker 免登录代提网关与 GitHub IssueOps 机器人转换引擎，同时支持使用个人 GitHub 账号一键提交点亮贡献绿墙；
- **多端互通与源码透视**：规则卡片支持一键生成高清海阔口令导入二维码、一键提取口令、复制原始 JSON 及完整源码安全预览。

#### 2. 海阔视界 (Hiker) 跨端同构与全息沙箱自愈
- **运行沙箱彻底隔离**：重构 JS 执行上下文，根治变量跨规则穿透借用与全局变量污染，100% 对齐 Android 移动端隔离标准与安全基线（台账 #373）；
- **全息过盾与验证码自愈**：深度修复滑块过盾感知，修复人机验证码误判为 HeroBanner 巨幅拉伸缺陷与验证码提交错位，完善 HostAdapter 自动刷新返回闭环（台账 #359, #362）；
- **多媒体流与选集调度算法择优**：落地极速多线融合回溯选集折叠与批量下载全场景算法择优，修复有声书分页加载及历史记录精准分发至音频播放器。

#### 3. 旗舰影音与原生 Native 扩展集成
- **LibVLC 离屏渲染扩展**：集成基于 N-API 的 deepcloud-vlc 纯动态加载扩展与 RV32 离屏双缓冲管线；
- **组件探查与防误选锁死机制**：补齐 components-manager 中 LibVLC 运行时检测、系统路径免下载探测与 PE 架构校验，落地引擎未就绪状态下的多重锁死与防误选拦截守卫。

#### 4. SuperAgent 智能体核心升维 (Hub AI Sidecar)
- **对齐开源顶级架构 (Claude Code / OpenHands / Manus)**：重构智能工具网关 `ToolExecutionGateway`，支持全局透明别名映射（`read_file` -> `view_file`，`write_file` -> `write_to_file`，`bash` -> `run_command` 等 12 组别名）与跨工具参数智能归一化；
- **开发构建命令零审批放行**：大幅扩展 `ToolPolicy` 安全命令矩阵，常规 `cargo test`、`npm test`、`git status` 等安全放行，彻底消除 `approval_required` 导致的审批卡死与认知熔断器误杀（台账 #297）；
- **8 大核心工程工具置顶与注意力聚焦**：在 Function Calling Schema 中按核心优先级排序置顶，避免 38 个工具全量倾倒导致的注意力稀释与选择瘫痪；
- **Observation 编译器自愈诊断与物理磁盘工作记忆**：命令执行失败自动提取编译错误行并注入 `diagnostic_hint`；系统提示词深度对齐 Manus 物理磁盘工作记忆（`.superagent_todo.md`）强状态机。

#### 5. 内核安全加固与生产级交付
- **V8 字节码保护全面覆盖**：全量 160 个核心 JavaScript 模块全面采用 V8 原生字节码编译加固（Bytenode），明文源码安全擦除；
- **双端加速网络与免登录反馈**：客户端接入自定义加速域名 `mowen.mcccd.cc.cd` 实现国内秒级直连闭环，顶部系统栏挂载免登录问题反馈直通发版主库 Issue。

---

### 📥 发行资产哈希基线 (SHA256 Checksums)

- `deepcloud-ui Setup 0.2.21.exe`: `8ce19e1c4a130331740fbf9d8e379dbfca55bbe43b0c9d4cc7becb3cc4b1d72f`
- `deepcloud-ui.Setup.0.2.21.exe`: `8ce19e1c4a130331740fbf9d8e379dbfca55bbe43b0c9d4cc7becb3cc4b1d72f`
- `deepcloud-update-v0.2.21.asar`: `e512f8937a35529aef23d4c4ddb07c65147344864d9946bfdeded9cc0b627477`
- `app.asar`: `e512f8937a35529aef23d4c4ddb07c65147344864d9946bfdeded9cc0b627477`
- `hub-windows-amd64.zip`: `0f2fc42b94ff284430dcb5a544c8e87817ffcbaf98e5008d977c4b748af141cc`
- `hub.exe`: `19a89c37ff2bca95993a4f81622cd44d1ccf64cbc8859decbbb6b0391a42c0d4`

---

> ⚖️ **发版免责声明**：本安装程序及更新补丁仅供技术研究交流使用。本软件作为通用中立执行沙箱，坚决不内置、不提供亦不分发任何受版权保护的音视频及商业内容。用户自行加载第三方规则引发的一切法律与版权争议均由使用者独立承担。详见 [《官方发版免责声明》(DISCLAIMER.md)](./DISCLAIMER.md)。
