/**
 * @deepcloud/hiker-shims
 * 海阔视界兼容垫片主入口 (Android / Java / CryptoUtil)
 */

const { createAndroidBase64, createJavaUtilBase64 } = require('./android-base64');
const {
  JavaImporter,
  createSafePackagesProxy,
  createSafeStub,
  createJavaStringClass,
  createArraysClass,
  createCipherClass,
  createSecretKeySpecClass,
  createGCMParameterSpecClass,
  createIvParameterSpecClass,
  createMessageDigestClass,
  createMacClass,
  createUUIDClass,
  createBigIntegerClass,
  createSimpleDateFormatClass,
  createArrayListClass,
  createHashMapClass,
  createJSONObjectClass,
  createJSONArrayClass,
  createByteArrayInputStreamClass,
  createByteArrayOutputStreamClass,
  createJavaFileClass,
  createStringBuilderClass,
  createAndroidGraphicsShims,
  createAndroidOsShims,
  createJavaUtilZipShims,
  createAndroidNetUriClass,
  createJavaRegexShims,
  createBigDecimalClass,
  createDecimalFormatClass,
  createJavaDateAndCalendarShims,
  createJavaSetClasses,
  createJavaExtraCollectionsShims,
  createComHikerviewUtilsShims,
  StandardCharsets,
} = require('./java-shims');
const CryptoUtil = require('./crypto-util');
const {
  levenshteinDistance,
  similarity,
  sortByPinyin,
  dateFormat,
  createRuleHelpers,
} = require('./rule-helpers');

/**
 * 将全部 Android、Java 标准库与 CryptoUtil 垫片挂载到目标沙箱对象上
 * @param {Object} sandbox 目标沙箱环境 (如 VM context 或全局对象)
 * @param {Object} [hostAdapter] 宿主平台适配器
 */
