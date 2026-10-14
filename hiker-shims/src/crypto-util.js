/**
 * Hiker Native Assets: crypto-java.js
 * 100% 同构兼容移动端海阔视界 (Rhino/Android) 内置 Java 加密工具集 (CryptoUtil)
 * 具备 Node.js 原生 OpenSSL + CryptoJS 双引擎降级机制，彻底规避 OpenSSL 3.0 下 DES/TripleDES 的 ERR_OSSL_EVP_UNSUPPORTED
 */
(function() {
  const crypto = typeof require === 'function' ? require('crypto') : null;
  let CryptoJS;
  try {
    CryptoJS = typeof require === 'function' ? require('crypto-js') : (globalThis.CryptoJS || null);
  } catch (_) {
    CryptoJS = globalThis.CryptoJS || null;
  }

  class CryptoData {
    constructor(buffer) {
      if (Buffer.isBuffer(buffer)) {
        this.buf = buffer;
      } else if (typeof buffer === 'string') {
        this.buf = Buffer.from(buffer, 'utf8');
      } else if (buffer instanceof Uint8Array) {
        this.buf = Buffer.from(buffer);
      } else if (Array.isArray(buffer)) {
        this.buf = Buffer.from(buffer);
      } else {
        this.buf = Buffer.alloc(0);
      }
    }

    toBase64(flag) {
      return this.buf.toString('base64');
    }

    toHex() {
      return this.buf.toString('hex');
    }

    toBytes() {
      return this.buf;
    }

    toUint8Array() {
      return new Uint8Array(this.buf);
    }

    toString(encoding = 'utf8') {
      const enc = String(encoding || 'utf8').toLowerCase();
      if (enc.includes('iso-8859-1') || enc.includes('latin1')) {
        return this.buf.toString('latin1');
      }
      if (enc.includes('utf-16le') || enc.includes('utf16le')) {
        return this.buf.toString('utf16le');
      }
      return this.buf.toString('utf8');
    }

    toLatin1() {
      return this.buf.toString('latin1');
    }

    toUTF16() {
      return this.buf.toString('utf16le');
    }

    toUTF16LE() {
      return this.buf.toString('utf16le');
    }

    toDigest() {
      return new Digest(this);
    }

    base64Decode() {
      const decoded = Buffer.from(this.buf.toString('utf8'), 'base64');
      return new CryptoData(decoded);
    }

    base64Encode() {
      const encoded = Buffer.from(this.buf.toString('base64'), 'utf8');
      return new CryptoData(encoded);
    }

    toInputStream() {
      return Object.assign(this.buf, {
        read: () => this.buf,
        available: () => this.buf.length,
        toBase64: () => this.buf.toString('base64'),
        toString: (enc = 'utf8') => this.toString(enc),
        toByteArray: () => Array.from(this.buf)
      });
    }

    length() {
      return this.buf.length;
    }

    get length() {
      return this.buf.length;
    }
  }

  function toBuffer(val, defaultEncoding = 'utf8') {
    if (val instanceof CryptoData) return val.buf;
    if (Buffer.isBuffer(val)) return val;
    if (val && Buffer.isBuffer(val.buf)) return val.buf;
    if (typeof val === 'string') {
      return Buffer.from(val, defaultEncoding);
    }
    if (val instanceof Uint8Array || Array.isArray(val)) return Buffer.from(val);
    return Buffer.alloc(0);
  }

  function bufferToCryptoJS(buf) {
    if (!CryptoJS) return null;
    return CryptoJS.enc.Hex.parse(buf.toString('hex'));
  }

  function cryptoJSToBuffer(wordArray) {
    if (!wordArray || !CryptoJS) return Buffer.alloc(0);
    const hex = CryptoJS.enc.Hex.stringify(wordArray);
    return Buffer.from(hex, 'hex');
  }

  const Data = {
    parseStr(str, charset) {
      return new CryptoData(toBuffer(str, charset || 'utf8'));
    },
    parseUTF8(str) {
      return new CryptoData(Buffer.from(String(str || ''), 'utf8'));
    },
    parseUTF16(str) {
      return new CryptoData(Buffer.from(String(str || ''), 'utf16le'));
    },
    parseUTF16LE(str) {
      return new CryptoData(Buffer.from(String(str || ''), 'utf16le'));
    },
    parseLatin1(str) {
      return new CryptoData(Buffer.from(String(str || ''), 'latin1'));
    },
    parseHex(str) {
      return new CryptoData(Buffer.from(String(str || '').replace(/\s+/g, ''), 'hex'));
    },
    parseBase64(str) {
      return new CryptoData(Buffer.from(String(str || '').trim(), 'base64'));
    },
    parseInputStream(stream) {
      if (Buffer.isBuffer(stream)) return new CryptoData(stream);
      if (stream instanceof Uint8Array) return new CryptoData(Buffer.from(stream));
      if (typeof stream === 'string') {
        if (stream.startsWith('data:') && stream.includes('base64,')) {
          return new CryptoData(Buffer.from(stream.split('base64,')[1], 'base64'));
        }
        return new CryptoData(Buffer.from(stream, 'utf8'));
      }
      return new CryptoData(Buffer.alloc(0));
    }
  };

  function Digest(data) {
    this.data = data;
  }
  Digest.digest = function(data, algorithm) {
    const buf = toBuffer(data);
    const alg = String(algorithm || 'md5').toLowerCase().replace('-', '');
    if (crypto) {
      try {
        return crypto.createHash(alg).update(buf).digest('hex');
      } catch (_) {}
    }
    if (CryptoJS) {
      const wa = bufferToCryptoJS(buf);
      if (alg.includes('md5')) return CryptoJS.MD5(wa).toString();
      if (alg.includes('sha256')) return CryptoJS.SHA256(wa).toString();
      if (alg.includes('sha1')) return CryptoJS.SHA1(wa).toString();
      if (alg.includes('sha512')) return CryptoJS.SHA512(wa).toString();
    }
    return '';
  };
  Object.assign(Digest.prototype, {
    md5() { return Digest.digest(this.data, 'MD5'); },
    sha256() { return Digest.digest(this.data, 'SHA-256'); },
    md2() { return Digest.digest(this.data, 'MD2'); },
    sha1() { return Digest.digest(this.data, 'SHA-1'); },
    sha512() { return Digest.digest(this.data, 'SHA-512'); },
    sha384() { return Digest.digest(this.data, 'SHA-384'); }
  });

  function resolveCipherAlgorithm(algorithm, keyLen, modeStr) {
    const alg = String(algorithm || 'AES').toUpperCase();
    const mode = String(modeStr || 'CBC').toUpperCase();

    if (alg.includes('AES')) {
      let bits = 128;
      if (keyLen >= 32) bits = 256;
      else if (keyLen >= 24) bits = 192;
      else bits = 128;

      let subMode = 'cbc';
      if (mode.includes('ECB')) subMode = 'ecb';
      else if (mode.includes('CTR')) subMode = 'ctr';
      else if (mode.includes('OFB')) subMode = 'ofb';
      else if (mode.includes('CFB')) subMode = 'cfb';
      else if (mode.includes('GCM')) subMode = 'gcm';
      return `aes-${bits}-${subMode}`;
    }

    if (alg.includes('DES3') || alg.includes('TRIPLEDES') || alg.includes('DESEDE')) {
      return mode.includes('ECB') ? 'des-ede3' : 'des-ede3-cbc';
    }

    if (alg.includes('DES')) {
      return mode.includes('ECB') ? 'des-ecb' : 'des-cbc';
    }

    return 'aes-128-cbc';
  }

  const AES = {
    encrypt(plaintext, key, options = {}) {
      try {
        const plainBuf = toBuffer(plaintext);
        let keyBuf = toBuffer(key);
        if (keyBuf.length < 16) {
          const padded = Buffer.alloc(16, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 16 && keyBuf.length < 24) {
          const padded = Buffer.alloc(24, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 24 && keyBuf.length < 32) {
          const padded = Buffer.alloc(32, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 32) {
          keyBuf = keyBuf.subarray(0, 32);
        }

        const modeStr = String(options.mode || 'AES/CBC/PKCS7Padding');
        const cipherAlg = resolveCipherAlgorithm('AES', keyBuf.length, modeStr);
        let ivBuf = options.iv ? toBuffer(options.iv) : Buffer.alloc(16, 0);
        if (ivBuf.length < 16) {
          const padded = Buffer.alloc(16, 0); ivBuf.copy(padded); ivBuf = padded;
        } else if (ivBuf.length > 16) {
          ivBuf = ivBuf.subarray(0, 16);
        }

        const isEcb = cipherAlg.includes('-ecb');
        const cipher = isEcb ? crypto.createCipheriv(cipherAlg, keyBuf, null) : crypto.createCipheriv(cipherAlg, keyBuf, ivBuf);
        cipher.setAutoPadding(!modeStr.toUpperCase().includes('NOPADDING'));

        const enc = Buffer.concat([cipher.update(plainBuf), cipher.final()]);
        return new CryptoData(enc);
      } catch (e) {
        return new CryptoData(Buffer.alloc(0));
      }
    },

    decrypt(ciphertext, key, options = {}) {
      try {
        let cipherBuf;
        if (typeof ciphertext === 'string') {
          const trimmed = ciphertext.trim();
          if (/^[0-9a-fA-F]{32,}$/.test(trimmed)) {
            cipherBuf = Buffer.from(trimmed, 'hex');
          } else {
            cipherBuf = Buffer.from(trimmed, 'base64');
          }
        } else {
          cipherBuf = toBuffer(ciphertext);
        }

        let keyBuf = toBuffer(key);
        if (keyBuf.length < 16) {
          const padded = Buffer.alloc(16, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 16 && keyBuf.length < 24) {
          const padded = Buffer.alloc(24, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 24 && keyBuf.length < 32) {
          const padded = Buffer.alloc(32, 0); keyBuf.copy(padded); keyBuf = padded;
        } else if (keyBuf.length > 32) {
          keyBuf = keyBuf.subarray(0, 32);
        }

        const modeStr = String(options.mode || 'AES/CBC/PKCS7Padding');
        const cipherAlg = resolveCipherAlgorithm('AES', keyBuf.length, modeStr);
        let ivBuf = options.iv ? toBuffer(options.iv) : Buffer.alloc(16, 0);
        if (ivBuf.length < 16) {
          const padded = Buffer.alloc(16, 0); ivBuf.copy(padded); ivBuf = padded;
        } else if (ivBuf.length > 16) {
          ivBuf = ivBuf.subarray(0, 16);
        }

        const isEcb = cipherAlg.includes('-ecb');
        const decipher = isEcb ? crypto.createDecipheriv(cipherAlg, keyBuf, null) : crypto.createDecipheriv(cipherAlg, keyBuf, ivBuf);
        decipher.setAutoPadding(!modeStr.toUpperCase().includes('NOPADDING'));

        const dec = Buffer.concat([decipher.update(cipherBuf), decipher.final()]);
        return new CryptoData(dec);
      } catch (e) {
        return new CryptoData(Buffer.alloc(0));
      }
    }
  };

  function executeDesPure(operation, cipherType, input, key, options = {}) {
    if (!CryptoJS) return new CryptoData(Buffer.alloc(0));
    try {
      const modeStr = String(options.mode || '').toUpperCase();
      const isEcb = modeStr.includes('ECB') || (!options.iv && !modeStr.includes('CBC'));
      const isNoPadding = modeStr.includes('NOPADDING');
      const cryptoMode = isEcb ? CryptoJS.mode.ECB : CryptoJS.mode.CBC;
      const cryptoPad = isNoPadding ? CryptoJS.pad.NoPadding : CryptoJS.pad.Pkcs7;

      const keyBuf = toBuffer(key);
      const keyWords = bufferToCryptoJS(keyBuf);
      const cipherEngine = cipherType === 'DESede' ? CryptoJS.TripleDES : CryptoJS.DES;

      const cfg = { mode: cryptoMode, padding: cryptoPad };
      if (!isEcb && options.iv) {
        cfg.iv = bufferToCryptoJS(toBuffer(options.iv));
      }

      if (operation === 'encrypt') {
        const plainBuf = toBuffer(input);
        const plainWords = bufferToCryptoJS(plainBuf);
        const encrypted = cipherEngine.encrypt(plainWords, keyWords, cfg);
        return new CryptoData(cryptoJSToBuffer(encrypted.ciphertext));
      } else {
        let cipherWords;
        if (typeof input === 'string') {
          const trimmed = input.trim();
          if (/^[0-9a-fA-F]{16,}$/.test(trimmed)) {
            cipherWords = CryptoJS.enc.Hex.parse(trimmed);
          } else {
            cipherWords = CryptoJS.enc.Base64.parse(trimmed);
          }
        } else {
          cipherWords = bufferToCryptoJS(toBuffer(input));
        }
        const decrypted = cipherEngine.decrypt({ ciphertext: cipherWords }, keyWords, cfg);
        return new CryptoData(cryptoJSToBuffer(decrypted));
      }
    } catch (_) {
      return new CryptoData(Buffer.alloc(0));
    }
  }

  const DES = {
    encrypt(plaintext, key, options = {}) {
      const modeStr = String(options.mode || '').toUpperCase();
      const isEcb = modeStr.includes('ECB') || (!options.iv && !modeStr.includes('CBC'));
      if (crypto) {
        try {
          const plainBuf = toBuffer(plaintext);
          let keyBuf = toBuffer(key);
          if (keyBuf.length < 8) {
            const p = Buffer.alloc(8, 0); keyBuf.copy(p); keyBuf = p;
          } else if (keyBuf.length > 8) {
            keyBuf = keyBuf.subarray(0, 8);
          }
          const alg = isEcb ? 'des-ecb' : 'des-cbc';
          const ivBuf = isEcb ? null : (options.iv ? toBuffer(options.iv).subarray(0, 8) : Buffer.alloc(8, 0));
          const cipher = crypto.createCipheriv(alg, keyBuf, ivBuf);
          cipher.setAutoPadding(!modeStr.includes('NOPADDING'));
          return new CryptoData(Buffer.concat([cipher.update(plainBuf), cipher.final()]));
        } catch (_) {
          // OpenSSL 3 legacy algorithm unsupported -> fallback to CryptoJS pure JS
        }
      }
      return executeDesPure('encrypt', 'DES', plaintext, key, options);
    },
    decrypt(ciphertext, key, options = {}) {
      const modeStr = String(options.mode || '').toUpperCase();
      const isEcb = modeStr.includes('ECB') || (!options.iv && !modeStr.includes('CBC'));
      if (crypto) {
        try {
          let cipherBuf;
          if (typeof ciphertext === 'string') {
            const trimmed = ciphertext.trim();
            if (/^[0-9a-fA-F]{16,}$/.test(trimmed)) {
              cipherBuf = Buffer.from(trimmed, 'hex');
            } else {
              cipherBuf = Buffer.from(trimmed, 'base64');
            }
          } else {
            cipherBuf = toBuffer(ciphertext);
          }
          let keyBuf = toBuffer(key);
          if (keyBuf.length < 8) {
            const p = Buffer.alloc(8, 0); keyBuf.copy(p); keyBuf = p;
          } else if (keyBuf.length > 8) {
            keyBuf = keyBuf.subarray(0, 8);
          }
          const alg = isEcb ? 'des-ecb' : 'des-cbc';
          const ivBuf = isEcb ? null : (options.iv ? toBuffer(options.iv).subarray(0, 8) : Buffer.alloc(8, 0));
          const decipher = crypto.createDecipheriv(alg, keyBuf, ivBuf);
          decipher.setAutoPadding(!modeStr.includes('NOPADDING'));
          return new CryptoData(Buffer.concat([decipher.update(cipherBuf), decipher.final()]));
        } catch (_) {
          // OpenSSL 3 legacy algorithm unsupported -> fallback to CryptoJS pure JS
        }
      }
      return executeDesPure('decrypt', 'DES', ciphertext, key, options);
    }
  };

  const DESede = {
    encrypt(plaintext, key, options = {}) {
      const modeStr = String(options.mode || '').toUpperCase();
      const isEcb = modeStr.includes('ECB') || (!options.iv && !modeStr.includes('CBC'));
      if (crypto) {
        try {
          const plainBuf = toBuffer(plaintext);
          let keyBuf = toBuffer(key);
          if (keyBuf.length < 24) {
            const p = Buffer.alloc(24, 0); keyBuf.copy(p); keyBuf = p;
          } else if (keyBuf.length > 24) {
            keyBuf = keyBuf.subarray(0, 24);
          }
          const alg = isEcb ? 'des-ede3' : 'des-ede3-cbc';
          const ivBuf = isEcb ? null : (options.iv ? toBuffer(options.iv).subarray(0, 8) : Buffer.alloc(8, 0));
          const cipher = crypto.createCipheriv(alg, keyBuf, ivBuf);
          cipher.setAutoPadding(!modeStr.includes('NOPADDING'));
          return new CryptoData(Buffer.concat([cipher.update(plainBuf), cipher.final()]));
        } catch (_) {}
      }
      return executeDesPure('encrypt', 'DESede', plaintext, key, options);
    },
    decrypt(ciphertext, key, options = {}) {
      const modeStr = String(options.mode || '').toUpperCase();
      const isEcb = modeStr.includes('ECB') || (!options.iv && !modeStr.includes('CBC'));
      if (crypto) {
        try {
          let cipherBuf;
          if (typeof ciphertext === 'string') {
            const trimmed = ciphertext.trim();
            if (/^[0-9a-fA-F]{16,}$/.test(trimmed)) {
              cipherBuf = Buffer.from(trimmed, 'hex');
            } else {
              cipherBuf = Buffer.from(trimmed, 'base64');
            }
          } else {
            cipherBuf = toBuffer(ciphertext);
          }
          let keyBuf = toBuffer(key);
          if (keyBuf.length < 24) {
            const p = Buffer.alloc(24, 0); keyBuf.copy(p); keyBuf = p;
          } else if (keyBuf.length > 24) {
            keyBuf = keyBuf.subarray(0, 24);
          }
          const alg = isEcb ? 'des-ede3' : 'des-ede3-cbc';
          const ivBuf = isEcb ? null : (options.iv ? toBuffer(options.iv).subarray(0, 8) : Buffer.alloc(8, 0));
          const decipher = crypto.createDecipheriv(alg, keyBuf, ivBuf);
          decipher.setAutoPadding(!modeStr.includes('NOPADDING'));
          return new CryptoData(Buffer.concat([decipher.update(cipherBuf), decipher.final()]));
        } catch (_) {}
      }
      return executeDesPure('decrypt', 'DESede', ciphertext, key, options);
    }
  };

  const MD5 = (data) => new CryptoData(crypto ? crypto.createHash('md5').update(toBuffer(data)).digest() : Buffer.alloc(0));
  const SHA1 = (data) => new CryptoData(crypto ? crypto.createHash('sha1').update(toBuffer(data)).digest() : Buffer.alloc(0));
  const SHA256 = (data) => new CryptoData(crypto ? crypto.createHash('sha256').update(toBuffer(data)).digest() : Buffer.alloc(0));

  const CryptoUtil = {
    Data,
    Digest,
    AES,
    DES,
    DESede,
    MD5,
    SHA1,
    SHA256,
    CryptoData
  };

  if (typeof $ !== 'undefined' && $) {
    $.exports = CryptoUtil;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = CryptoUtil;
  }
  if (typeof globalThis !== 'undefined') {
    globalThis.CryptoUtil = CryptoUtil;
    globalThis._base64 = globalThis._base64 || { DEFAULT: 0, NO_PADDING: 1, NO_WRAP: 2, CRLF: 4, URL_SAFE: 8 };
  }

  return CryptoUtil;
})();
