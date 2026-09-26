// ===== 数据加载（一次 fetch + Promise.all） =====
// cache: 'no-cache' —— python http.server 不发 Cache-Control，浏览器会启发式缓存 JSON，
// 导致改了数据却看不到更新。强制回源校验，始终拿最新数据。
let data = { music: [], doujin: [], game: [], video: [], originals: [] };
async function loadData() {
  const [m, d, g, v, o] = await Promise.all(
    ['music','doujin','game','video','originals'].map(k =>
      fetch(`data/${k}.json`, { cache: 'no-cache' })
        .then(r => {
          if (!r.ok) throw new Error(`data/${k}.json 返回 HTTP ${r.status}`);
          return r.json();
        }))
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

// ===== 可复用组件：作品卡片（Day 8 余力加练） =====
// 模块列表页与反查页共用同一张卡片，两处展示天然一致。
// opts.search 传搜索串时附带 data-search / data-original 属性（列表页的搜索/原曲筛选依赖它们）；
// 反查页不传 opts，卡片不带筛选属性。
const workCard = (w, module, opts = {}) => {
  const attrs = 'search' in opts
    ? ` data-search="${esc(opts.search)}" data-original="${esc(w.original || '')}"`
    : '';
  const origLink = w.original ? `<br>原曲: ${lnkOriginal(w.original)}` : '';
  return `<div class="work-item"${attrs}>
      <h3><a href="#/${module}/${w.id}">${esc(w.name)}</a></h3>
      <div class="work-meta">
        <span>社团: ${lnkCircle(w.circle)}</span>
        <span>${w.year}</span>
        <span class="popularity" title="${w.popularity}">${stars(w.popularity)}</span>
      </div>
      <div class="work-meta">角色: ${(w.characters || []).map(lnkChar).join(', ')}</div>
      <div class="work-meta">原作: ${(w.tags || []).map(lnkTag).join(' ')}${origLink}</div>
    </div>`;
};

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
    return workCard(w, module, { search });
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
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空筛选条件<br><button id="clearBtn" style="padding:4px 16px;margin-top:8px;cursor:pointer;">清空搜索与筛选</button></p>
    <div class="work-list">${items}</div>`;

  // 统一过滤：搜索词 AND 原曲筛选同时生效（PRD 通用规则），无结果时显示空状态
  const applyFilter = () => {
    const q = document.getElementById('search').value.toLowerCase();
    const oid = module === 'music' ? document.getElementById('origFilter').value : '';
    let visible = 0;
    document.querySelectorAll('.work-item').forEach(it => {
      const ok = it.dataset.search.includes(q) && (!oid || it.dataset.original === oid);
      it.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    document.getElementById('no-result').hidden = visible !== 0;
  };
  document.getElementById('search').addEventListener('input', applyFilter);
  if (module === 'music') {
    document.getElementById('origFilter').addEventListener('change', applyFilter);
  }
  document.getElementById('clearBtn').addEventListener('click', () => {
    document.getElementById('search').value = '';
    if (module === 'music') document.getElementById('origFilter').value = '';
    applyFilter();
  });
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
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空搜索<br><button id="clearBtn" style="padding:4px 16px;margin-top:8px;cursor:pointer;">清空搜索</button></p>
    <div class="video-grid">${items}</div>`;

  const applyFilter = () => {
    const q = document.getElementById('search').value.toLowerCase();
    let visible = 0;
    document.querySelectorAll('.video-card').forEach(it => {
      const ok = it.dataset.search.includes(q);
      it.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    document.getElementById('no-result').hidden = visible !== 0;
  };
  document.getElementById('search').addEventListener('input', applyFilter);
  document.getElementById('clearBtn').addEventListener('click', () => {
    document.getElementById('search').value = '';
    applyFilter();
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
      ${g.items.map(w => workCard(w, g.m)).join('')}
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
  try {
    await loadData();
  } catch (e) {
    // 错误态：数据加载失败时给出原因和出路，而不是停在「加载中」
    $app.innerHTML = `
      <div class="empty-state" style="text-align:center;margin-top:48px;">
        <p>数据加载失败：${esc(e.message)}</p>
        <p style="color:#999;font-size:13px;">常见原因：本地服务没启动 / 端口不对 / 数据文件缺失。<br>请按 RUN.md 启动服务后再试。</p>
        <button id="retryBtn" style="padding:8px 24px;margin-top:8px;cursor:pointer;">重试</button>
      </div>`;
    document.getElementById('retryBtn').addEventListener('click', route);
    return;
  }
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
