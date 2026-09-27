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

// ===== 大图预览（点击详情页配图放大；Day 10 新增） =====
const $lightbox = document.getElementById('lightbox');
const $lightboxImg = document.getElementById('lightbox-img');
function openLightbox(src, alt) {
  if (!$lightbox || !$lightboxImg || !src) return;
  $lightboxImg.src = src;
  $lightboxImg.alt = alt || '';
  $lightbox.hidden = false;
  document.body.classList.add('no-scroll');
}
function closeLightbox() {
  if (!$lightbox) return;
  $lightbox.hidden = true;
  document.body.classList.remove('no-scroll');
}
// 事件委托：详情页内任何带 .zoomable 的配图都可点开放大
$app.addEventListener('click', e => {
  const t = e.target && e.target.closest ? e.target.closest('.zoomable') : null;
  if (t) openLightbox(t.currentSrc || t.src, t.alt);
});
if ($lightbox) $lightbox.addEventListener('click', closeLightbox);
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

// ===== 顶栏返回按钮：回到上一个所处页面（Day 10 新增） =====
const $backBtn = document.getElementById('backBtn');
if ($backBtn) $backBtn.addEventListener('click', () => {
  // 无历史记录时（新标签直接打开）退回首页
  if (window.history && window.history.length > 1) window.history.back();
  else location.hash = '#/';
});

// ===== 我的收藏（Day 10 新增） =====
// 存储结构：[{ module, id }]。优先 localStorage 持久化；
// 无 localStorage 环境（如无头验证脚本）读取会抛 ReferenceError，被 catch 后退化为内存数组。
let favs = [];
try { favs = JSON.parse(localStorage.getItem('touhou_favs') || '[]'); } catch (e) {}
const saveFavs = () => { try { localStorage.setItem('touhou_favs', JSON.stringify(favs)); } catch (e) {} };
const isFav = (module, id) => favs.some(f => f.module === module && f.id === id);
const toggleFav = (module, id) => {
  const i = favs.findIndex(f => f.module === module && f.id === id);
  if (i >= 0) favs.splice(i, 1); else favs.push({ module, id });
  saveFavs();
};
// 详情页收藏按钮：三态文案由 CSS 控制（收藏 / 已收藏 / hover 取消收藏）
const favBtn = (module, id) => {
  const on = isFav(module, Number(id)) ? ' is-faved' : '';
  return `<button class="detail-cta detail-cta-fav${on}" type="button"
            data-module="${esc(module)}" data-id="${esc(id)}" aria-label="收藏该作品">
          <span class="lbl-off">收藏</span><span class="lbl-on">已收藏</span><span class="lbl-un">取消收藏</span>
        </button>`;
};
// 事件委托：详情页内任意收藏按钮，点击即切换收藏状态并同步按钮样式
$app.addEventListener('click', e => {
  const b = e.target && e.target.closest ? e.target.closest('.detail-cta-fav') : null;
  if (!b) return;
  e.preventDefault();
  const { module, id } = b.dataset;
  toggleFav(module, Number(id));
  b.classList.toggle('is-faved', isFav(module, Number(id)));
});

// ===== 修改作品信息：详情页右栏「修改介绍」按钮 + 编辑弹窗（Day 10 新增） =====
// 弹窗容器在 index.html 预置（与 lightbox 同套路），表单字段按模块动态填充。
// 保存直接改内存中的 work 对象并重渲染详情页（不重新 fetch，避免丢失修改）。
const $editModal = document.getElementById('editModal');
const $editForm = document.getElementById('editForm');
const $editClose = document.getElementById('editClose');
function closeEditModal() {
  if ($editModal) $editModal.hidden = true;
  document.body.classList.remove('no-scroll');
}
if ($editClose) $editClose.addEventListener('click', closeEditModal);
if ($editModal) $editModal.addEventListener('click', e => { if (e.target === $editModal) closeEditModal(); });

const editField = (id, label, val, ph) =>
  `<label>${label}<input id="${id}" class="field" value="${esc(val == null ? '' : val)}" placeholder="${esc(ph || '')}"></label>`;
