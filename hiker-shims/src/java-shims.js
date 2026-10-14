/**
 * Java 标准库与 JCE (javax.crypto) 兼容垫片实现
 */

const crypto = require('crypto');

function JavaImporter(...packages) {
  if (!(this instanceof JavaImporter)) {
    return new JavaImporter(...packages);
  }
  this.importPackage = (...pkgs) => {
    for (const pkg of pkgs) {
      if (pkg && typeof pkg === 'object') {
        Object.assign(this, pkg);
      }
    }
    return this;
  };
  if (packages.length > 0) {
    this.importPackage(...packages);
  }
}

function createSafeStub(name = 'Stub') {
  const stubTarget = function(...args) {
    return createSafeStub(`${name}()`);
  };
  stubTarget.toString = () => '';
  stubTarget.valueOf = () => 0;
  stubTarget[Symbol.toPrimitive] = (hint) => (hint === 'number' ? 0 : '');

  const stubHandler = {
    get(target, prop, receiver) {
      if (prop === 'then') return undefined; // 极重要：防止 Promise / await 将其误判为 thenable 导致卡死
      if (typeof prop === 'symbol') {
        if (prop === Symbol.toPrimitive) return (hint) => (hint === 'number' ? 0 : '');
        if (prop === Symbol.iterator) return function* () {};
        if (prop === Symbol.toStringTag) return 'SafeStub';
        return Reflect.get(target, prop, receiver);
      }
      if (prop === 'toString' || prop === 'valueOf') {
        return () => '';
      }
      if (prop === 'toJSON') {
        return () => null;
      }
      if (prop === 'length' || prop === 'size') {
        const numFn = function() { return 0; };
        numFn[Symbol.toPrimitive] = () => 0;
        numFn.valueOf = () => 0;
        numFn.toString = () => '0';
        return numFn;
      }
      if (prop === 'isEmpty') {
        const boolFn = function() { return true; };
        boolFn[Symbol.toPrimitive] = () => 1;
        boolFn.valueOf = () => true;
        return boolFn;
      }
      if (prop === 'optString' || prop === 'getString') {
        return (k, def = '') => def;
      }
      if (prop === 'optInt' || prop === 'getInt' || prop === 'optLong' || prop === 'getLong') {
        return (k, def = 0) => def;
      }
      if (prop === 'optBoolean' || prop === 'getBoolean') {
        return (k, def = false) => def;
      }
      if (prop === 'optDouble' || prop === 'getDouble') {
        return (k, def = 0.0) => def;
      }
      if (prop === 'optJSONObject' || prop === 'getJSONObject' || prop === 'optJSONArray' || prop === 'getJSONArray') {
        return () => null;
      }
      if (prop === 'has') {
        return () => false;
      }
      if (prop === 'iterator') {
        return () => ({
          hasNext: () => false,
          next: () => null,
        });
      }
      if (prop === 'toArray') {
        return () => [];
      }
      if (prop === 'put' || prop === 'append' || prop === 'add') {
        return function() { return receiver; };
      }
      // 链式调用：默认返回新的 safe stub
      return createSafeStub(`${name}.${String(prop)}`);
    },
    apply(target, thisArg, argArray) {
      // 当作为函数调用时，返回新的 safe stub，允许继续链式调用 a().b().c()
      return createSafeStub(`${name}()`);
    },
    construct(target, argArray) {
      // 当作为构造函数 new Class() 调用时，返回新的 safe stub
      return createSafeStub(`new ${name}()`);
    }
  };

  return new Proxy(stubTarget, stubHandler);
}

function createSafePackagesProxy(rootTarget, namespaceName = 'Packages') {
  if (rootTarget === null || (typeof rootTarget !== 'object' && typeof rootTarget !== 'function')) {
    return rootTarget;
  }
  const handler = {
    get(target, prop, receiver) {
      if (prop === 'then') return undefined;
      if (typeof prop === 'symbol' || prop === 'inspect') {
        return Reflect.get(target, prop, receiver);
      }
      if (prop in target) {
        const val = target[prop];
        if (val !== null && typeof val === 'object' && !Array.isArray(val) && !(val instanceof Buffer) && !(val instanceof Uint8Array)) {
          return createSafePackagesProxy(val, `${namespaceName}.${String(prop)}`);
        }
        return val;
      }
      // 如果目标对象中不存在该属性，返回万能自适应 safeStub
      return createSafeStub(`${namespaceName}.${String(prop)}`);
    },
    apply(targetFn, thisArg, argArray) {
      if (typeof targetFn === 'function') {
        return Reflect.apply(targetFn, thisArg, argArray);
      }
      return createSafeStub(`${namespaceName}()`);
    },
    construct(targetFn, argArray) {
      if (typeof targetFn === 'function') {
        return Reflect.construct(targetFn, argArray);
      }
      return createSafeStub(`new ${namespaceName}()`);
    }
  };
  return new Proxy(rootTarget, handler);
}


function createJavaStringClass() {
  function JavaString(val, charset) {
    if (!new.target) {
      return new JavaString(val, charset);
    }
    let str = '';
    if (Buffer.isBuffer(val)) {
      const enc = charset ? String(charset).toLowerCase().replace(/[-_]/g, '') : 'utf8';
      try {
        str = val.toString(enc);
      } catch (_) {
        str = val.toString('utf8');
      }
    } else if (val instanceof Uint8Array || Array.isArray(val)) {
      str = Buffer.from(val).toString(charset ? String(charset).toLowerCase().replace(/[-_]/g, '') : 'utf8');
    } else {
      str = String(val ?? '');
    }
    this._str = str;

    const lenFn = () => this._str.length;
    lenFn[Symbol.toPrimitive] = () => this._str.length;
    lenFn.valueOf = () => this._str.length;
    this.length = lenFn;
  }

  JavaString.prototype.toString = function() { return this._str; };
  JavaString.prototype.valueOf = function() { return this._str; };
  JavaString.prototype[Symbol.toPrimitive] = function() { return this._str; };

  JavaString.prototype.getBytes = function(charset) {
    const enc = charset ? String(charset).toLowerCase().replace(/[-_]/g, '') : 'utf8';
    try {
      return Buffer.from(this._str, enc);
    } catch (_) {
      return Buffer.from(this._str, 'utf8');
    }
  };

  JavaString.prototype.replaceAll = function(pattern, replacement) {
    return new JavaString(this._str.replace(new RegExp(pattern, 'g'), replacement));
  };

  JavaString.prototype.replace = function(pattern, replacement) {
    return new JavaString(this._str.replace(pattern, replacement));
  };

  JavaString.prototype.substring = function(start, end) {
    return new JavaString(this._str.substring(start, end));
  };

  JavaString.prototype.charAt = function(index) {
    return this._str.charAt(index);
  };

  JavaString.prototype.indexOf = function(search, fromIndex) {
    return this._str.indexOf(search, fromIndex);
  };

  JavaString.prototype.toLowerCase = function() {
    return new JavaString(this._str.toLowerCase());
  };

  JavaString.prototype.toUpperCase = function() {
    return new JavaString(this._str.toUpperCase());
  };

  JavaString.prototype.trim = function() {
    return new JavaString(this._str.trim());
  };

  JavaString.prototype.split = function(separator) {
    return this._str.split(separator).map(s => new JavaString(s));
  };

  JavaString.prototype.startsWith = function(prefix) {
    return this._str.startsWith(prefix);
  };

  JavaString.prototype.endsWith = function(suffix) {
    return this._str.endsWith(suffix);
  };

  JavaString.prototype.contains = function(sub) {
    return this._str.includes(sub);
  };

  JavaString.prototype.equals = function(other) {
    return this._str === String(other ?? '');
  };

  JavaString.prototype.equalsIgnoreCase = function(other) {
    return this._str.toLowerCase() === String(other ?? '').toLowerCase();
  };

  JavaString.prototype.isEmpty = function() {
    return this._str.length === 0;
  };

  return JavaString;
}

if (typeof String.prototype.getBytes !== 'function') {
  String.prototype.getBytes = function(charset) {
    const enc = charset ? String(charset).toLowerCase().replace(/[-_]/g, '') : 'utf8';
    try {
      return Buffer.from(this, enc);
    } catch (_) {
      return Buffer.from(this, 'utf8');
    }
  };
}

function resolveNodeCipherAlgo(transformation, keyLen) {
  const parts = String(transformation || 'AES/CBC/PKCS7Padding').split('/');
  const algo = (parts[0] || 'AES').toUpperCase();
  const mode = (parts[1] || 'CBC').toUpperCase();
  if (algo === 'AES') {
    let bits = 128;
    if (keyLen >= 32) bits = 256;
    else if (keyLen >= 24) bits = 192;
    if (mode === 'ECB') return `aes-${bits}-ecb`;
    if (mode === 'CTR') return `aes-${bits}-ctr`;
    if (mode === 'GCM') return `aes-${bits}-gcm`;
    if (mode === 'CFB') return `aes-${bits}-cfb`;
    if (mode === 'OFB') return `aes-${bits}-ofb`;
    return `aes-${bits}-cbc`;
  }
  if (algo === 'DES') {
    if (mode === 'ECB') return 'des-ecb';
    return 'des-cbc';
  }
  if (algo === 'DESEDE' || algo === 'TRIPLEDES') {
    if (mode === 'ECB') return 'des-ede3';
    return 'des-ede3-cbc';
  }
  return 'aes-128-cbc';
}