function attachCryptoAndCodecBuiltins(sandbox, hostAdapter) {
  const AndroidBase64 = createAndroidBase64();
  const JavaUtilBase64 = createJavaUtilBase64(AndroidBase64);
  const Arrays = createArraysClass();
  const JavaString = createJavaStringClass();
  const Cipher = createCipherClass();
  const MessageDigest = createMessageDigestClass();
  const UUID = createUUIDClass();
  const BigInteger = createBigIntegerClass();
  const BigDecimal = createBigDecimalClass();
  const DecimalFormat = createDecimalFormatClass();
  const SimpleDateFormat = createSimpleDateFormatClass();
  const ArrayList = createArrayListClass();
  const HashMap = createHashMapClass();
  const JSONObject = createJSONObjectClass();
  const JSONArray = createJSONArrayClass();
  const ByteArrayInputStream = createByteArrayInputStreamClass();
  const ByteArrayOutputStream = createByteArrayOutputStreamClass();
  const JavaFile = createJavaFileClass();
  const StringBuilder = createStringBuilderClass();
  const AndroidGraphics = createAndroidGraphicsShims();
  const AndroidOs = createAndroidOsShims();
  const JavaUtilZip = createJavaUtilZipShims();
  const AndroidNetUri = createAndroidNetUriClass();
  const { Pattern, Matcher } = createJavaRegexShims();
  const { JavaDate, Calendar } = createJavaDateAndCalendarShims();
  const { HashSet, TreeSet } = createJavaSetClasses();
  const { LinkedList, Stack } = createJavaExtraCollectionsShims();
  const HikerviewUtils = createComHikerviewUtilsShims(sandbox);

  // 基础编解码与 Buffer
  sandbox.Buffer = sandbox.Buffer || Buffer;
  sandbox.Date = sandbox.Date || Date;
  sandbox._base64 = AndroidBase64;
  sandbox.Base64 = sandbox.Base64 || AndroidBase64;
  sandbox.JavaImporter = JavaImporter;
  sandbox.CryptoUtil = CryptoUtil;

  // android.*
  const androidObj = sandbox.android || {};
  androidObj.util = androidObj.util || {};
  androidObj.util.Base64 = AndroidBase64;
  androidObj.net = androidObj.net || {};
  androidObj.net.Uri = AndroidNetUri;
  androidObj.graphics = Object.assign(androidObj.graphics || {}, AndroidGraphics);
  androidObj.os = Object.assign(androidObj.os || {}, AndroidOs);
  androidObj.content = Object.assign(androidObj.content || {}, {
    res: {
      Configuration: {
        UI_MODE_NIGHT_MASK: 48,
        UI_MODE_NIGHT_YES: 32,
        UI_MODE_NIGHT_NO: 16,
      },
    },
    Context: {},
  });
  androidObj.view = androidObj.view || {
    View: {},
    LayoutInflater: { from: () => ({ inflate: () => ({}) }) },
  };
  androidObj.widget = androidObj.widget || {
    LinearLayout: {},
    FrameLayout: { LayoutParams: function() {} },
  };
  androidObj.R = androidObj.R || {
    layout: { simple_list_item_1: 1 },
    drawable: {},
  };
  sandbox.android = createSafePackagesProxy(androidObj, 'android');

  // java.io
  const javaObj = sandbox.java || {};
  javaObj.io = javaObj.io || {};
  javaObj.io.ByteArrayInputStream = ByteArrayInputStream;
  javaObj.io.ByteArrayOutputStream = ByteArrayOutputStream;
  javaObj.io.File = JavaFile;

  // java.lang
  function createJavaNumberClass(parseFn) {
    function JavaNumber(v) {
      if (!new.target) return new JavaNumber(v);
      this._val = parseFn ? parseFn(v) : Number(v || 0);
    }
    JavaNumber.prototype.valueOf = function() { return this._val; };
    JavaNumber.prototype.toString = function() { return String(this._val); };
    JavaNumber.prototype.doubleValue = function() { return Number(this._val); };
    JavaNumber.prototype.intValue = function() { return parseInt(this._val, 10); };
    JavaNumber.prototype.longValue = function() { return parseInt(this._val, 10); };
    JavaNumber.prototype.floatValue = function() { return Number(this._val); };
    JavaNumber.valueOf = function(v) { return new JavaNumber(v); };
    JavaNumber.parseDouble = function(s) { return parseFloat(s); };
    JavaNumber.parseFloat = function(s) { return parseFloat(s); };
    JavaNumber.parseInt = function(s, r = 10) { return parseInt(s, r); };
    JavaNumber.parseLong = function(s, r = 10) { return parseInt(s, r); };
    JavaNumber.MAX_VALUE = Number.MAX_VALUE;
    JavaNumber.MIN_VALUE = Number.MIN_VALUE;
    JavaNumber.TYPE = 'number';
    Object.defineProperty(JavaNumber, Symbol.hasInstance, {
      value: (instance) => typeof instance === 'number' || instance instanceof Number || (instance && instance._val !== undefined)
    });
    return JavaNumber;
  }

  function createJavaBooleanClass() {
    function JavaBool(v) {
      if (!new.target) return new JavaBool(v);
      this._val = typeof v === 'string' ? v.toLowerCase() === 'true' : Boolean(v);
    }
    JavaBool.prototype.valueOf = function() { return this._val; };
    JavaBool.prototype.toString = function() { return String(this._val); };
    JavaBool.prototype.booleanValue = function() { return this._val; };
    JavaBool.valueOf = function(s) { return new JavaBool(String(s).toLowerCase() === 'true'); };
    JavaBool.parseBoolean = function(s) { return String(s).toLowerCase() === 'true'; };
    JavaBool.TRUE = true;
    JavaBool.FALSE = false;
    JavaBool.TYPE = 'boolean';
    Object.defineProperty(JavaBool, Symbol.hasInstance, {
      value: (instance) => typeof instance === 'boolean' || instance instanceof Boolean || (instance && instance._val !== undefined)
    });
    return JavaBool;
  }

  try {
    Object.defineProperty(JavaString, Symbol.hasInstance, {
      value: (instance) => typeof instance === 'string' || instance instanceof String || (instance && instance._str !== undefined)
    });
  } catch (_) {}

  const JavaDouble = createJavaNumberClass((v) => parseFloat(v));
  const JavaFloat = createJavaNumberClass((v) => parseFloat(v));
  const JavaInteger = createJavaNumberClass((v) => parseInt(v, 10));
  const JavaLong = createJavaNumberClass((v) => parseInt(v, 10));
  const JavaBoolean = createJavaBooleanClass();

  function JavaObject(val) {
    if (!new.target) return new JavaObject(val);
    this._val = val;
  }
  JavaObject.prototype.toString = function() { return String(this._val); };

  function JavaException(msg) {
    if (!new.target) return new JavaException(msg);
    this.message = String(msg || '');
  }
  JavaException.prototype.toString = function() { return this.message; };


  javaObj.lang = javaObj.lang || {};
  javaObj.lang.String = JavaString;
  javaObj.lang.Double = JavaDouble;
  javaObj.lang.Float = JavaFloat;
  javaObj.lang.Long = JavaLong;
  javaObj.lang.Integer = JavaInteger;
  javaObj.lang.Boolean = JavaBoolean;
  javaObj.lang.Object = JavaObject;
  javaObj.lang.Exception = JavaException;
  javaObj.lang.Throwable = JavaException;
  javaObj.lang.Byte = { TYPE: 'byte' };
  javaObj.lang.Class = { forName: () => ({}) };
  javaObj.lang.Runnable = function(fn) {
    return {
      run: () => {
        if (typeof fn === 'function') return fn();
        if (fn && typeof fn.run === 'function') return fn.run();
      },
    };
  };
  javaObj.lang.reflect = { Array: { newInstance: (t, len) => Buffer.alloc(len) } };
  javaObj.lang.StringBuilder = StringBuilder;
  javaObj.lang.StringBuffer = StringBuilder;
  javaObj.lang.Math = Math;
  javaObj.lang.Thread = {
    sleep: (ms) => {
      const timeout = Math.min(Math.max(Number(ms) || 0, 0), 10000);
      if (timeout <= 0) return;
      try {
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, timeout);
      } catch (e) {
        const start = Date.now();
        while (Date.now() - start < timeout) {}
      }
    },
    currentThread: () => ({ getName: () => 'main', getId: () => 1 }),
  };
  javaObj.lang.System = {
    currentTimeMillis: () => Date.now(),
    nanoTime: () => Number(process.hrtime.bigint()),
    arraycopy: (src, srcPos, dest, destPos, length) => {
      if (!src || !dest) return;
      if (Buffer.isBuffer(src) && Buffer.isBuffer(dest)) {
        src.copy(dest, destPos, srcPos, srcPos + length);
      } else if (src instanceof Uint8Array && dest instanceof Uint8Array) {
        dest.set(src.subarray(srcPos, srcPos + length), destPos);
      } else {
        for (let i = 0; i < length; i++) {
          dest[destPos + i] = src[srcPos + i];
        }
      }
    },
    identityHashCode: () => 1,
    gc: () => {},
    getProperty: (_k, def) => def || '',
    out: {
      println: (...args) => (typeof sandbox.log === 'function' ? sandbox.log(args.join(' ')) : console.log(...args)),
      print: (...args) => (typeof sandbox.log === 'function' ? sandbox.log(args.join(' ')) : console.log(...args)),
    },
    err: {
      println: (...args) => (typeof sandbox.log === 'function' ? sandbox.log('[Error] ' + args.join(' ')) : console.error(...args)),
      print: (...args) => (typeof sandbox.log === 'function' ? sandbox.log('[Error] ' + args.join(' ')) : console.error(...args)),
    },
  };

  // java.math
  javaObj.math = javaObj.math || {};
  javaObj.math.BigInteger = BigInteger;
  javaObj.math.BigDecimal = BigDecimal;

  // java.net
  javaObj.net = javaObj.net || {};
  javaObj.net.URLEncoder = {
    encode: (str, _charset) => {
      if (str === null || str === undefined) return '';
      return encodeURIComponent(String(str)).replace(/%20/g, '+');
    },
  };
  javaObj.net.URLDecoder = {
    decode: (str, _charset) => {
      if (str === null || str === undefined) return '';
      try {
        return decodeURIComponent(String(str).replace(/\+/g, '%20'));
      } catch (_) {
        return String(str);
      }
    },
  };
  javaObj.net.URL = function(u) {
    return new URL(u);
  };
  javaObj.net.URI = function(u) {
    return new URL(u);
  };
  javaObj.net.URI.create = (u) => new URL(u);

  // java.nio
  javaObj.nio = javaObj.nio || {};
  javaObj.nio.charset = javaObj.nio.charset || {};
  javaObj.nio.charset.StandardCharsets = StandardCharsets;
  javaObj.nio.file = javaObj.nio.file || {
    Paths: {
      get: function(...parts) {
        const raw = parts.filter(Boolean).map(String).join('/');
        return {
          toAbsolutePath: () => ({ toString: () => raw, normalize: () => raw }),
          normalize: () => raw,
          toString: () => raw,
        };
      },
    },
  };

  // java.security
  javaObj.security = javaObj.security || {};
  javaObj.security.MessageDigest = MessageDigest;

  // java.text
  javaObj.text = javaObj.text || {};
  javaObj.text.SimpleDateFormat = SimpleDateFormat;
  javaObj.text.DecimalFormat = DecimalFormat;
  javaObj.text.NumberFormat = {
    getInstance: () => new DecimalFormat('#.##'),
    getCurrencyInstance: () => new DecimalFormat('￥#,##0.00'),
    getPercentInstance: () => new DecimalFormat('#.##%'),
  };

  // java.util
  javaObj.util = javaObj.util || {};
  javaObj.util.Arrays = Arrays;
  javaObj.util.Base64 = JavaUtilBase64;
  javaObj.util.UUID = UUID;
  javaObj.util.ArrayList = ArrayList;
  javaObj.util.HashMap = HashMap;
  javaObj.util.LinkedHashMap = HashMap;
  javaObj.util.ConcurrentHashMap = HashMap;
  javaObj.util.HashSet = HashSet;
  javaObj.util.TreeSet = TreeSet;
  javaObj.util.LinkedList = LinkedList;
  javaObj.util.Stack = Stack;
  javaObj.util.Date = JavaDate;
  javaObj.util.Calendar = Calendar;
  javaObj.util.Collections = {
    sort: (list, comparator) => {
      if (Array.isArray(list)) {
        return typeof comparator === 'function' ? list.sort(comparator) : list.sort();
      }
      if (list && typeof list.sort === 'function') {
        return list.sort(comparator);
      }
      return list;
    },
    reverse: (list) => {
      if (Array.isArray(list)) list.reverse();
      else if (list && typeof list.reverse === 'function') list.reverse();
      return list;
    },
    shuffle: (list) => {
      if (!list) return list;
      const arr = Array.isArray(list) ? list : (list._items || []);
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
      return list;
    },
    emptyList: () => [],
    emptyMap: () => ({}),
    emptySet: () => new Set(),
    singletonList: (item) => [item],
    singletonMap: (k, v) => ({ [k]: v }),
    unmodifiableList: (list) => list,
    unmodifiableMap: (map) => map,
    max: (coll, comparator) => {
      const arr = Array.isArray(coll) ? coll : (coll ? Array.from(coll) : []);
      if (arr.length === 0) return null;
      if (typeof comparator === 'function') {
        return arr.reduce((a, b) => (comparator(a, b) >= 0 ? a : b));
      }
      return arr.reduce((a, b) => (a >= b ? a : b));
    },
    min: (coll, comparator) => {
      const arr = Array.isArray(coll) ? coll : (coll ? Array.from(coll) : []);
      if (arr.length === 0) return null;
      if (typeof comparator === 'function') {
        return arr.reduce((a, b) => (comparator(a, b) <= 0 ? a : b));
      }
      return arr.reduce((a, b) => (a <= b ? a : b));
    },
    addAll: (coll, ...elements) => {
      if (!coll) return false;
      if (Array.isArray(coll)) {
        coll.push(...elements);
        return true;
      }
      if (typeof coll.add === 'function') {
        for (const el of elements) coll.add(el);
        return true;
      }
      return false;
    },
    binarySearch: (list, key, comparator) => {
      const arr = Array.isArray(list) ? list : (list ? Array.from(list) : []);
      let low = 0;
      let high = arr.length - 1;
      while (low <= high) {
        const mid = (low + high) >>> 1;
        const midVal = arr[mid];
        const cmp = typeof comparator === 'function' ? comparator(midVal, key) : (midVal < key ? -1 : (midVal > key ? 1 : 0));
        if (cmp < 0) low = mid + 1;
        else if (cmp > 0) high = mid - 1;
        else return mid;
      }
      return -(low + 1);
    },
    swap: (list, i, j) => {
      const arr = Array.isArray(list) ? list : (list ? list._items : null);
      if (arr && i >= 0 && i < arr.length && j >= 0 && j < arr.length) {
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
    },
    fill: (list, val) => {
      const arr = Array.isArray(list) ? list : (list ? list._items : null);
      if (arr) arr.fill(val);
    },
  };
  javaObj.util.HexFormat = {
    of: () => ({
      parseHex: (hexStr) => Buffer.from(String(hexStr).replace(/\s+/g, ''), 'hex'),
    }),
  };
  javaObj.util.regex = {
    Pattern,
    Matcher,
  };
  javaObj.util.zip = Object.assign(javaObj.util.zip || {}, JavaUtilZip);
  sandbox.java = createSafePackagesProxy(javaObj, 'java');

  // javax.crypto
  const javaxObj = sandbox.javax || {};
  javaxObj.crypto = javaxObj.crypto || {};
  javaxObj.crypto.Cipher = Cipher;
  javaxObj.crypto.Mac = createMacClass();
  javaxObj.crypto.spec = javaxObj.crypto.spec || {};
  javaxObj.crypto.spec.SecretKeySpec = createSecretKeySpecClass();
  javaxObj.crypto.spec.IvParameterSpec = createIvParameterSpecClass();
  javaxObj.crypto.spec.GCMParameterSpec = createGCMParameterSpecClass();
  sandbox.javax = createSafePackagesProxy(javaxObj, 'javax');

  // com / org / androidx 常见反射包兼容
  const comObj = sandbox.com || {};
  comObj.example = comObj.example || {};
  comObj.example.hikerview = comObj.example.hikerview || {};
  comObj.example.hikerview.utils = Object.assign(comObj.example.hikerview.utils || {}, HikerviewUtils);
  comObj.example.hikerview.ui = comObj.example.hikerview.ui || {
    ActivityManager: {
      getInstance: () => ({
        getCurrentActivity: () => (typeof sandbox.getCurrentActivity === 'function' ? sandbox.getCurrentActivity() : {}),
      }),
    },
  };
  comObj.example.hikerview.R = comObj.example.hikerview.R || {
    drawable: {},
    id: {},
    layout: {},
  };
  comObj.alibaba = comObj.alibaba || {
    fastjson: {
      JSON: {
        parseObject: (str) => JSON.parse(str || '{}'),
        parseArray: (str) => JSON.parse(str || '[]'),
        toJSONString: (obj) => JSON.stringify(obj),
      },
    },
  };
  comObj.lxj = comObj.lxj || {
    xpopup: {
      XPopup: {
        Builder: function() {
          return createSafePackagesProxy({}, 'XPopup.Builder');
        },
      },
    },
  };
  sandbox.com = createSafePackagesProxy(comObj, 'com');

  const orgObj = sandbox.org || {};
  orgObj.mozilla = orgObj.mozilla || {
    javascript: {
      Context: {
        getCurrentContext: () => ({
          getLanguageVersion: () => 200,
        }),
      },
    },
  };
  orgObj.json = {
    JSONObject,
    JSONArray,
  };
  orgObj.jsoup = orgObj.jsoup || {
    Jsoup: {
      parse: (html) => ({
        text: () => String(html || '').replace(/<[^>]+>/g, ''),
        html: () => String(html || ''),
      }),
    },
  };
  sandbox.org = createSafePackagesProxy(orgObj, 'org');

  sandbox.androidx = createSafePackagesProxy(sandbox.androidx || {}, 'androidx');

  // 海阔原生 _globalMap (java.util.HashMap 实例，供 globalmap.js / GM 插件使用)
  sandbox._globalMap = sandbox._globalMap || new HashMap();

  // Packages 安全代理
  sandbox.Packages = createSafePackagesProxy({
    android: sandbox.android,
    java: sandbox.java,
    javax: sandbox.javax,
    com: sandbox.com,
    org: sandbox.org,
    androidx: sandbox.androidx,
  }, 'Packages');

  // 沙箱顶层无前缀全局自动注入常用类
  const topClasses = {
    JSONObject,
    JSONArray,
    File: JavaFile,
    HashMap,
    ArrayList,
    HashSet,
    TreeSet,
    LinkedList,
    Stack,
    StandardCharsets,
    Pattern,
    Matcher,
    Uri: AndroidNetUri,
    URLEncoder: javaObj.net.URLEncoder,
    URLDecoder: javaObj.net.URLDecoder,
    SimpleDateFormat,
    DecimalFormat,
    Calendar,
    BigDecimal,
    BigInteger,
    Collections: javaObj.util.Collections,
    Arrays,
    StringBuilder,
    StringBuffer: StringBuilder,
    Cipher,
    MessageDigest,
    UUID,
  };
  for (const [key, cls] of Object.entries(topClasses)) {
    if (typeof sandbox[key] === 'undefined') {
      sandbox[key] = cls;
    }
    if (sandbox.global && typeof sandbox.global[key] === 'undefined') {
      sandbox.global[key] = cls;
    }
  }

  // 规则辅助函数与算法垫片
  const helpers = createRuleHelpers(sandbox, hostAdapter);
  for (const [key, fn] of Object.entries(helpers)) {
    if (typeof sandbox[key] === 'undefined') {
      sandbox[key] = fn;
    }
    if (sandbox.global && typeof sandbox.global[key] === 'undefined') {
      sandbox.global[key] = fn;
    }
  }

  return sandbox;
}