const editArea = (id, label, val) =>
  `<label>${label}<textarea id="${id}" class="field" rows="4">${esc(val || '')}</textarea></label>`;
const editSelect = (id, label, val, opts) =>
  `<label>${label}<select id="${id}" class="field">${opts}</select></label>`;

// 表单字段：覆盖详情页右栏全部信息（视频模块有类型/平台/链接/原曲，其余模块有原作原曲/原作游戏下拉）
function buildEditFields(module, w) {
  const fields = [
    editField('edName', '作品名 *', w.name, '必填'),
    editField('edCircle', '作者（社团）', w.circle, '如：IOSYS'),
    editField('edCreator', '创作者', w.creator || '', '如：ARM'),
    editField('edYear', '年份', w.year, '如：2024'),
    editField('edPop', '热度（数字）', w.popularity, '如：5000'),
    editField('edChars', '登场角色（逗号分隔）', (w.characters || []).join(', '), '如：博丽灵梦, 雾雨魔理沙'),
    editField('edTags', '原作标签（逗号分隔）', (w.tags || []).join(', '), '如：红魔乡, 妖妖梦'),
  ];
  if (module === 'video') {
    fields.push(
      editField('edType', '视频类型', w.type, '如：PV / 手书 / MMD'),
      editField('edPlatform', '平台', w.platform, '如：Bilibili'),
      editField('edUrl', '视频链接', w.url, 'https://…'),
      editField('edOrigTitle', '原曲', w.original_title || '', '如：U.N.オーエンは彼女なのか？'),
    );
  } else {
    const origOpts = ['<option value="">（无）</option>', ...data.originals.map(o =>
      `<option value="${esc(o.id)}"${o.id === w.original ? ' selected' : ''}>${esc(o.title)}</option>`)].join('');
    const ogOpts = ['<option value="">（无）</option>', ...(data.original_games.games || []).map(g =>
      `<option value="${esc(g.tag)}"${g.tag === w.original_game ? ' selected' : ''}>${esc(g.title)}</option>`)].join('');
    fields.push(
      editSelect('edOriginal', '原作原曲', w.original, origOpts),
      editSelect('edOrigGame', '原作游戏', w.original_game, ogOpts),
    );
  }
  fields.push(
    editField('edSource', '资料来源地址', w.source_url, 'https://…'),
    editArea('edDesc', '作品简介', w.description),
  );
  return fields.join('');
}

// 保存：读取表单值写回 work 对象（供提交回调与无头验证共用）
function applyEdit(module, w) {
  const val = id => (document.getElementById(id)?.value || '').trim();
  const split = s => s ? s.split(/[,，、\s]+/).filter(Boolean) : [];
  w.name = val('edName') || w.name;
  w.circle = val('edCircle') || w.circle;
  w.creator = val('edCreator');
  w.year = Number(val('edYear')) || w.year;
  w.popularity = Number(val('edPop')) || 0;
  w.characters = split(val('edChars'));
  w.tags = split(val('edTags'));
  w.source_url = val('edSource');
  w.description = val('edDesc') || '（暂无简介）';
  if (module === 'video') {
    w.type = val('edType') || w.type;
    w.platform = val('edPlatform') || w.platform;
    w.url = val('edUrl') || w.url;
    w.original_title = val('edOrigTitle');
  } else {
    w.original = val('edOriginal') || '';
    w.original_game = val('edOrigGame') || '';
  }
}

function openEditModal(module, w) {
  if (!$editForm) return;
  $editForm.innerHTML = buildEditFields(module, w) + `
      <div class="add-actions">
        <button type="button" class="btn" id="editCancel">取消</button>
        <button class="detail-cta add-submit" type="submit">保存</button>
      </div>`;
  $editForm.onsubmit = e => {
    e.preventDefault();
    applyEdit(module, w);
    closeEditModal();
    renderDetail(module, String(w.id)); // 重渲染详情页展示新信息（不重新加载数据）
  };
  const cancel = document.getElementById('editCancel');
  if (cancel) cancel.addEventListener('click', closeEditModal);
  if ($editModal) $editModal.hidden = false;
  document.body.classList.add('no-scroll');
}