function createArraysClass() {
  return {
    copyOfRange: function(original, from, to) {
      if (!original) return Buffer.alloc(0);
      const buf = Buffer.isBuffer(original) ? original : (original instanceof Uint8Array || Array.isArray(original) ? Buffer.from(original) : Buffer.from(String(original), 'utf8'));
      const start = Math.max(0, from || 0);
      const end = Math.min(buf.length, to !== undefined ? to : buf.length);
      if (start >= end) return Buffer.alloc(0);
      return Buffer.from(buf.subarray(start, end));
    },
    copyOf: function(original, newLength) {
      if (!original) return Buffer.alloc(newLength || 0);
      const buf = Buffer.isBuffer(original) ? original : (original instanceof Uint8Array || Array.isArray(original) ? Buffer.from(original) : Buffer.from(String(original), 'utf8'));
      const len = Math.max(0, newLength || 0);
      const res = Buffer.alloc(len);
      buf.copy(res, 0, 0, Math.min(buf.length, len));
      return res;
    },
    equals: function(a, b) {
      if (a === b) return true;
      if (!a || !b) return false;
      const bufA = Buffer.isBuffer(a) ? a : (a instanceof Uint8Array || Array.isArray(a) ? Buffer.from(a) : Buffer.from(String(a)));
      const bufB = Buffer.isBuffer(b) ? b : (b instanceof Uint8Array || Array.isArray(b) ? Buffer.from(b) : Buffer.from(String(b)));
      return bufA.equals(bufB);
    },
    fill: function(a, val) {
      if (!a) return a;
      if (Buffer.isBuffer(a) || a instanceof Uint8Array) {
        a.fill(val);
      } else if (Array.isArray(a)) {
        a.fill(val);
      }
      return a;
    },
    toString: function(a) {
      if (a === null || a === undefined) return 'null';
      if (Buffer.isBuffer(a) || a instanceof Uint8Array || Array.isArray(a)) {
        return '[' + Array.from(a).join(', ') + ']';
      }
      return String(a);
    },
    sort: function(a) {
      if (Array.isArray(a)) return a.sort();
      if (Buffer.isBuffer(a) || a instanceof Uint8Array) return a.sort();
      return a;
    },
    asList: function(...items) {
      return Array.isArray(items[0]) ? items[0] : items;
    }
  };
}

function createCipherClass() {
  function CipherInstance(transformation) {
    this.transformation = transformation || 'AES/CBC/PKCS5Padding';
    this.opmode = 2; // DECRYPT_MODE
    this.key = null;
    this.iv = null;
    this.tLen = 128;
    this.aad = null;
    this.cipher = null;
  }

  CipherInstance.prototype.init = function(opmode, keySpec, paramSpec) {
    this.opmode = opmode;
    this.key = keySpec ? (keySpec.getEncoded ? keySpec.getEncoded() : (Buffer.isBuffer(keySpec) ? keySpec : Buffer.from(keySpec))) : Buffer.alloc(16);
    this.iv = Buffer.alloc(0);
    this.tLen = 128;
    this.aad = null;
    if (paramSpec) {
      if (paramSpec.getIV) {
        this.iv = paramSpec.getIV();
      } else if (Buffer.isBuffer(paramSpec)) {
        this.iv = paramSpec;
      }
      if (paramSpec.getTLen) {
        this.tLen = paramSpec.getTLen();
      }
    }
    const nodeAlgo = resolveNodeCipherAlgo(this.transformation, this.key.length);
    this.nodeAlgo = nodeAlgo;
    this.isGcm = nodeAlgo.includes('gcm');
  };

  CipherInstance.prototype.updateAAD = function(src) {
    if (!src) return;
    const buf = Buffer.isBuffer(src) ? src : Buffer.from(src);
    this.aad = this.aad ? Buffer.concat([this.aad, buf]) : buf;
  };

  CipherInstance.prototype.update = function(input) {
    if (input === undefined || input === null) return Buffer.alloc(0);
    const buf = Buffer.isBuffer(input) ? input : (input instanceof Uint8Array || Array.isArray(input) ? Buffer.from(input) : Buffer.from(String(input), 'utf8'));
    return buf;
  };

  CipherInstance.prototype.doFinal = function(input) {
    let inputBuf = input !== undefined && input !== null ? (Buffer.isBuffer(input) ? input : (input instanceof Uint8Array || Array.isArray(input) ? Buffer.from(input) : Buffer.from(String(input), 'utf8'))) : Buffer.alloc(0);
    const isEncrypt = this.opmode === 1;

    try {
      if (isEncrypt) {
        const cipher = crypto.createCipheriv(this.nodeAlgo, this.key, this.iv.length > 0 ? this.iv : null);
        if (this.isGcm && this.aad) {
          cipher.setAAD(this.aad);
        }
        const output = Buffer.concat([cipher.update(inputBuf), cipher.final()]);
        if (this.isGcm) {
          const authTag = cipher.getAuthTag();
          return Buffer.concat([output, authTag]);
        }
        return output;
      } else {
        const decipher = crypto.createDecipheriv(this.nodeAlgo, this.key, this.iv.length > 0 ? this.iv : null);
        decipher.setAutoPadding(true);
        if (this.isGcm) {
          const tagBytes = Math.floor(this.tLen / 8) || 16;
          if (inputBuf.length >= tagBytes) {
            const cipherText = inputBuf.subarray(0, inputBuf.length - tagBytes);
            const authTag = inputBuf.subarray(inputBuf.length - tagBytes);
            decipher.setAuthTag(authTag);
            if (this.aad) decipher.setAAD(this.aad);
            return Buffer.concat([decipher.update(cipherText), decipher.final()]);
          }
        }
        if (this.transformation && this.transformation.includes('NoPadding')) {
          decipher.setAutoPadding(false);
        }
        return Buffer.concat([decipher.update(inputBuf), decipher.final()]);
      }
    } catch (err) {
      if (!isEncrypt && this.transformation && !this.transformation.includes('NoPadding')) {
        try {
          const fallback = crypto.createDecipheriv(this.nodeAlgo, this.key, this.iv.length > 0 ? this.iv : null);
          fallback.setAutoPadding(false);
          let res = Buffer.concat([fallback.update(inputBuf), fallback.final()]);
          if (res.length > 0) {
            const padLen = res[res.length - 1];
            if (padLen > 0 && padLen <= 16) {
              let validPad = true;
              for (let i = res.length - padLen; i < res.length; i++) {
                if (res[i] !== padLen) { validPad = false; break; }
              }
              if (validPad) res = res.subarray(0, res.length - padLen);
            }
          }
          return res;
        } catch (_) {}
      }
      throw err;
    }
  };

  return {
    ENCRYPT_MODE: 1,
    DECRYPT_MODE: 2,
    WRAP_MODE: 3,
    UNWRAP_MODE: 4,
    getInstance: (transformation) => new CipherInstance(transformation)
  };
}

function createSecretKeySpecClass() {
  function SecretKeySpec(key, algorithm) {
    if (!(this instanceof SecretKeySpec)) {
      return new SecretKeySpec(key, algorithm);
    }
    this.key = Buffer.isBuffer(key) ? key : (key instanceof Uint8Array || Array.isArray(key) ? Buffer.from(key) : Buffer.from(String(key || ''), 'utf8'));
    this.algorithm = algorithm || 'AES';
  }
  SecretKeySpec.prototype.getAlgorithm = function() { return this.algorithm; };
  SecretKeySpec.prototype.getEncoded = function() { return this.key; };
  SecretKeySpec.prototype.getFormat = function() { return 'RAW'; };
  return SecretKeySpec;
}

function createGCMParameterSpecClass() {
  function GCMParameterSpec(tLen, src, offset, byteCount) {
    if (!(this instanceof GCMParameterSpec)) {
      return new GCMParameterSpec(tLen, src, offset, byteCount);
    }
    this.tLen = tLen || 128;
    const buf = Buffer.isBuffer(src) ? src : (src instanceof Uint8Array || Array.isArray(src) ? Buffer.from(src) : Buffer.from(String(src || '')));
    const off = offset || 0;
    const len = byteCount !== undefined ? byteCount : buf.length - off;
    this.iv = buf.subarray(off, off + len);
  }
  GCMParameterSpec.prototype.getTLen = function() { return this.tLen; };
  GCMParameterSpec.prototype.getIV = function() { return this.iv; };
  return GCMParameterSpec;
}

function createIvParameterSpecClass() {
  function IvParameterSpec(iv, offset, byteCount) {
    if (!(this instanceof IvParameterSpec)) {
      return new IvParameterSpec(iv, offset, byteCount);
    }
    const buf = Buffer.isBuffer(iv) ? iv : (iv instanceof Uint8Array || Array.isArray(iv) ? Buffer.from(iv) : Buffer.from(String(iv || '')));
    const off = offset || 0;
    const len = byteCount !== undefined ? byteCount : buf.length - off;
    this.iv = buf.subarray(off, off + len);
  }
  IvParameterSpec.prototype.getIV = function() { return this.iv; };
  return IvParameterSpec;
}

