/**
 * @deepcloud/hiker-shims - rule-helpers
 * 海阔视界规则支撑函数与算法垫片库
 * 包含插件本地化、拼音排序、文本相似度、文件与目录扩展、环境与原生控制垫片
 */

const fs = require('fs');
const path = require('path');

/**
 * 字符串 Levenshtein 编辑距离算法
 */
function levenshteinDistance(s1, s2) {
  const a = String(s1 || '');
  const b = String(s2 || '');
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;

  const m = a.length;
  const n = b.length;
  const d = [];

  for (let i = 0; i <= m; i++) d[i] = [i];
  for (let j = 0; j <= n; j++) d[0][j] = j;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(
        d[i - 1][j] + 1,       // 删除
        d[i][j - 1] + 1,       // 插入
        d[i - 1][j - 1] + cost // 替换
      );
    }
  }

  return d[m][n];
}

/**
 * 字符串相似度 (0 ~ 1)
 */
function similarity(s1, s2) {
  const a = String(s1 || '');
  const b = String(s2 || '');
  if (a === b) return 1;
  const maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 1;
  const dist = levenshteinDistance(a, b);
  return Math.max(0, 1 - dist / maxLen);
}

/**
 * 中文拼音/本地化排序
 */
function sortByPinyin(list, key) {
  if (!Array.isArray(list)) return [];
  const collator = new Intl.Collator('zh-Hans-CN', { sensitivity: 'accent', numeric: true });
  return [...list].sort((a, b) => {
    let strA = '';
    let strB = '';
    if (typeof a === 'object' && a !== null) {
      strA = a[key || 'title'] || a.name || a.label || '';
    } else {
      strA = String(a || '');
    }
    if (typeof b === 'object' && b !== null) {
      strB = b[key || 'title'] || b.name || b.label || '';
    } else {
      strB = String(b || '');
    }
    return collator.compare(String(strA), String(strB));
  });
}

/**
 * 日期格式化
 */
function dateFormat(date, fmt = 'YYYY-MM-DD HH:mm:ss') {
  let d = date instanceof Date ? date : new Date(date || Date.now());
  if (isNaN(d.getTime())) d = new Date();

  const pad = (n) => String(n).padStart(2, '0');
  const opt = {
    'YYYY': d.getFullYear(),
    'YY': String(d.getFullYear()).slice(-2),
    'MM': pad(d.getMonth() + 1),
    'M': d.getMonth() + 1,
    'DD': pad(d.getDate()),
    'D': d.getDate(),
    'HH': pad(d.getHours()),
    'H': d.getHours(),
    'mm': pad(d.getMinutes()),
    'm': d.getMinutes(),
    'ss': pad(d.getSeconds()),
    's': d.getSeconds(),
    'SSS': String(d.getMilliseconds()).padStart(3, '0')
  };

  let res = String(fmt);
  for (const k of Object.keys(opt)) {
    res = res.replace(new RegExp(k, 'g'), opt[k]);
  }
  return res;
}

/**
 * 聚阅/海阔视界 设置菜单项构造函数 (SettingItem)
 * 支持普通项、开关项与分隔线 (Divider)
 */
function SettingItem(title, descOrSelected, extra) {
  if (!(this instanceof SettingItem)) {
    return new SettingItem(title, descOrSelected, extra);
  }
  this.isDivider = (!title && title !== 0);
  this.title = title != null ? String(title) : '';
  this.extra = extra || {};

  if (typeof descOrSelected === 'boolean') {
    this.isSwitch = true;
    this.selected = descOrSelected ? 1 : -1;
    this.desc = '';
  } else if (typeof descOrSelected === 'number') {
    this.isSwitch = false;
    this.selected = descOrSelected;
    this.desc = String(descOrSelected);
  } else if (descOrSelected != null) {
    this.isSwitch = false;
    this.selected = 0;
    this.desc = String(descOrSelected);
  } else {
    this.isSwitch = false;
    this.selected = 0;
    this.desc = '';
  }

  this.getTitle = function () { return this.title; };
  this.setTitle = function (t) { this.title = String(t != null ? t : ''); return this; };
  this.getDesc = function () { return this.desc; };
  this.setDesc = function (d) { this.desc = String(d != null ? d : ''); return this; };
  this.getSelected = function () { return this.selected; };
  this.setSelected = function (sel) {
    if (typeof sel === 'boolean') {
      this.selected = sel ? 1 : -1;
    } else {
      this.selected = Number(sel) || 0;
    }
    return this;
  };
  this.isChecked = function () { return this.selected === 1; };
  this.setChecked = function (chk) { this.selected = chk ? 1 : -1; return this; };
  this.getValue = function () { return this.desc; };
  this.setValue = function (v) { this.desc = String(v != null ? v : ''); return this; };
}

