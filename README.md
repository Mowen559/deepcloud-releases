# DeepCloud Desktop Releases 🚀

欢迎访问 **DeepCloud** 桌面客户端官方发行版与更新分发仓库。

DeepCloud 是一款现代化的一体化桌面工作台与数据采集、智能分析与视听娱乐系统，基于 **Java 21 + Spring Cloud 微服务后端** 与 **Next.js 16 + React 19 + Electron 43 客户端** 构建。

---

## 📥 最新版本下载 (Latest Release)

[![Latest Release](https://img.shields.io/github/v/release/Mowen559/deepcloud-releases?color=brightgreen&label=Latest%20Version)](https://github.com/Mowen559/deepcloud-releases/releases/latest)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue.svg)](https://github.com/Mowen559/deepcloud-releases/releases)
[![License](https://img.shields.io/badge/License-MIT-orange.svg)](#)

👉 **前往下载最新客户端**：[GitHub Releases 页面](https://github.com/Mowen559/deepcloud-releases/releases/latest)

| 发行资产 (Asset) | 适用场景 | 说明 |
| :--- | :--- | :--- |
| **`deepcloud-ui Setup <version>.exe`** | 完整安装 | 首次使用请下载此安装包，支持自定义路径并自动创建快捷方式 |
| **`deepcloud-update-<version>.asar`** | 增量补丁 | 针对已有安装的轻量热更新补丁包，仅几十MB，秒级升级 |
| **`app.asar`** | 核心文件 | 完整核心脚本文件，可直接替换安装目录 `resources/app.asar` |
| **`checksums.txt`** | 安全校验 | 官方发布的各安装包与核心组件 SHA256 哈希校验清单 |

---

## ✨ 核心特性

- 🎬 **现代化流媒体与全功能播放器**：
  - 支持本地高码率视频、电视直播、夸克/阿里网盘与海阔视界全平台直链无缝解析播放；
  - 深度集成 **弹弹play 官方 API v2 开放平台**，具备 16MB 流式哈希精准匹配与大剧名智能正则检索，彻底打破防和谐文件名断层；
  - 内置画质增强着色器（Anime4K、FSR、CAS、插帧）与 WASAPI 独占高保真音频混音；
  - 支持多态悬浮球、画中画（PiP）与无边框沉浸模式。
- 🤖 **本地边缘与云端协同架构**：
  - 私有凭据端侧加密存储（基于系统级 `safeStorage`），保障用户账号绝对安全；
  - 支持多代理网关、Sidecar 守护进程与本地 AList / WebDAV 存储挂载。
- ⚡ **无感 ASAR 增量热更新**：
  - 客户端启动自动探测差分更新，秒级应用更新并软重启，免去频繁全量重装的繁琐流程。

---

## 🔒 校验和验证

在下载可执行文件后，推荐在终端中使用以下命令进行 SHA256 完整性校验：

```powershell
Get-FileHash -Path ".\deepcloud-ui Setup <version>.exe" -Algorithm SHA256
```

比对输出的哈希值是否与各版本 Release Notes 或 `checksums.txt` 中公布的一致。