function createMessageDigestClass() {
  function MessageDigest(algo) {
    this.algo = String(algo || 'MD5').toLowerCase().replace('-', '');
    this.hasher = crypto.createHash(this.algo === 'sha1' ? 'sha1' : (this.algo.includes('256') ? 'sha256' : 'md5'));
  }
  MessageDigest.prototype.update = function(input) {
    const buf = Buffer.isBuffer(input) ? input : Buffer.from(String(input || ''), 'utf8');
    this.hasher.update(buf);
  };
  MessageDigest.prototype.digest = function(input) {
    if (input) this.update(input);
    return this.hasher.digest();
  };
  MessageDigest.prototype.reset = function() {
    this.hasher = crypto.createHash(this.algo === 'sha1' ? 'sha1' : (this.algo.includes('256') ? 'sha256' : 'md5'));
  };
  return {
    getInstance: (algo) => new MessageDigest(algo)
  };
}

function createMacClass() {
  function Mac(algo) {
    this.algo = String(algo || 'HmacSHA256').toLowerCase().replace('hmac', '');
    this.key = null;
    this.hmac = null;
  }
  Mac.prototype.init = function(keySpec) {
    this.key = keySpec ? (keySpec.getEncoded ? keySpec.getEncoded() : Buffer.from(keySpec)) : Buffer.alloc(0);
    const nodeAlgo = this.algo.includes('256') ? 'sha256' : (this.algo.includes('1') ? 'sha1' : 'md5');
    this.hmac = crypto.createHmac(nodeAlgo, this.key);
  };
  Mac.prototype.update = function(input) {
    if (this.hmac && input) {
      const buf = Buffer.isBuffer(input) ? input : Buffer.from(String(input), 'utf8');
      this.hmac.update(buf);
    }
  };
  Mac.prototype.doFinal = function(input) {
    if (input) this.update(input);
    return this.hmac ? this.hmac.digest() : Buffer.alloc(0);
  };
  return {
    getInstance: (algo) => new Mac(algo)
  };
}

function createUUIDClass() {
  return {
    randomUUID: () => ({
      toString: () => crypto.randomUUID()
    })
  };
}

function createBigIntegerClass() {
  function BigInteger(val, radix = 10) {
    if (!(this instanceof BigInteger)) return new BigInteger(val, radix);
    if (typeof val === 'string') {
      if (radix === 16) {
        this.val = BigInt('0x' + val);
      } else {
        this.val = BigInt(val);
      }
    } else if (typeof val === 'number' || typeof val === 'bigint') {
      this.val = BigInt(val);
    } else if (Buffer.isBuffer(val)) {
      this.val = BigInt('0x' + val.toString('hex'));
    } else {
      this.val = 0n;
    }
  }
  BigInteger.prototype.toString = function(radix = 10) { return this.val.toString(radix); };
  BigInteger.prototype.toByteArray = function() {
    let hex = this.val.toString(16);
    if (hex.length % 2 !== 0) hex = '0' + hex;
    return Buffer.from(hex, 'hex');
  };
  return BigInteger;
}

function createSimpleDateFormatClass() {
  function SimpleDateFormat(pattern) {
    this.pattern = pattern || 'yyyy-MM-dd HH:mm:ss';
  }
  SimpleDateFormat.prototype.format = function(dateInput) {
    const d = dateInput instanceof Date ? dateInput : new Date(Number(dateInput) || Date.now());
    const pad = (n, len = 2) => String(n).padStart(len, '0');
    return this.pattern
      .replace('yyyy', String(d.getFullYear()))
      .replace('MM', pad(d.getMonth() + 1))
      .replace('dd', pad(d.getDate()))
      .replace('HH', pad(d.getHours()))
      .replace('mm', pad(d.getMinutes()))
      .replace('ss', pad(d.getSeconds()))
      .replace('SSS', pad(d.getMilliseconds(), 3));
  };
  SimpleDateFormat.prototype.parse = function(dateStr) {
    return new Date(dateStr);
  };
  return SimpleDateFormat;
}

function createArrayListClass() {
  function ArrayList(initial) {
    if (!(this instanceof ArrayList)) return new ArrayList(initial);
    this._items = Array.isArray(initial) ? [...initial] : [];
  }
  ArrayList.prototype.add = function(item) { this._items.push(item); return true; };
  ArrayList.prototype.get = function(i) { return this._items[i]; };
  ArrayList.prototype.size = function() { return this._items.length; };
  ArrayList.prototype.isEmpty = function() { return this._items.length === 0; };
  ArrayList.prototype.clear = function() { this._items = []; };
  ArrayList.prototype.toArray = function() { return [...this._items]; };
  ArrayList.prototype.iterator = function() {
    let idx = 0;
    const items = this._items;
    return {
      hasNext: () => idx < items.length,
      next: () => items[idx++],
    };
  };
  ArrayList.prototype[Symbol.iterator] = function* () { yield* this._items; };
  return ArrayList;
}

function createHashMapClass() {
  function MapEntry(k, v) {
    this.key = k;
    this.value = v;
  }
  MapEntry.prototype.getKey = function() { return this.key; };
  MapEntry.prototype.getValue = function() { return this.value; };

  function HashMap(initial) {
    if (!(this instanceof HashMap)) return new HashMap(initial);
    this._map = new Map();
    if (initial && typeof initial === 'object') {
      if (initial instanceof HashMap) {
        for (const [k, v] of initial._map.entries()) {
          this._map.set(k, v);
        }
      } else if (typeof initial.forEach === 'function') {
        initial.forEach((v, k) => this._map.set(k, v));
      } else {
        for (const k of Object.keys(initial)) {
          this._map.set(k, initial[k]);
        }
      }
    }
  }
  HashMap.prototype.put = function(k, v) { this._map.set(k, v); return v; };
  HashMap.prototype.get = function(k) { return this._map.get(k); };
  HashMap.prototype.remove = function(k) {
    const val = this._map.get(k);
    this._map.delete(k);
    return val !== undefined ? val : null;
  };
  HashMap.prototype.containsKey = function(k) { return this._map.has(k); };
  HashMap.prototype.containsValue = function(v) {
    for (const val of this._map.values()) {
      if (val === v) return true;
    }
    return false;
  };
  HashMap.prototype.size = function() { return this._map.size; };
  HashMap.prototype.isEmpty = function() { return this._map.size === 0; };
  HashMap.prototype.keySet = function() {
    const keys = Array.from(this._map.keys());
    keys.iterator = function() {
      let idx = 0;
      return {
        hasNext: () => idx < keys.length,
        next: () => keys[idx++],
      };
    };
    return keys;
  };
  HashMap.prototype.values = function() { return Array.from(this._map.values()); };
  HashMap.prototype.entrySet = function() {
    const entries = [];
    for (const [k, v] of this._map.entries()) {
      entries.push(new MapEntry(k, v));
    }
    entries.iterator = function() {
      let idx = 0;
      return {
        hasNext: () => idx < entries.length,
        next: () => entries[idx++],
      };
    };
    return entries;
  };
  HashMap.prototype.forEach = function(cb) {
    if (typeof cb === 'function') {
      for (const [k, v] of this._map.entries()) {
        cb(k, v);
      }
    }
  };
  HashMap.prototype.putAll = function(other) {
    if (!other) return;
    if (other instanceof HashMap) {
      for (const [k, v] of other._map.entries()) {
        this._map.set(k, v);
      }
    } else if (typeof other === 'object') {
      for (const k of Object.keys(other)) {
        this._map.set(k, other[k]);
      }
    }
  };
  HashMap.prototype.clear = function() { this._map.clear(); };
  HashMap.prototype[Symbol.iterator] = function* () {
    for (const [k, v] of this._map.entries()) {
      yield new MapEntry(k, v);
    }
  };
  return HashMap;
}

