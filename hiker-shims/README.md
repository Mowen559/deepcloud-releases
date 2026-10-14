# @deepcloud/hiker-shims

> 🌐 海阔视界（HikerView）与 Android / Java 核心 API 的轻量级 JavaScript 兼容垫片库。
> 供开源社区共建规则执行所需的 Java 标准库、Android 特性与加解密算法适配。

---

## 📖 概述

在 PC 端或无头 Node.js 环境下运行海阔视界规则与爬虫小程序时，规则脚本通常会调用 Android 原生或 Java 平台的类库（例如 `android.util.Base64`、`java.lang.String`、`java.util.Arrays`、`javax.crypto.Cipher` 以及 `CryptoUtil`）。

本项目致力于以 **纯 JavaScript（基于 Node.js 标准 Buffer 与 crypto）** 模拟并补齐这些标准 API，使各类复杂规则无需底层真实 Android 设备即可顺畅执行。

**本项目仅包含通用兼容性垫片（Polyfills），不包含任何私有沙箱引擎、播放器或反爬调度核心。**

---

## 📦 包含的核心垫片模块

1. **Android 核心组件**：
   - `android.util.Base64`（支持 `DEFAULT`, `NO_PADDING`, `NO_WRAP`, `CRLF`, `URL_SAFE`）
   - `_base64` 全局别名
2. **Java 标准库核心类**：
   - `java.lang.String`（支持 `.getBytes(charset)`、`.replaceAll`、`.substring`、`.indexOf` 等）
   - `java.lang.StringBuilder` / `System`（支持 `currentTimeMillis()`, `arraycopy` 等）
   - `java.util.Arrays`（支持 `copyOfRange`, `copyOf`, `equals`, `fill`, `sort`, `asList`）
   - `java.util.Base64`（Java 8 标准编码解码器）
   - `java.util.ArrayList` / `java.util.HashMap` / `java.util.UUID`
   - `java.math.BigInteger` / `java.text.SimpleDateFormat`
   - `java.io.ByteArrayInputStream` / `ByteArrayOutputStream`
   - `Packages` 安全代理与 `JavaImporter`
3. **Java 加密扩展（JCE / javax.crypto）**：
   - `javax.crypto.Cipher`（支持 AES/CBC, AES/ECB, AES/GCM/NoPadding, DES 等）
   - `javax.crypto.spec.SecretKeySpec`
   - `javax.crypto.spec.GCMParameterSpec`
   - `javax.crypto.spec.IvParameterSpec`
   - `java.security.MessageDigest`
4. **海阔 CryptoUtil 工具套件**：
   - `CryptoUtil.Data`（Hex, Base64, UTF8, InputStream 互转）
   - `CryptoUtil.AES` / `DES` / `MD5` / `SHA1` / `SHA256`

---

## 🎯 核心标杆适配：聚阅（Juyue）超全规则支持

本垫片库以海阔生态中最复杂、功能最集大成的**「聚阅（Juyue）」**小程序作为黄金测试基准，全面覆盖其底层运行依赖：
- **两阶段接口加解密**：100% 对齐海阔官方 `AesUtil`（AES/ECB/PKCS5Padding，字符 `'0'` 自动补齐）与 Gzip 解压；
- **核心依赖自愈加载**：支持 `SrcJu.js`、`SrcJuPublic.js` 与 `SrcJuMethod.js` 依赖链的无缝沙箱拦截与本地化加载；
- **阻塞式交互桥接**：与主宿主配合提供 `selectBottomSettingMenu`、`SettingItem` 菜单项构造与切源交互；
- **多源爬虫中继**：无缝解析 TVBox / 海阔 Python 爬虫源所导出的标准聚阅规则。

---

## 🤝 欢迎社区贡献！

如果您在编写或调试海阔规则时遇到了 **“缺少某某 Java 类或方法”**（如 `java.text.DecimalFormat is not a function`），非常欢迎直接向本仓库提交 Pull Request：

1. **查阅贡献规范**：请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解代码规范与安全红线；
2. **就地模拟实现**：在 `src/java-shims.js` 或对应子模块中增加该类的模拟实现；
3. **编写原生测试**：在 `__tests__/` 下编写单元测试，运行 `npm test` 保证全量测试通过；
4. **提交 PR**：通过 CI 审查后合并打 Tag，DeepCloud 桌面客户端与爬虫引擎将**自动静默拉取热更新，秒级生效**！

---

## 📄 授权协议

[MIT License](LICENSE)
