/**
 * Android Base64 兼容垫片 (android.util.Base64 与 _base64 别名)
 */

function createAndroidBase64() {
  const flags = {
    DEFAULT: 0,
    NO_PADDING: 1,
    NO_WRAP: 2,
    CRLF: 4,
    URL_SAFE: 8,
    NO_CLOSE: 16,
  };

  function toBuffer(input) {
    if (Buffer.isBuffer(input)) return input;
    if (input instanceof Uint8Array || Array.isArray(input)) return Buffer.from(input);
    return Buffer.from(String(input ?? ''), 'utf8');
  }

  function decode(input, flagVal = 0) {
    if (input === null || input === undefined) return Buffer.alloc(0);
    let str = '';
    if (typeof input === 'string') {
      str = input.trim();
    } else if (Buffer.isBuffer(input) || input instanceof Uint8Array) {
      str = Buffer.from(input).toString('utf8').trim();
    } else {
      str = String(input).trim();
    }
    const f = Number(flagVal) || 0;
    if ((f & 8) !== 0) {
      str = str.replace(/-/g, '+').replace(/_/g, '/');
    }
    const remainder = str.length % 4;
    if (remainder === 2) str += '==';
    else if (remainder === 3) str += '=';

    try {
      return Buffer.from(str, 'base64');
    } catch (_) {
      return Buffer.alloc(0);
    }
  }

  function encodeToString(input, flagVal = 0) {
    if (input === null || input === undefined) return '';
    const buf = toBuffer(input);
    let b64 = buf.toString('base64');
    const f = Number(flagVal) || 0;
    if (f & 8) {
      b64 = b64.replace(/\+/g, '-').replace(/\//g, '_');
    }
    if (f & 1) {
      b64 = b64.replace(/=+$/, '');
    }
    return b64;
  }

  function decodeToString(input, flagVal = 0) {
    return decode(input, flagVal).toString('utf8');
  }

  function encode(input, flagVal = 0) {
    const str = encodeToString(input, flagVal);
    return Buffer.from(str, 'utf8');
  }

  return {
    ...flags,
    decode,
    decodeToString,
    encodeToString,
    encode,
  };
}

function createJavaUtilBase64(androidBase64) {
  return {
    getDecoder: () => ({
      decode: (input) => androidBase64.decode(input, 0),
    }),
    getEncoder: () => ({
      encodeToString: (input) => androidBase64.encodeToString(input, 0),
      encode: (input) => androidBase64.encode(input, 0),
    }),
    getUrlDecoder: () => ({
      decode: (input) => androidBase64.decode(input, 8),
    }),
    getUrlEncoder: () => ({
      encodeToString: (input) => androidBase64.encodeToString(input, 8),
    }),
  };
}

module.exports = {
  createAndroidBase64,
  createJavaUtilBase64,
};