function createJSONObjectClass() {
  function JSONObject(arg) {
    if (!(this instanceof JSONObject)) return new JSONObject(arg);
    if (typeof arg === 'string') {
      try {
        this._obj = JSON.parse(arg || '{}');
      } catch (_) {
        this._obj = {};
      }
    } else if (arg && typeof arg === 'object') {
      if (arg instanceof JSONObject) {
        this._obj = { ...arg._obj };
      } else if (typeof arg.forEach === 'function' && !Array.isArray(arg)) {
        this._obj = {};
        arg.forEach((v, k) => { this._obj[k] = v; });
      } else {
        this._obj = { ...arg };
      }
    } else {
      this._obj = {};
    }
  }

  JSONObject.prototype.optString = function(key, def = '') {
    return this._obj[key] !== undefined && this._obj[key] !== null ? String(this._obj[key]) : def;
  };
  JSONObject.prototype.getString = function(key) {
    if (this._obj[key] === undefined) throw new Error(`JSONObject["${key}"] not found.`);
    return String(this._obj[key]);
  };
  JSONObject.prototype.optInt = function(key, def = 0) {
    if (this._obj[key] === undefined || this._obj[key] === null) return def;
    const n = parseInt(this._obj[key], 10);
    return isNaN(n) ? def : n;
  };
  JSONObject.prototype.getInt = function(key) {
    const n = parseInt(this._obj[key], 10);
    if (isNaN(n)) throw new Error(`JSONObject["${key}"] is not an int.`);
    return n;
  };
  JSONObject.prototype.optLong = function(key, def = 0) {
    return this.optInt(key, def);
  };
  JSONObject.prototype.getLong = function(key) {
    return this.getInt(key);
  };
  JSONObject.prototype.optDouble = function(key, def = 0.0) {
    if (this._obj[key] === undefined || this._obj[key] === null) return def;
    const n = parseFloat(this._obj[key]);
    return isNaN(n) ? def : n;
  };
  JSONObject.prototype.getDouble = function(key) {
    const n = parseFloat(this._obj[key]);
    if (isNaN(n)) throw new Error(`JSONObject["${key}"] is not a double.`);
    return n;
  };
  JSONObject.prototype.optBoolean = function(key, def = false) {
    if (this._obj[key] === undefined || this._obj[key] === null) return def;
    return Boolean(this._obj[key]);
  };
  JSONObject.prototype.getBoolean = function(key) {
    if (this._obj[key] === undefined) throw new Error(`JSONObject["${key}"] not found.`);
    return Boolean(this._obj[key]);
  };
  JSONObject.prototype.optJSONObject = function(key) {
    const v = this._obj[key];
    return v && typeof v === 'object' && !Array.isArray(v) ? new JSONObject(v) : null;
  };
  JSONObject.prototype.getJSONObject = function(key) {
    const v = this.optJSONObject(key);
    if (!v) throw new Error(`JSONObject["${key}"] is not a JSONObject.`);
    return v;
  };
  JSONObject.prototype.optJSONArray = function(key) {
    const v = this._obj[key];
    return Array.isArray(v) ? new (createJSONArrayClass())(v) : null;
  };
  JSONObject.prototype.getJSONArray = function(key) {
    const v = this.optJSONArray(key);
    if (!v) throw new Error(`JSONObject["${key}"] is not a JSONArray.`);
    return v;
  };
  JSONObject.prototype.has = function(key) {
    return key in this._obj;
  };
  JSONObject.prototype.isNull = function(key) {
    return this._obj[key] === null || this._obj[key] === undefined;
  };
  JSONObject.prototype.put = function(k, v) {
    if (v instanceof JSONObject) this._obj[k] = v._obj;
    else if (v && v._arr) this._obj[k] = v._arr;
    else this._obj[k] = v;
    return this;
  };
  JSONObject.prototype.remove = function(k) {
    const val = this._obj[k];
    delete this._obj[k];
    return val !== undefined ? val : null;
  };
  JSONObject.prototype.length = function() {
    return Object.keys(this._obj).length;
  };
  JSONObject.prototype.keys = function() {
    const keyList = Object.keys(this._obj);
    let idx = 0;
    return {
      hasNext: () => idx < keyList.length,
      next: () => keyList[idx++],
    };
  };
  JSONObject.prototype.keySet = function() {
    return new Set(Object.keys(this._obj));
  };
  JSONObject.prototype.names = function() {
    return new (createJSONArrayClass())(Object.keys(this._obj));
  };
  JSONObject.prototype.toString = function(indentFactor) {
    return indentFactor ? JSON.stringify(this._obj, null, indentFactor) : JSON.stringify(this._obj);
  };
  return JSONObject;
}

function createJSONArrayClass() {
  function JSONArray(arg) {
    if (!(this instanceof JSONArray)) return new JSONArray(arg);
    if (typeof arg === 'string') {
      try {
        this._arr = JSON.parse(arg || '[]');
      } catch (_) {
        this._arr = [];
      }
    } else if (Array.isArray(arg)) {
      this._arr = [...arg];
    } else if (arg && typeof arg.toArray === 'function') {
      this._arr = arg.toArray();
    } else {
      this._arr = [];
    }
  }

  JSONArray.prototype.length = function() { return this._arr.length; };
  JSONArray.prototype.get = function(i) { return this._arr[i]; };
  JSONArray.prototype.getJSONObject = function(i) {
    return new (createJSONObjectClass())(this._arr[i]);
  };
  JSONArray.prototype.optJSONObject = function(i) {
    const item = this._arr[i];
    return item && typeof item === 'object' && !Array.isArray(item) ? new (createJSONObjectClass())(item) : null;
  };
  JSONArray.prototype.getJSONArray = function(i) {
    return new JSONArray(this._arr[i]);
  };
  JSONArray.prototype.optJSONArray = function(i) {
    const item = this._arr[i];
    return Array.isArray(item) ? new JSONArray(item) : null;
  };
  JSONArray.prototype.getString = function(i) { return String(this._arr[i] ?? ''); };
  JSONArray.prototype.optString = function(i, def = '') {
    return this._arr[i] !== undefined && this._arr[i] !== null ? String(this._arr[i]) : def;
  };
  JSONArray.prototype.getInt = function(i) { return parseInt(this._arr[i], 10); };
  JSONArray.prototype.optInt = function(i, def = 0) {
    const n = parseInt(this._arr[i], 10);
    return isNaN(n) ? def : n;
  };
  JSONArray.prototype.getDouble = function(i) { return parseFloat(this._arr[i]); };
  JSONArray.prototype.optDouble = function(i, def = 0.0) {
    const n = parseFloat(this._arr[i]);
    return isNaN(n) ? def : n;
  };
  JSONArray.prototype.getBoolean = function(i) { return Boolean(this._arr[i]); };
  JSONArray.prototype.optBoolean = function(i, def = false) {
    return this._arr[i] !== undefined ? Boolean(this._arr[i]) : def;
  };
  JSONArray.prototype.put = function(item) {
    if (item && item._obj) this._arr.push(item._obj);
    else if (item && item._arr) this._arr.push(item._arr);
    else this._arr.push(item);
    return this;
  };
  JSONArray.prototype.remove = function(i) {
    return this._arr.splice(i, 1)[0];
  };
  JSONArray.prototype.isNull = function(i) {
    return this._arr[i] === null || this._arr[i] === undefined;
  };
  JSONArray.prototype.toString = function(indentFactor) {
    return indentFactor ? JSON.stringify(this._arr, null, indentFactor) : JSON.stringify(this._arr);
  };
  return JSONArray;
}

function createByteArrayInputStreamClass() {
  function ByteArrayInputStream(buf, off = 0, len) {
    const b = Buffer.isBuffer(buf) ? buf : (buf instanceof Uint8Array || Array.isArray(buf) ? Buffer.from(buf) : Buffer.from(String(buf || '')));
    this._buf = b.subarray(off, len !== undefined ? off + len : b.length);
    this._pos = 0;
  }
  ByteArrayInputStream.prototype.read = function(b, off = 0, len) {
    if (this._pos >= this._buf.length) return -1;
    if (!b) return this._buf[this._pos++];
    const toRead = Math.min(len !== undefined ? len : b.length - off, this._buf.length - this._pos);
    this._buf.copy(b, off, this._pos, this._pos + toRead);
    this._pos += toRead;
    return toRead;
  };
  ByteArrayInputStream.prototype.available = function() {
    return Math.max(0, this._buf.length - this._pos);
  };
  ByteArrayInputStream.prototype.close = function() {};
  return ByteArrayInputStream;
}

function createByteArrayOutputStreamClass() {
  function ByteArrayOutputStream() {
    this._chunks = [];
  }
  ByteArrayOutputStream.prototype.write = function(b, off = 0, len) {
    if (typeof b === 'number') {
      this._chunks.push(Buffer.from([b]));
    } else {
      const buf = Buffer.isBuffer(b) ? b : Buffer.from(b || []);
      this._chunks.push(buf.subarray(off, len !== undefined ? off + len : buf.length));
    }
  };
  ByteArrayOutputStream.prototype.toByteArray = function() {
    return Buffer.concat(this._chunks);
  };
  ByteArrayOutputStream.prototype.toString = function(enc = 'utf8') {
    return Buffer.concat(this._chunks).toString(enc);
  };
  ByteArrayOutputStream.prototype.close = function() {};
  return ByteArrayOutputStream;
}

