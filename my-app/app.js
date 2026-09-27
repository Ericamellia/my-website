// ===== 数据加载（一次 fetch + Promise.all） =====
// cache: 'no-cache' —— python http.server 不发 Cache-Control，浏览器会启发式缓存 JSON，
// 导致改了数据却看不到更新。强制回源校验，始终拿最新数据。
let data = { music: [], doujin: [], game: [], video: [], art: [], originals: [], original_games: { categories: [], games: [] } };
async function loadData() {
  const [m, d, g, v, a, o, og] = await Promise.all(
    ['music','doujin','game','video','art','originals','original_games'].map(k =>
      fetch(`data/${k}.json`, { cache: 'no-cache' })
        .then(r => {
          if (!r.ok) throw new Error(`data/${k}.json 返回 HTTP ${r.status}`);
          return r.json();
        }))
  );
  data = { music: m, doujin: d, game: g, video: v, art: a, originals: o, original_games: og };
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

// ===== 封面解析（Day 10：全板块统一视频卡片式配图） =====
// 优先级：视频用自身 cover 外链；其他模块按「原作标签 → 官方原作封面」映射；
// 都没有时回退到各板块占位图，保证卡片永远有图。
const moduleFallback = {
  music: 'assets/modules/module-music.webp',
  doujin: 'assets/modules/module-doujin.jpg',
  game: 'assets/modules/module-game2.jpg',
  video: 'assets/modules/module-video2.jpg',
  art: 'assets/modules/module-art.jpg',
};
const tagCover = t => {
  const g = (data.original_games.games || []).find(x => x.tag === t);
  return g ? g.cover : '';
};
const workCover = (w, module) => {
  if (module === 'video' && w.cover) return w.cover;
  const hit = (w.tags || []).map(tagCover).filter(Boolean)[0];
  return hit || moduleFallback[module] || moduleFallback.video;
};

// ===== 可复用组件：作品卡片（Day 8 余力加练） =====
// 模块列表页与反查页共用同一张卡片，两处展示天然一致。
// opts.search 传搜索串时附带 data-search / data-original 属性（列表页的搜索/原曲筛选依赖它们）；
// 反查页不传 opts，卡片不带筛选属性。
const workCard = (w, module, opts = {}) => {
  const attrs = 'search' in opts
    ? ` data-search="${esc(opts.search)}" data-original="${esc(w.original || '')}"`
    : '';
  const origLink = w.original ? `<br>原曲: ${lnkOriginal(w.original)}` : '';
  const badge = module === 'video' && w.type ? `<span class="card-badge">${esc(w.type)}</span>` : '';
  const extraRow = module === 'video'
    ? `<div class="work-meta">创作者: ${esc(w.creator)} · 平台: ${esc(w.platform)}</div>`
    : (w.creator ? `<div class="work-meta">创作者: ${esc(w.creator)}</div>` : '');
  return `<div class="work-item"${attrs}>
      <div class="card-thumb">
        <img src="${esc(workCover(w, module))}" alt="${esc(w.name)} 封面" loading="lazy"${module === 'video' ? ' referrerpolicy="no-referrer"' : ''} onerror="this.remove()">
        ${badge}
      </div>
      <div class="card-body">
        <h3><a href="#/${module}/${w.id}">${esc(w.name)}</a></h3>
        <div class="work-meta">
          <span>社团: ${lnkCircle(w.circle)}</span>
          <span>${w.year}</span>
          <span class="popularity" title="${w.popularity}">${stars(w.popularity)}</span>
        </div>
        ${extraRow}
        <div class="work-meta">角色: ${(w.characters || []).map(lnkChar).join(', ')}</div>
        ${(w.tags || []).length || origLink ? `<div class="work-meta">原作: ${(w.tags || []).map(lnkTag).join(' ')}${origLink}</div>` : ''}
      </div>
    </div>`;
};

// ===== 首页 =====
function renderHome() {
  const { music, doujin, game, video, art } = data;
  const origWorks = [...new Set([...music, ...doujin, ...game, ...video, ...art].flatMap(w => w.tags || []))];
  $app.innerHTML = `
    <h2>按分类查询</h2>
    <div class="module-grid">
      <a class="module-card" href="#/music"><div class="module-thumb"><img src="assets/modules/module-music.webp" alt="同人音乐" loading="lazy" onerror="this.parentElement.remove()"></div><h2>同人音乐</h2><p>${music.length} 张精选专辑</p></a>
      <a class="module-card" href="#/doujin"><div class="module-thumb"><img src="assets/modules/module-doujin.jpg" alt="同人漫画" loading="lazy" onerror="this.parentElement.remove()"></div><h2>同人漫画</h2><p>${doujin.length} 本漫画</p></a>
      <a class="module-card" href="#/game"><div class="module-thumb"><img src="assets/modules/module-game2.jpg" alt="同人游戏" loading="lazy" onerror="this.parentElement.remove()"></div><h2>同人游戏</h2><p>${game.length} 个游戏</p></a>
      <a class="module-card" href="#/video"><div class="module-thumb"><img src="assets/modules/module-video2.jpg" alt="同人视频" loading="lazy" onerror="this.parentElement.remove()"></div><h2>同人视频</h2><p>${video.length} 个视频</p></a>
      <a class="module-card" href="#/art"><div class="module-thumb"><img src="assets/modules/module-art.jpg" alt="同人图" loading="lazy" onerror="this.parentElement.remove()"></div><h2>同人图</h2><p>${art.length} 张精选同人图</p></a>
    </div>
    <h2 class="section-title">按原作查询</h2>
    <div class="module-grid">
      <a class="module-card" href="#/original"><div class="module-thumb"><img src="assets/modules/module-original.jpg" alt="原作" loading="lazy" onerror="this.parentElement.remove()"></div><h2>原作</h2><p>${data.original_games.games.length} 部官方原作</p></a>
    </div>`;
}

// ===== 模块列表（共用渲染，支持搜索 + 原曲筛选） =====
function renderList(module) {
  if (module === 'video') return renderVideoList();
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', art: '同人图' };
  const items = data[module].map(w => {
    const search = [w.name, w.circle, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase();
    return workCard(w, module, { search });
  }).join('') || '<p class="empty-state">暂无数据</p>';

  const origFilter = module === 'music' ? `
    <div style="margin-top:12px;">
      <label>原曲筛选:
        <select id="origFilter" class="field">
          <option value="">全部</option>
          ${data.originals.map(o => `<option value="${o.id}">${esc(o.title)}</option>`).join('')}
        </select>
      </label>
    </div>` : '';

  $app.innerHTML = `
    <h2>${labels[module]}</h2>
    <input id="search" class="field" placeholder="搜索作品名/社团/角色/标签…">
    ${origFilter}
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空筛选条件<br><button id="clearBtn" class="btn">清空搜索与筛选</button></p>
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
    <input id="search" class="field" placeholder="搜索视频名/社团/创作者/角色/标签…">
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空搜索<br><button id="clearBtn" class="btn">清空搜索</button></p>
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

// ===== 原作板块：全部官方原作按「旧作/新作/格斗作/外传」分组 =====
function ogCard(g) {
  return `<a class="og-card" href="#/original/${g.id}">
    <div class="og-cover-wrap">
      <img src="${esc(g.cover)}" alt="${esc(g.title)} 封面" loading="lazy" onerror="this.parentElement.style.display='none'">
      <span class="og-th">${esc(g.th)}</span>
    </div>
    <div class="og-info">
      <h4>${esc(g.title)}</h4>
      <p class="og-sub">${esc(g.subtitle)}</p>
      <p class="og-year">${g.year}</p>
    </div>
  </a>`;
}

function renderOriginals() {
  const cats = data.original_games.categories;
  const groups = cats.map(c => {
    const list = data.original_games.games.filter(g => g.category === c.id);
    return `<section class="og-group" data-cat="${c.id}">
      <h3>${esc(c.label)} (${list.length} 部)</h3>
      <div class="og-grid">${list.map(ogCard).join('')}</div>
    </section>`;
  }).join('');

  $app.innerHTML = `
    <h2>官方原作</h2>
    <div class="og-tabs">
      ${cats.map(c => `<button class="og-tab" data-tab="${c.id}">${esc(c.label)}</button>`).join('')}
    </div>
    <div class="og-panels">${groups}</div>`;

  const tabs = document.querySelectorAll('.og-tab');
  const panels = document.querySelectorAll('.og-group');
  const switchTab = id => {
    tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === id));
    panels.forEach(p => p.classList.toggle('hidden', p.dataset.cat !== id));
  };
  tabs.forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  switchTab(cats[0]?.id || 'old');
}

// ===== 单个原作详情页：封面 + Th 标注 + 人物/原曲标签页 + 同人作品 =====
function renderOriginalGame(id) {
  const g = data.original_games.games.find(x => x.id === id);
  if (!g) {
    $app.innerHTML = `<p class="empty-state">未找到该原作</p><p><a href="#/original">← 返回原作列表</a></p>`;
    return;
  }

  // 按 tag 匹配该原作下的同人作品
  const worksByModule = {};
  ['music','doujin','game','video','art'].forEach(m => {
    (data[m] || []).forEach(w => {
      if ((w.tags || []).includes(g.tag) || w.original_game === g.tag) {
        (worksByModule[m] ||= []).push(w);
      }
    });
  });
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const workBlocks = Object.keys(worksByModule).map(m => `
    <div class="group-block">
      <h3>${labels[m]} (${worksByModule[m].length})</h3>
      ${worksByModule[m].map(w => workCard(w, m)).join('')}
    </div>`).join('');

  $app.innerHTML = `
    <div class="og-detail-header">
      <div class="og-detail-cover-wrap">
        <img class="og-detail-cover" src="${esc(g.cover)}" alt="${esc(g.title)} 封面" onerror="this.remove()">
        <span class="og-th">${esc(g.th)}</span>
      </div>
      <div class="og-detail-meta">
        <h2>${esc(g.title)}</h2>
        <p class="og-sub">${esc(g.subtitle)}</p>
        <p class="og-year">${g.year} · ${esc(data.original_games.categories.find(c => c.id === g.category)?.label || '')}</p>
      </div>
    </div>
    <div class="og-tabs">
      <button class="og-tab active" data-tab="chars">人物标签</button>
      <button class="og-tab" data-tab="music">原曲标签</button>
    </div>
    <div class="og-panel" data-panel="chars"><p class="empty-state">人物标签内容待补充…</p></div>
    <div class="og-panel hidden" data-panel="music"><p class="empty-state">原曲标签内容待补充…</p></div>
    <h3 class="og-section-title">该原作下的同人作品</h3>
    ${workBlocks || '<p class="empty-state">暂无同人作品数据</p>'}
    <p><a href="#/original">← 返回原作列表</a></p>`;

  const tabs = document.querySelectorAll('.og-tab');
  const panels = document.querySelectorAll('.og-panel');
  tabs.forEach(tab => tab.addEventListener('click', () => {
    const t = tab.dataset.tab;
    tabs.forEach(b => b.classList.remove('active'));
    tab.classList.add('active');
    panels.forEach(p => p.classList.toggle('hidden', p.dataset.panel !== t));
  }));
}

// ===== 全站搜索（Day 10：顶栏搜索框 → #/search/<词> 分组结果页） =====
function renderSearch(q) {
  const gs = document.getElementById('globalSearch');
  if (gs && (gs.value || '') !== q) gs.value = q;
  if (!q) { $app.innerHTML = '<p class="empty-state">输入关键词开始全站搜索</p>'; return; }
  const ql = q.toLowerCase();
  const matchWork = w => [w.name, w.circle, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase().includes(ql);
  const matchVideo = w => [w.name, w.circle, w.creator, w.type, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase().includes(ql);
  const groups = [
    { m: 'music',    label: '同人音乐', items: data.music.filter(matchWork) },
    { m: 'doujin',   label: '同人漫画', items: data.doujin.filter(matchWork) },
    { m: 'game',     label: '同人游戏', items: data.game.filter(matchWork) },
    { m: 'video',    label: '同人视频', items: data.video.filter(matchVideo) },
    { m: 'art',      label: '同人图',   items: data.art.filter(matchWork) },
    { m: 'original', label: '原作', items: [...new Set([...data.music, ...data.doujin, ...data.game, ...data.video, ...data.art].flatMap(w => w.tags || []))].filter(t => t.toLowerCase().includes(ql)) },
  ];
  const total = groups.reduce((s, g) => s + g.items.length, 0);
  if (!total) {
    $app.innerHTML = `<p class="empty-state">全站搜索「${esc(q)}」无匹配结果 —— 换个关键词试试<br><button id="clearBtn" class="btn">清空搜索</button></p>`;
    const b = document.getElementById('clearBtn');
    b.addEventListener('click', () => { location.hash = '#/'; });
    return;
  }
  const blocks = groups.filter(g => g.items.length).map(g => `
    <div class="group-block">
      <h2>${esc(g.label)} (${g.items.length})</h2>
      <div class="work-list">${g.items.map(w => {
        if (g.m === 'original') {
          const cov = tagCover(w) || moduleFallback.video;
          return `<div class="work-item">
          <div class="card-thumb"><img src="${esc(cov)}" alt="${esc(w)} 封面" loading="lazy" onerror="this.remove()"></div>
          <div class="card-body">
            <h3><a href="#/original">${esc(w)}</a></h3>
            <div class="work-meta">原作游戏 · 点击查看该原作下的同人作品</div>
          </div>
        </div>`;
        }
        return workCard(w, g.m);
      }).join('')}</div>
    </div>`).join('');
  $app.innerHTML = `<h2>全站搜索：${esc(q)}（${total} 条）</h2>${blocks}<p><a href="#/">← 返回首页</a></p>`;
}

// ===== 反查（角色 / 社团 / 标签） =====
function renderReverse(kind, val) {
  const fieldMap = { character: 'characters', circle: 'circle', tag: 'tags' };
  const field = fieldMap[kind];
  const groups = ['music','doujin','game','video','art'].map(m => {
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
  const creatorRow = w.creator ? `<div class="work-meta">创作者: ${esc(w.creator)}</div>` : '';
  $app.innerHTML = `
    <h2>${esc(w.name)}</h2>
    <div class="video-thumb" style="max-width:520px;margin:16px 0;">
      <img src="${esc(workCover(w, module))}" alt="${esc(w.name)} 封面" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">
    </div>
    <div class="work-meta">社团: ${lnkCircle(w.circle)} · ${w.year} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
    ${creatorRow}
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
      <div class="empty-state">
        <p>数据加载失败：${esc(e.message)}</p>
        <p class="hint">常见原因：本地服务没启动 / 端口不对 / 数据文件缺失。<br>请按 RUN.md 启动服务后再试。</p>
        <button id="retryBtn" class="btn">重试</button>
      </div>`;
    document.getElementById('retryBtn').addEventListener('click', route);
    return;
  }
  const h = location.hash.slice(1) || '/';
  const p = h.split('/').filter(Boolean);
  // 首页才显示背景图，子页面保持干净白底
  if (document.body && document.body.classList) document.body.classList.toggle('home-bg', !p.length);
  // 离开搜索页时清空顶栏搜索框（renderSearch 内部负责同步成搜索词）
  const gs = document.getElementById('globalSearch');
  if (gs && p[0] !== 'search') gs.value = '';
  if (!p.length) return renderHome();
  if (p[0] === 'original') {
    return p[1] ? renderOriginalGame(decodeURIComponent(p[1])) : renderOriginals();
  }
  if (['music','doujin','game','video','art'].includes(p[0])) {
    return p[1] ? renderDetail(p[0], p[1]) : renderList(p[0]);
  }
  if (['character','circle','tag'].includes(p[0])) {
    const val = decodeURIComponent(p.slice(1).join('/'));
    return renderReverse(p[0], val);
  }
  if (p[0] === 'search') {
    const val = decodeURIComponent(p.slice(1).join('/')).trim();
    return renderSearch(val);
  }
  $app.innerHTML = '<p class="empty-state">404 — 未识别路径</p>';
}

// 顶栏全站搜索：输入防抖 300ms 跳转结果页；清空回首页
let searchTimer;
document.getElementById('globalSearch').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const q = e.target.value.trim();
    const target = q ? `#/search/${encodeURIComponent(q)}` : '#/';
    if (location.hash !== target) location.hash = target;
  }, 300);
});

window.addEventListener('hashchange', route);
route();
