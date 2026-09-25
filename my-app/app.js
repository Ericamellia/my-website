// ===== 数据加载（一次 fetch + Promise.all） =====
// cache: 'no-cache' —— python http.server 不发 Cache-Control，浏览器会启发式缓存 JSON，
// 导致改了数据却看不到更新。强制回源校验，始终拿最新数据。
let data = { music: [], doujin: [], game: [], video: [], originals: [] };
async function loadData() {
  const [m, d, g, v, o] = await Promise.all(
    ['music','doujin','game','video','originals'].map(k =>
      fetch(`data/${k}.json`, { cache: 'no-cache' }).then(r => r.json()))
  );
  data = { music: m, doujin: d, game: g, video: v, originals: o };
}

// ===== 通用 =====
const $app = document.getElementById('app');
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const lnkCircle = c => `<a href="#/circle/${encodeURIComponent(c)}">${esc(c)}</a>`;
const lnkChar = n => `<a href="#/character/${encodeURIComponent(n)}">${esc(n)}</a>`;
const lnkTag = t => `<a href="#/tag/${encodeURIComponent(t)}" class="tag">${esc(t)}</a>`;
const lnkOriginal = id => {
  const o = data.originals.find(x => x.id === id);
  return o ? `<a href="#/original/${id}">${esc(o.title)}</a>` : esc(id);
};
const stars = p => '★'.repeat(Math.min(5, Math.round(p / 2500)));

// ===== 首页 =====
function renderHome() {
  const { music, doujin, game, video, originals } = data;
  $app.innerHTML = `
    <h2>按分类查询</h2>
    <div class="module-grid">
      <a class="module-card" href="#/music"><h2>同人音乐</h2><p>${music.length} 张精选专辑</p></a>
      <a class="module-card" href="#/doujin"><h2>同人漫画</h2><p>${doujin.length} 本漫画</p></a>
      <a class="module-card" href="#/game"><h2>同人游戏</h2><p>${game.length} 个游戏</p></a>
      <a class="module-card" href="#/video"><h2>同人视频</h2><p>${video.length} 个视频</p></a>
    </div>
    <h2 style="margin-top:32px;">反查入口</h2>
    <div class="module-grid">
      <a class="module-card" href="#/original"><h2>ZUN 原曲</h2><p>${originals.length} 首原曲</p></a>
    </div>`;
}

// ===== 模块列表（共用渲染，支持搜索 + 原曲筛选） =====
function renderList(module) {
  if (module === 'video') return renderVideoList();
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏' };
  const items = data[module].map(w => {
    const search = [w.name, w.circle, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase();
    const origLink = w.original ? `<br>原曲: ${lnkOriginal(w.original)}` : '';
    return `<div class="work-item" data-search="${esc(search)}" data-original="${esc(w.original||'')}">
      <h3><a href="#/${module}/${w.id}">${esc(w.name)}</a></h3>
      <div class="work-meta">
        <span>社团: ${lnkCircle(w.circle)}</span>
        <span>${w.year}</span>
        <span class="popularity" title="${w.popularity}">${stars(w.popularity)}</span>
      </div>
      <div class="work-meta">角色: ${w.characters.map(lnkChar).join(', ')}</div>
      <div class="work-meta">原作: ${(w.tags||[]).map(lnkTag).join(' ')}${origLink}</div>
    </div>`;
  }).join('') || '<p class="empty-state">暂无数据</p>';

  const origFilter = module === 'music' ? `
    <div style="margin-top:12px;">
      <label>原曲筛选:
        <select id="origFilter" style="padding:4px 8px;">
          <option value="">全部</option>
          ${data.originals.map(o => `<option value="${o.id}">${esc(o.title)}</option>`).join('')}
        </select>
      </label>
    </div>` : '';

  $app.innerHTML = `
    <h2>${labels[module]}</h2>
    <input id="search" placeholder="搜索作品名/社团/角色/标签…" style="width:100%;padding:8px;margin-top:12px;border:1px solid #ccc;border-radius:4px;">
    ${origFilter}
    <div class="work-list">${items}</div>`;

  document.getElementById('search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.work-item').forEach(it => {
      it.style.display = it.dataset.search.includes(q) ? '' : 'none';
    });
  });
  if (module === 'music') {
    document.getElementById('origFilter').addEventListener('change', e => {
      const oid = e.target.value;
      document.querySelectorAll('.work-item').forEach(it => {
        it.style.display = !oid || it.dataset.original === oid ? '' : 'none';
      });
    });
  }
}