function createJavaFileClass() {
  const fs = require('fs');
  const path = require('path');
  return function File(pathname, child) {
    const fullPath = child ? path.join(String(pathname || ''), String(child)) : String(pathname || '');
    return {
      exists: () => { try { return fs.existsSync(fullPath); } catch(_) { return false; } },
      isFile: () => { try { return fs.statSync(fullPath).isFile(); } catch(_) { return false; } },
      isDirectory: () => { try { return fs.statSync(fullPath).isDirectory(); } catch(_) { return false; } },
      length: () => { try { return fs.statSync(fullPath).size; } catch(_) { return 0; } },
      getPath: () => fullPath,
      getAbsolutePath: () => fullPath,
      getName: () => path.basename(fullPath),
      listFiles: () => {
        try {
          if (!fs.existsSync(fullPath) || !fs.statSync(fullPath).isDirectory()) return [];
          return fs.readdirSync(fullPath).map(name => new File(fullPath, name));
        } catch (_) {
          return [];
        }
      },
      delete: () => { try { fs.rmSync(fullPath, { recursive: true, force: true }); return true; } catch(_) { return false; } },
      mkdir: () => { try { fs.mkdirSync(fullPath, { recursive: true }); return true; } catch(_) { return false; } },
      mkdirs: () => { try { fs.mkdirSync(fullPath, { recursive: true }); return true; } catch(_) { return false; } },
      createNewFile: () => { try { fs.writeFileSync(fullPath, ''); return true; } catch(_) { return false; } }
    };
  };
}

function createStringBuilderClass() {
  function StringBuilder(initial) {
    if (!(this instanceof StringBuilder)) return new StringBuilder(initial);
    this._str = String(initial || '');
  }
  StringBuilder.prototype.append = function(val) {
    this._str += String(val ?? '');
    return this;
  };
  StringBuilder.prototype.toString = function() { return this._str; };
  StringBuilder.prototype.valueOf = function() { return this._str; };
  StringBuilder.prototype.length = function() { return this._str.length; };
  return StringBuilder;
}

function createAndroidGraphicsShims() {
  function BitmapInstance(width = 100, height = 100, bytes = null) {
    this._width = Number(width) || 100;
    this._height = Number(height) || 100;
    this._bytes = bytes ? (Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes)) : Buffer.alloc(0);
    this._recycled = false;
  }
  BitmapInstance.prototype.getWidth = function() { return this._width; };
  BitmapInstance.prototype.getHeight = function() { return this._height; };
  BitmapInstance.prototype.compress = function(_format, _quality, outStream) {
    if (outStream && typeof outStream.write === 'function' && this._bytes && this._bytes.length > 0) {
      outStream.write(this._bytes);
    }
    return true;
  };
  BitmapInstance.prototype.recycle = function() { this._recycled = true; };
  BitmapInstance.prototype.isRecycled = function() { return this._recycled; };
  BitmapInstance.prototype.getPixels = function() {};
  BitmapInstance.prototype.setPixels = function() {};

  const Bitmap = {
    CompressFormat: {
      JPEG: 'JPEG',
      PNG: 'PNG',
      WEBP: 'WEBP',
    },
    Config: {
      ARGB_8888: 'ARGB_8888',
      RGB_565: 'RGB_565',
      ALPHA_8: 'ALPHA_8',
      ARGB_4444: 'ARGB_4444',
    },
    createBitmap: function(w, h, _config) {
      if (w instanceof BitmapInstance) {
        return new BitmapInstance(w.getWidth(), w.getHeight(), w._bytes);
      }
      return new BitmapInstance(w, h);
    },
    createScaledBitmap: function(src, dstWidth, dstHeight, _filter) {
      const bytes = src && src._bytes ? src._bytes : Buffer.alloc(0);
      return new BitmapInstance(dstWidth, dstHeight, bytes);
    },
  };

  function BitmapOptions() {
    this.inSampleSize = 1;
    this.inJustDecodeBounds = false;
    this.inPreferredConfig = 'ARGB_8888';
    this.outWidth = 100;
    this.outHeight = 100;
  }

  const BitmapFactory = {
    Options: BitmapOptions,
    decodeByteArray: function(data, offset = 0, length, opts) {
      const buf = Buffer.isBuffer(data)
        ? data.subarray(offset, length !== undefined ? offset + length : data.length)
        : (data instanceof Uint8Array || Array.isArray(data)
            ? Buffer.from(data).subarray(offset, length !== undefined ? offset + length : data.length)
            : Buffer.alloc(0));
      let width = 100;
      let height = 100;
      // 尝试解析 PNG 头部宽高
      if (buf.length >= 24 && buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4E && buf[3] === 0x47) {
        width = buf.readUInt32BE(16) || 100;
        height = buf.readUInt32BE(20) || 100;
      }
      if (opts && typeof opts === 'object') {
        opts.outWidth = width;
        opts.outHeight = height;
      }
      return new BitmapInstance(width, height, buf);
    },
    decodeStream: function(stream) {
      if (stream && stream._buf) {
        return BitmapFactory.decodeByteArray(stream._buf);
      }
      return new BitmapInstance(100, 100);
    },
    decodeFile: function() {
      return new BitmapInstance(100, 100);
    },
  };

  function Canvas(bitmap) {
    if (!(this instanceof Canvas)) return new Canvas(bitmap);
    this._bitmap = bitmap;
  }
  Canvas.prototype.drawBitmap = function(srcBitmap) {
    if (this._bitmap && srcBitmap && srcBitmap._bytes && srcBitmap._bytes.length > 0) {
      this._bitmap._bytes = Buffer.from(srcBitmap._bytes);
    }
  };
  Canvas.prototype.drawRect = function() {};
  Canvas.prototype.drawColor = function() {};
  Canvas.prototype.save = function() { return 1; };
  Canvas.prototype.restore = function() {};
  Canvas.prototype.scale = function() {};
  Canvas.prototype.translate = function() {};
  Canvas.prototype.rotate = function() {};

  function Paint() {
    if (!(this instanceof Paint)) return new Paint();
  }
  Paint.prototype.setColorFilter = function(filter) { this._filter = filter; return filter; };
  Paint.prototype.setAntiAlias = function() {};
  Paint.prototype.setColor = function() {};
  Paint.prototype.setStyle = function() {};
  Paint.prototype.setTextSize = function() {};
  Paint.prototype.setTypeface = function() {};
  Paint.prototype.setStrokeWidth = function() {};

  Paint.Style = {
    FILL: 'FILL',
    STROKE: 'STROKE',
    FILL_AND_STROKE: 'FILL_AND_STROKE',
  };

  function ColorMatrix() {
    if (!(this instanceof ColorMatrix)) return new ColorMatrix();
    this._saturation = 1;
  }
  ColorMatrix.prototype.setSaturation = function(sat) { this._saturation = sat; };
  ColorMatrix.prototype.set = function() {};

  function ColorMatrixColorFilter(matrix) {
    if (!(this instanceof ColorMatrixColorFilter)) return new ColorMatrixColorFilter(matrix);
    this._matrix = matrix;
  }

  function Rect(left = 0, top = 0, right = 0, bottom = 0) {
    if (!(this instanceof Rect)) return new Rect(left, top, right, bottom);
    this.left = left;
    this.top = top;
    this.right = right;
    this.bottom = bottom;
  }
  Rect.prototype.width = function() { return this.right - this.left; };
  Rect.prototype.height = function() { return this.bottom - this.top; };

  const Color = {
    parseColor: () => 0,
    rgb: () => 0,
    argb: () => 0,
    TRANSPARENT: 0,
    BLACK: -16777216,
    WHITE: -1,
  };

  return {
    Bitmap,
    BitmapFactory,
    Canvas,
    Paint,
    ColorMatrix,
    ColorMatrixColorFilter,
    Rect,
    Color,
  };
}

function createAndroidOsShims() {
  return {
    Build: {
      VERSION: {
        SDK_INT: 30,
        RELEASE: '11',
      },
      VERSION_CODES: {
        KITKAT: 19,
        LOLLIPOP: 21,
        M: 23,
        N: 24,
        O: 26,
        P: 28,
        Q: 29,
        R: 30,
        S: 31,
        TIRAMISU: 33,
      },
      BRAND: 'Xiaomi',
      MODEL: 'Mi 10 Pro',
    },
    Looper: {
      getMainLooper: () => ({}),
      myLooper: () => ({}),
    },
    Handler: function() {
      return {
        post: (fn) => { if (typeof fn === 'function') fn(); else if (fn && typeof fn.run === 'function') fn.run(); },
        postDelayed: (fn, ms) => setTimeout(() => { if (typeof fn === 'function') fn(); else if (fn && typeof fn.run === 'function') fn.run(); }, ms || 0),
      };
    },
    Environment: {
      getExternalStorageDirectory: () => ({ getAbsolutePath: () => '/storage/emulated/0' }),
    },
  };
}

