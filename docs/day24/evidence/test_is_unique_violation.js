/**
 * Day 24 余力加练 · isUniqueViolation() 修复前后对比（纯函数，不连库）
 * 跑法：node docs/day24/evidence/test_is_unique_violation.js
 *
 * 修复前：status===409 直接 return true → 外键违规 23503 被误判成唯一冲突。
 * 修复后：409 还要看错误码是不是 23505。
 */
const path = require('path');
const r = require(path.join(__dirname, '..', '..', '..', 'deploy', 'db', 'rest.js'));

const FIXED = r.isUniqueViolation;   // 当前（修复后）的实现

// 修复前的实现（原样抄下来，用来做「前后对比」）
function isUniqueViolation_OLD(status, data) {
  if (status === 409) return true;
  if (data && typeof data === 'object' && String(data.code || '').indexOf('23505') !== -1) return true;
  return false;
}

const cases = [
  ['唯一冲突', 409, { code: 'DATABASE_23505' }, true],
  ['外键违规', 409, { code: 'DATABASE_23503' }, false],
  ['409 无码', 409, null, false],
  ['400 无码', 400, null, false],
  ['201 成功', 201, null, false],
  ['其它码', 422, { code: 'DATABASE_23503' }, false],
];

let p = 0, f = 0;
function pad(s, n) {
  s = String(s);
  while (s.length < n) s += ' ';
  return s;
}
console.log(pad('场景', 12) + pad('status', 8) + pad('错误码', 20) + pad('修复前', 9) + pad('修复后', 9) + pad('期望', 8) + '结果');
console.log('-'.repeat(78));
for (const [tag, st, d, exp] of cases) {
  const code = (d && d.code) || '-';
  const oldV = isUniqueViolation_OLD(st, d);
  const newV = FIXED(st, d);
  const ok = newV === exp;
  ok ? p++ : f++;
  console.log(pad(tag, 12) + pad(st, 8) + pad(code, 20) + pad(oldV, 9) + pad(newV, 9) + pad(exp, 8) + (ok ? 'OK' : 'NG'));
}
console.log('-'.repeat(78));
console.log('修复后：%d PASS / %d FAIL', p, f);
console.log('');
console.log('对照点：第 2 行「外键违规」—— 修复前 true（误判），修复后 false（正确）。');
