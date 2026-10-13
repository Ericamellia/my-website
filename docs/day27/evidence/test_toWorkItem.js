// Day 27 修复验证：toWorkItem 对两种列名的兼容性
//
// 为什么用纯函数测试：本地没有真库凭据，起服务也走不通 rest 通道；
// 而这个 bug 的本质就是「mapper 读错了列名」——
// 直接喂两种输入给 mapper，看输出，是最直接的验证。
'use strict';
const path = require('path');
const MAPPER = path.join(__dirname, '..', '..', '..', 'deploy', 'db', 'mappers.js');
const mappers = require(MAPPER);

let pass = 0, fail = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (ok) { pass++; console.log('  [PASS] ' + name); }
  else { fail++; console.log('  [FAIL] ' + name + '\n         期望=' + JSON.stringify(expected) + ' 实际=' + JSON.stringify(actual)); }
}

console.log('='.repeat(64));
console.log('toWorkItem 列名兼容性验证');
console.log('='.repeat(64));
console.log();

// ── 场景1：真库返回的是 circle 列（线上实际情况） ──
console.log('场景1：输入列名 = circle（真库实际列名）');
const out1 = mappers.toWorkItem({
  work_id: 'music-1', category: 'music', name: 'ハルトマンの妖怪少女',
  circle: 'COOL&CREATE',            // ← 真库叫这个
  creator: '有泉', year: 2007,
  characters: ['西行寺幽幽子'], tags: ['妖妖梦'],
  popularity: 16800, views: 5921,
  cover: 'assets/music/cover1.jpg',
  source_url: 'https://thwiki.cc/x'
});
check('circle 有值', out1.circle, 'COOL&CREATE');
check('name 有值', out1.name, 'ハルトマンの妖怪少女');
check('id 是板块内数字 1', out1.id, 1);
check('workId 保留原串', out1.workId, 'music-1');
console.log('  输出 circle =', JSON.stringify(out1.circle));
console.log();

// ── 场景2：pg 通道若真返回 circle_name（兼容性） ──
console.log('场景2：输入列名 = circle_name（兼容旧写法）');
const out2 = mappers.toWorkItem({
  work_id: 'music-2', category: 'music', name: 'チルノのパーフェクトさんすう教室',
  circle_name: 'IOSYS',             // ← 旧代码期望的列名
  creator: 'ARM', year: 2009,
  characters: ['チルノ'], tags: ['紅魔郷'],
  popularity: 25000, views: 8800,
  cover: 'assets/music/cover2.jpg'
});
check('circle 有值（兼容路径）', out2.circle, 'IOSYS');
console.log('  输出 circle =', JSON.stringify(out2.circle));
console.log();

// ── 场景3：两列都有时优先用 circle_name ──
console.log('场景3：两列都有 → 优先 circle_name');
const out3 = mappers.toWorkItem({
  work_id: 'music-3', name: 'x', circle: 'A', circle_name: 'B'
});
check('优先 circle_name', out3.circle, 'B');
console.log();

// ── 场景4：两列都没有（数据异常） → undefined，不能崩 ──
console.log('场景4：两列都缺（异常数据）→ 不崩');
const out4 = mappers.toWorkItem({ work_id: 'music-4', name: 'x' });
check('circle 为 undefined 而非抛错', out4.circle, undefined);
check('其他字段仍正常', out4.name, 'x');
console.log();

// ── 场景5：回归 —— 确认其他字段没被改坏 ──
console.log('场景5：回归检查其他字段');
const out5 = mappers.toWorkItem({
  work_id: 'video-2', category: 'video', name: 'v',
  circle: 'C', creator: 'cu', year: 2020,
  characters: ['a'], tags: ['t'],
  popularity: 100, views: 200,
  cover: 'c.jpg', source_url: 's',
  video_type: '手书', video_platform: 'bilibili',
  video_url: 'https://b23.tv/x', bvid: 'BV1xx'
});
check('category', out5.category, 'video');
check('creator', out5.creator, 'cu');
check('year', out5.year, 2020);
check('type（video 专属）', out5.type, '手书');
check('platform（video 专属）', out5.platform, 'bilibili');
check('bvid', out5.bvid, 'BV1xx');
check('url 与 video_url 都有', out5.url === out5.video_url && out5.url === 'https://b23.tv/x', true);
check('characters 是数组', Array.isArray(out5.characters), true);
check('tags 是数组', Array.isArray(out5.tags), true);
console.log();

console.log('='.repeat(64));
console.log('汇总：通过 ' + pass + ' 项，失败 ' + fail + ' 项');
console.log('='.repeat(64));
process.exit(fail === 0 ? 0 : 1);