function createJavaUtilZipShims() {
  const zlib = require('zlib');

  function GZIPInputStream(inStream) {
    if (!(this instanceof GZIPInputStream)) return new GZIPInputStream(inStream);
    const raw = inStream && inStream._buf ? inStream._buf : Buffer.alloc(0);
    try {
      this._buf = zlib.gunzipSync(raw);
    } catch (_) {
      this._buf = raw;
    }
    this._pos = 0;
  }
  GZIPInputStream.prototype.read = function(b, off = 0, len) {
    if (this._pos >= this._buf.length) return -1;
    if (!b) return this._buf[this._pos++];
    const toRead = Math.min(len !== undefined ? len : b.length - off, this._buf.length - this._pos);
    this._buf.copy(b, off, this._pos, this._pos + toRead);
    this._pos += toRead;
    return toRead;
  };
  GZIPInputStream.prototype.close = function() {};

  function GZIPOutputStream(outStream) {
    if (!(this instanceof GZIPOutputStream)) return new GZIPOutputStream(outStream);
    this._out = outStream;
    this._chunks = [];
    this._finished = false;
  }
  GZIPOutputStream.prototype.write = function(b, off = 0, len) {
    if (typeof b === 'number') {
      this._chunks.push(Buffer.from([b]));
    } else {
      const buf = Buffer.isBuffer(b) ? b : Buffer.from(b || []);
      this._chunks.push(Buffer.from(buf.subarray(off, len !== undefined ? off + len : buf.length)));
    }
  };
  GZIPOutputStream.prototype.finish = function() {
    if (this._finished) return;
    this._finished = true;
    const raw = Buffer.concat(this._chunks);
    const compressed = zlib.gzipSync(raw);
    if (this._out && typeof this._out.write === 'function') {
      this._out.write(compressed);
    }
  };
  GZIPOutputStream.prototype.close = function() {
    this.finish();
  };

  function InflaterInputStream(inStream) {
    if (!(this instanceof InflaterInputStream)) return new InflaterInputStream(inStream);
    const raw = inStream && inStream._buf ? inStream._buf : Buffer.alloc(0);
    try {
      this._buf = zlib.inflateSync(raw);
    } catch (_) {
      try {
        this._buf = zlib.inflateRawSync(raw);
      } catch (__) {
        this._buf = raw;
      }
    }
    this._pos = 0;
  }
  InflaterInputStream.prototype.read = GZIPInputStream.prototype.read;
  InflaterInputStream.prototype.close = function() {};

  function DeflaterOutputStream(outStream) {
    if (!(this instanceof DeflaterOutputStream)) return new DeflaterOutputStream(outStream);
    this._out = outStream;
    this._chunks = [];
    this._finished = false;
  }
  DeflaterOutputStream.prototype.write = GZIPOutputStream.prototype.write;
  DeflaterOutputStream.prototype.finish = function() {
    if (this._finished) return;
    this._finished = true;
    const raw = Buffer.concat(this._chunks);
    const compressed = zlib.deflateSync(raw);
    if (this._out && typeof this._out.write === 'function') {
      this._out.write(compressed);
    }
  };
  DeflaterOutputStream.prototype.close = function() {
    this.finish();
  };

  return {
    GZIPInputStream,
    GZIPOutputStream,
    InflaterInputStream,
    DeflaterOutputStream,
  };
}

function createAndroidNetUriClass() {
  function Uri(parsedUrl, rawString) {
    this._url = parsedUrl;
    this._raw = rawString || '';
  }

  Uri.prototype.getHost = function() {
    return this._url ? (this._url.hostname || '') : '';
  };
  Uri.prototype.getPath = function() {
    return this._url ? (this._url.pathname || '') : '';
  };
  Uri.prototype.getScheme = function() {
    if (!this._url) return '';
    return this._url.protocol ? this._url.protocol.replace(/:$/, '') : '';
  };
  Uri.prototype.getQuery = function() {
    if (!this._url) return '';
    const search = this._url.search || '';
    return search.startsWith('?') ? search.slice(1) : search;
  };
  Uri.prototype.getPort = function() {
    if (!this._url || !this._url.port) return -1;
    const p = parseInt(this._url.port, 10);
    return isNaN(p) ? -1 : p;
  };
  Uri.prototype.getAuthority = function() {
    return this._url ? (this._url.host || '') : '';
  };
  Uri.prototype.getFragment = function() {
    if (!this._url) return '';
    const hash = this._url.hash || '';
    return hash.startsWith('#') ? hash.slice(1) : hash;
  };
  Uri.prototype.getPathSegments = function() {
    if (!this._url || !this._url.pathname) return [];
    return this._url.pathname.split('/').filter(Boolean);
  };
  Uri.prototype.getLastPathSegment = function() {
    const segs = this.getPathSegments();
    return segs.length > 0 ? segs[segs.length - 1] : null;
  };
  Uri.prototype.getQueryParameter = function(key) {
    if (!this._url || !this._url.searchParams) return null;
    return this._url.searchParams.get(key);
  };
  Uri.prototype.getQueryParameters = function(key) {
    if (!this._url || !this._url.searchParams) return [];
    return this._url.searchParams.getAll(key);
  };
  Uri.prototype.getQueryParameterNames = function() {
    if (!this._url || !this._url.searchParams) return [];
    const names = Array.from(new Set(this._url.searchParams.keys()));
    names.iterator = function() {
      let idx = 0;
      return {
        hasNext: () => idx < names.length,
        next: () => names[idx++],
      };
    };
    names.size = () => names.length;
    names.isEmpty = () => names.length === 0;
    return names;
  };
  Uri.prototype.getBooleanQueryParameter = function(key, defaultValue = false) {
    const val = this.getQueryParameter(key);
    if (val === null) return defaultValue;
    return val === 'true' || val === '1';
  };
  Uri.prototype.toString = function() {
    return this._url ? this._url.toString() : this._raw;
  };
  Uri.prototype.buildUpon = function() {
    return new UriBuilder(this._url ? this._url.toString() : this._raw);
  };

  function UriBuilder(baseUriStr) {
    let urlObj = null;
    try {
      urlObj = new URL(baseUriStr);
    } catch (_) {
      try {
        urlObj = new URL(baseUriStr, 'http://localhost');
      } catch (__) {
        urlObj = new URL('http://localhost');
      }
    }
    this._url = urlObj;
  }

  UriBuilder.prototype.scheme = function(s) {
    if (this._url) this._url.protocol = String(s).endsWith(':') ? s : `${s}:`;
    return this;
  };
  UriBuilder.prototype.authority = function(a) {
    if (this._url) this._url.host = a;
    return this;
  };
  UriBuilder.prototype.path = function(p) {
    if (this._url) this._url.pathname = p;
    return this;
  };
  UriBuilder.prototype.appendPath = function(seg) {
    if (this._url) {
      const cur = this._url.pathname.replace(/\/$/, '');
      this._url.pathname = `${cur}/${seg}`;
    }
    return this;
  };
  UriBuilder.prototype.appendEncodedPath = function(seg) {
    return this.appendPath(seg);
  };
  UriBuilder.prototype.query = function(q) {
    if (this._url) this._url.search = q ? (q.startsWith('?') ? q : `?${q}`) : '';
    return this;
  };
  UriBuilder.prototype.encodedQuery = function(q) {
    return this.query(q);
  };
  UriBuilder.prototype.appendQueryParameter = function(k, v) {
    if (this._url && this._url.searchParams) {
      this._url.searchParams.append(k, String(v ?? ''));
    }
    return this;
  };
  UriBuilder.prototype.clearQuery = function() {
    if (this._url) this._url.search = '';
    return this;
  };
  UriBuilder.prototype.fragment = function(f) {
    if (this._url) this._url.hash = f ? (f.startsWith('#') ? f : `#${f}`) : '';
    return this;
  };
  UriBuilder.prototype.build = function() {
    return new Uri(new URL(this._url.toString()), this._url.toString());
  };
  UriBuilder.prototype.toString = function() {
    return this._url ? this._url.toString() : '';
  };

  const UriClass = {
    parse: function(uriString) {
      if (!uriString) return new Uri(null, '');
      const str = String(uriString);
      try {
        const u = new URL(str);
        return new Uri(u, str);
      } catch (_) {
        try {
          const u = new URL(str, 'http://localhost');
          return new Uri(u, str);
        } catch (__) {
          return new Uri(null, str);
        }
      }
    },
    fromFile: function(file) {
      const p = file && typeof file.getAbsolutePath === 'function' ? file.getAbsolutePath() : String(file || '');
      return UriClass.parse(`file://${p}`);
    },
    fromParts: function(scheme, ssp, fragment) {
      let res = `${scheme}:${ssp}`;
      if (fragment) res += `#${fragment}`;
      return UriClass.parse(res);
    },
    Builder: UriBuilder,
    EMPTY: new Uri(null, ''),
  };

  return UriClass;
}