/**
 * 创建与沙箱环境及 hostAdapter 绑定的规则辅助方法集
 */
function createRuleHelpers(sandbox, hostAdapter) {
  // 1. 聚阅插件下载本地化兜底
  function downloadPlugins(update) {
    try {
      const cfg = sandbox.config || {};
      const repoUrl = (cfg.聚阅 || (typeof sandbox.getPublicItem === 'function' ? sandbox.getPublicItem('聚阅', '') : '') || '').replace(/[^/]*$/, '');
      if (repoUrl) {
        const files = [
          'plugins/hikerPop.js',
          'plugins/gzip.js',
          'plugins/pinyin-match.js',
          'plugins/categories-header.js',
          'plugins/globalmap.js',
          'template/GetAppApi.js',
          'template/parseCode.js',
          'template/采集cms.js'
        ];
        const libsPath = typeof sandbox.libspath !== 'undefined' ? sandbox.libspath : 'hiker://files/libs/';
        files.forEach((it) => {
          const dest = libsPath + it;
          if (update && typeof sandbox.deleteFile === 'function') {
            try { sandbox.deleteFile(dest); } catch (_) {}
          }
          if (typeof sandbox.requireDownload === 'function') {
            try {
              sandbox.requireDownload(repoUrl + it, dest);
            } catch (err) {
              if (typeof sandbox.xlog === 'function') sandbox.xlog(`下载插件 [${it}] 警告: ` + err.message);
            }
          }
        });
      }
    } catch (e) {
      if (typeof sandbox.xlog === 'function') {
        sandbox.xlog('插件文件本地化失败>' + (e && e.message ? e.message : String(e)));
      }
    }
  }

  // 2. 文件与目录辅助函数
  function exists(targetPath) {
    if (typeof sandbox.fileExist === 'function') {
      return sandbox.fileExist(targetPath);
    }
    if (hostAdapter && typeof hostAdapter.fileExists === 'function') {
      return hostAdapter.fileExists(targetPath);
    }
    return false;
  }

  function resolveRuleDirPath(targetPath) {
    let resolved = String(targetPath || '');
    if (!resolved) return '';
    if (hostAdapter && typeof hostAdapter.resolvePath === 'function') {
      resolved = hostAdapter.resolvePath(resolved);
    } else if (hostAdapter && typeof hostAdapter.resolveHikerPath === 'function' && (resolved.startsWith('hiker://') || resolved.startsWith('file://'))) {
      resolved = hostAdapter.resolveHikerPath(resolved);
    } else if (resolved.startsWith('file://')) {
      resolved = resolved.slice('file://'.length);
      if (/^\/[a-zA-Z]:[\\/]/.test(resolved)) resolved = resolved.slice(1);
    }
    return resolved;
  }

  function isDirectory(targetPath) {
    try {
      const resolved = resolveRuleDirPath(targetPath);
      return Boolean(resolved) && fs.existsSync(resolved) && fs.statSync(resolved).isDirectory();
    } catch (_) {
      return false;
    }
  }

  function listFiles(dirPath) {
    try {
      const resolved = resolveRuleDirPath(dirPath);
      if (resolved && fs.existsSync(resolved) && fs.statSync(resolved).isDirectory()) {
        return fs.readdirSync(resolved);
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  function deleteDir(dirPath) {
    try {
      const resolved = resolveRuleDirPath(dirPath);
      if (resolved && fs.existsSync(resolved)) {
        fs.rmSync(resolved, { recursive: true, force: true });
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  // 3. 弹幕与文件下载
  function danmuDownLoad(url, savePath, options) {
    if (typeof sandbox.downloadFile === 'function') {
      return sandbox.downloadFile(url, savePath, options);
    }
    if (typeof sandbox.requireDownload === 'function') {
      return sandbox.requireDownload(url, savePath, options);
    }
  }

  function downloadFile(url, savePath, headers) {
    if (hostAdapter && typeof hostAdapter.downloadFile === 'function') {
      return hostAdapter.downloadFile(url, savePath, headers);
    }
    if (typeof sandbox.requireDownload === 'function') {
      return sandbox.requireDownload(url, savePath, headers);
    }
  }

  // 4. m3u8 增强垫片
  function batchCacheM3u8(params) {
    if (!Array.isArray(params)) return [];
    return params.map(p => {
      const u = typeof p === 'string' ? p : p?.url;
      return typeof sandbox.cacheM3u8 === 'function' ? sandbox.cacheM3u8(u, p?.options) : u;
    });
  }

  function clearM3u8Ad(url) {
    return url;
  }

  function clearM3u8AdLazy(url, options) {
    return `${url}#clearAd#`;
  }

  function convertM3u8WithPngProxy(content) {
    return String(content || '');
  }

  function cacheM3u8WithPngProxy(url, options, fileName) {
    return typeof sandbox.cacheM3u8 === 'function' ? sandbox.cacheM3u8(url, options, fileName) : url;
  }

  // 5. 状态与环境判定
  function isDarkMode() {
    return false;
  }

  function canBiometric() {
    return false;
  }

  function checkByBiometric(callback) {
    if (typeof callback === 'function') {
      try { callback(true); } catch (_) {}
    }
    return true;
  }

  function getCpuAbi() {
    return process.arch === 'arm64' ? 'arm64-v8a' : 'x86_64';
  }

  function isLogin() {
    return false;
  }

  function parsePaste(pasteUrl) {
    if (hostAdapter && typeof hostAdapter.parsePaste === 'function') {
      return hostAdapter.parsePaste(pasteUrl);
    }
    if (typeof sandbox.parsePaste === 'function' && sandbox.parsePaste !== parsePaste) {
      return sandbox.parsePaste(pasteUrl);
    }
    return String(pasteUrl || '');
  }

  function sharePaste(content, paste) {
    if (hostAdapter && typeof hostAdapter.sharePaste === 'function') {
      return hostAdapter.sharePaste(content, paste);
    }
    if (typeof sandbox.sharePaste === 'function' && sandbox.sharePaste !== sharePaste) {
      return sandbox.sharePaste(content, paste);
    }
    return '';
  }

  function getPastes() {
    if (hostAdapter && typeof hostAdapter.getPastes === 'function') {
      return hostAdapter.getPastes();
    }
    return ['云剪贴板6', '云剪贴板5', '云剪贴板2'];
  }

  function executeWebRule(url, jsCode, options) {
    if (typeof sandbox.fetchCodeByWebView === 'function') {
      return sandbox.fetchCodeByWebView(url, options);
    }
    return '';
  }

  function publishRule(rule) {
    if (typeof sandbox.toast === 'function') {
      sandbox.toast('规则已记录');
    }
    return 'ok';
  }

  // 6. UI 与 原生控制
  function scrollToPosition(pos) {}
  function selectBottomResIcon(opts) {
    if (!opts) return { dismiss() {} };
    const rawList = opts.iconList || opts.options || [];
    const items = rawList.map((it) => {
      if (typeof it === 'object' && it) {
        return {
          title: it.title || it.name || '',
          icon: it.icon || it.img || '',
          data: it.data || it,
        };
      }
      return { title: String(it ?? ''), icon: '', data: it };
    });

    const jsCallback = opts.click && typeof sandbox.$ === 'object' && typeof sandbox.$.toString === 'function'
      ? sandbox.$.toString((items) => {
          let item = items[MY_INDEX];
          if (item) {
            require(config.聚阅.replace(/[^/]*$/, '') + 'SrcJuPublic.js');
            if (typeof changeSource === 'function' && item.data) {
              return changeSource(item.data);
            }
          }
        }, items)
      : undefined;

    if (typeof sandbox.showSelectOptions === 'function') {
      sandbox.showSelectOptions({
        title: opts.title || '请选择',
        options: items,
        selectedIndex: opts.position ?? -1,
        col: opts.columns || 3,
        bottom: true,
        js: jsCallback,
      });
    }
    return {
      dismiss() {},
      change(newItems) {},
      setTitle(t) {},
      setSelectedIndex(idx) {},
      scrollToPosition(idx, anim) {},
      changeColumns(cols) {}
    };
  }

  function selectCenter(opts) {
    if (!opts) return { dismiss() {} };
    const rawList = opts.options || [];
    if (typeof sandbox.showSelectOptions === 'function') {
      sandbox.showSelectOptions({
        title: opts.title || '请选择',
        options: rawList,
        selectedIndex: opts.position ?? -1,
        col: opts.columns || 3,
        bottom: false,
      });
    }
    return { dismiss() {} };
  }
  function setUseStartActivity(val) {}
  function changeColumns(cols) {}
  function startQRScanPage() {}
  function registerDNS(dnsMap) {}

  // 7. EPUB 占位
  function getEpubChapters(path) { return []; }
  function getEpubContent(path, url) { return ''; }
  function getEpubMetadata(path) { return {}; }

  // 8. 文本搜索与格式转换
  function searchContains(text, key, ignoreCase = false) {
    if (!text || !key) return false;
    let t = String(text);
    let k = String(key);
    if (ignoreCase) {
      t = t.toLowerCase();
      k = k.toLowerCase();
    }
    const keywords = k.split(/\s+/).filter(Boolean);
    if (keywords.length === 0) return true;
    return keywords.every(kw => t.includes(kw));
  }

  function convertBase64Image(url) {
    if (!url) return '';
    if (typeof url === 'string' && url.startsWith('data:image/')) return url;
    if (typeof sandbox.fetch === 'function' && typeof url === 'string' && url.startsWith('http')) {
      try {
        const res = sandbox.fetch(url, { toHex: true });
        if (res && typeof sandbox.hexToBase64 === 'function') {
          return 'data:image/jpeg;base64,' + sandbox.hexToBase64(res);
        }
      } catch (_) {}
    }
    return '';
  }

  function getJsPlugin() { return ''; }
  function getJsLazyPlugin() { return ''; }
  function getFilePath(p) {
    return typeof sandbox.getAbsolutePath === 'function' ? sandbox.getAbsolutePath(p) : String(p || '');
  }
  function setImmersion(val) {}

  // 9. 聚阅 (Juyue) 规则生态运行基础设施
  const libspath = "hiker://files/data/聚阅/";
  const rulepath = "hiker://files/rules/Src/Juyue/";
  const codePath = rulepath;
  const cachepath = "hiker://files/_cache/Juyue/";
  const jkfilespath = rulepath + "jiekou/";
  const jkfile = rulepath + "jiekou.json";
  const cfgfile = rulepath + "config.json";
  const sortfile = rulepath + "jksort.json";
  const casefile = rulepath + "case.json";

  const xlog = (...args) => (typeof sandbox.log === 'function' ? sandbox.log(...args) : console.log(...args));
  const log2 = (...args) => (typeof sandbox.log === 'function' ? sandbox.log(...args) : console.log(...args));

  function juItemF(id, s) {
    const filePath = s ? `${rulepath}juItem.json` : `${libspath}juItem.json`;
    return {
      file: filePath,
      items: function() {
        let items = {};
        if (typeof sandbox.fetch === 'function') {
          try {
            const raw = sandbox.fetch(this.file);
            if (raw && typeof raw === 'string' && raw.trim()) {
              items = JSON.parse(raw);
            }
          } catch (_) {}
        }
        return items;
      },
      set: function(key, str, id2) {
        if (!key || str === undefined || str === null) return;
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        const items = this.items();
        const item = items[targetId] || {};
        item[key] = str;
        items[targetId] = item;
        if (typeof sandbox.writeFile === 'function') {
          sandbox.writeFile(this.file, JSON.stringify(items));
        }
      },
      get: function(key, str, id2) {
        if (!key) return '';
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        const items = this.items();
        const item = items[targetId] || {};
        if (item[key] !== undefined && item[key] !== null) {
          return item[key];
        }
        return str !== undefined ? str : '';
      },
      clear: function(key, id2) {
        if (!key) return;
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        const items = this.items();
        const item = items[targetId] || {};
        if (item[key] !== undefined) {
          delete item[key];
          items[targetId] = item;
          if (typeof sandbox.writeFile === 'function') {
            sandbox.writeFile(this.file, JSON.stringify(items));
          }
        }
      },
      getAll: function(id2) {
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        const items = this.items();
        return items[targetId] || {};
      },
      clearAll: function(id2) {
        if (!id2) return;
        const items = this.items();
        delete items[id2];
        if (typeof sandbox.writeFile === 'function') {
          sandbox.writeFile(this.file, JSON.stringify(items));
        }
      },
      listKeys: function(id2) {
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        const items = this.items();
        return Object.keys(items[targetId] || {});
      }
    };
  }

  function juFileF(id) {
    return {
      file: function(jkid, filename) {
        const safeName = String(filename || '');
        return `hiker://files/data2/聚阅/juFile/${jkid}/${safeName}` + (safeName.includes('.') ? '' : '.txt');
      },
      save: function(key, str, id2) {
        if (!key || str === undefined || str === null || str === '') return;
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        if (typeof sandbox.writeFile === 'function') {
          sandbox.writeFile(this.file(targetId, key), String(str));
        }
      },
      read: function(key, id2) {
        if (!key) return '';
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        if (typeof sandbox.fetch === 'function') {
          return sandbox.fetch(this.file(targetId, key)) || '';
        }
        return '';
      },
      delete: function(key, id2) {
        if (!key) return;
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        if (typeof sandbox.deleteFile === 'function') {
          sandbox.deleteFile(this.file(targetId, key));
        }
      },
      exist: function(key, id2) {
        if (!key) return false;
        const targetId = id2 || id || (sandbox.storage0?.getMyVar?.('二级源接口信息') || sandbox.storage0?.getMyVar?.('一级源接口信息'))?.id || 'default';
        if (typeof sandbox.fileExist === 'function') {
          return sandbox.fileExist(this.file(targetId, key));
        }
        return false;
      }
    };
  }

  const juItem = juItemF();
  const juItem2 = juItemF('Juyue', 1);
  const juFile = juFileF();

  function getJuconfig() {
    let Juconfig = {};
    if (typeof sandbox.fetch === 'function') {
      try {
        const Jucfg = sandbox.fetch(cfgfile);
        if (Jucfg && typeof Jucfg === 'string' && Jucfg.trim()) {
          Juconfig = JSON.parse(Jucfg);
        }
      } catch (_) {}
    }
    return Juconfig;
  }

  function setJuconfig(cfg) {
    if (typeof sandbox.writeFile === 'function') {
      sandbox.writeFile(cfgfile, JSON.stringify(cfg || {}));
    }
  }

  // 跨平台环境下确保聚阅默认选用跨平台原生选择组件
  try {
    if (typeof sandbox.getItem === 'function' && typeof sandbox.setItem === 'function') {
      if (!sandbox.getItem('选择主页源插件')) {
        sandbox.setItem('选择主页源插件', '原生组件');
      }
    }
  } catch (_) {}

  function setJkSort(idOrData, obj) {
    if (typeof sandbox.writeFile !== 'function') return;
    if (arguments.length >= 2 || Array.isArray(idOrData)) {
      let jksort = {};
      if (typeof sandbox.fetch === 'function') {
        try {
          const raw = sandbox.fetch(sortfile);
          if (raw && typeof raw === 'string' && raw.trim()) {
            jksort = JSON.parse(raw);
          }
        } catch (_) {}
      }
      if (!jksort || typeof jksort !== 'object' || Array.isArray(jksort)) {
        jksort = {};
      }
      if (Array.isArray(idOrData)) {
        const idList = idOrData;
        for (const key in jksort) {
          if (Object.prototype.hasOwnProperty.call(jksort, key) && !idList.includes(key)) {
            delete jksort[key];
          }
        }
      } else if (idOrData && typeof obj === 'object') {
        jksort[idOrData] = Object.assign(jksort[idOrData] || {}, obj);
      }
      sandbox.writeFile(sortfile, JSON.stringify(jksort));
    } else {
      sandbox.writeFile(sortfile, JSON.stringify(idOrData || {}));
    }
  }

  function getOptions(inSampleSize) {
    return { inSampleSize: inSampleSize || 1 };
  }

  const evalPublicStr = `
    let juItem = juItemF(jkdata.id);
    let juFile = juFileF(jkdata.id);
    if (parse['预处理1'] && !getMyVar(jkdata.id+'执行预处理1')) {
        parse['预处理1'].call(parse);
        putMyVar(jkdata.id+'执行预处理1', '1');
    } else if (parse['预处理']) {
        parse['预处理'].call(parse);
    }
  `;

  // 10. 全局缓存管理 (GlobalMap / GM) 垫片
  const GM = {
    get _map() {
      if (!sandbox._globalMap) {
        const MapClass = sandbox.java?.util?.HashMap;
        sandbox._globalMap = MapClass ? new MapClass() : new Map();
      }
      return sandbox._globalMap;
    },
    get(key, defaultValue) {
      const m = this._map;
      const has = typeof m.containsKey === 'function' ? m.containsKey(key) : m.has(key);
      if (has) return m.get(key);
      return defaultValue !== undefined ? defaultValue : null;
    },
    put(key, value) {
      const m = this._map;
      if (typeof m.put === 'function') m.put(key, value);
      else m.set(key, value);
      return value;
    },
    clear(key) {
      const m = this._map;
      if (typeof m.remove === 'function') return m.remove(key);
      const val = m.get(key);
      m.delete(key);
      return val;
    },
    clearAll() {
      const m = this._map;
      if (typeof m.clear === 'function') m.clear();
    },
    has(key) {
      const m = this._map;
      return typeof m.containsKey === 'function' ? m.containsKey(key) : m.has(key);
    },
    define(key, value, force = false) {
      if (force || !this.has(key)) {
        this.put(key, value);
      }
      return this.get(key);
    },
    defineLazy(key, factoryFn, force = false) {
      if (force || !this.has(key)) {
        if (typeof factoryFn !== 'function') {
          throw new Error('GM.defineLazy requires a function as the second argument');
        }
        const val = factoryFn();
        this.put(key, val);
      }
      return this.get(key);
    },
    defineModule(key, filePath, force = false) {
      return this.defineLazy(key, () => {
        if (sandbox.$ && typeof sandbox.$.require === 'function') {
          return sandbox.$.require(filePath);
        }
        if (typeof sandbox.require === 'function') {
          return sandbox.require(filePath);
        }
        return {};
      }, force);
    },
    listKeys() {
      const m = this._map;
      if (typeof m.keySet === 'function') {
        const ks = m.keySet();
        if (typeof ks.toArray === 'function') return ks.toArray();
      }
      if (typeof m.keys === 'function') return Array.from(m.keys());
      return [];
    },
    toJSON() {
      const obj = {};
      for (const k of this.listKeys()) {
        obj[k] = this.get(k);
      }
      return obj;
    }
  };

  return {
    libspath,
    rulepath,
    codePath,
    cachepath,
    jkfilespath,
    jkfile,
    cfgfile,
    sortfile,
    casefile,
    xlog,
    log2,
    juItemF,
    juFileF,
    juItem,
    juItem2,
    juFile,
    getJuconfig,
    setJuconfig,
    setJkSort,
    getOptions,
    evalPublicStr,
    GM,
    downloadPlugins,
    danmuDownLoad,
    downloadFile,
    batchCacheM3u8,
    bcm: batchCacheM3u8,
    clearM3u8Ad,
    clearM3u8AdLazy,
    convertM3u8WithPngProxy,
    cacheM3u8WithPngProxy,
    levenshtein: levenshteinDistance,
    levenshteinDistance,
    similarity,
    sortByPinyin,
    dateFormat,
    exists,
    isDirectory,
    listFiles,
    readDir: listFiles,
    deleteDir,
    isDarkMode,
    canBiometric,
    checkByBiometric,
    getCpuAbi,
    isLogin,
    parsePaste,
    sharePaste,
    getPastes,
    executeWebRule,
    publishRule,
    scrollToPosition,
    selectBottomResIcon,
    selectCenter,
    setUseStartActivity,
    changeColumns,
    getEpubChapters,
    getEpubContent,
    getEpubMetadata,
    searchContains,
    convertBase64Image,
    getJsPlugin,
    getJsLazyPlugin,
    getFilePath,
    setImmersion,
    SettingItem,
  };
}

module.exports = {
  levenshteinDistance,
  similarity,
  sortByPinyin,
  dateFormat,
  SettingItem,
  createRuleHelpers,
};
