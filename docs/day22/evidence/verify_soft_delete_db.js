/* eslint-disable no-console */
/**
 * Day 22 余力加练 · 数据层直测 —— 软删除（不依赖 HTTP 服务）
 * ---------------------------------------------------------------------------
 * 为什么需要这个脚本（和 verify_soft_delete.py 的分工）：
 *   · verify_soft_delete.py 走 HTTP，验的是「接口对外的样子」。但它要求
 *     有一个人在终端里把 server.js 起起来 —— 服务是会话级的，AI 会话里
 *     起的进程活不过一次工具调用。
 *   · 本脚本**直接 require deploy/db/index.js**，绕过 HTTP 层，
 *     所以不需要服务在跑，能在任何环境里立刻验证软删除的**数据层逻辑**。
 *   · 两者互补：本地快速自检用这个；正式取证用 python 那个。
 *
 * 跑法（在项目根）：
 *     node docs/day22/evidence/verify_soft_delete_db.js
 *
 * ⚠️ 必须先加载 .env（否则掉到快照通道，不是真库）。在 bash 里：
 *     set -a && . ./deploy/.env && set +a && node docs/day22/evidence/verify_soft_delete_db.js
 * ⚠️ 本机有代理环境变量，Node 的 fetch 会把 127.0.0.1 也塞进代理，
 *    跑之前清掉：env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy node ...
 *
 * ★ 注意 addFavorite 的调用方式：它收的是**一个对象**
 *     db.addFavorite({ userId, workId, note })
 *   不是三个位置参数 —— 传错会得到 DATABASE_23502（work_id 为 null）。
 */
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const db = require(path.join(ROOT, 'deploy', 'db', 'index.js'));

const USER = 'local';
const WORK = 'art-6';        // 存在于 works 表的真实作品（不存在会撞外键 23503）

let pass = 0;
let fail = 0;
function ck(name, cond, extra) {
  if (cond) { pass += 1; console.log('  [PASS] ' + name); }
  else { fail += 1; console.log('  [FAIL] ' + name + (extra ? '  >> ' + extra : '')); }
}

(async function main() {
  console.log('=== 数据层直测：软删除（不依赖 HTTP 服务）===');
  console.log('work = ' + WORK + '   user = ' + USER + '\n');

  const before = await db.getFavorites(USER, 50);
  const beforeIds = (before.items || []).map(function (x) { return x.id; });
  console.log('起始：' + beforeIds.length + ' 条，source = ' + before.source + '\n');

  let createdId = null;
  let revivedId = null;

  try {
    // 1) 新增
    console.log('【1】新增');
    const c = await db.addFavorite({ userId: USER, workId: WORK, note: '软删测试' });
    ck('新增成功', c.created === true, JSON.stringify(c).slice(0, 200));
    createdId = c.item && c.item.id;
    console.log('    → id = ' + createdId + '  source = ' + c.source);

    // 2) 列表可见
    console.log('\n【2】列表应可见');
    let l = await db.getFavorites(USER, 50);
    let ids = (l.items || []).map(function (x) { return x.id; });
    ck('列表含新记录', ids.indexOf(createdId) >= 0, 'ids=' + ids);
    ck('总数 +1', ids.length === beforeIds.length + 1,
      ids.length + ' vs ' + (beforeIds.length + 1));

    // 3) 软删
    console.log('\n【3】软删除（打 is_deleted 标记）');
    const d = await db.deleteFavorite(createdId);
    ck('删除返回 deleted = true', d.deleted === true, JSON.stringify(d).slice(0, 200));
    ck('带回被删数据（凭证）', !!(d.item && d.item.workId === WORK),
      JSON.stringify(d.item || {}).slice(0, 160));

    // 4) ★ 列表应消失
    console.log('\n【4】★ 列表应消失（软删对用户可见的效果）');
    l = await db.getFavorites(USER, 50);
    ids = (l.items || []).map(function (x) { return x.id; });
    ck('列表已看不到', ids.indexOf(createdId) === -1, 'ids=' + ids);
    ck('总数回到起始', ids.length === beforeIds.length,
      ids.length + ' vs ' + beforeIds.length);

    // 5) 二次删 → notFound（幂等）
    console.log('\n【5】二次删同一 id → notFound（软删行视同不存在）');
    const d2 = await db.deleteFavorite(createdId);
    ck('二次删 notFound = true', d2.notFound === true, JSON.stringify(d2).slice(0, 160));

    // 6) PATCH 已软删的行 → notFound
    //    ★ 必须放在「复活」之前测：复活之后这条又是活行了，改它会成功。
    console.log('\n【6】PATCH 已软删的行 → notFound（已删的行不该还能改）');
    const p = await db.updateFavorite(createdId, { note: '试图改已删的' });
    ck('改已软删行 notFound = true', p.notFound === true, JSON.stringify(p).slice(0, 160));

    // 7) ★★ 重新收藏 → 复活，不撞唯一约束
    console.log('\n【7】★★ 重新收藏同一作品（软删除最关键的坑）');
    const re = await db.addFavorite({ userId: USER, workId: WORK, note: '复活测试' });
    ck('重新收藏成功（没撞 409）', re.created === true, JSON.stringify(re).slice(0, 250));
    revivedId = re.item && re.item.id;
    console.log('    → 新 id = ' + revivedId + '（原 id = ' + createdId + '）');
    ck('复活复用的是同一行（id 不变）', revivedId === createdId,
      'revived=' + revivedId + ' original=' + createdId);

    // 8) 列表又能看到
    console.log('\n【8】列表应重新出现');
    l = await db.getFavorites(USER, 50);
    ids = (l.items || []).map(function (x) { return x.id; });
    ck('列表又可见', ids.indexOf(revivedId) >= 0, 'ids=' + ids);
    ck('总数 +1', ids.length === beforeIds.length + 1,
      ids.length + ' vs ' + (beforeIds.length + 1));

    // 9) 复活后能正常改备注（证明它确实是"活的"）
    console.log('\n【9】复活后可正常 PATCH（证明复活的是活行）');
    const p2 = await db.updateFavorite(revivedId, { note: '复活后改的' });
    ck('复活后改备注成功', p2.updated === true && p2.item && p2.item.note === '复活后改的',
      JSON.stringify(p2).slice(0, 200));
  } finally {
    // 10) 清理
    console.log('\n【10】清理测试数据');
    if (revivedId != null) await db.deleteFavorite(revivedId);
    else if (createdId != null) await db.deleteFavorite(createdId);

    const after = await db.getFavorites(USER, 50);
    const afterIds = (after.items || []).map(function (x) { return x.id; });
    const extra = afterIds.filter(function (i) { return beforeIds.indexOf(i) < 0; });
    const missing = beforeIds.filter(function (i) { return afterIds.indexOf(i) < 0; });
    ck('库里没多出记录', extra.length === 0, 'extra=' + extra);
    ck('库里没少记录', missing.length === 0, 'missing=' + missing);
  }

  console.log('\n=== 结果：' + pass + ' 通过 / ' + fail + ' 失败 ===');
  process.exit(fail === 0 ? 0 : 1);
})().catch(function (e) {
  console.log('ERR ' + (e && e.stack ? e.stack : e));
  process.exit(1);
});
