# @deepcloud/hiker-shims 社区开发者与贡献指南 (Contributing Guide)

感谢您关注并参与 `@deepcloud/hiker-shims` 开源垫片库的共建！

海阔视界（HikerView）与聚阅（Juyue）规则生态庞大，许多站点规则或插件会调用各种 Android 原生类、Java JRE 核心类、JCE 加密算法及海阔独创的辅助函数。
本项目的核心目标是：**以 100% 纯 JavaScript（基于 Node.js 标准原生能力）高保真模拟这些 API，供端侧桌面沙箱、边缘爬虫引擎与无头执行器直接使用。**

---

## 🛠️ 目录结构与架构分工

```text
packages/hiker-shims/ (或发布仓库 hiker-shims/)
├── src/
│   ├── index.js               # 垫片库主入口，负责向沙箱挂载全部 Polyfills
│   ├── android-base64.js      # android.util.Base64 高保真模拟（支持 DEFAULT, NO_WRAP, CRLF 等）
│   ├── java-shims.js          # Java 核心类模拟 (String, Arrays, JCE Cipher, Regex, Calendar 等)
│   ├── crypto-util.js         # 海阔独创 CryptoUtil 套件 (Data, AES, DES, MD5, SHA256)
│   └── rule-helpers.js        # 规则辅助函数 (SettingItem, PinyinSort, Gzip, GM, UrlDSL 等)
├── __tests__/
│   └── shims.test.js          # 基于 Node.js 原生 node:test 的自动化测试套件
├── package.json               # 零重型第三方依赖（仅依赖纯 JS 的 crypto-js）
├── CONTRIBUTING.md            # 本贡献开发指南
└── README.md                  # 核心使用与标杆场景说明
```

---

## 🚀 极速上手开发

本项目无需安装任何复杂的构建工具或前端打包器，仅需 Node.js 18+ 环境。

### 1. 克隆与安装依赖

```bash
cd packages/hiker-shims
npm install
```

### 2. 运行自动化测试

```bash
npm test
```
测试通过 Node.js 原生 `node --test` 运行，毫秒级输出测试报告。

---

## 📝 如何新增一个缺失的 Java / Android 类或方法？

当规则在桌面端或爬虫引擎执行报错（例如：`TypeError: java.text.DecimalFormat is not a function`）时，只需三步即可完成贡献：

### 第一步：在对应子模块中实现该类或方法

* **如果是 Java 类**：在 `src/java-shims.js` 中编写工厂函数或 Class；
* **如果是 Android 特性**：在 `src/android-base64.js` 或对应模块中增加；
* **如果是加解密工具**：在 `src/crypto-util.js` 中增加。

**示例：增加 `java.text.DecimalFormat` 模拟**：

```javascript
// src/java-shims.js
function createDecimalFormatClass() {
  return class DecimalFormat {
    constructor(pattern) {
      this.pattern = pattern || '#.##';
    }
    format(number) {
      const num = Number(number);
      if (Number.isNaN(num)) return 'NaN';
      // 简单模式匹配格式化，或按需补齐
      return num.toFixed(2);
    }
  };
}
```

### 第二步：在 `src/index.js` 中注册并挂载

在 `attachCryptoAndCodecBuiltins(sandbox, hostAdapter)` 函数中将新类挂载到沙箱上下文：

```javascript
// src/index.js
const DecimalFormat = createDecimalFormatClass();
sandbox.java = sandbox.java || {};
sandbox.java.text = sandbox.java.text || {};
sandbox.java.text.DecimalFormat = DecimalFormat;
```

### 第三步：在 `__tests__/shims.test.js` 编写单元测试

```javascript
test('hiker-shims: DecimalFormat formats numbers correctly', () => {
  const sandbox = {};
  attachCryptoAndCodecBuiltins(sandbox);
  const df = new sandbox.java.text.DecimalFormat('0.00');
  assert.equal(df.format(3.14159), '3.14');
});
```

运行 `npm test` 确保 100% 绿灯 PASS！

---

## 🛡️ 代码贡献红线与安全规范

为了确保垫片能够在客户端与无头沙箱中安全运行，必须遵守以下铁律：

1. **严禁引入本地进程与原生文件特权**：
   - 严禁 `require('child_process')`、`require('fs')`（除受控内存流 `ByteArrayInputStream` 外）；
   - 垫片代码必须是纯计算、纯算法或纯内存流模拟，绝不能穿透沙箱访问用户本地物理磁盘。
2. **严禁引入笨重第三方包**：
   - 优先使用 Node.js 原生 `crypto`、`buffer`、`util` 模块；
   - 保持垫片包压缩后体积在 **50KB 以内**，确保客户端与爬虫能秒级静默拉取。
3. **保持链式安全代理（Packages Proxy）兼容**：
   - 对于尚未实现的生僻包名，通过 `createSafePackagesProxy` 拦截，确保规则在访问未定义类时返回安全空桩（Safe Stub），而不是直接抛出致命的 `Cannot read properties of undefined`。

---

## 🔄 动态发布与热重载运作原理

1. **PR 评审与合并**：
   - 社区提交的 PR 通过 CI 自动化测试后，合并至主分支并打上新版本 Tag（如 `v1.0.2`）；
2. **Release 自动化产出**：
   - GitHub Action 将 `src/` 源码打包为 `hiker-shims-vX.Y.Z.zip`，并更新 `version.json`；
3. **客户端无感热生效**：
   - DeepCloud 客户端后台检测到新版本后，仅下载这几十 KB 的补丁并解压至用户数据目录 `userData/bundles/hiker-shims/`；
   - 客户端无需重启，沙箱 Worker 在下次调用时优先加载此外部最新垫片，**几分钟内完成规则自愈**。
