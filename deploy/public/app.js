'use strict';
/**
 * 前端页面脚本（Day 17 读接口 → Day 18 加写接口 → Day 20 跨域接线）
 * ------------------------------------------------------------------
 * 这一版真实调用四个接口：
 *   GET  /api/health      → 链路 + 数据源状态
 *   POST /api/favorites   → 新增收藏（Day 18 重点：看防重复 + 防错输）
 *   GET  /api/favorites   → 收藏列表（写入后刷新，能看见库里多了那一行）
 *   GET  /api/hot         → 热搜榜
 *
 * 为什么前端要跟着改：
 *   Day 18 的目标是「证明写接口真的能写、且挡得住脏请求」，
 *   所以页面上要能现场发 POST、并把**接口返回的原始 JSON 原样显示出来**——
 *   这正是当天那张「POST 成功返回」截图要拍的东西。
 *   同时也让「重复提交被拒」「缺字段被拒」能一键复现，不用敲 curl。
 *
 * ★ Day 20 新增：跨域接线
 *   health 卡片改为**直连 CloudBase 云函数公网地址**（而不是本站相对路径）。
 *   目的：让 F12 里能亲眼看到「请求打到了公网云函数域名」，
 *   并借此暴露/验证**跨域（CORS）**这一关。
 */

/* ===========================================================================
 * ★ Day 20：接口地址配置
 * ===========================================================================
 * 关键区别（今天要认出的那件事）：
 *   API_BASE  —— 本站相对路径，走**发布平台的 Node 服务**（同源，无跨域）
 *   FN_BASE   —— CloudBase 云函数公网地址，走**云函数网关**（跨域，需 CORS 放行）
 *
 * 为什么 health 要单独走云函数：
 *   云函数是真的跑在 CloudBase 上的独立后端，域名与本站不同 →
 *   浏览器会先发一次 OPTIONS 预检（preflight），这就是「跨域」的现场。
 *
 * ⚠️ 用哪个云函数地址？（Day 20 踩坑，务必看）
 *   CloudBase 上同一个函数有**两条通道**，长得像但不是一回事：
 *
 *   ① {envId}.api.tcloudbasegateway.com/v1/functions/{name}?webfn=true
 *      —— **管理端 API 网关**。给服务端/CLI 调用，**必须带凭证**
 *         （service_role Key 或登录态）。匿名调用会依次被
 *         401 MISSING_CREDENTIALS → 403 EXCEED_AUTHORITY 挡下。
 *         ❌ 不适合浏览器前端。
 *
 *   ② {envId}.service.tcloudbase.com/api/health
 *      —— **云函数 HTTP 访问服务**（`cloudbaserc.json` 里配的 http trigger）。
 *         面向公网，**不需要任何凭证**，且自带 `Access-Control-Allow-Origin: *`。
 *         ✅ 这才是浏览器该用的地址。
 *
 * envId 来源：cloudbase/cloudbaserc.json 的 envId 字段。
 * 换环境时只改这一处即可。
 */
var TCB_ENV_ID = 'ericamellia24-d2gk0ftukc71292c5';

/** 本站业务接口（Node 服务，同源）。 */
var API_BASE = '';

/** CloudBase 云函数公网入口（跨域，无需凭证）。
 *  走「云函数 HTTP 访问服务」，路径即 cloudbaserc.json 的 http trigger `/api/health`。 */
var FN_BASE = 'https://' + TCB_ENV_ID + '.service.tcloudbase.com/api/health';

/** ① 统一的 fetch 封装：拿文本 + 状态码 + 耗时，方便出错时定位。 */
function getJson(url) {
  var t0 = Date.now();
  return fetch(url, { cache: 'no-store' }).then(function (r) {
    var ms = Date.now() - t0;
    return r.text().then(function (txt) {
      var data = null;
      try { data = JSON.parse(txt); } catch (e) { data = null; }
      return { status: r.status, txt: txt, data: data, ms: ms, url: url };
    });
  });
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m];
  });
}

/** ② 把播放量格式化成「1.6亿」「12345」这种，便于阅读。 */
function fmtNum(n) {
  n = Number(n) || 0;
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
  if (n >= 10000) return (n / 10000).toFixed(1) + '万';
  return String(n);
}