function createJavaRegexShims() {
  function Matcher(regex, input) {
    this._regex = new RegExp(regex.source, regex.flags.includes('g') ? regex.flags : regex.flags + 'g');
    this._input = String(input ?? '');
    this._lastMatch = null;
  }

  Matcher.prototype.find = function(start) {
    if (start !== undefined) {
      this._regex.lastIndex = Number(start) || 0;
    }
    const match = this._regex.exec(this._input);
    this._lastMatch = match;
    return match !== null;
  };

  Matcher.prototype.group = function(groupIndex = 0) {
    if (!this._lastMatch) throw new Error('No match available');
    return this._lastMatch[groupIndex] !== undefined ? this._lastMatch[groupIndex] : null;
  };

  Matcher.prototype.groupCount = function() {
    if (!this._lastMatch) return 0;
    return Math.max(0, this._lastMatch.length - 1);
  };

  Matcher.prototype.start = function(groupIndex = 0) {
    if (!this._lastMatch) throw new Error('No match available');
    if (groupIndex === 0) return this._lastMatch.index;
    const fullIdx = this._lastMatch.index;
    const groupVal = this._lastMatch[groupIndex];
    if (groupVal === undefined) return -1;
    const relIdx = this._lastMatch[0].indexOf(groupVal);
    return relIdx >= 0 ? fullIdx + relIdx : -1;
  };

  Matcher.prototype.end = function(groupIndex = 0) {
    const s = this.start(groupIndex);
    if (s < 0) return -1;
    const g = this.group(groupIndex);
    return s + (g ? g.length : 0);
  };

  Matcher.prototype.replaceAll = function(replacement) {
    const r = new RegExp(this._regex.source, this._regex.flags.includes('g') ? this._regex.flags : this._regex.flags + 'g');
    return this._input.replace(r, replacement);
  };

  Matcher.prototype.replaceFirst = function(replacement) {
    const flagsWithoutG = this._regex.flags.replace('g', '');
    const r = new RegExp(this._regex.source, flagsWithoutG);
    return this._input.replace(r, replacement);
  };

  Matcher.prototype.matches = function() {
    const flags = this._regex.flags.replace('g', '');
    const fullRegex = new RegExp(`^(?:${this._regex.source})$`, flags);
    return fullRegex.test(this._input);
  };

  Matcher.prototype.reset = function(newInput) {
    if (newInput !== undefined) this._input = String(newInput);
    this._regex.lastIndex = 0;
    this._lastMatch = null;
    return this;
  };

  function Pattern(patternStr, flags = 0) {
    let jsFlags = '';
    if (flags & 2) jsFlags += 'i';
    if (flags & 8) jsFlags += 'm';
    if (flags & 32) jsFlags += 's';

    this._source = String(patternStr || '');
    this._flags = jsFlags;
    this._rawFlags = flags;
    this._regex = new RegExp(this._source, jsFlags);
  }

  Pattern.prototype.matcher = function(input) {
    return new Matcher(this._regex, input);
  };

  Pattern.prototype.split = function(input, limit = 0) {
    const res = String(input || '').split(this._regex);
    if (limit > 0) return res.slice(0, limit);
    return res;
  };

  Pattern.prototype.pattern = function() {
    return this._source;
  };

  Pattern.prototype.flags = function() {
    return this._rawFlags;
  };

  Pattern.prototype.toString = function() {
    return this._source;
  };

  const PatternClass = {
    compile: function(regex, flags = 0) {
      return new Pattern(regex, flags);
    },
    matches: function(regex, input) {
      return PatternClass.compile(regex).matcher(input).matches();
    },
    quote: function(s) {
      return String(s || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    },
    CASE_INSENSITIVE: 2,
    MULTILINE: 8,
    DOTALL: 32,
    CANON_EQ: 128,
    LITERAL: 16,
    UNICODE_CASE: 64,
  };

  return {
    Pattern: PatternClass,
    Matcher,
  };
}

function createBigDecimalClass() {
  function BigDecimal(val) {
    if (!(this instanceof BigDecimal)) return new BigDecimal(val);
    if (typeof val === 'number') {
      this._num = val;
      this._str = String(val);
    } else if (typeof val === 'string') {
      this._str = val.trim();
      this._num = parseFloat(this._str) || 0;
    } else if (val instanceof BigDecimal) {
      this._num = val._num;
      this._str = val._str;
    } else {
      this._num = Number(val || 0);
      this._str = String(this._num);
    }
  }

  BigDecimal.prototype.add = function(other) {
    const o = other instanceof BigDecimal ? other._num : Number(other || 0);
    return new BigDecimal(this._num + o);
  };
  BigDecimal.prototype.subtract = function(other) {
    const o = other instanceof BigDecimal ? other._num : Number(other || 0);
    return new BigDecimal(this._num - o);
  };
  BigDecimal.prototype.multiply = function(other) {
    const o = other instanceof BigDecimal ? other._num : Number(other || 0);
    return new BigDecimal(this._num * o);
  };
  BigDecimal.prototype.divide = function(other, scale, roundingMode) {
    const o = other instanceof BigDecimal ? other._num : Number(other || 1);
    if (o === 0) throw new Error('/ by zero');
    let res = this._num / o;
    if (scale !== undefined) {
      res = Number(res.toFixed(scale));
    }
    return new BigDecimal(res);
  };
  BigDecimal.prototype.compareTo = function(other) {
    const o = other instanceof BigDecimal ? other._num : Number(other || 0);
    if (this._num < o) return -1;
    if (this._num > o) return 1;
    return 0;
  };
  BigDecimal.prototype.doubleValue = function() { return this._num; };
  BigDecimal.prototype.floatValue = function() { return this._num; };
  BigDecimal.prototype.intValue = function() { return parseInt(this._num, 10); };
  BigDecimal.prototype.longValue = function() { return parseInt(this._num, 10); };
  BigDecimal.prototype.toString = function() { return this._str; };
  BigDecimal.prototype.toPlainString = function() { return String(this._num); };
  BigDecimal.prototype.stripTrailingZeros = function() {
    return new BigDecimal(parseFloat(this._str));
  };
  BigDecimal.prototype.setScale = function(scale, roundingMode) {
    return new BigDecimal(this._num.toFixed(scale));
  };
  BigDecimal.valueOf = function(v) { return new BigDecimal(v); };
  BigDecimal.ZERO = new BigDecimal(0);
  BigDecimal.ONE = new BigDecimal(1);
  BigDecimal.TEN = new BigDecimal(10);
  BigDecimal.ROUND_UP = 0;
  BigDecimal.ROUND_DOWN = 1;
  BigDecimal.ROUND_CEILING = 2;
  BigDecimal.ROUND_FLOOR = 3;
  BigDecimal.ROUND_HALF_UP = 4;
  BigDecimal.ROUND_HALF_DOWN = 5;
  BigDecimal.ROUND_HALF_EVEN = 6;
  BigDecimal.ROUND_UNNECESSARY = 7;

  return BigDecimal;
}

function createDecimalFormatClass() {
  function DecimalFormat(pattern = '#.##') {
    this.pattern = pattern;
  }
  DecimalFormat.prototype.format = function(num) {
    const n = Number(num || 0);
    const m = this.pattern.match(/\.([#0]+)/);
    if (!m) {
      return String(Math.round(n));
    }
    const decDigits = m[1].length;
    const isZeroPad = m[1].includes('0');
    if (isZeroPad) {
      return n.toFixed(decDigits);
    }
    return String(parseFloat(n.toFixed(decDigits)));
  };
  DecimalFormat.prototype.parse = function(str) {
    return parseFloat(str) || 0;
  };
  return DecimalFormat;
}

function createJavaDateAndCalendarShims() {
  if (typeof Date.prototype.before !== 'function') {
    Date.prototype.before = function(other) {
      const ot = other instanceof Date ? other.getTime() : Number(other);
      return this.getTime() < ot;
    };
  }
  if (typeof Date.prototype.after !== 'function') {
    Date.prototype.after = function(other) {
      const ot = other instanceof Date ? other.getTime() : Number(other);
      return this.getTime() > ot;
    };
  }
  if (typeof Date.prototype.equals !== 'function') {
    Date.prototype.equals = function(other) {
      const ot = other instanceof Date ? other.getTime() : Number(other);
      return this.getTime() === ot;
    };
  }

  function JavaDate(...args) {
    if (args.length === 0) return new Date();
    if (args.length === 1) {
      const a0 = args[0];
      if (a0 instanceof Date) return new Date(a0.getTime());
      if (typeof a0 === 'number' || (typeof a0 === 'string' && !isNaN(Number(a0)))) return new Date(Number(a0));
      return new Date(a0);
    }
    return new Date(...args);
  }
  JavaDate.now = Date.now;
  JavaDate.parse = Date.parse;
  JavaDate.UTC = Date.UTC;
  JavaDate.prototype = Date.prototype;

  function Calendar() {
    this._date = new Date();
  }
  Calendar.YEAR = 1;
  Calendar.MONTH = 2;
  Calendar.DATE = 5;
  Calendar.DAY_OF_MONTH = 5;
  Calendar.HOUR = 10;
  Calendar.HOUR_OF_DAY = 11;
  Calendar.MINUTE = 12;
  Calendar.SECOND = 13;
  Calendar.MILLISECOND = 14;
  Calendar.AM_PM = 9;

  Calendar.getInstance = function() {
    return new Calendar();
  };

  Calendar.prototype.setTime = function(date) {
    const t = date instanceof Date ? date.getTime() : (typeof date === 'number' ? date : (Number(date) || Date.now()));
    this._date = new Date(t);
  };
  Calendar.prototype.getTime = function() {
    return new Date(this._date.getTime());
  };
  Calendar.prototype.getTimeInMillis = function() {
    return this._date.getTime();
  };
  Calendar.prototype.setTimeInMillis = function(millis) {
    this._date.setTime(Number(millis) || 0);
  };
  Calendar.prototype.get = function(field) {
    switch (field) {
      case Calendar.YEAR: return this._date.getFullYear();
      case Calendar.MONTH: return this._date.getMonth();
      case Calendar.DATE:
      case Calendar.DAY_OF_MONTH: return this._date.getDate();
      case Calendar.HOUR_OF_DAY: return this._date.getHours();
      case Calendar.HOUR: return this._date.getHours() % 12;
      case Calendar.MINUTE: return this._date.getMinutes();
      case Calendar.SECOND: return this._date.getSeconds();
      case Calendar.MILLISECOND: return this._date.getMilliseconds();
      default: return 0;
    }
  };
  Calendar.prototype.set = function(field, value) {
    const val = Number(value) || 0;
    switch (field) {
      case Calendar.YEAR: this._date.setFullYear(val); break;
      case Calendar.MONTH: this._date.setMonth(val); break;
      case Calendar.DATE:
      case Calendar.DAY_OF_MONTH: this._date.setDate(val); break;
      case Calendar.HOUR_OF_DAY: this._date.setHours(val); break;
      case Calendar.MINUTE: this._date.setMinutes(val); break;
      case Calendar.SECOND: this._date.setSeconds(val); break;
      case Calendar.MILLISECOND: this._date.setMilliseconds(val); break;
    }
  };
  Calendar.prototype.add = function(field, amount) {
    const cur = this.get(field);
    this.set(field, cur + (Number(amount) || 0));
  };

  return {
    JavaDate,
    Calendar,
  };
}

function createJavaSetClasses() {
  function HashSet(initial) {
    if (!(this instanceof HashSet)) return new HashSet(initial);
    this._set = new Set();
    if (initial) {
      if (Array.isArray(initial)) {
        for (const item of initial) this._set.add(item);
      } else if (typeof initial.forEach === 'function') {
        initial.forEach(item => this._set.add(item));
      }
    }
  }
  HashSet.prototype.add = function(item) {
    const has = this._set.has(item);
    this._set.add(item);
    return !has;
  };
  HashSet.prototype.contains = function(item) { return this._set.has(item); };
  HashSet.prototype.remove = function(item) { return this._set.delete(item); };
  HashSet.prototype.size = function() { return this._set.size; };
  HashSet.prototype.isEmpty = function() { return this._set.size === 0; };
  HashSet.prototype.clear = function() { this._set.clear(); };
  HashSet.prototype.toArray = function() { return Array.from(this._set); };
  HashSet.prototype.iterator = function() {
    const arr = Array.from(this._set);
    let idx = 0;
    return {
      hasNext: () => idx < arr.length,
      next: () => arr[idx++],
    };
  };
  HashSet.prototype[Symbol.iterator] = function* () { yield* this._set; };

  function TreeSet(initial) {
    if (!(this instanceof TreeSet)) return new TreeSet(initial);
    HashSet.call(this, initial);
  }
  TreeSet.prototype = Object.create(HashSet.prototype);
  TreeSet.prototype.constructor = TreeSet;
  TreeSet.prototype.first = function() {
    const arr = this.toArray().sort();
    return arr.length > 0 ? arr[0] : null;
  };
  TreeSet.prototype.last = function() {
    const arr = this.toArray().sort();
    return arr.length > 0 ? arr[arr.length - 1] : null;
  };

  return {
    HashSet,
    TreeSet,
  };
}

function createJavaExtraCollectionsShims() {
  function LinkedList(initial) {
    if (!(this instanceof LinkedList)) return new LinkedList(initial);
    this._items = Array.isArray(initial) ? [...initial] : [];
  }
  LinkedList.prototype.add = function(item) { this._items.push(item); return true; };
  LinkedList.prototype.addFirst = function(item) { this._items.unshift(item); };
  LinkedList.prototype.addLast = function(item) { this._items.push(item); };
  LinkedList.prototype.get = function(i) { return this._items[i]; };
  LinkedList.prototype.getFirst = function() { return this._items[0]; };
  LinkedList.prototype.getLast = function() { return this._items[this._items.length - 1]; };
  LinkedList.prototype.remove = function(i) {
    if (i !== undefined) return this._items.splice(i, 1)[0];
    return this._items.shift();
  };
  LinkedList.prototype.removeFirst = function() { return this._items.shift(); };
  LinkedList.prototype.removeLast = function() { return this._items.pop(); };
  LinkedList.prototype.size = function() { return this._items.length; };
  LinkedList.prototype.isEmpty = function() { return this._items.length === 0; };
  LinkedList.prototype.clear = function() { this._items = []; };
  LinkedList.prototype.poll = function() { return this._items.shift() || null; };
  LinkedList.prototype.peek = function() { return this._items[0] || null; };
  LinkedList.prototype.pop = function() { return this._items.pop(); };
  LinkedList.prototype.push = function(item) { this._items.push(item); };
  LinkedList.prototype.toArray = function() { return [...this._items]; };

  function Stack() {
    if (!(this instanceof Stack)) return new Stack();
    this._items = [];
  }
  Stack.prototype.push = function(item) { this._items.push(item); return item; };
  Stack.prototype.pop = function() { return this._items.pop(); };
  Stack.prototype.peek = function() { return this._items[this._items.length - 1]; };
  Stack.prototype.empty = function() { return this._items.length === 0; };
  Stack.prototype.search = function(item) {
    const idx = this._items.lastIndexOf(item);
    return idx >= 0 ? this._items.length - idx : -1;
  };

  return {
    LinkedList,
    Stack,
  };
}

function createComHikerviewUtilsShims(sandbox) {
  const fs = require('fs');
  const path = require('path');
  const { similarity } = require('./rule-helpers');

  return {
    FileUtil: {
      toBytes: (inp) => (Buffer.isBuffer(inp) ? inp : Buffer.from(String(inp || ''), 'utf8')),
      toInputStream: (bytes) => new (createByteArrayInputStreamClass())(bytes),
      toString: (bytes, charset) => (Buffer.isBuffer(bytes) ? bytes.toString(charset || 'utf8') : String(bytes || '')),
      fileToString: (filePath) => {
        try {
          if (sandbox && typeof sandbox.readFile === 'function') return sandbox.readFile(filePath);
          return fs.readFileSync(filePath, 'utf8');
        } catch (_) { return ''; }
      },
      stringToFile: (filePath, content) => {
        try {
          if (sandbox && typeof sandbox.writeFile === 'function') return sandbox.writeFile(filePath, content);
          fs.writeFileSync(filePath, String(content || ''));
          return true;
        } catch (_) { return false; }
      },
      getFileName: (filePath) => path.basename(String(filePath || '')),
      getFileExtension: (filePath) => path.extname(String(filePath || '')).replace(/^\./, ''),
      deleteFile: (filePath) => {
        try {
          if (sandbox && typeof sandbox.deleteFile === 'function') return sandbox.deleteFile(filePath);
          fs.rmSync(filePath, { force: true });
          return true;
        } catch (_) { return false; }
      },
      clearDir: () => true,
    },
    StringUtil: {
      levenshtein: (s1, s2) => similarity(s1, s2),
      similarity: (s1, s2) => similarity(s1, s2),
      isEmpty: (s) => !s || String(s).length === 0,
      isNotEmpty: (s) => !!s && String(s).length > 0,
      isNotEmptyTrim: (s) => !!s && String(s).trim().length > 0,
      equals: (s1, s2) => String(s1 || '') === String(s2 || ''),
      md5: (s) => crypto.createHash('md5').update(String(s || '')).digest('hex'),
    },
    ScreenUtil: {
      getScreenWidth: () => 1080,
      getScreenHeight: () => 1920,
      dp2px: (_ctx, dp) => Math.round((Number(dp) || 0) * 2),
      px2dp: (_ctx, px) => Math.round((Number(px) || 0) / 2),
      getDensity: () => 2.0,
    },
    ThreadTool: {
      INSTANCE: {
        executeNewTask: (fn) => {
          if (typeof fn === 'function') fn();
          else if (fn && typeof fn.run === 'function') fn.run();
        },
        runOnUI: (fn) => {
          if (typeof fn === 'function') fn();
          else if (fn && typeof fn.run === 'function') fn.run();
        },
        runOnUIResume: (fn) => {
          if (typeof fn === 'function') fn();
          else if (fn && typeof fn.run === 'function') fn.run();
        },
      },
    },
    ToastMgr: {
      shortBottomCenter: (_ctx, msg) => (sandbox && typeof sandbox.toast === 'function' ? sandbox.toast(msg) : undefined),
      shortCenter: (_ctx, msg) => (sandbox && typeof sandbox.toast === 'function' ? sandbox.toast(msg) : undefined),
      show: (_ctx, msg) => (sandbox && typeof sandbox.toast === 'function' ? sandbox.toast(msg) : undefined),
    },
    ClipboardUtil: {
      copyToClipboard: (_ctx, text) => (sandbox && typeof sandbox.setClip === 'function' ? sandbox.setClip(text) : undefined),
      getClipboardText: (_ctx) => (sandbox && typeof sandbox.getCopy === 'function' ? sandbox.getCopy() : ''),
    },
  };
}

const StandardCharsets = {
  UTF_8: 'utf8',
  US_ASCII: 'ascii',
  ISO_8859_1: 'latin1',
};

module.exports = {
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
};