// ===== 同人视频列表（封面卡片） =====
function renderVideoList() {
  const items = data.video.map(w => {
    const search = [w.name, w.circle, w.creator, w.type, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase();
    return `<div class="video-card" data-search="${esc(search)}">
      <div class="video-thumb">
        <img src="${esc(w.cover)}" alt="${esc(w.name)} 封面" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">
        <span class="video-type">${esc(w.type)}</span>
      </div>
      <div class="video-body">
        <h3><a href="#/video/${w.id}">${esc(w.name)}</a></h3>
        <div class="work-meta">
          <span>社团: ${lnkCircle(w.circle)}</span>
          <span>${w.year}</span>
          <span class="popularity" title="${w.popularity}">${stars(w.popularity)}</span>
        </div>
        <div class="work-meta">创作者: ${esc(w.creator)} · 平台: ${esc(w.platform)}</div>
        <div class="work-meta">角色: ${(w.characters||[]).map(lnkChar).join(', ')}</div>
        ${(w.tags||[]).length ? `<div class="work-meta">${w.tags.map(lnkTag).join(' ')}</div>` : ''}
      </div>
    </div>`;
  }).join('') || '<p class="empty-state">暂无数据</p>';

  $app.innerHTML = `
    <h2>同人视频</h2>
    <input id="search" placeholder="搜索视频名/社团/创作者/角色/标签…" style="width:100%;padding:8px;margin-top:12px;border:1px solid #ccc;border-radius:4px;">
    <div class="video-grid">${items}</div>`;

  document.getElementById('search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.video-card').forEach(it => {
      it.style.display = it.dataset.search.includes(q) ? '' : 'none';
    });
  });
}

// ===== ZUN 原曲列表（含反向引用数） =====
function renderOriginals() {
  const items = data.originals.map(o => {
    const refs = [];
    ['music','doujin','game','video'].forEach(m => {
      (data[m]||[]).forEach(w => {
        if (w.original === o.id || (w.tags||[]).includes(o.game)) {
          refs.push({ module: m, work: w });
        }
      });
    });
    const refBlocks = refs.length ? refs.map(r => `
      <div class="work-item">
        <h3><a href="#/${r.module}/${r.work.id}">${esc(r.work.name)}</a></h3>
        <div class="work-meta">社团: ${lnkCircle(r.work.circle)} · ${r.module}</div>
      </div>`).join('') : '<p class="empty-state">暂无引用此曲的同人作品</p>';
    return `<div class="work-item">
      <h3>${esc(o.title)}</h3>
      <div class="work-meta">游戏: ${lnkTag(o.game)} · 第 ${o.track_no} 轨 · ID: ${esc(o.id)}</div>
      <div class="work-meta">${esc(o.description)}</div>
      <div class="work-meta">被引用: ${refs.length} 次</div>
      ${refBlocks}
    </div>`;
  }).join('');
  $app.innerHTML = `<h2>ZUN 原曲库</h2><div class="work-list">${items}</div>`;
}

// ===== 反查（角色 / 社团 / 标签） =====
function renderReverse(kind, val) {
  const fieldMap = { character: 'characters', circle: 'circle', tag: 'tags' };
  const field = fieldMap[kind];
  const groups = ['music','doujin','game','video'].map(m => {
    const items = (data[m]||[]).filter(w => {
      if (Array.isArray(w[field])) return w[field].includes(val);
      return w[field] === val;
    });
    return { m, items };
  });
  const total = groups.reduce((s, g) => s + g.items.length, 0);
  if (!total) { $app.innerHTML = `<p class="empty-state">无匹配：${esc(val)}</p><p><a href="#/">← 返回首页</a></p>`; return; }
  const blocks = groups.filter(g => g.items.length).map(g => `
    <div class="group-block">
      <h2>${esc(g.m)} (${g.items.length})</h2>
      ${g.items.map(w => `
        <div class="work-item">
          <h3><a href="#/${g.m}/${w.id}">${esc(w.name)}</a></h3>
          <div class="work-meta">社团: ${lnkCircle(w.circle)} · ${w.year}</div>
          <div class="work-meta">${(w.tags||[]).map(lnkTag).join(' ')}</div>
        </div>`).join('')}
    </div>`).join('');
  $app.innerHTML = `<h2>${esc(kind)}: ${esc(val)}</h2><div class="work-list">${blocks}</div><p><a href="#/">← 返回首页</a></p>`;
}