module.exports = {
  createAndroidBase64,
  createJavaUtilBase64,
  JavaImporter,
  createSafePackagesProxy,
  createSafeStub,
  createJavaStringClass,
  createArraysClass,
  createCipherClass,
  createSecretKeySpecClass,
  createGCMParameterSpecClass,
  createIvParameterSpecClass,
  createMessageDigestClass,
  createMacClass,
  createUUIDClass,
  createBigIntegerClass,
  createSimpleDateFormatClass,
  createArrayListClass,
  createHashMapClass,
  createJSONObjectClass,
  createJSONArrayClass,
  createByteArrayInputStreamClass,
  createByteArrayOutputStreamClass,
  createJavaFileClass,
  createStringBuilderClass,
  createAndroidGraphicsShims,
  createAndroidOsShims,
  createJavaUtilZipShims,
  createAndroidNetUriClass,
  createJavaRegexShims,
  createBigDecimalClass,
  createDecimalFormatClass,
  createJavaDateAndCalendarShims,
  createJavaSetClasses,
  createJavaExtraCollectionsShims,
  createComHikerviewUtilsShims,
  StandardCharsets,
  CryptoUtil,
  levenshteinDistance,
  similarity,
  sortByPinyin,
  dateFormat,
  createRuleHelpers,
  attachCryptoAndCodecBuiltins,
};