function fmtTime(ts) {
  if (!ts) return '';
  var d = new Date(Number(ts) * 1000);
  var p = function (x) { return (x < 10 ? '0' : '') + x; };
  return (d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}

/** ③ 卡片外壳（复用 work 样式） */
function cardHtml(cover, coverText, title, meta, tags) {
  var cov = cover
    ? '<img class="cover" src="' + esc(cover) + '" alt="" referrerpolicy="no-referrer" ' +
      'style="width:100%;height:96px;object-fit:cover" onerror="this.style.display=\'none\'">'
    : '';
  var fallback = cover ? '' : '<div class="cover" style="background:#e8a0b0">' + esc(coverText) + '</div>';
  return '<article class="work">' + cov + fallback +
    '<div class="body"><h3>' + esc(title) + '</h3>' +
    '<p class="meta">' + meta + '</p>' +
    (tags && tags.length ? '<div class="tags">' + tags.map(function (t) {
      return '<span>' + esc(t) + '</span>';
    }).join('') + '</div>' : '') +
    '</div></article>';
}

// ===========================================================================
// 健康检查（★ Day 20：改为直连 CloudBase 云函数公网地址）
// ===========================================================================
/**
 * 余力加练：把「最后更新时间」显示在检查台上。
 * 记录**本地**完成这次检查的时刻（不是服务端时间）——
 * 因为它回答的是「我上一次看它是什么时候」，属于观察者视角。
 */
function fmtClock(d) {
  var p = function (x) { return (x < 10 ? '0' : '') + x; };
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
    ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

function setLastChecked(at, ms, ok) {
  var el = document.getElementById('hLastChecked');
  if (!el) return;
  el.textContent = '最后更新：' + fmtClock(at) +
    '（' + (ok ? '成功' : '失败') + ' · ' + ms + 'ms）';
}

function loadHealth() {
  var card = document.getElementById('healthCard');
  var badge = document.getElementById('hBadge');
  var out = document.getElementById('hJson');
  var meta = document.getElementById('hMeta');

  // 页面上一眼可见「请求打到哪了」——截图和 F12 互相印证
  var urlLine = document.getElementById('hUrl');
  if (urlLine) urlLine.textContent = FN_BASE;

  var t0 = Date.now();

  getJson(FN_BASE).then(function (res) {
    out.textContent = res.txt;
    var d = res.data;
    var ok = res.status === 200 && d && d.ok === true;
    card.classList.add(ok ? 'ok' : 'bad');
    badge.textContent = 'HTTP ' + res.status + (ok ? ' · 正常' : ' · 异常');
    meta.textContent = ok
      ? '来源=云函数 · env=' + d.env + ' · node=' + d.node +
        ' · uptime=' + d.uptimeSec + 's · 耗时 ' + res.ms + 'ms'
      : '返回不是预期的 JSON（若为 401/CORS，见下方提示）';
    setLastChecked(new Date(), Date.now() - t0, ok);
  }).catch(function (err) {
    // 跨域被拦时，fetch 抛 TypeError，message 通常是 "Failed to fetch"
    card.classList.add('bad');
    badge.textContent = '请求失败';
    meta.textContent = '跨域或网络被拦：' + String(err.message || err) +
      '（F12 Console 会有 CORS 提示）';
    out.textContent = String(err);
    setLastChecked(new Date(), Date.now() - t0, false);
  });
}

// ===========================================================================
// 热搜榜
// ===========================================================================
var hotState = { board: 'fresh' };

function loadHot() {
  var badge = document.getElementById('hotBadge');
  var meta = document.getElementById('hotMeta');
  var grid = document.getElementById('hotGrid');
  var url = API_BASE + '/api/hot?board=' + encodeURIComponent(hotState.board) + '&limit=12';

  grid.innerHTML = '';
  getJson(url).then(function (res) {
    var d = res.data;
    var ok = res.status === 200 && d && d.ok === true && Array.isArray(d.data);
    badge.textContent = 'HTTP ' + res.status + (ok ? ' · ' + d.data.length + ' 条' : ' · 异常');
    if (!ok) {
      meta.textContent = '接口返回异常：' + res.txt.slice(0, 200);
      return;
    }
    meta.textContent = '数据源=' + d.source +
      ' · 榜单=' + d.board +
      ' · 同步时间=' + (d.syncedAt || '—') +
      ' · 耗时 ' + res.ms + 'ms' +
      ' · ' + url;

    if (!d.data.length) {
      meta.textContent += '（本榜暂无数据）';
      return;
    }
    d.data.forEach(function (it) {
      grid.insertAdjacentHTML('beforeend', cardHtml(
        it.cover,
        '#' + it.rank,
        '#' + it.rank + ' ' + it.title,
        '播放 ' + fmtNum(it.play) + ' · 弹幕 ' + fmtNum(it.danmaku) +
          ' · ' + esc(it.author) + (it.publishedAt ? ' · ' + fmtTime(it.pubdate) : ''),
        [it.category, it.duration, it.bvid].filter(Boolean)
      ));
    });
  }).catch(function (err) {
    badge.textContent = '请求失败';
    meta.textContent = String(err);
  });
}

function switchBoard(b) {
  hotState.board = b;
  document.getElementById('tabFresh').setAttribute('aria-selected', String(b === 'fresh'));
  document.getElementById('tabHot').setAttribute('aria-selected', String(b === 'hot'));
  loadHot();
}

// ===========================================================================
// 收藏列表
// ===========================================================================
function loadFavorites() {
  var badge = document.getElementById('favBadge');
  var meta = document.getElementById('favMeta');
  var grid = document.getElementById('favGrid');
  var url = API_BASE + '/api/favorites?limit=20';

  grid.innerHTML = '';
  getJson(url).then(function (res) {
    var d = res.data;
    var ok = res.status === 200 && d && d.ok === true && Array.isArray(d.data);
    badge.textContent = 'HTTP ' + res.status + (ok ? ' · ' + d.count + ' 条' : ' · 异常');
    if (!ok) {
      meta.textContent = '接口返回异常：' + res.txt.slice(0, 200);
      return;
    }
    meta.textContent = '数据源=' + d.source + ' · userId=' + d.userId +
      ' · 耗时 ' + res.ms + 'ms · ' + url;

    d.data.forEach(function (it) {
      var tags = (it.tags || []).slice(0, 2).concat(it.characters || []).slice(0, 3);
      grid.insertAdjacentHTML('beforeend', cardHtml(
        it.cover && /^https?:/.test(it.cover) ? it.cover : '',
        it.category || '作品',
        it.name,
        esc(it.circle || '—') + ' · ' + (it.year || '—') +
          (it.note ? '<br>备注：' + esc(it.note) : ''),
        tags
      ));
      // 把「本次刚写入的那条」（id 最大）标记出来，截图时一眼可见
      var maxId = d.data.reduce(function (m, x) { return Math.max(m, Number(x.id) || 0); }, 0);
      if (Number(it.id) === maxId) {
        var last = grid.lastElementChild;
        if (last) {
          last.style.borderColor = '#3aa675';
          last.style.boxShadow = '0 0 0 2px rgba(58,166,117,.25)';
          var body = last.querySelector('.body');
          if (body) {
            body.insertAdjacentHTML('afterbegin',
              '<span class="new-mark">本次新增 #' + it.id + '</span>');
          }
        }
      }
    });
  }).catch(function (err) {
    badge.textContent = '请求失败';
    meta.textContent = String(err);
  });
}

// ===========================================================================
// POST /api/favorites —— 写接口验证（Day 18 重点）
// ===========================================================================

/**
 * 发一次 POST，并把结果原样显示在页面上。
 * 刻意**不做前端校验** —— 我们要看的就是后端的闸门挡不挡得住，
 * 前端先挡了反而验证不到服务端。
 */
function doPost(body) {
  var badge = document.getElementById('wBadge');
  var statusEl = document.getElementById('wStatus');
  var pre = document.getElementById('wJson');
  var t0 = Date.now();

  badge.textContent = '请求中…';
  pre.textContent = 'POST /api/favorites\n发送内容：' + JSON.stringify(body) + '\n\n等待响应…';

  fetch(API_BASE + '/api/favorites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(function (r) {
    var ms = Date.now() - t0;
    return r.text().then(function (txt) {
      var data = null;
      try { data = JSON.parse(txt); } catch (e) { data = null; }
      return { status: r.status, txt: txt, data: data, ms: ms };
    });
  }).then(function (res) {
    statusEl.textContent = 'HTTP ' + res.status + ' · 耗时 ' + res.ms + 'ms';

    // 徽章直观区分四种结局
    if (res.status === 201) {
      badge.textContent = '201 写入成功';
      badge.className = 'badge ok';
    } else if (res.status === 409) {
      badge.textContent = '409 重复提交被拒';
      badge.className = 'badge warn';
    } else {
      badge.textContent = res.status + ' 被拒';
      badge.className = 'badge bad';
    }

    pre.textContent = 'POST /api/favorites\n发送内容：' + JSON.stringify(body) +
      '\nHTTP ' + res.status + ' · ' + res.ms + 'ms\n\n' + res.txt;

    // 写入成功或被判重复，都刷新一下列表（能看到库里那条）
    if (res.status === 201 || res.status === 409) loadFavorites();
  }).catch(function (err) {
    badge.textContent = '请求失败';
    badge.className = 'badge bad';
    pre.textContent = 'POST /api/favorites\n\n请求失败：' + String(err);
  });
}

/** 收集表单 → 发 POST */
function postFromForm() {
  doPost({
    workId: document.getElementById('wWorkId').value,
    note: document.getElementById('wNote').value
  });
}

// ===========================================================================
// 初始化
// ===========================================================================
loadHealth();
loadHot();
loadFavorites();

document.getElementById('tabFresh').addEventListener('click', function () { switchBoard('fresh'); });
document.getElementById('tabHot').addEventListener('click', function () { switchBoard('hot'); });

document.getElementById('btnWrite').addEventListener('click', postFromForm);

// 「再点一次」= 用完全相同的 body 再发一遍，用来复现「重复提交被拒」
document.getElementById('btnDup').addEventListener('click', postFromForm);

// 空对象 → 触发「缺必填字段」
document.getElementById('btnMissing').addEventListener('click', function () { doPost({}); });

// 格式错的 workId → 触发格式校验
document.getElementById('btnBadFmt').addEventListener('click', function () {
  doPost({ workId: '这不是作品编号' });
});

document.getElementById('btnReload').addEventListener('click', loadFavorites);

// 余力加练：手动重跑一次云函数检查（会刷新「最后更新」时间）
document.getElementById('btnRecheck').addEventListener('click', function () {
  document.getElementById('healthCard').classList.remove('ok', 'bad');
  document.getElementById('hBadge').textContent = '检测中…';
  loadHealth();
});

// 截图/演示用：带 ?auto=1 打开时，页面自动发一次 POST，
// 这样浏览器地址栏截图里能同时看到「页面 + 真实写入结果」。
// ?auto=dup 则自动连发两次，第二发用来展示「重复提交被拒」。
(function () {
  var q = new URLSearchParams(location.search);
  var auto = q.get('auto');
  var focus = q.get('focus');

  // focus=fav：直接滚到收藏列表（截图「库里新增的那一行」用）
  if (focus === 'fav') {
    setTimeout(function () {
      var el = document.getElementById('favGrid');
      if (!el) return;
      // 滚到收藏列表区域：让卡片区完整进入视口（新增那条第 1 张带绿框高亮）
      var top = el.getBoundingClientRect().top + window.pageYOffset;
      window.scrollTo(0, Math.max(0, top - 90));
    }, 1800);
  }

  if (!auto) return;
  if (auto === 'dup') {
    // 连发两次相同请求：第一发应该 201，第二发应该 409
    doPost({ workId: 'art-2', note: 'Day19 持久化验证' });
    setTimeout(postFromForm, 1200);
  } else if (auto === 'missing') {
    setTimeout(function () { doPost({}); }, 400);
  } else {
    setTimeout(postFromForm, 400);
  }
})();