// ===== 详情页 =====
function renderDetail(module, id) {
  const w = data[module].find(x => x.id === Number(id));
  if (!w) { $app.innerHTML = `<p class="empty-state">未找到该作品</p><p><a href="#/">← 首页</a></p>`; return; }
  if (module === 'video') return renderVideoDetail(w);
  const origRow = w.original ? `<div class="work-meta">原作原曲: ${lnkOriginal(w.original)}</div>` : '';
  const gameRow = w.original_game ? `<div class="work-meta">原作游戏: ${lnkTag(w.original_game)}</div>` : '';
  $app.innerHTML = `
    <h2>${esc(w.name)}</h2>
    <div class="work-meta">社团: ${lnkCircle(w.circle)} · ${w.year} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
    ${origRow}${gameRow}
    <div class="work-meta">角色: ${w.characters.map(lnkChar).join(', ')}</div>
    <div class="work-meta">原作: ${(w.tags||[]).map(lnkTag).join(' ')}</div>
    <p style="margin-top:16px;">${esc(w.description)}</p>
    <p><a href="${w.source_url}" target="_blank">资料来源 ↗</a></p>
    <p><a href="#/${module}">← 返回${esc(module)}</a> · <a href="#/">首页</a></p>`;
}

// ===== 视频详情页 =====
function renderVideoDetail(w) {
  const origRow = w.original_title ? `<div class="work-meta">原曲: ${esc(w.original_title)}</div>` : '';
  $app.innerHTML = `
    <h2>${esc(w.name)}</h2>
    <div class="video-thumb" style="max-width:520px;margin:16px 0;">
      <img src="${esc(w.cover)}" alt="${esc(w.name)} 封面" referrerpolicy="no-referrer" onerror="this.remove()">
      <span class="video-type">${esc(w.type)}</span>
    </div>
    <div class="work-meta">社团: ${lnkCircle(w.circle)} · 创作者: ${esc(w.creator)} · ${w.year}</div>
    <div class="work-meta">平台: ${esc(w.platform)}${w.bvid ? ` · <a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.bvid)}</a>` : ''} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
    ${origRow}
    <div class="work-meta">角色: ${(w.characters||[]).map(lnkChar).join(', ')}</div>
    ${(w.tags||[]).length ? `<div class="work-meta">原作: ${w.tags.map(lnkTag).join(' ')}</div>` : ''}
    <p style="margin-top:16px;">${esc(w.description)}</p>
    <p><a href="${esc(w.url)}" target="_blank" rel="noopener">▶ 前往 ${esc(w.platform)} 观看 ↗</a></p>
    <p><a href="${esc(w.source_url)}" target="_blank" rel="noopener">资料来源 ↗</a></p>
    <p><a href="#/video">← 返回同人视频</a> · <a href="#/">首页</a></p>`;
}

// ===== 路由 =====
async function route() {
  await loadData();
  const h = location.hash.slice(1) || '/';
  const p = h.split('/').filter(Boolean);
  if (!p.length) return renderHome();
  if (p[0] === 'original') return renderOriginals();
  if (['music','doujin','game','video'].includes(p[0])) {
    return p[1] ? renderDetail(p[0], p[1]) : renderList(p[0]);
  }
  if (['character','circle','tag'].includes(p[0])) {
    const val = decodeURIComponent(p.slice(1).join('/'));
    return renderReverse(p[0], val);
  }
  $app.innerHTML = '<p class="empty-state">404 — 未识别路径</p>';
}

window.addEventListener('hashchange', route);
route();