// 详情页「修改介绍」按钮（事件委托）：找到对应作品后唤起编辑弹窗
$app.addEventListener('click', e => {
  const b = e.target && e.target.closest ? e.target.closest('.edit-btn') : null;
  if (!b) return;
  e.preventDefault();
  const w = (data[b.dataset.module] || []).find(x => x.id === Number(b.dataset.id));
  if (w) openEditModal(b.dataset.module, w);
});

// Esc 同时关弹窗（原有关 lightbox 的监听扩展）
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeEditModal(); });

// 下载原图按钮的文件名：取配图 URL 的文件名部分（如 assets/works/music01.jpg → music01.jpg）
const dlName = src => String(src || '').split('/').pop() || 'cover.jpg';
// 按钮组：左「点击查看」（跳原网站）+ 中「收藏」+ 右「下载原图」（download 属性保存本地配图）
const detailActions = (module, id, srcUrl, cover) => `
        <div class="detail-actions">
          <a class="detail-cta" href="${esc(srcUrl)}" target="_blank" rel="noopener">点击查看</a>
          ${favBtn(module, id)}
          <a class="detail-cta detail-cta-ghost" href="${esc(cover)}" download="${esc(dlName(cover))}">下载原图</a>
        </div>`;

const lnkCircle = c => `<a href="#/circle/${encodeURIComponent(c)}">${esc(c)}</a>`;
const lnkChar = n => `<a href="#/character/${encodeURIComponent(n)}">${esc(n)}</a>`;
const lnkTag = t => `<a href="#/tag/${encodeURIComponent(t)}" class="tag">${esc(t)}</a>`;
const lnkOriginal = id => {
  const o = data.originals.find(x => x.id === id);
  return o ? `<a href="#/original/${id}">${esc(o.title)}</a>` : esc(id);
};
const stars = p => '★'.repeat(Math.min(5, Math.round(p / 2500)));
const lnkSource = u => {
  if (!u) return '';
  let host = u;
  try { host = new URL(u).hostname; } catch (e) {}
  return `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(host)} ↗</a>`;
};

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
  if (w.cover) return w.cover;
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
  const cover = workCover(w, module);
  return `<div class="work-item"${attrs}>
      <a class="card-thumb" href="#/${module}/${w.id}" aria-label="查看 ${esc(w.name)} 详情">
        <img src="${esc(cover)}" alt="${esc(w.name)} 封面" loading="lazy"${module === 'video' ? ' referrerpolicy="no-referrer"' : ''} onerror="this.remove()">
        ${badge}
        <span class="hover-pop" aria-hidden="true"><img src="${esc(cover)}" alt=""${module === 'video' ? ' referrerpolicy="no-referrer"' : ''} onerror="this.parentElement.remove()"></span>
      </a>
      <div class="card-body">
        <h3><a href="#/${module}/${w.id}">${esc(w.name)}</a></h3>
        <div class="work-meta">
          <span>作者: ${lnkCircle(w.circle)}</span>
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
    <input id="search" class="field" placeholder="搜索作品名/作者/角色/标签…">
    ${origFilter}
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空筛选条件<br><button id="clearBtn" class="btn">清空搜索与筛选</button></p>
    <div class="work-list${module === 'music' ? ' work-list-music' : ''}">${items}</div>
    ${fabBtn(module)}`;

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
      <a class="video-thumb" href="#/video/${w.id}" aria-label="查看 ${esc(w.name)} 详情">
        <img src="${esc(w.cover)}" alt="${esc(w.name)} 封面" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">
        <span class="video-type">${esc(w.type)}</span>
        <span class="hover-pop" aria-hidden="true"><img src="${esc(w.cover)}" alt="" referrerpolicy="no-referrer" onerror="this.parentElement.remove()"></span>
      </a>
      <div class="video-body">
        <h3><a href="#/video/${w.id}">${esc(w.name)}</a></h3>
        <div class="work-meta">
          <span>作者: ${lnkCircle(w.circle)}</span>
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
    <input id="search" class="field" placeholder="搜索视频名/作者/创作者/角色/标签…">
    <p id="no-result" class="empty-state" hidden>无匹配结果 —— 换个关键词，或清空搜索<br><button id="clearBtn" class="btn">清空搜索</button></p>
    <div class="video-grid">${items}</div>
    ${fabBtn('video')}`;

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

// ===== 添加作品：右下角浮动按钮（FAB）+ 上传表单（Day 10 新增） =====
const fabBtn = module => `
  <a class="fab-add" href="#/${module}/add" aria-label="添加作品" title="添加作品">
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
    <span class="fab-tip">点击上传作品</span>
  </a>`;

function renderAddForm(module) {
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const videoFields = module === 'video' ? `
      <label>视频类型<input id="addType" class="field" placeholder="如：PV / 手书 / MMD"></label>
      <label>平台<input id="addPlatform" class="field" placeholder="如：Bilibili"></label>
      <label>视频链接<input id="addUrl" class="field" placeholder="https://…"></label>` : '';
  $app.innerHTML = `
    <h2>添加作品 · ${labels[module]}</h2>
    <p class="work-meta">填写完成后点击右下方「上传」按钮，作品将以同列表一致的卡片形式加入${labels[module]}板块。</p>
    <form id="addForm" class="add-form">
      <label>作品名 *<input id="addName" class="field" required placeholder="必填"></label>
      <label>作者（社团）<input id="addCircle" class="field" placeholder="如：IOSYS"></label>
      <label>创作者<input id="addCreator" class="field" placeholder="如：ARM"></label>
      <label>年份<input id="addYear" class="field" type="number" placeholder="如：2024"></label>
      <label>登场角色（逗号分隔）<input id="addChars" class="field" placeholder="如：博丽灵梦, 雾雨魔理沙"></label>
      <label>原作标签（逗号分隔）<input id="addTags" class="field" placeholder="如：红魔乡, 妖妖梦"></label>
      <label>热度（数字）<input id="addPop" class="field" type="number" placeholder="如：5000"></label>
      <label>封面图地址<input id="addCover" class="field" placeholder="https://… 留空则按原作标签匹配封面"></label>
      <label>资料来源地址<input id="addSource" class="field" placeholder="https://…"></label>
      ${videoFields}
      <label>作品简介<textarea id="addDesc" class="field" rows="4" placeholder="一两句话介绍这部作品"></textarea></label>
      <div class="add-actions">
        <a class="btn" href="#/${module}">取消</a>
        <button class="detail-cta add-submit" type="submit">上传</button>
      </div>
    </form>`;
  document.getElementById('addForm').addEventListener('submit', e => {
    e.preventDefault();
    const val = id => (document.getElementById(id).value || '').trim();
    if (!val('addName')) return;
    const split = s => s ? s.split(/[,，、\s]+/).filter(Boolean) : [];
    const w = {
      id: Math.max(0, ...data[module].map(x => x.id)) + 1,
      name: val('addName'),
      circle: val('addCircle') || '未知作者',
      creator: val('addCreator'),
      year: Number(val('addYear')) || new Date().getFullYear(),
      characters: split(val('addChars')),
      tags: split(val('addTags')),
      popularity: Number(val('addPop')) || 0,
      cover: val('addCover'),
      source_url: val('addSource'),
      description: val('addDesc') || '（暂无简介）',
    };
    if (module === 'video') {
      w.type = val('addType') || '视频';
      w.platform = val('addPlatform') || 'Bilibili';
      w.url = val('addUrl') || w.source_url || '#';
    }
    data[module].push(w);
    location.hash = `#/${module}`;
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

