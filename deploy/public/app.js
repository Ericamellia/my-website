'use strict';
/**
 * 前端 mock 版（Day 15）
 * 只做两件事：
 *   1) 真实请求同源的 /api/health，把返回的 JSON 原样显示出来（证明后端链路通）
 *   2) 用写死的示例数据渲染列表 + 搜索 + 分类切换（证明前端在公网能正常打开、手机上可看）
 * 数据全部是 mock，不调用任何真实业务接口——真实接口排在 Day 16–20。
 */

/** ① 示例数据：结构沿用真实站的字段（title / author / tags / category），方便以后换成真接口。 */
var WORKS = [
  { title: '东方梦想夏', author: '上海アリス幻樂団', tags: ['同人音乐', '示例'], category: 'music', color: '#e87a8c' },
  { title: '博丽神社例大祭', author: 'Sample Circle A', tags: ['同人音乐', '示例'], category: 'music', color: '#c98ad0' },
  { title: '红魔乡 四格合集', author: 'Sample Circle B', tags: ['同人漫画', '示例'], category: 'doujin', color: '#8fb8e8' },
  { title: '雾雨魔法店', author: 'Sample Circle C', tags: ['同人漫画', '示例'], category: 'doujin', color: '#7fc4b0' },
  { title: '东方天空璋 STG', author: 'Sample Team D', tags: ['同人游戏', '示例'], category: 'game', color: '#e8a45c' },
  { title: '妖精大战争', author: 'Sample Team E', tags: ['同人游戏', '示例'], category: 'game', color: '#d98a8a' },
  { title: '幻想万华镜', author: 'Sample Creator F', tags: ['同人视频', '示例'], category: 'video', color: '#9a8ae8' },
  { title: '东方手书短剧', author: 'Sample Creator G', tags: ['同人视频', '示例'], category: 'video', color: '#6fb0d8' },
  { title: '灵梦 立绘集', author: 'Sample Artist H', tags: ['同人图', '示例'], category: 'art', color: '#e8c45c' },
  { title: '魔理沙 插画集', author: 'Sample Artist I', tags: ['同人图', '示例'], category: 'art', color: '#c4a05c' }
];

var CATS = [
  { key: 'all', name: '全部' },
  { key: 'music', name: '同人音乐' },
  { key: 'doujin', name: '同人漫画' },
  { key: 'game', name: '同人游戏' },
  { key: 'video', name: '同人视频' },
  { key: 'art', name: '同人图' }
];

var state = { cat: 'all', q: '' };

/** ② 渲染分类 Tab */
function renderTabs() {
  var box = document.getElementById('tabs');
  box.innerHTML = '';
  CATS.forEach(function (c) {
    var b = document.createElement('button');
    b.className = 'tab';
    b.type = 'button';
    b.textContent = c.name;
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(state.cat === c.key));
    b.addEventListener('click', function () { state.cat = c.key; renderTabs(); renderList(); });
    box.appendChild(b);
  });
}

/** ③ 渲染作品卡片（搜索 + 分类两重筛选，全部在前端完成） */
function renderList() {
  var q = state.q.trim().toLowerCase();
  var list = WORKS.filter(function (w) {
    if (state.cat !== 'all' && w.category !== state.cat) return false;
    if (!q) return true;
    var hay = (w.title + ' ' + w.author + ' ' + w.tags.join(' ')).toLowerCase();
    return hay.indexOf(q) !== -1;
  });

  var grid = document.getElementById('grid');
  grid.innerHTML = '';
  list.forEach(function (w) {
    var el = document.createElement('article');
    el.className = 'work';
    el.innerHTML =
      '<div class="cover" style="background:' + w.color + '">' + esc(w.category) + '</div>' +
      '<div class="body">' +
        '<h3>' + esc(w.title) + '</h3>' +
        '<p class="meta">' + esc(w.author) + '</p>' +
        '<div class="tags">' + w.tags.map(function (t) { return '<span>' + esc(t) + '</span>'; }).join('') + '</div>' +
      '</div>';
    grid.appendChild(el);
  });
  document.getElementById('empty').hidden = list.length > 0;
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m];
  });
}

/** ④ 打 /api/health：拿到 JSON 原样显示，并把关键字段做成状态灯。 */
function loadHealth() {
  var card = document.getElementById('healthCard');
  var badge = document.getElementById('hBadge');
  var out = document.getElementById('hJson');
  var meta = document.getElementById('hMeta');
  var t0 = Date.now();

  fetch('/api/health', { cache: 'no-store' })
    .then(function (r) {
      var ms = Date.now() - t0;
      return r.text().then(function (txt) { return { status: r.status, txt: txt, ms: ms }; });
    })
    .then(function (res) {
      var data = null;
      try { data = JSON.parse(res.txt); } catch (e) { data = null; }
      out.textContent = res.txt;
      var ok = res.status === 200 && data && data.ok === true;
      card.classList.add(ok ? 'ok' : 'bad');
      badge.textContent = 'HTTP ' + res.status + (ok ? ' · 正常' : ' · 异常');
      meta.textContent = ok
        ? 'env=' + data.env + ' · version=' + data.version + ' · uptime=' + data.uptimeSec + 's · 耗时 ' + res.ms + 'ms'
        : '返回不是预期的 JSON，请检查服务是否启动';
    })
    .catch(function (err) {
      card.classList.add('bad');
      badge.textContent = '请求失败';
      out.textContent = String(err);
      meta.textContent = '无法访问 /api/health，服务可能未启动或地址有误';
    });
}

renderTabs();
renderList();
loadHealth();

var input = document.getElementById('q');
input.addEventListener('input', function () { state.q = input.value; renderList(); });
