const test = require('node:test');
const assert = require('node:assert/strict');
const {
  attachCryptoAndCodecBuiltins,
  createAndroidBase64,
  CryptoUtil,
} = require('../src/index');

test('hiker-shims: attachCryptoAndCodecBuiltins attaches all Android and Java polyfills', () => {
  const sandbox = {};
  attachCryptoAndCodecBuiltins(sandbox);

  // 1. Android Base64
  assert.ok(sandbox.android.util.Base64, 'android.util.Base64 should exist');
  assert.equal(typeof sandbox.android.util.Base64.encodeToString, 'function');
  assert.equal(typeof sandbox._base64.decode, 'function');

  const b64 = sandbox.android.util.Base64.encodeToString(Buffer.from('hello deepcloud'), sandbox.android.util.Base64.NO_WRAP);
  assert.equal(b64, 'aGVsbG8gZGVlcGNsb3Vk');

  const decoded = sandbox._base64.decode(b64, sandbox._base64.NO_WRAP);
  assert.equal(decoded.toString('utf8'), 'hello deepcloud');

  // 2. Java String
  const jstr = new sandbox.java.lang.String(Buffer.from('hello world'));
  assert.equal(jstr.toString(), 'hello world');
  assert.equal(jstr.replaceAll('world', 'deepcloud').toString(), 'hello deepcloud');

  // 3. Java Arrays
  const sliced = sandbox.java.util.Arrays.copyOfRange(Buffer.from([1, 2, 3, 4, 5]), 1, 3);
  assert.deepEqual(Array.from(sliced), [2, 3]);

  // 4. JCE AES Cipher
  const cipher = sandbox.javax.crypto.Cipher.getInstance('AES/CBC/PKCS5Padding');
  const keySpec = new sandbox.javax.crypto.spec.SecretKeySpec(Buffer.from('0123456789abcdef'), 'AES');
  const ivSpec = new sandbox.javax.crypto.spec.IvParameterSpec(Buffer.from('abcdef0123456789'));

  // Encrypt
  cipher.init(sandbox.javax.crypto.Cipher.ENCRYPT_MODE, keySpec, ivSpec);
  const encrypted = cipher.doFinal(Buffer.from('secret payload', 'utf8'));
  assert.ok(encrypted.length > 0);

  // Decrypt
  cipher.init(sandbox.javax.crypto.Cipher.DECRYPT_MODE, keySpec, ivSpec);
  const decrypted = cipher.doFinal(encrypted);
  assert.equal(decrypted.toString('utf8'), 'secret payload');

  // 5. CryptoUtil
  assert.ok(sandbox.CryptoUtil.AES, 'CryptoUtil.AES should exist');
  assert.equal(typeof sandbox.CryptoUtil.AES.encrypt, 'function');
  assert.equal(typeof sandbox.CryptoUtil.AES.decrypt, 'function');

  // 6. Extended Java Shims: StringBuilder, System.out, Collections, Date, File
  const sb = new sandbox.java.lang.StringBuilder('init_');
  sb.append('val');
  assert.equal(sb.toString(), 'init_val');

  let loggedMsg = '';
  sandbox.log = (msg) => { loggedMsg = msg; };
  sandbox.java.lang.System.out.println('test-system-out');
  assert.equal(loggedMsg, 'test-system-out');

  const list = [3, 1, 2];
  sandbox.java.util.Collections.sort(list);
  assert.deepEqual(list, [1, 2, 3]);

  const date = new sandbox.java.util.Date(1600000000000);
  assert.equal(date.getTime(), 1600000000000);

  const file = new sandbox.java.io.File('/dummy/test.txt');
  assert.equal(file.getName(), 'test.txt');

  // 7. SettingItem & rule helpers
  assert.equal(typeof sandbox.SettingItem, 'function', 'sandbox.SettingItem should be defined');
  const item1 = sandbox.SettingItem('分组列表设置', '按源接口的分组');
  assert.equal(item1.getTitle(), '分组列表设置');
  assert.equal(item1.getDesc(), '按源接口的分组');
  item1.setDesc('新分组');
  assert.equal(item1.getDesc(), '新分组');

  const itemSwitch = sandbox.SettingItem('开关项', true);
  assert.equal(itemSwitch.isChecked(), true);
  itemSwitch.setSelected(-1);
  assert.equal(itemSwitch.isChecked(), false);

  const itemDivider = sandbox.SettingItem();
  assert.equal(itemDivider.isDivider, true);
});

test('hiker-shims: Packages safe proxy prevents TypeError on non-existent Java packages and supports chaining', () => {
  const sandbox = {};
  attachCryptoAndCodecBuiltins(sandbox);

  const unknown = sandbox.Packages.com.example.nonexistent.util.Helper;
  assert.doesNotThrow(() => {
    const res = unknown();
    assert.ok(res !== undefined);
    // 验证无限链式调用
    const chained = unknown().foo().bar().baz();
    assert.ok(chained !== undefined);
    assert.equal(chained.size(), 0);
    assert.equal(chained.isEmpty(), true);
  });
});

test('hiker-shims: Android Uri, Pattern and BigDecimal work seamlessly', () => {
  const sandbox = {};
  attachCryptoAndCodecBuiltins(sandbox);

  // 1. android.net.Uri
  const uri = sandbox.android.net.Uri.parse('https://deepcloud.io/api?page=1&size=20');
  assert.equal(uri.getHost(), 'deepcloud.io');
  assert.equal(uri.getQueryParameter('page'), '1');
  assert.equal(uri.getQueryParameter('size'), '20');

  // 2. Pattern & Matcher
  const pattern = sandbox.Pattern.compile('\\d+');
  const matcher = pattern.matcher('id=9988');
  assert.equal(matcher.find(), true);
  assert.equal(matcher.group(0), '9988');

  // 3. BigDecimal
  const bd = new sandbox.BigDecimal('10.5').add(new sandbox.BigDecimal('2.5'));
  assert.equal(bd.toString(), '13');
});