// ===== 反查（角色 / 作者 / 标签） =====
function renderReverse(kind, val) {
  const fieldMap = { character: 'characters', circle: 'circle', tag: 'tags' };
  const labelMap = { character: '角色', circle: '作者', tag: '原作' };
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
  $app.innerHTML = `<h2>${esc(labelMap[kind] || kind)}: ${esc(val)}</h2><div class="work-list">${blocks}</div><p><a href="#/">← 返回首页</a></p>`;
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
    <div class="detail-layout">
      <div class="detail-media">
        <div class="video-thumb" style="margin:0;max-width:100%;">
          <img class="zoomable" src="${esc(workCover(w, module))}" alt="${esc(w.name)} 封面" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">
        </div>
        <p class="zoom-hint">点击配图查看大图</p>
        ${detailActions(module, w.id, w.source_url, workCover(w, module))}
      </div>
      <div class="detail-info">
        <div class="work-meta">作者: ${lnkCircle(w.circle)} · ${w.year} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
        ${creatorRow}
        ${origRow}${gameRow}
        <div class="work-meta">角色: ${w.characters.map(lnkChar).join(', ')}</div>
        <div class="work-meta">原作: ${(w.tags||[]).map(lnkTag).join(' ')}</div>
        <p style="margin-top:0;">${esc(w.description)}</p>
        <p>资料来源: ${lnkSource(w.source_url)}</p>
        <button class="btn edit-btn" type="button" data-module="${esc(module)}" data-id="${esc(w.id)}">✎ 修改介绍</button>
      </div>
    </div>
    <p><a href="#/${module}">← 返回${esc(module)}</a> · <a href="#/">首页</a></p>`;
}

// ===== 视频详情页 =====
function renderVideoDetail(w) {
  const origRow = w.original_title ? `<div class="work-meta">原曲: ${esc(w.original_title)}</div>` : '';
  $app.innerHTML = `
    <h2>${esc(w.name)}</h2>
    <div class="detail-layout">
      <div class="detail-media">
        <div class="video-thumb" style="margin:0;max-width:100%;">
          <img class="zoomable" src="${esc(w.cover)}" alt="${esc(w.name)} 封面" referrerpolicy="no-referrer" onerror="this.remove()">
          <span class="video-type">${esc(w.type)}</span>
        </div>
        <p class="zoom-hint">点击配图查看大图</p>
        ${detailActions('video', w.id, w.source_url, w.cover)}
      </div>
      <div class="detail-info">
        <div class="work-meta">作者: ${lnkCircle(w.circle)} · 创作者: ${esc(w.creator)} · ${w.year}</div>
        <div class="work-meta">平台: ${esc(w.platform)}${w.bvid ? ` · <a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.bvid)}</a>` : ''} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
        ${origRow}
        <div class="work-meta">角色: ${(w.characters||[]).map(lnkChar).join(', ')}</div>
        ${(w.tags||[]).length ? `<div class="work-meta">原作: ${w.tags.map(lnkTag).join(' ')}</div>` : ''}
        <p style="margin-top:0;">${esc(w.description)}</p>
        <p><a href="${esc(w.url)}" target="_blank" rel="noopener">▶ 前往 ${esc(w.platform)} 观看 ↗</a></p>
        <p>资料来源: ${lnkSource(w.source_url)}</p>
        <button class="btn edit-btn" type="button" data-module="video" data-id="${esc(w.id)}">✎ 修改介绍</button>
      </div>
    </div>
    <p><a href="#/video">← 返回同人视频</a> · <a href="#/">首页</a></p>`;
}

// ===== 我的收藏页：跨模块聚合所有收藏作品（Day 10 新增） =====
// 数据被移除/刷新丢失的作品自动跳过，不会出现死卡片。
function renderFavs() {
  const cards = favs.map(f => {
    const w = (data[f.module] || []).find(x => x.id === f.id);
    return w ? workCard(w, f.module) : '';
  }).filter(Boolean).join('');
  $app.innerHTML = `
    <h2>我的收藏 (${favs.length})</h2>
    ${cards
      ? `<div class="work-list">${cards}</div>`
      : '<p class="empty-state">还没有收藏任何作品<br>打开任意作品详情页，点击「收藏」按钮即可加入这里</p>'}
    <p><a href="#/">← 返回首页</a></p>`;
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
  if (p[0] === 'fav') return renderFavs();
  if (['music','doujin','game','video','art'].includes(p[0])) {
    if (p[1] === 'add') return renderAddForm(p[0]);
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
