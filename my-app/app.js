// ===== 数据加载（首次进入才真正 fetch，之后复用内存 data） =====
// cache: 'no-cache' —— python http.server 不发 Cache-Control，浏览器会启发式缓存 JSON，
// 导致改了数据却看不到更新。强制回源校验，始终拿最新数据。
// dataPromise：加载缓存。首次进入时 fetch 一次并缓存 Promise；之后所有路由（hashchange → route）
// 都 await 同一个 Promise，绝不重复请求。这同时修掉两个坑：
//   ①【baka 冻结页随机误现】——之前每次切页面都并发 7 个 fetch，快速连点/来回点会成打请求，
//     任一瞬时失败（网络抖动/连接数上限/限流）就让 Promise.all 整体 reject → 误弹「baka 冻结」页。
//     现在只请求一次，正常浏览时根本不再发网络请求，也就不会再误弹。
//   ②【内存修改跨页丢失】——「上传作品 / 修改介绍」改的是内存里的 data，之前每次导航重新 fetch 会覆盖掉；
//     现在跨页面保留（刷新仍清空，Day 23 接数据库后再持久化）。
let data = { music: [], doujin: [], game: [], video: [], art: [], originals: [], original_games: { categories: [], games: [] }, characters: [], circles: [] };
let dataPromise = null;
function loadData() {
  if (dataPromise) return dataPromise; // 已加载或正在加载：并发调用共享同一结果，不重复发请求
  dataPromise = (async () => {
    const [m, d, g, v, a, o, og, c, ci] = await Promise.all(
      ['music','doujin','game','video','art','originals','original_games','characters','circles'].map(k =>
        fetch(`data/${k}.json`, { cache: 'no-cache' })
          .then(r => {
            if (!r.ok) throw new Error(`data/${k}.json 返回 HTTP ${r.status}`);
            return r.json();
          }))
    );
    data = { music: m, doujin: d, game: g, video: v, art: a, originals: o, original_games: og, characters: c?.characters || [], circles: Array.isArray(ci) ? ci : (ci?.circles || []) };
  })();
  return dataPromise;
}

// ===== 通用 =====
const $app = document.getElementById('app');
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// 入场动画结束后清除该元素的 animation：若将来误用 both/forwards，末帧会被永久套用，
// 使元素长期处于层叠上下文，把卡片上的 hover 小窗等「小窗图层」困在顶栏(z-index:1000)之下。
// 动画结束即释放，保证任何界面产生的小窗都位于顶栏之上。
document.addEventListener('animationend', e => {
  const el = e.target;
  if (el && el.style && el.matches &&
      el.matches('#app > *, #app .work-item, #app .video-card, #app .og-card, #app .module-card')) {
    el.style.animation = 'none';
  }
}, true);
// 分类页空状态：任何分类没有作品时统一显示这句话
const EMPTY_CATEGORY = '幻想乡的未知之地？！(𑘧ˬ𑘧)！？';

// ===== 排序控件（收藏页 / 子列表页 / 搜索页 共用） =====
// 排序维度：fav（收藏时间/数据顺序）、pop（热度）、views（浏览次数）。
// 方向：asc = 升序（由远到近 / 由低到高 / 由少到多），desc = 降序（由近到远 / 由高到低 / 由多到少）。
// 默认方向：fav 由近到远、pop 由高到低、views 由多到少（均为 desc）。
let currentSort = 'fav';
// 收藏页当前激活的分类标签（全部 / music / doujin / game / video / art）
let currentFavTab = 'all';
const SORT_LABELS = { fav: '按收藏时间', pop: '按热度', views: '按浏览次数' };
const DIR_LABELS = {
  fav:   { asc: '由远到近', desc: '由近到远' },
  pop:   { asc: '由低到高', desc: '由高到低' },
  views: { asc: '由少到多', desc: '由多到少' },
};
const DEFAULT_DIR = { fav: 'desc', pop: 'desc', views: 'desc' };
const currentDir = { ...DEFAULT_DIR };
const SORT_OPTIONS = [
  { key: 'fav',   text: '按收藏时间排序' },
  { key: 'pop',   text: '按热度排序' },
  { key: 'views', text: '按浏览次数排序' },
];
// 对容器内卡片按排序键 + 方向重排（原地移动 DOM，保留搜索筛选的显隐状态）
function sortDom(container, key, dir) {
  if (!container) return;
  const d = dir || (currentDir[key] || 'desc');
  const mult = d === 'asc' ? 1 : -1;
  const kids = Array.from(container.children);
  const val = el => {
    if (key === 'pop')   return Number(el.dataset.sortPop || 0);
    if (key === 'views') return Number(el.dataset.sortViews || 0);
    if (key === 'fav')   return el.dataset.idx !== undefined ? Number(el.dataset.idx) : Number(el.dataset.id || 0);
    return Number(el.dataset.id || 0);
  };
  kids.sort((a, b) => mult * (val(a) - val(b)));
  kids.forEach(el => container.appendChild(el));
}
// 方向按钮 HTML：依当前排序键生成对应的两个方向按钮（默认方向高亮）
function dirButtonsHTML(key) {
  const dir = currentDir[key] || 'desc';
  return ['desc', 'asc'].map(d => `<button class="sort-dir${d === dir ? ' active' : ''}" type="button" data-dir="${d}">${esc(DIR_LABELS[key][d])}</button>`).join('');
}
// 排序控件 HTML：按钮显示当前「方式（方向）」，hover/展开可换方式，下方显示该方式对应的方向切换按钮
function sortControlHTML() {
  const key = currentSort;
  const dir = currentDir[key] || 'desc';
  return `
  <div class="sort-control" id="sortControl">
    <button class="sort-btn" id="sortBtn" type="button" aria-haspopup="true" aria-expanded="false">
      <span class="sort-btn-label">排序：${esc(SORT_LABELS[key] + '（' + DIR_LABELS[key][dir] + '）')}</span>
      <span class="sort-caret" aria-hidden="true">▾</span>
    </button>
    <ul class="sort-menu" id="sortMenu">
      ${SORT_OPTIONS.map(o => `<li class="sort-opt${o.key === currentSort ? ' active' : ''}" data-sort="${o.key}" role="button" tabindex="0">${esc(o.text)}</li>`).join('')}
    </ul>
    <div class="sort-dirs" id="sortDirs">${dirButtonsHTML(key)}</div>
  </div>`;
}
// 绑定排序控件：换方式 → 切换方向按钮并重排；换方向 → 重排。两个维度均即时生效
function bindSort(gridSelector) {
  const ctrl = document.getElementById('sortControl');
  if (!ctrl || !ctrl.classList) return;
  const btn = document.getElementById('sortBtn');
  const menu = document.getElementById('sortMenu');
  const dirs = document.getElementById('sortDirs');
  const label = (ctrl.querySelector && ctrl.querySelector('.sort-btn-label')) || null;
  const qsa = sel => (typeof document.querySelectorAll === 'function') ? document.querySelectorAll(sel) : [];
  // 重排后列表回到「只显示三行」：换排序后前三行应该是新顺序的前三行
  const reSort = () => qsa(gridSelector).forEach(c => {
    sortDom(c, currentSort, currentDir[currentSort] || 'desc');
    resetPagedList(c);
  });
  const updateLabel = () => { if (label) label.textContent = '排序：' + SORT_LABELS[currentSort] + '（' + DIR_LABELS[currentSort][currentDir[currentSort] || 'desc'] + '）'; };
  const bindDirs = () => {
    const db = (dirs && typeof dirs.querySelectorAll === 'function') ? dirs.querySelectorAll('.sort-dir') : [];
    db.forEach(b => {
      const act = () => {
        const d = b.dataset && b.dataset.dir;
        if (!d) return;
        currentDir[currentSort] = d;
        db.forEach(x => x.classList && x.classList.toggle('active', !!(x.dataset && x.dataset.dir === d)));
        updateLabel();
        reSort();
      };
      if (b.addEventListener) b.addEventListener('click', act);
    });
  };
  if (btn && btn.addEventListener) {
    btn.addEventListener('click', e => {
      e.stopPropagation && e.stopPropagation();
      const open = !(ctrl.classList.contains && ctrl.classList.contains('open'));
      ctrl.classList.toggle('open', open);
      btn.setAttribute && btn.setAttribute('aria-expanded', String(open));
    });
  }
  const opts = (menu && typeof menu.querySelectorAll === 'function') ? menu.querySelectorAll('.sort-opt') : [];
  opts.forEach(li => {
    const act = () => {
      const key = li.dataset && li.dataset.sort;
      if (!key) return;
      currentSort = key;
      if (menu && typeof menu.querySelectorAll === 'function') {
        menu.querySelectorAll('.sort-opt').forEach(x => x.classList && x.classList.toggle('active', !!(x.dataset && x.dataset.sort === key)));
      }
      if (dirs && typeof dirs.querySelectorAll === 'function') { dirs.innerHTML = dirButtonsHTML(key); bindDirs(); }
      ctrl.classList.remove('open');
      btn && btn.setAttribute && btn.setAttribute('aria-expanded', 'false');
      updateLabel();
      reSort();
    };
    if (li.addEventListener) {
      li.addEventListener('click', act);
      li.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault && e.preventDefault(); act(); } });
    }
  });
  bindDirs();
  // 初始化时立即按当前排序方式 + 方向重排一次（切换页面后保持用户上次的选择）
  reSort();
}
// 全局：点击控件外部时收起菜单（脚本加载时注册一次）
if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
  document.addEventListener('click', e => {
    const ctrl = document.getElementById('sortControl');
    if (ctrl && !ctrl.contains(e.target)) {
      ctrl.classList.remove('open');
      const b = document.getElementById('sortBtn');
      if (b) b.setAttribute('aria-expanded', 'false');
    }
  });
}
// 全局：任何方式跳转外部其他网站前，先显示「少女祈祷中」页（拦截 target=_blank 的外链点击）
if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
  document.addEventListener('click', e => {
    const a = (e.target && e.target.closest) ? e.target.closest('a[target="_blank"]') : null;
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (/^https?:\/\//i.test(href)) {
      e.preventDefault();
      goExternal(href, true);
    }
  });
}

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
// 事件委托：详情页 .zoomable 点开放大；列表/视频/原作卡片的 hover-pop 小窗点击打开原图
$app.addEventListener('click', e => {
  const t = e.target && e.target.closest ? e.target.closest('.zoomable') : null;
  if (t) { openLightbox(t.currentSrc || t.src, t.alt); return; }
  const pop = e.target && e.target.closest ? e.target.closest('.hover-pop') : null;
  if (pop) {
    e.preventDefault();
    e.stopPropagation();
    const img = pop.querySelector('img');
    if (img) goExternal(img.currentSrc || img.src, true);
  }
});
if ($lightbox) $lightbox.addEventListener('click', closeLightbox);
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

// ===== 页面状态记忆：返回上一页时恢复分类标签与滚动位置 =====
// pageState[hash] = { tab/wtab: 激活的分类标签, scrollTop: 离开时的滚动位置 }（内存态，刷新即清）
const pageState = {};
let backNav = false; // 左上角返回键按下时置 true，路由渲染完成后消费一次
// 标记「这次是返回导航」：只有返回时才恢复上次状态，正常点进来一律走默认分类
const markBackNav = () => { backNav = true; };
const saveScroll = () => {
  const k = location.hash || '#/';
  (pageState[k] ||= {}).scrollTop = window.scrollY || 0;
};
// 滚动节流记录：离开页面前 pageState 里始终有最新位置可取
let scrollTimer;
window.addEventListener('scroll', () => {
  clearTimeout(scrollTimer);
  scrollTimer = setTimeout(saveScroll, 150);
});

// ===== 页面背景：原作详情页用该原作封面做整页背景（--page-bg 由 CSS 统一处理样式） =====
// 只在渲染原作详情页时挂上，离开任何页面都会先清掉，避免串页。
// 无头验证环境 document.body.style 不存在，故用能力检测保护。
const setPageBg = url => {
  if (!document.body) return;
  document.body.classList.add('og-bg');
  if (document.body.style && document.body.style.setProperty) {
    document.body.style.setProperty('--page-bg', `url('${String(url).replace(/'/g, "\\'")}')`);
  }
};
const clearPageBg = () => {
  if (!document.body) return;
  document.body.classList.remove('og-bg');
  if (document.body.style && document.body.style.removeProperty) {
    document.body.style.removeProperty('--page-bg');
  }
};

// ===== 顶栏返回按钮：回到上一个所处页面（Day 10 新增；Day 11 补：返回后恢复页面状态） =====
const $backBtn = document.getElementById('backBtn');
if ($backBtn) $backBtn.addEventListener('click', () => {
  // 无历史记录时（新标签直接打开）退回首页
  if (window.history && window.history.length > 1) {
    saveScroll();       // 先记下当前页退出位置（滚动节流可能差最后一帧）
    markBackNav();      // 标记返回导航：渲染时恢复分类，渲染后恢复滚动位置
    window.history.back();
  }
  else location.hash = '#/';
});

// ===== 操作反馈 toast（Day 11：让每个关键动作「生效」得看得见） =====
// 容器在 index.html 预置（fixed 定位，跨 hash 路由不消失——上传后跳列表页提示仍可见）。
// 连续触发时重置计时器：快速连点收藏/取消，只保留最后一条提示，不会叠一串。
const $toast = document.getElementById('toast');
let toastTimer;
function showToast(msg) {
  if (!$toast) return;
  $toast.textContent = msg;
  $toast.hidden = false;
  // 重开动画：先摘掉类再强制回流，连续触发时每次都重新滑入
  $toast.classList.remove('toast-in');
  void $toast.offsetWidth;
  $toast.classList.add('toast-in');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $toast.hidden = true; }, 2200);
}

// ===== 我的收藏（Day 10 新增） =====
// 存储结构：[{ module, id }]。优先 localStorage 持久化；
// 无 localStorage 环境（如无头验证脚本）读取会抛 ReferenceError，被 catch 后退化为内存数组。
let favs = [];
// 本次停留在「我的收藏」页期间取消收藏的作品：卡片仍保留在列表中（星为空心，可再次收藏），
// 离开收藏页、或下次重新进入时才真正移除。记录原 idx/ts 以便原位保留、不打乱顺序。
let stickyFavs = [];
let wasOnFav = false; // 上一次路由是否停在收藏页，用于判断是否为「重新进入」
try { favs = JSON.parse(localStorage.getItem('touhou_favs') || '[]'); } catch (e) {}
const saveFavs = () => { try { localStorage.setItem('touhou_favs', JSON.stringify(favs)); } catch (e) {} };
const isFav = (module, id) => favs.some(f => f.module === module && f.id === id);
const toggleFav = (module, id) => {
  const i = favs.findIndex(f => f.module === module && f.id === id);
  if (i >= 0) favs.splice(i, 1); else favs.push({ module, id, ts: Date.now() });
  saveFavs();
};
// 详情页收藏按钮：星形图标——未收藏空心（描边）、已收藏实心（填充），由 CSS 按 .is-faved 切换
const favBtn = (module, id) => {
  const on = isFav(module, Number(id));
  return `<button class="detail-cta detail-cta-fav${on ? ' is-faved' : ''}" type="button"
            data-module="${esc(module)}" data-id="${esc(id)}"
            aria-label="${on ? '取消收藏' : '收藏该作品'}" title="${on ? '取消收藏' : '收藏'}">
          <svg class="star-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
        </button>`;
};
// 事件委托：详情页内任意收藏按钮，点击即切换收藏状态并同步按钮样式
$app.addEventListener('click', e => {
  const b = e.target && e.target.closest ? e.target.closest('.detail-cta-fav') : null;
  if (!b) return;
  e.preventDefault();
  const { module, id } = b.dataset;
  const nid = Number(id);
  // 取消收藏前先记下它在收藏列表中的原始位置与时间，便于本页内原位保留、不打乱顺序
  const prev = favs.find(f => f.module === module && f.id === nid);
  const prevIdx = prev ? favs.indexOf(prev) : -1;
  const prevTs = prev ? prev.ts : Date.now();
  const wasOn = !!prev;
  toggleFav(module, nid);
  const on = isFav(module, nid);
  b.classList.toggle('is-faved', on);
  showToast(on ? '⭐ 已加入我的收藏' : '已从我的收藏移除');
  // 收藏页卡片上的星形按钮：取消收藏后卡片暂留（星变空心，可再次收藏），
  // 下次进入收藏页才真正移除；切换分类/计数仍保持正确。
  const isCardStar = b.classList && b.classList.contains && b.classList.contains('fav-card-star');
  if (isCardStar) {
    if (wasOn && !on) {
      stickyFavs = stickyFavs.filter(s => !(s.module === module && s.id === nid));
      stickyFavs.push({ module, id: nid, ts: prevTs, idx: prevIdx });
    }
    if (typeof renderFavs === 'function') renderFavs();
  }
});

// ===== 原作下载资源（下载链接 / 安装包） =====
// 结构：{ [gameId]: [ { id, type:'link'|'pkg', name, url, note, kind } ] }，按原作分类存放。
// 上传后优先 localStorage 持久化；无 localStorage 环境（无头验证脚本）退化为内存对象。
let downloads = {};
try { downloads = JSON.parse(localStorage.getItem('touhou_downloads') || '{}') || {}; } catch (e) {}
const saveDownloads = () => { try { localStorage.setItem('touhou_downloads', JSON.stringify(downloads)); } catch (e) {} };
const gameDownloads = id => (downloads[id] || (downloads[id] = []));
const dlUid = () => 'dl_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

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
    showToast('✓ 修改已保存');
    renderDetail(module, String(w.id)); // 重渲染详情页展示新信息（不重新加载数据）
  };
  const cancel = document.getElementById('editCancel');
  if (cancel) cancel.addEventListener('click', closeEditModal);
  if ($editModal) $editModal.hidden = false;
  document.body.classList.add('no-scroll');
  // 键盘友好（Day 11 加练）：弹窗一开焦点就落在作品名输入框，可直接打字；Esc 关闭见全局监听
  try { document.getElementById('edName')?.focus?.(); } catch (e) {}
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
  const idxAttr = (opts.idx !== undefined) ? ` data-idx="${esc(opts.idx)}"` : '';
  const origLink = w.original ? `<br>原曲: ${lnkOriginal(w.original)}` : '';
  const badge = module === 'video' && w.type ? `<span class="card-badge">${esc(w.type)}</span>` : '';
  const extraRow = module === 'video'
    ? `<div class="work-meta">创作者: ${esc(w.creator)} · 平台: ${esc(w.platform)}</div>`
    : (w.creator ? `<div class="work-meta">创作者: ${esc(w.creator)}</div>` : '');
  const cover = workCover(w, module);
  const moduleLabels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const catLabel = opts.showModule && moduleLabels[module] ? `<span class="cat-label">${esc(moduleLabels[module])}</span>` : '';
  // 星形按钮的实心/空心按「当前真实收藏状态」渲染：
  // 收藏页上刚取消收藏、但本次仍暂留的卡片会显示为空心星，可再次点击收藏。
  const starOn = isFav(module, w.id);
  const favStar = opts.favStar
    ? `<button class="detail-cta-fav fav-card-star${starOn ? ' is-faved' : ''}" type="button" data-module="${esc(module)}" data-id="${esc(w.id)}" aria-label="${starOn ? '取消收藏' : '收藏'}" title="${starOn ? '取消收藏' : '收藏'}">
        <svg class="star-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
       </button>`
    : '';
  return `<div class="work-item"${attrs}${idxAttr} data-id="${esc(w.id)}" data-sort-pop="${w.popularity || 0}" data-sort-views="${w.views || 0}">
      <a class="card-thumb" href="#/${module}/${w.id}" aria-label="查看 ${esc(w.name)} 详情">
        <img src="${esc(cover)}" alt="${esc(w.name)} 封面" loading="lazy"${module === 'video' ? ' referrerpolicy="no-referrer"' : ''} onerror="this.remove()">
        ${badge}
        <span class="hover-pop" aria-hidden="true"><img src="${esc(cover)}" alt=""${module === 'video' ? ' referrerpolicy="no-referrer"' : ''} onerror="this.parentElement.remove()"></span>
      </a>
      <div class="card-body">
        ${catLabel}
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
      ${favStar}
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
    </div>
    ${fabAddHome}`;
}

// 首页「加入作品」浮动按钮：形状/位置与子页面 FAB 一致，点击进入分类选择页
const fabAddHome = `
  <a class="fab-add" href="#/add" aria-label="加入作品" title="加入作品">
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></path></svg>
    <span class="fab-tip">点击上传作品</span>
  </a>`;

// ===== 搜索无结果：趣味空状态 + 三按钮（与全站搜索 renderSearch 一致） =====
// 在 applyFilter 判定 0 命中时调用；q 为当前搜索框内容（用于百度预填）
function fillSearchEmpty(el, q) {
  const baiduUrl = 'https://www.baidu.com/s?wd=' + encodeURIComponent(q || '');
  el.innerHTML = `
    <p class="search-empty-title">你想要的知识或许在幻想乡境界之外哦</p>
    <div class="search-empty-actions">
      <button id="searchOtherBtn" class="btn" type="button">去看看幻想乡的其他风景</button>
      <button id="baiduBtn" class="btn" type="button" data-baidu="${esc(baiduUrl)}">去幻想乡以外的世界寻找</button>
      <button id="addWorkBtn" class="btn" type="button" data-go="#/add">寻找境界的妖怪将其遁入幻想</button>
    </div>`;
  const gs = document.getElementById('globalSearch');
  // ① 去看看幻想乡的其他风景：清空搜索框，并跳转到空白搜索页 #/search/
  document.getElementById('searchOtherBtn').addEventListener('click', () => {
    if (gs) { gs.value = ''; if (gs.focus) gs.focus(); }
    const inline = document.getElementById('search');
    if (inline) {
      inline.value = '';
      if (inline.dispatchEvent) inline.dispatchEvent(new Event('input'));
    }
    const oid = document.getElementById('origFilter');
    if (oid) oid.value = '';
    if (typeof location !== 'undefined') location.hash = '#/search/';
  });
  // ② 去幻想乡以外的世界寻找：新标签打开百度，预填未搜到的内容
  document.getElementById('baiduBtn').addEventListener('click', () => {
    goExternal(document.getElementById('baiduBtn').dataset.baidu, true);
  });
  // ③ 寻找境界的妖怪将其遁入幻想：跳转首页「加入作品」编辑页
  document.getElementById('addWorkBtn').addEventListener('click', () => {
    location.hash = document.getElementById('addWorkBtn').dataset.go;
  });
}

// ===== 模块列表（共用渲染，支持搜索 + 原曲筛选） =====
function renderList(module) {
  if (module === 'video') return renderVideoList();
  currentSort = 'pop'; // 模块子列表默认按热度排序
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', art: '同人图' };
  const items = data[module].map(w => {
    const search = [w.name, w.circle, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase();
    return workCard(w, module, { search });
  }).join('') || `<p class="empty-state">${EMPTY_CATEGORY}</p>`;

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
    ${sortControlHTML()}
    <input id="search" class="field" aria-label="搜索作品：可按作品名、作者、角色、标签筛选" placeholder="搜索作品名/作者/角色/标签…">
    ${origFilter}
    <div id="no-result" class="search-empty" role="status" aria-live="polite" hidden></div>
    <div class="work-list${module === 'music' ? ' work-list-music' : ''}" id="workGrid">${items}</div>
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
    const nr = document.getElementById('no-result');
    if (visible === 0) { fillSearchEmpty(nr, q); nr.hidden = false; }
    else { nr.hidden = true; }
    // 筛选结果变了 → 列表回到「只显示三行」，避免沿用上一次展开的数量
    resetPagedList(document.getElementById('workGrid'));
  };
  document.getElementById('search').addEventListener('input', applyFilter);
  if (module === 'music') {
    document.getElementById('origFilter').addEventListener('change', applyFilter);
  }
  bindSort('#workGrid');
  applyPresetQuery();
}

// ===== 同人视频列表（封面卡片） =====
function renderVideoList() {
  currentSort = 'pop'; // 同人视频列表默认按热度排序
  const items = data.video.map(w => {
    const search = [w.name, w.circle, w.creator, w.type, ...(w.characters||[]), ...(w.tags||[])].join(' ').toLowerCase();
    return `<div class="video-card" data-search="${esc(search)}" data-id="${esc(w.id)}" data-sort-pop="${w.popularity || 0}" data-sort-views="${w.views || 0}">
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
  }).join('') || `<p class="empty-state">${EMPTY_CATEGORY}</p>`;

  $app.innerHTML = `
    <h2>同人视频</h2>
    ${sortControlHTML()}
    <input id="search" class="field" aria-label="搜索视频：可按视频名、作者、创作者、角色、标签筛选" placeholder="搜索视频名/作者/创作者/角色/标签…">
    <div id="no-result" class="search-empty" role="status" aria-live="polite" hidden></div>
    <div class="video-grid" id="workGrid">${items}</div>
    ${fabBtn('video')}`;

  const applyFilter = () => {
    const q = document.getElementById('search').value.toLowerCase();
    let visible = 0;
    document.querySelectorAll('.video-card').forEach(it => {
      const ok = it.dataset.search.includes(q);
      it.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    const nr = document.getElementById('no-result');
    if (visible === 0) { fillSearchEmpty(nr, q); nr.hidden = false; }
    else { nr.hidden = true; }
    // 筛选结果变了 → 列表回到「只显示三行」，避免沿用上一次展开的数量
    resetPagedList(document.getElementById('workGrid'));
  };
  document.getElementById('search').addEventListener('input', applyFilter);
  bindSort('#workGrid');
  applyPresetQuery();
}

// 地址栏预设筛选词：#/music?q=灵梦 这类链接可直达筛选结果，方便复现与分享
function presetQuery() {
  const m = String((window.location && window.location.hash) || '').match(/[?&]q=([^&]*)/);
  return m ? decodeURIComponent(m[1] || '') : '';
}
// 列表页渲染后：把预设词填进搜索框并立刻筛一次
function applyPresetQuery() {
  const q = presetQuery();
  if (!q) return;
  const input = document.getElementById('search');
  if (!input) return;
  input.value = q;
  input.dispatchEvent && input.dispatchEvent(new Event('input'));
}

// ===== 添加作品：分类选择页（首页「加入作品」FAB 入口） =====
function renderAddChooser() {
  const items = [
    { m: 'music',  label: '同人音乐', img: 'assets/modules/module-music.webp' },
    { m: 'doujin', label: '同人漫画', img: 'assets/modules/module-doujin.jpg' },
    { m: 'game',   label: '同人游戏', img: 'assets/modules/module-game2.jpg' },
    { m: 'video',  label: '同人视频', img: 'assets/modules/module-video2.jpg' },
    { m: 'art',    label: '同人图',   img: 'assets/modules/module-art.jpg' },
  ];
  $app.innerHTML = `
    <div class="add-page">
      <div class="add-card">
        <h2>加入作品 · 选择所属分类</h2>
        <p class="work-meta">这部作品属于哪个板块？点击下方分类，进入对应的编辑界面。</p>
        <div class="module-grid">
          ${items.map(it => `
            <a class="module-card" href="#/${it.m}/add">
              <div class="module-thumb"><img src="${it.img}" alt="${it.label}" loading="lazy" onerror="this.parentElement.remove()"></div>
              <h2>${it.label}</h2>
            </a>`).join('')}
        </div>
        <div class="home-back">${homeFabHTML()}</div>
      </div>
    </div>`;
}

// ===== 返回首页按钮：粉色圆形 + 房子图标（页内所有「返回首页」链接统一复用） =====
function homeFabHTML(extraClass) {
  const cls = extraClass ? ' ' + extraClass : '';
  return `<a class="home-fab${cls}" href="#/" aria-label="返回首页" title="返回首页">
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
  </a>`;
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
    <div class="add-page">
      <div class="add-card">
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
        </form>
      </div>
    </div>`;
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
    showToast(`✓ 「${w.name}」上传成功，已加入${labels[module]}`);
    location.hash = `#/${module}`;
  });
}

// ===== 原作板块：全部官方原作按「旧作/新作/格斗作/外传」分组 =====
function ogCard(g) {
  return `<div class="og-card">
    <a class="og-thumb" href="#/original/${g.id}" aria-label="查看 ${esc(g.title)} 详情">
      <div class="og-cover-wrap">
        <img src="${esc(g.cover)}" alt="${esc(g.title)} 封面" loading="lazy" onerror="this.parentElement.style.display='none'">
        <span class="og-th">${esc(g.th)}</span>
      </div>
      <span class="hover-pop" aria-hidden="true"><img src="${esc(g.cover)}" alt=""></span>
    </a>
    <div class="og-info">
      <h4><a href="#/original/${g.id}">${esc(g.title)}</a></h4>
      <p class="og-sub">${esc(g.subtitle)}</p>
      <p class="og-year">${g.year}</p>
    </div>
  </div>`;
}

// Th 号转数值（Th7.5 → 7.5），用于把格斗作插到正确的整数作之间。
// 官方漫画等没有 Th 号的条目返回 9999，统一排在最后（按数据里的年份顺序）。
const thNum = g => {
  const m = String(g.th || '').match(/^th\s*([\d.]+)/i);
  return m ? parseFloat(m[1]) : 9999;
};

function renderOriginals() {
  const cats = data.original_games.categories;
  // 所有原作按 Th 号从小到大排一次，各分类视图继承这个顺序（filter 不改变顺序）
  const sorted = [...data.original_games.games].sort((a, b) => thNum(a) - thNum(b));
  // 分类视图：最前面加「全部」，点它一次看所有原作；savedTab 允许 'all'
  const views = [
    { id: 'all', label: '全部', list: sorted },
    ...cats.map(c => ({ id: c.id, label: c.label, list: sorted.filter(g => g.category === c.id) })),
  ];
  // 只有返回导航才恢复上次激活的分类；从首页等处正常进来一律停在「全部」
  const savedTab = backNav ? (pageState['#/original'] || {}).tab : null;
  const initTab = views.some(v => v.id === savedTab) ? savedTab : 'all';
  const groups = views.map(v => `
    <section class="og-group${v.id === initTab ? '' : ' hidden'}" data-cat="${v.id}">
      <h3>${esc(v.label)} (${v.list.length} 部)</h3>
      <div class="og-grid">${v.list.map(ogCard).join('')}</div>
    </section>`).join('');

  $app.innerHTML = `
    <h2>官方原作</h2>
    <div class="og-tabs">
      ${views.map(v => `<button class="og-tab" data-tab="${v.id}">${esc(v.label)}</button>`).join('')}
    </div>
    <div class="og-panels">${groups}</div>`;

  const tabs = document.querySelectorAll('.og-tab');
  const panels = document.querySelectorAll('.og-group');
  const switchTab = id => {
    tabs.forEach(b => b.classList.toggle('active', b.dataset.tab === id));
    panels.forEach(p => p.classList.toggle('hidden', p.dataset.cat !== id));
    (pageState['#/original'] ||= {}).tab = id; // 记住激活的分类，返回时恢复
  };
  tabs.forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  switchTab(initTab);
}

// ===== 角色查询辅助 =====
// 角色按 id / 中文名 / 别名（如「蕾米莉亚·斯卡雷特」）都能命中，兼容作品数据里的两种写法
const findCharacter = key => {
  const k = String(key || '').trim();
  return (data.characters || []).find(c => c.id === k || c.name === k || (c.aliases || []).includes(k));
};
const findCircle = name => (data.circles || []).find(c => c.name === name);
// 某原作下、除「自机主角」外的全部角色（用于原作详情页「人物标签」面板）
const gameCharacters = gameId => (data.characters || [])
  .filter(c => (c.games || []).includes(gameId) && !(c.playableIn || []).includes(gameId));

// ===== 单个原作详情页：封面 + Th 标注 + 人物/原曲标签页 + 同人作品 =====
function renderOriginalGame(id) {
  const g = data.original_games.games.find(x => x.id === id);
  if (!g) {
    $app.innerHTML = `<p class="empty-state">未找到该原作</p><p><a href="#/original">← 返回原作列表</a></p>`;
    return;
  }

  // 「人物标签」面板用的角色集合（除自机主角外）；下面的同人作品也按这些角色分类
  const chars = gameCharacters(g.id);
  // 该原作下的同人作品：以「人物标签」里的角色作为分类标签，
  // 作品按其「介绍栏(description)」是否出现该角色（含别名）归类；哪个角色都没命中的进「其他」。
  const matched = [];
  ['music','doujin','game','video','art'].forEach(m => {
    (data[m] || []).forEach(w => {
      if ((w.tags || []).includes(g.tag) || w.original_game === g.tag) {
        matched.push({ w, m });
      }
    });
  });
  const descOf = w => String(w.description || '');
  const hitNames = (w, ch) => [ch.name, ...(ch.aliases || [])].some(n => descOf(w).includes(n));
  // 角色标签：只保留至少有 1 部作品的角色，避免空标签
  const charTabs = chars
    .map(ch => ({
      id: ch.id,
      label: ch.name,
      items: matched.filter(({ w }) => hitNames(w, ch)).map(({ w, m }) => workCard(w, m, { showModule: true })),
    }))
    .filter(t => t.items.length);
  // 介绍栏未提及任何人物标签角色的作品归入「其他」
  const others = matched
    .filter(({ w }) => !chars.some(ch => hitNames(w, ch)))
    .map(({ w, m }) => workCard(w, m, { showModule: true }));
  if (others.length) charTabs.push({ id: 'other', label: '其他', items: others });
  const firstActive = charTabs[0]?.id || 'other';
  // 只有返回导航才恢复上次激活的分类；正常点进来一律从第一个有作品的分类开始
  const savedWtab = backNav ? (pageState[`#/original/${id}`] || {}).wtab : null;
  const initWork = charTabs.some(t => t.id === savedWtab) ? savedWtab : firstActive;
  const workTabs = charTabs.map(t =>
    `<button class="og-tab" data-wtab="${esc(t.id)}" type="button">${esc(t.label)} (${t.items.length})</button>`
  ).join('');
  const workPanels = charTabs.map(t => `
    <div class="og-panel${t.id === initWork ? '' : ' hidden'}" data-wpanel="${esc(t.id)}">
      ${t.items.length
        ? `<div class="work-list work-list-og">${t.items.join('')}</div>`
        : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
    </div>`).join('');

  setPageBg(g.cover); // 整页背景换成该原作的封面（样式由 CSS 的 body.og-bg 处理）

  // 「人物标签」面板：该原作下除自机主角外的全部角色，每个带黄昏边境绘图缩略图，点开进角色详细页
  const charsPanel = chars.length
    ? `<div class="char-grid">${chars.map(ch => `
        <a class="char-tag" href="#/character/${encodeURIComponent(ch.id)}" title="${esc(ch.name)}">
          <span class="char-art${ch.twilight_art ? '' : ' no-art'}">
            <img src="${esc(ch.twilight_art || '')}" alt="${esc(ch.name)} 绘图" loading="lazy"
              onerror="this.style.display='none';this.parentNode.classList.add('no-art')">
            <span class="char-art-fallback">${esc(ch.name)}</span>
          </span>
          <span class="char-name">${esc(ch.name)}</span>
        </a>`).join('')}</div>`
    : `<p class="empty-state">该原作的角色资料整理中…</p>`;

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
        <a class="detail-cta dl-entry-btn" href="#/original/${encodeURIComponent(g.id)}/download">
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z"/></svg>
          下载原作
        </a>
      </div>
    </div>
    <div class="og-tabs">
      <button class="og-tab active" data-tab="chars">人物标签</button>
      <button class="og-tab" data-tab="music">原曲标签</button>
    </div>
    <div class="og-panel" data-panel="chars">${charsPanel}</div>
    <div class="og-panel hidden" data-panel="music"><p class="empty-state">原曲标签内容待补充…</p></div>
    <h3 class="og-section-title">该原作下的同人作品</h3>
    <div class="og-tabs">${workTabs}</div>
    ${workPanels}
    <p><a href="#/original">← 返回原作列表</a></p>`;

  // 人物/原曲标签页（data-tab）与同人作品分类标签页（data-wtab）属性隔离，互不干扰
  const tabs = document.querySelectorAll('.og-tab[data-tab]');
  const panels = document.querySelectorAll('.og-panel[data-panel]');
  tabs.forEach(tab => tab.addEventListener('click', () => {
    const t = tab.dataset.tab;
    tabs.forEach(b => b.classList.remove('active'));
    tab.classList.add('active');
    panels.forEach(p => p.classList.toggle('hidden', p.dataset.panel !== t));
  }));
  // 同人作品分类切换：点标签只显示对应板块的作品面板
  const wtabs = document.querySelectorAll('.og-tab[data-wtab]');
  const wpanels = document.querySelectorAll('.og-panel[data-wpanel]');
  const switchWork = m => {
    wtabs.forEach(b => b.classList.toggle('active', b.dataset.wtab === m));
    wpanels.forEach(p => p.classList.toggle('hidden', p.dataset.wpanel !== m));
    (pageState[`#/original/${id}`] ||= {}).wtab = m; // 记住激活的分类，返回时恢复
  };
  wtabs.forEach(tab => tab.addEventListener('click', () => switchWork(tab.dataset.wtab)));
  switchWork(initWork);
}

// ===== 下载原作页：按「下载链接 / 安装包」分类展示 + 右下角上传按钮 =====
function renderOriginalDownload(id) {
  const g = data.original_games.games.find(x => x.id === id);
  if (!g) {
    $app.innerHTML = `<p class="empty-state">未找到该原作</p><p><a href="#/original">← 返回原作列表</a></p>`;
    return;
  }
  const list = gameDownloads(id);
  const links = list.filter(d => d.type === 'link');
  const pkgs = list.filter(d => d.type === 'pkg');

  const itemHTML = d => `
    <li class="dl-item">
      <div class="dl-item-main">
        <span class="dl-name">${esc(d.name || '未命名资源')}</span>
        ${d.kind ? `<span class="dl-kind">${esc(d.kind)}</span>` : ''}
      </div>
      ${d.note ? `<p class="dl-note">${esc(d.note)}</p>` : ''}
      <div class="dl-item-actions">
        <a class="detail-cta detail-cta-ghost dl-go" href="${esc(d.url)}"
           target="_blank" rel="noopener"${d.type === 'pkg' ? ` download="${esc(d.filename || d.name || '')}"` : ''}>
          ${d.type === 'pkg' ? '下载安装包' : '前往下载'}
        </a>
        <button class="dl-del" type="button" data-dl-del="${esc(d.id)}" aria-label="删除该资源" title="删除该资源">✕ 删除</button>
      </div>
    </li>`;

  const section = (title, arr, emptyHint) => `
    <section class="dl-section">
      <h3 class="dl-title">${title} (${arr.length})</h3>
      ${arr.length ? `<ul class="dl-list">${arr.map(itemHTML).join('')}</ul>`
        : `<p class="empty-state">${emptyHint}</p>`}
    </section>`;

  $app.innerHTML = `
    <div class="dl-page">
      <p class="dl-breadcrumb"><a href="#/original/${encodeURIComponent(id)}">← 返回 ${esc(g.title)}</a></p>
      <h2 class="dl-head">${esc(g.title)} · 下载</h2>
      <p class="work-meta">本页按「下载链接」与「安装包」分类整理该原作的下载资源。点击右下角按钮可上传多个下载链接或安装包。</p>
      ${section('下载链接', links, '暂无下载链接，点右下角按钮添加')}
      ${section('安装包', pkgs, '暂无安装包，点右下角按钮上传')}
    </div>
    <button class="fab-add" id="dlUploadBtn" type="button" aria-label="上传下载链接 / 安装包" title="上传下载链接 / 安装包">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
      <span class="fab-tip">上传下载链接 / 安装包</span>
    </button>`;

  // 删除某条资源
  $app.querySelectorAll('[data-dl-del]').forEach(btn => btn.addEventListener('click', () => {
    const lid = btn.dataset.dlDel;
    downloads[id] = (downloads[id] || []).filter(d => String(d.id) !== String(lid));
    saveDownloads();
    showToast('已删除该下载资源');
    renderOriginalDownload(id);
  }));
  const upBtn = document.getElementById('dlUploadBtn');
  if (upBtn) upBtn.addEventListener('click', () => openDownloadModal(id));
}

// 下载资源上传弹窗：一行 = 一条资源（类型 / 名称 / 链接或本地文件 / 备注），可「＋ 添加一行」批量提交
const $dlModal = document.getElementById('dlModal');
const $dlForm = document.getElementById('dlForm');
const $dlClose = document.getElementById('dlClose');
function closeDownloadModal() {
  if ($dlModal) $dlModal.hidden = true;
  document.body.classList.remove('no-scroll');
}
if ($dlClose) $dlClose.addEventListener('click', closeDownloadModal);
if ($dlModal) $dlModal.addEventListener('click', e => { if (e.target === $dlModal) closeDownloadModal(); });

function dlRowHTML() {
  return `
    <div class="dl-row" data-row>
      <div class="dl-row-head">
        <select class="field dl-row-type" aria-label="资源类型">
          <option value="link">下载链接</option>
          <option value="pkg">安装包</option>
        </select>
        <button class="dl-row-del" type="button" aria-label="删除此行" title="删除此行">✕</button>
      </div>
      <input class="field dl-row-name" placeholder="名称，如：Steam 商店页 / 官方安装包 v1.0">
      <input class="field dl-row-url" placeholder="链接（https://…）">
      <input class="field dl-row-note" placeholder="备注（选填），如：Windows / 需科学上网">
      <label class="dl-row-file-label">或直接选择本地安装包文件
        <input class="field dl-row-file" type="file">
      </label>
    </div>`;
}
function bindDlRowDel(scope) {
  (scope || $dlForm).querySelectorAll('[data-row] .dl-row-del').forEach(btn => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      const rows = $dlForm.querySelectorAll('[data-row]');
      if (rows.length <= 1) { showToast('至少保留一行'); return; }
      btn.closest('[data-row]').remove();
    });
  });
}
function openDownloadModal(id) {
  if (!$dlForm) return;
  $dlForm.innerHTML = `
    <div class="dl-rows" id="dlRows">${dlRowHTML()}</div>
    <div class="dl-form-actions">
      <button class="btn" type="button" id="dlAddRow">＋ 添加一行</button>
    </div>
    <div class="add-actions">
      <button class="btn" type="button" id="dlCancel">取消</button>
      <button class="detail-cta add-submit" type="submit">上传</button>
    </div>`;
  bindDlRowDel();
  document.getElementById('dlAddRow').addEventListener('click', () => {
    document.getElementById('dlRows').insertAdjacentHTML('beforeend', dlRowHTML());
    bindDlRowDel();
  });
  document.getElementById('dlCancel').addEventListener('click', closeDownloadModal);
  $dlForm.onsubmit = e => {
    e.preventDefault();
    const rows = Array.from($dlForm.querySelectorAll('[data-row]'));
    let added = 0;
    rows.forEach(row => {
      const type = row.querySelector('.dl-row-type').value;
      let name = (row.querySelector('.dl-row-name').value || '').trim();
      let url = (row.querySelector('.dl-row-url').value || '').trim();
      const note = (row.querySelector('.dl-row-note').value || '').trim();
      const file = row.querySelector('.dl-row-file').files && row.querySelector('.dl-row-file').files[0];
      let kind = '', filename = '';
      // 选了本地文件：用 blob URL 作为临时直链（仅本次会话有效），文件名作为默认名称
      if (file) {
        try { url = URL.createObjectURL(file); } catch (err) { url = url || ''; }
        filename = file.name;
        if (!name) name = file.name;
        kind = '本地文件（仅本次会话）';
      }
      if (!url && !name) return; // 整行空白，跳过
      if (!url) { showToast('「' + (name || '未命名') + '」缺少链接或文件，已跳过'); return; }
      gameDownloads(id).push({ id: dlUid(), type, name: name || (type === 'pkg' ? '安装包' : '下载链接'), url, note, kind, filename });
      added++;
    });
    if (!added) { showToast('没有可上传的内容'); return; }
    saveDownloads();
    closeDownloadModal();
    showToast('✓ 已上传 ' + added + ' 条下载资源');
    renderOriginalDownload(id);
  };
  if ($dlModal) $dlModal.hidden = false;
  document.body.classList.add('no-scroll');
}

// ===== 全站搜索（Day 10：顶栏搜索框 → #/search/<词> 分组结果页） =====
function renderSearch(q) {
  currentSort = 'pop'; // 搜索页默认按热度排序（由高到低）
  const gs = document.getElementById('globalSearch');
  if (gs && (gs.value || '') !== q) gs.value = q;
  if (!q) { $app.innerHTML = '<p class="empty-state">输入关键词探寻幻想乡</p>'; return; }
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
    // 全站搜索无结果：显示趣味空状态 + 三个引导按钮
    const baiduUrl = 'https://www.baidu.com/s?wd=' + encodeURIComponent(q); // 跳转百度时预填未搜到的内容
    $app.innerHTML = `
      <div class="search-empty">
        <p class="search-empty-title">你想要的知识或许在幻想乡境界之外哦</p>
        <div class="search-empty-actions">
          <button id="searchOtherBtn" class="btn" type="button">去看看幻想乡的其他风景</button>
          <button id="baiduBtn" class="btn" type="button" data-baidu="${esc(baiduUrl)}">去幻想乡以外的世界寻找</button>
          <button id="addWorkBtn" class="btn" type="button" data-go="#/add">寻找境界的妖怪将其遁入幻想</button>
        </div>
      </div>`;
    const gs = document.getElementById('globalSearch');
    // ① 去看看幻想乡的其他风景：清空搜索框，并跳转到空白搜索页 #/search/
    document.getElementById('searchOtherBtn').addEventListener('click', () => {
      if (gs) { gs.value = ''; if (gs.focus) gs.focus(); }
      const inline = document.getElementById('search');
      if (inline) inline.value = '';
      if (typeof location !== 'undefined') location.hash = '#/search/';
    });
    // ② 去幻想乡以外的世界寻找：新标签打开百度，搜索框预填未搜到的内容
    document.getElementById('baiduBtn').addEventListener('click', () => {
      const url = document.getElementById('baiduBtn').dataset.baidu;
      goExternal(url, true);
    });
    // ③ 寻找境界的妖怪将其遁入幻想：跳转首页「加入作品」编辑页
    document.getElementById('addWorkBtn').addEventListener('click', () => {
      location.hash = document.getElementById('addWorkBtn').dataset.go;
    });
    return;
  }
  const blocks = groups.filter(g => g.items.length).map(g => `
    <div class="group-block">
      <h2>${esc(g.label)} (${g.items.length})</h2>
      <div class="work-list">${g.items.map(w => {
        if (g.m === 'original') {
          const cov = tagCover(w) || moduleFallback.video;
          return `<div class="work-item" data-id="0" data-sort-pop="0" data-sort-views="0">
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
  $app.innerHTML = `
    <h2>全站搜索：${esc(q)}（${total} 条）</h2>
    ${sortControlHTML()}
    <div id="searchResults">${blocks}</div>
    <div class="home-back">${homeFabHTML()}</div>`;
  bindSort('#searchResults .work-list');
}

// ===== 反查（角色 / 作者 / 标签） =====
function renderReverse(kind, val) {
  if (kind === 'circle') return renderCircle(val);
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
  if (!total) { $app.innerHTML = `<p class="empty-state">无匹配：${esc(val)}</p><div class="home-back">${homeFabHTML()}</div>`; return; }
  const blocks = groups.filter(g => g.items.length).map(g => `
    <div class="group-block">
      <h2>${esc(g.m)} (${g.items.length})</h2>
      ${g.items.map(w => workCard(w, g.m)).join('')}
    </div>`).join('');
  $app.innerHTML = `<h2>${esc(labelMap[kind] || kind)}: ${esc(val)}</h2><div class="work-list">${blocks}</div><div class="home-back">${homeFabHTML()}</div>`;
}

// ===== 作者详细页：与角色页同格式（头像 + 简介 + 平台信息 + 分类作品） =====
function renderCircle(val) {
  const ci = findCircle(val) || {};
  const groups = ['music','doujin','game','video','art'].map(m => {
    const items = (data[m]||[]).filter(w => {
      const c = w.circle;
      if (Array.isArray(c)) return c.includes(val);
      return c === val;
    });
    return { m, items };
  });
  const total = groups.reduce((s, g) => s + g.items.length, 0);
  if (!total) { $app.innerHTML = `<p class="empty-state">无匹配：${esc(val)}</p><div class="home-back">${homeFabHTML()}</div>`; return; }

  const labels = { all: '全部', music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const moduleTabs = ['music','doujin','game','video','art'].map(m => ({ id: m, label: labels[m], count: groups.find(g => g.m === m).items.length }));
  const allTab = { id: 'all', label: labels.all, count: total };
  const workTabs = [allTab, ...moduleTabs].map(t => `
    <button class="og-tab${t.id === 'all' ? ' active' : ''}" data-wtab="${esc(t.id)}" type="button">${esc(t.label)} (${t.count})</button>`
  ).join('');
  const allItems = groups.flatMap(g => g.items.map(w => ({ w, m: g.m })));
  const allPanel = `
    <div class="og-panel" data-wpanel="all">
      ${allItems.length
        ? `<div class="work-list work-list-og">${allItems.map(({ w, m }) => workCard(w, m, { showModule: true })).join('')}</div>`
        : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
    </div>`;
  const workPanels = allPanel + groups.map(g => `
    <div class="og-panel hidden" data-wpanel="${esc(g.m)}">
      ${g.items.length
        ? `<div class="work-list work-list-og">${g.items.map(w => workCard(w, g.m, { showModule: true })).join('')}</div>`
        : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
    </div>`
  ).join('');

  const tp = ci.top_platform || {};
  const platformName = tp.name || 'unknown';
  const platformLine = platformName !== 'unknown' && tp.url
    ? `<p class="circle-platform">主平台：<a href="${esc(tp.url)}" target="_blank" rel="noopener">${esc(platformName)}${tp.followers ? ' · ' + esc(tp.followers) + ' 粉丝' : ''}</a></p>`
    : '';
  const intro = ci.intro || '（简介整理中）';
  const sourceLine = ci.source_url
    ? `<p class="circle-src">资料来源：<a href="${esc(ci.source_url)}" target="_blank" rel="noopener">${esc(ci.source_url)}</a></p>`
    : '';
  const avatar = ci.avatar || '';

  $app.innerHTML = `
    <div class="char-detail circle-detail">
      <div class="char-head circle-head">
        <div class="char-info circle-info">
          <h2 class="char-name-h">${esc(val)}</h2>
          ${ci.name_en ? `<p class="char-en">${esc(ci.name_en)}</p>` : ''}
          <section class="char-moe circle-moe">
            <h3>社团 · 简介</h3>
            <p class="clamp-3">${esc(intro)}</p>
            ${platformLine}
            ${sourceLine}
          </section>
        </div>
        <div class="char-art-box circle-art-box">
          <span class="char-art${avatar ? '' : ' no-art'}">
            <img class="zoomable" src="${esc(avatar)}" alt="${esc(val)} 头像" loading="lazy"
              onerror="this.style.display='none';this.parentNode.classList.add('no-art')">
            <span class="char-art-fallback">${esc(val)}<br>头像待补</span>
          </span>
        </div>
      </div>
      <h3 class="char-section-title">该社团/作者的作品</h3>
      ${total ? `<div class="og-tabs">${workTabs}</div>${workPanels}` : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
      <p><a href="#/">← 返回首页</a> · ${homeFabHTML('home-fab--sm')}</p>
    </div>`;

  if (total) {
    const wtabs = document.querySelectorAll('.og-tab[data-wtab]');
    const wpanels = document.querySelectorAll('.og-panel[data-wpanel]');
    const switchWork = m => {
      wtabs.forEach(b => b.classList.toggle('active', b.dataset.wtab === m));
      wpanels.forEach(p => p.classList.toggle('hidden', p.dataset.wpanel !== m));
    };
    wtabs.forEach(tab => tab.addEventListener('click', () => switchWork(tab.dataset.wtab)));
  }
}

// ===== 角色详细页：右上黄昏边境绘图 + 萌娘百科简介/基本资料 + 相关同人作品 =====
function renderCharacter(key) {
  const ch = findCharacter(key);
  if (!ch) {
    $app.innerHTML = `<p class="empty-state">未找到该角色</p><p><a href="#/original">← 返回原作列表</a></p>`;
    return;
  }
  // 关联作品：作品 characters 字段含该角色的中文名或任一别名（兼容「蕾米莉亚」/「蕾米莉亚·斯卡雷特」两种写法）
  const names = [ch.name, ...(ch.aliases || [])];
  const labels = { all: '全部', music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const modules = ['music', 'doujin', 'game', 'video', 'art'];
  const groups = modules.map(m => {
    const items = (data[m] || []).filter(w => (w.characters || []).some(n => names.includes(n)));
    return { m, items };
  });
  const total = groups.reduce((s, g) => s + g.items.length, 0);
  const allTab = { id: 'all', label: labels.all, count: total };
  const moduleTabs = modules.map(m => ({ id: m, label: labels[m], count: groups.find(g => g.m === m).items.length }));
  const workTabs = [allTab, ...moduleTabs].map(t => `
    <button class="og-tab${t.id === 'all' ? ' active' : ''}" data-wtab="${esc(t.id)}" type="button">${esc(t.label)} (${t.count})</button>`
  ).join('');
  // 「全部」面板：汇总所有分类作品并横向排列；每个卡片额外标注所属分类
  const allItems = groups.flatMap(g => g.items.map(w => ({ w, m: g.m })));
  const allPanel = `
    <div class="og-panel" data-wpanel="all">
      ${allItems.length
        ? `<div class="work-list work-list-og">${allItems.map(({ w, m }) => workCard(w, m, { showModule: true })).join('')}</div>`
        : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
    </div>`;
  const workPanels = allPanel + groups.map(g => `
    <div class="og-panel hidden" data-wpanel="${esc(g.m)}">
      ${g.items.length
        ? `<div class="work-list work-list-og">${g.items.map(w => workCard(w, g.m, { showModule: true })).join('')}</div>`
        : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
    </div>`
  ).join('');

  const mg = ch.moegirl || {};
  const basic = mg.basic || {};
  const basicRows = Object.entries(basic)
    .map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('');

  $app.innerHTML = `
    <div class="char-detail">
      <div class="char-head">
        <div class="char-info">
          <h2 class="char-name-h">${esc(ch.name)}</h2>
          ${ch.name_en ? `<p class="char-en">${esc(ch.name_en)}</p>` : ''}
          ${basic['称号'] ? `<p class="char-title">「${esc(basic['称号'])}」</p>` : ''}
          <section class="char-moe">
            <h3>萌娘百科 · 简介</h3>
            <p class="clamp-3">${esc(mg.intro || '（简介整理中）')}</p>
            ${basicRows ? `<h3>萌娘百科 · 基本资料</h3><table class="char-basic"><tbody>${basicRows}</tbody></table>` : ''}
            ${ch.source_url ? `<p class="char-src">资料来源：<a href="${esc(ch.source_url)}" target="_blank" rel="noopener">${esc(ch.source_url)}</a></p>` : ''}
          </section>
        </div>
        <div class="char-art-box">
          <span class="char-art${ch.twilight_art ? '' : ' no-art'}">
            <img class="zoomable" src="${esc(ch.twilight_art || '')}" alt="${esc(ch.name)} 黄昏边境绘图" loading="lazy"
              onerror="this.style.display='none';this.parentNode.classList.add('no-art')">
            <span class="char-art-fallback">${esc(ch.name)}<br>绘图待补</span>
          </span>
        </div>
      </div>
      <h3 class="char-section-title">与该角色相关的同人作品</h3>
      ${total ? `<div class="og-tabs">${workTabs}</div>${workPanels}` : `<p class="empty-state">${EMPTY_CATEGORY}</p>`}
      <p><a href="#/original">← 返回原作列表</a> · ${homeFabHTML('home-fab--sm')}</p>`;

  if (total) {
    const wtabs = document.querySelectorAll('.og-tab[data-wtab]');
    const wpanels = document.querySelectorAll('.og-panel[data-wpanel]');
    const switchWork = m => {
      wtabs.forEach(b => b.classList.toggle('active', b.dataset.wtab === m));
      wpanels.forEach(p => p.classList.toggle('hidden', p.dataset.wpanel !== m));
    };
    wtabs.forEach(tab => tab.addEventListener('click', () => switchWork(tab.dataset.wtab)));
  }
}

// ===== 介绍文字折叠：超过三行只显示三行，点「展开」看剩下文字 =====
// 用法：给介绍段落加 class="clamp-3"，路由渲染后由 applyClamp3() 统一处理：
//   · 不足三行 → 保持原样，不加按钮；
//   · 超过三行 → 折叠到三行，并在段落后面插入「展开 / 收起」按钮。
// 测量时机放在 rAF 里，确保浏览器已完成布局后再判断行数。
function applyClamp3(root) {
  const nodes = (root || document).querySelectorAll('.clamp-3');
  nodes.forEach(p => {
    if (p.dataset.clamp === 'done') return;
    p.dataset.clamp = 'done';
    // 判定是否真超过三行：先临时解除折叠量出「完整高度」，
    // 再回到折叠态量出「三行高度」，两者接近说明不足三行，就不加按钮。
    // （注意：Chromium 在 -webkit-line-clamp 下 scrollHeight 会等于 clientHeight，
    //   不能直接用 scrollHeight > clientHeight 判断溢出，故采用这种两态测量。）
    p.classList.add('clamp-open');
    const full = p.scrollHeight;
    p.classList.remove('clamp-open');
    const shown = p.clientHeight;
    if (!full || !shown || full - shown <= 2) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'clamp-toggle';
    btn.textContent = '展开';
    btn.setAttribute('aria-expanded', 'false');
    btn.addEventListener('click', () => {
      const open = p.classList.toggle('clamp-open');
      btn.textContent = open ? '收起' : '展开';
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    p.insertAdjacentElement('afterend', btn);
  });
}

// ===== 列表分页：一次只展示三行作品，点下方「展开更多」再加载三行 =====
// 作用范围：所有作品列表容器（.work-list / .video-grid），包含各分类 Tab 面板内的列表。
// 卡片始终渲染在 DOM 里，超出的只是被隐藏，排序/筛选/搜索不会丢数据。
const LM_ROWS = 3;

// 一行几列：把卡片临时全部显示后，按 offsetTop 分组统计第一行有几张卡
function lmCols(cards) {
  if (!cards.length) return 1;
  let cols = 0;
  const top0 = cards[0].offsetTop;
  for (let i = 0; i < cards.length; i++) {
    if (cards[i].offsetTop !== top0) break;
    cols++;
  }
  return cols || 1;
}
function lmRemoveBtn(list) {
  if (list.__lmBtn && list.__lmBtn.parentNode) list.__lmBtn.parentNode.removeChild(list.__lmBtn);
  list.__lmBtn = null;
}
// 对单个列表应用分页；reset=true 时回到「只显示三行」
function pageList(list, reset) {
  if (!list || !list.classList || !list.children) return;
  const cards = Array.prototype.filter.call(list.children,
    el => el.classList && (el.classList.contains('work-item') || el.classList.contains('video-card')));
  if (!cards.length) { lmRemoveBtn(list); return; }
  cards.forEach(c => c.classList.remove('lm-hidden'));
  // 容器不可见（处于未激活的分类面板中）时量不出列数，等面板切出来再处理
  if (!list.clientWidth) return;
  const active = cards.filter(c => c.style.display !== 'none'); // 已通过搜索/筛选的卡片
  const size = Math.max(1, lmCols(active) * LM_ROWS);           // 三行 = 列数 × 3
  if (reset) { delete list.dataset.lmShown; delete list.dataset.lmSize; }
  let shown = Number(list.dataset.lmShown) || size;
  if (shown < size) shown = size;
  if (shown > active.length) shown = active.length;
  active.forEach((c, i) => c.classList.toggle('lm-hidden', i >= shown));
  list.dataset.lmShown = String(shown);
  list.dataset.lmSize = String(size);

  const remain = active.length - shown;
  if (remain <= 0) { lmRemoveBtn(list); return; }   // 全部展示完，按钮自动消失
  let btn = list.__lmBtn;
  if (!btn) {
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'load-more-btn';
    btn.addEventListener('click', () => {
      list.dataset.lmShown = String((Number(list.dataset.lmShown) || 0) + (Number(list.dataset.lmSize) || LM_ROWS));
      pageList(list);
    });
    if (list.parentNode) list.parentNode.insertBefore(btn, list.nextSibling);
    list.__lmBtn = btn;
  }
  btn.textContent = '展开更多（还有 ' + remain + ' 部）';
}
// 统一入口：路由渲染后、分类 Tab 切换后、窗口尺寸变化后都要重新算一次
function initPagedLists(root, force) {
  const lists = (root && root.querySelectorAll) ? root.querySelectorAll('.work-list, .video-grid') : [];
  Array.prototype.forEach.call(lists, l => pageList(l, force));
}
function resetPagedList(list) { pageList(list, true); }

// ===== 详情页 =====
function renderDetail(module, id) {
  const w = data[module].find(x => x.id === Number(id));
  if (!w) { $app.innerHTML = `<p class="empty-state">未找到该作品</p><div class="home-back">${homeFabHTML()}</div>`; return; }
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
        ${detailActions(module, w.id, w.netease_url || w.source_url, workCover(w, module))}
      </div>
      <div class="detail-info">
        <div class="work-meta">作者: ${lnkCircle(w.circle)} · ${w.year} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
        ${creatorRow}
        ${origRow}${gameRow}
        ${w.netease_url ? `<div class="work-meta">网易云试听: <a href="${esc(w.netease_url)}" target="_blank" rel="noopener">music.163.com ↗</a></div>` : ''}
        <div class="work-meta">角色: ${w.characters.map(lnkChar).join(', ')}</div>
        <div class="work-meta">原作: ${(w.tags||[]).map(lnkTag).join(' ')}</div>
        <p class="clamp-3" style="margin-top:0;">${esc(w.description)}</p>
        <p>资料来源: ${lnkSource(w.source_url)}</p>
        <button class="btn edit-btn" type="button" data-module="${esc(module)}" data-id="${esc(w.id)}">✎ 修改介绍</button>
      </div>
    </div>
    <p class="detail-nav">
      <a class="nav-fab" href="#/${module}" aria-label="返回上一页" title="返回上一页">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        <span class="fab-tip">返回上一页</span>
      </a>
      ${homeFabHTML('home-fab--sm')}
    </p>`;
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
        ${detailActions('video', w.id, w.url || w.source_url, w.cover)}
      </div>
      <div class="detail-info">
        <div class="work-meta">作者: ${lnkCircle(w.circle)} · 创作者: ${esc(w.creator)} · ${w.year}</div>
        <div class="work-meta">平台: ${esc(w.platform)}${w.bvid ? ` · <a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.bvid)}</a>` : ''} · <span class="popularity">${stars(w.popularity)}</span> · 热度: ${w.popularity}</div>
        ${origRow}
        <div class="work-meta">角色: ${(w.characters||[]).map(lnkChar).join(', ')}</div>
        ${(w.tags||[]).length ? `<div class="work-meta">原作: ${w.tags.map(lnkTag).join(' ')}</div>` : ''}
        <p class="clamp-3" style="margin-top:0;">${esc(w.description)}</p>
        <p><a href="${esc(w.url)}" target="_blank" rel="noopener">▶ 前往 ${esc(w.platform)} 观看 ↗</a></p>
        <p>资料来源: ${lnkSource(w.source_url)}</p>
        <button class="btn edit-btn" type="button" data-module="video" data-id="${esc(w.id)}">✎ 修改介绍</button>
      </div>
    </div>
    <p class="detail-nav">
      <a class="nav-fab" href="#/video" aria-label="返回上一页" title="返回上一页">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        <span class="fab-tip">返回上一页</span>
      </a>
      <a class="home-fab home-fab--sm" href="#/" aria-label="返回首页" title="返回首页">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
        <span class="fab-tip">返回首页</span>
      </a>
    </p>`;
}

// ===== 我的收藏页：跨模块聚合所有收藏作品（Day 10 新增） =====
// 数据被移除/刷新丢失的作品自动跳过，不会出现死卡片。
function renderFavs() {
  currentSort = 'fav'; // 收藏页默认按收藏时间排序
  // 列表 = 真实收藏 + 本次停留期间取消收藏但暂留的条目（已被重新收藏的会自动过滤掉）
  const favEntries = favs.map((f, i) => ({ module: f.module, id: f.id, ts: f.ts, idx: i }));
  const stickyEntries = stickyFavs
    .filter(s => !isFav(s.module, s.id))
    .map(s => ({ module: s.module, id: s.id, ts: s.ts, idx: s.idx }));
  // 按原始收藏位置排序，暂留卡片保持在原位，列表顺序不会被打乱
  const favItems = [...favEntries, ...stickyEntries]
    .sort((a, b) => a.idx - b.idx)
    .map((f, i) => {
      const w = (data[f.module] || []).find(x => x.id === f.id);
      return w ? { ...w, _module: f.module, _idx: i, _ts: f.ts } : null;
    }).filter(Boolean);
  const hasFavs = favItems.length > 0;
  const slogan = '<div class="fav-slogan' + (hasFavs ? ' fav-slogan-fixed' : '') + '">将你感兴趣之物置入独属于你的隙间吧！</div>';

  if (!hasFavs) {
    $app.innerHTML = `
      <h2>我的收藏 (${favItems.length})</h2>
      <p class="empty-state">${slogan}</p>
      <div class="home-back">${homeFabHTML()}</div>`;
    return;
  }

  const modules = ['music', 'doujin', 'game', 'video', 'art'];
  const labels = { music: '同人音乐', doujin: '同人漫画', game: '同人游戏', video: '同人视频', art: '同人图' };
  const counts = { all: favItems.length };
  modules.forEach(m => counts[m] = favItems.filter(x => x._module === m).length);
  const makeCards = items => items.map(x => workCard(x, x._module, { idx: x._idx, favStar: true })).join('');
  const allCards = makeCards(favItems);

  const tabsHTML = `
    <div class="fav-tabs">
      <button class="fav-tab${currentFavTab === 'all' ? ' active' : ''}" data-ftab="all" type="button">全部 (${counts.all})</button>
      ${modules.map(m => `<button class="fav-tab${currentFavTab === m ? ' active' : ''}" data-ftab="${m}" type="button">${labels[m]} (${counts[m]})</button>`).join('')}
    </div>`;

  const panelsHTML = `
    <div class="fav-panels" id="workGrid">
      <div class="fav-panel${currentFavTab === 'all' ? ' active' : ''}" data-fpanel="all">
        ${allCards ? `<div class="work-list fav-work-list">${allCards}</div>` : '<p class="empty-state">暂无收藏</p>'}
      </div>
      ${modules.map(m => {
        const items = favItems.filter(x => x._module === m);
        return `<div class="fav-panel${currentFavTab === m ? ' active' : ''}" data-fpanel="${m}">
          ${items.length ? `<div class="work-list fav-work-list">${makeCards(items)}</div>` : '<p class="empty-state">暂无该分类收藏</p>'}
        </div>`;
      }).join('')}
    </div>`;

  const maxTs = favItems.reduce((m, x) => Math.max(m, x._ts || 0), 0);
  const lastTime = maxTs ? new Date(maxTs).toLocaleString('zh-CN') : '未知';

  $app.innerHTML = `
    <h2>我的收藏 (${favItems.length})</h2>
    ${sortControlHTML()}
    ${tabsHTML}
    ${panelsHTML}
    <div class="fav-last-time">最后收藏时间：${esc(lastTime)}</div>
    ${slogan}`;

  bindSort('.fav-panel .work-list');
  // 收藏页列表同样一次只展示三行（分类面板切换会整页重渲染，这里补一次分页）
  initPagedLists($app);
  // 分类标签切换：切模块时重新渲染，保留当前排序
  if (typeof document.querySelectorAll === 'function') {
    document.querySelectorAll('.fav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        currentFavTab = tab.dataset && tab.dataset.ftab;
        renderFavs();
      });
    });
  }
}

// ===== 路由 =====
// 跳转前统一显示「少女祈祷中」加载页：所有界面（含真实加载失败时的 baka 冻结页）
// 都先经过这一阶段，确保数据全部加载成功后才渲染目标页。
function showLoading() {
  $app.innerHTML = `
    <div class="loading-state">
      <div class="praying-text">少女祈祷中</div>
      <video class="praying-img" src="assets/praying.mp4?v=2" autoplay loop muted playsinline preload="auto" aria-label="少女祈祷中"></video>
    </div>`;
}

// ===== 子页面切换加载遮罩：目标子页首屏图片未就绪时，继续覆盖「少女祈祷中」 =====
// 首屏由根加载页（index.html）负责祈祷与等待；进入 my-app 后第一次路由不再重复祈祷，
// 其余子页面切换一律先亮起遮罩，等首屏图片（可见 img/video + body 级 CSS 背景图）就绪再揭开，
// 避免把没加载好的页面亮给用户。带超时兜底，绝不卡死。
let routeLoadingEl = null;
function ensureRouteLoading() {
  if (routeLoadingEl) return routeLoadingEl;
  routeLoadingEl = document.createElement('div');
  routeLoadingEl.id = 'route-loading';
  routeLoadingEl.className = 'route-loading';
  routeLoadingEl.innerHTML =
    '<div class="praying-text">少女祈祷中</div>' +
    '<video class="praying-img" src="assets/praying.mp4?v=2" autoplay loop muted playsinline preload="auto" aria-label="少女祈祷中"></video>';
  if (document.body) document.body.appendChild(routeLoadingEl);
  return routeLoadingEl;
}
function showRouteLoading() { ensureRouteLoading().classList.add('show'); }
function hideRouteLoading() { if (routeLoadingEl) routeLoadingEl.classList.remove('show'); }

// 元素是否处于可见子树（不被 display:none / visibility:hidden 的祖先隐藏）
function _elVisible(el) {
  let n = el;
  while (n && n !== document.body && n.nodeType === 1) {
    const s = getComputedStyle(n);
    if (s.display === 'none' || s.visibility === 'hidden') return false;
    n = n.parentNode;
  }
  return true;
}
// 元素是否在首屏视口内（懒加载图不在视口内则不阻塞切换）
function _inViewport(el) {
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight || document.documentElement.clientHeight || 0;
  return r.bottom > 0 && r.top < vh;
}
// 预载某个 CSS 背景图 URL
function _preloadBg(url) {
  return new Promise(res => {
    const img = new Image();
    img.onload = img.onerror = () => res();
    img.src = url;
  });
}
// 等目标页首屏图片就绪：可见 img/video + body 级 CSS 背景图；懒加载且不在首屏的图不阻塞；8s 超时兜底
async function waitForPageImages(root) {
  const proms = [];
  root.querySelectorAll('img, video').forEach(el => {
    if (!_elVisible(el)) return;
    if (el.tagName === 'IMG' && el.getAttribute('loading') === 'lazy' && !_inViewport(el)) return;
    if (el.tagName === 'IMG') {
      if (!el.complete || el.naturalWidth === 0) {
        proms.push(new Promise(res => {
          el.addEventListener('load', res, { once: true });
          el.addEventListener('error', res, { once: true });
        }));
      }
    } else if (el.tagName === 'VIDEO') {
      if (el.readyState < 2) {
        proms.push(new Promise(res => {
          el.addEventListener('loadeddata', res, { once: true });
          el.addEventListener('error', res, { once: true });
        }));
      }
    }
  });
  if (document.body) {
    const bi = getComputedStyle(document.body).backgroundImage;
    if (bi && bi !== 'none') {
      const m = bi.match(/url\(["']?([^"')]+)["']?\)/);
      if (m) proms.push(_preloadBg(m[1]));
    }
  }
  if (!proms.length) return;
  await Promise.race([
    Promise.all(proms),
    new Promise(res => setTimeout(res, 8000)),
  ]);
}
// 「被不明baka冻结」趣味页（数据加载失败 / 「教训baka」按钮直达均用此）。
// retryAction：揍完 baka 后的动作——真实加载失败传「重载数据」，按钮直达传「跳回原页面」。
function renderFrozen(retryAction) {
  $app.innerHTML = `
    <div class="empty-state error-frozen">
      <p class="frozen-msg">该页面似乎被不明baka冻结了<br>请狠狠地揍她一顿，让她知道你的厉害！</p>
      <button id="retryBtn" class="btn punch-btn" type="button">胖揍一顿baka</button>
      <img class="frozen-baka" src="assets/baka-cirno.jpg" alt="被冻住的baka" onerror="this.remove()">
    </div>`;
  const btn = document.getElementById('retryBtn');
  if (btn && btn.addEventListener) btn.addEventListener('click', () => {
    const img = document.querySelector ? document.querySelector('.frozen-baka') : null;
    if (img && img.classList) img.classList.add('shaking');
    showToast('正在胖揍baka…');
    setTimeout(() => { if (typeof retryAction === 'function') retryAction(); else route(); }, 500);
  });
}
// 自包含的「少女祈祷中」外部页 HTML（新标签打开时用，内联样式不依赖本站 CSS）
function prayingDocHtml() {
  const vid = (location.href.split('#')[0].replace(/index\.html$/, '')) + 'assets/praying.mp4?v=2';
  return '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>少女祈祷中…</title>'
    + '<style>html,body{margin:0;height:100%}body{display:flex;flex-direction:column;align-items:center;justify-content:center;'
    + 'background:linear-gradient(135deg,#fbeff3,#f4e7f0);font-family:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;'
    + 'color:#d96577;min-height:100vh}'
    + '.t{font-size:clamp(40px,8vw,86px);font-weight:800;background:linear-gradient(90deg,#e58aa0,#b06ab3);'
    + '-webkit-background-clip:text;background-clip:text;color:transparent;animation:p 1.4s ease-in-out infinite}'
    + '.t::after{content:"";animation:praying-dots 1.5s infinite}'
    + '.i{margin-top:24px;max-width:min(100%,520px);width:60%;max-height:60vh;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,.18);background:#fff}'
    + '.s{margin-top:16px;font-size:14px;color:#a86;opacity:.7}'
    + '@keyframes p{0%,100%{opacity:.55}50%{opacity:1}}'
    + '@keyframes praying-dots{0%,100%{content:""}25%{content:"."}50%{content:".."}75%{content:"..."}}</style></head><body>'
    + '<div class="t">少女祈祷中</div>'
    + '<video class="i" src="' + vid + '" autoplay loop muted playsinline preload="auto" aria-label="少女祈祷中"></video>'
    + '<div class="s">正在前往幻想乡之外…</div></body></html>';
}
// 跳转外部网站：先显示「少女祈祷中」页，待外部站点加载完成后自然取代祈祷页
function goExternal(url, newTab) {
  if (newTab !== false) {
    let w = null;
    try { w = window.open('about:blank', '_blank'); } catch (e) { w = null; }
    if (w) {
      try {
        w.document.open();
        w.document.write(prayingDocHtml());
        w.document.close();
      } catch (e) { /* 部分浏览器禁止写 about:blank，忽略，直接跳转 */ }
      // 稍等让祈祷页先渲染，再跳外部站（其自身加载完成后即取代祈祷页）
      setTimeout(() => { try { w.location.href = url; } catch (e2) { try { window.open(url, '_blank'); } catch (e3) {} } }, 350);
    } else {
      try { window.open(url, '_blank'); } catch (e) {} // 弹窗被拦截：直接打开，不再拦截祈祷页
    }
  } else {
    showLoading();
    setTimeout(() => { location.href = url; }, 350);
  }
}

let firstLoad = true; // 首次进入站点时，保证「少女祈祷中」加载页至少显示一段最短时间，让用户确实看到
let appFirstRoute = true; // 首屏由根加载页（index.html）负责祈祷与等待；进入 my-app 后第一次路由不再重复祈祷
let bakaReturnHash = '#/'; // 点「教训baka」按钮进入冻结页前的原页面，揍完返回用
async function routeInner() {
  const isFirst = appFirstRoute;
  appFirstRoute = false;
  // 子页面切换：先亮起「少女祈祷中」遮罩，等目标页首屏图片就绪再揭开；
  // 首屏已在根加载页祈祷过并确保图片就绪，进入 my-app 后第一次路由不重复祈祷。
  if (!isFirst) showRouteLoading();
  try {
    // 进入网站时：先加载好少女祈祷中页面，等数据全部就绪（且至少展示一个最短时长）再渲染
    const waits = [loadData()];
    if (firstLoad) waits.push(new Promise(r => setTimeout(r, 450)));
    await Promise.all(waits);
    firstLoad = false;
  } catch (e) {
    dataPromise = null; // 重置缓存，使「胖揍」重试（route）能重新拉取，而非复用上次失败的 Promise
    if (!isFirst) hideRouteLoading();
    // 错误态：加载失败时给出「被不明baka冻结」趣味页，按钮即重试（先揍动画再重载）
    renderFrozen(() => { dataPromise = null; route(); });
    return;
  }
  // 路径与查询串分开：#/music?q=灵梦 里的 ?q= 只用于预填筛选，不参与路由匹配
  const h = (location.hash.slice(1) || '/').split('?')[0];
  const p = h.split('/').filter(Boolean);
  // 首页才显示背景图，子页面保持干净白底
  if (document.body && document.body.classList) document.body.classList.toggle('home-bg', !p.length);
  // 上传作品两个页面（#/add 与 #/{模块}/add）：挂上与首页同层（body）的柔化八云紫背景
  const isAddPage = p[0] === 'add' ||
    (['music', 'doujin', 'game', 'video', 'art'].includes(p[0]) && p[1] === 'add');
  if (document.body && document.body.classList) document.body.classList.toggle('add-bg', isAddPage);
  // 收藏页暂存：本次停留期间取消收藏的条目会暂留在列表中；
  // 一旦离开收藏页、或下次重新进入（此前不在收藏页）就清空，届时才会真正移除。
  const onFav = p[0] === 'fav';
  if (!onFav || !wasOnFav) stickyFavs = [];
  wasOnFav = onFav;
  // 离开搜索页时清空顶栏搜索框（renderSearch 内部负责同步成搜索词）
  const gs = document.getElementById('globalSearch');
  if (gs && p[0] !== 'search') gs.value = '';
  // 每次路由先清掉原作详情页背景，由 renderOriginalGame 决定要不要重新挂上
  clearPageBg();
  if (!p.length) renderHome();
  else if (p[0] === 'original') {
    if (p[2] === 'download') renderOriginalDownload(decodeURIComponent(p[1]));
    else p[1] ? renderOriginalGame(decodeURIComponent(p[1])) : renderOriginals();
  }
  else if (p[0] === 'add') renderAddChooser();
  else if (p[0] === 'fav') renderFavs();
  else if (['music','doujin','game','video','art'].includes(p[0])) {
    if (p[1] === 'add') renderAddForm(p[0]);
    else p[1] ? renderDetail(p[0], p[1]) : renderList(p[0]);
  }
  else if (p[0] === 'character') renderCharacter(decodeURIComponent(p[1] || ''));
  else if (['circle','tag'].includes(p[0])) renderReverse(p[0], decodeURIComponent(p.slice(1).join('/')));
  else if (p[0] === 'search') renderSearch(decodeURIComponent(p.slice(1).join('/')).trim());
  else if (p[0] === 'baka') {
    if (!isFirst) hideRouteLoading();
    // 教训baka：直达冻结页，揍完跳回进入前的原页面（冻结页直接显示，不再覆盖祈祷遮罩）
    return renderFrozen(() => { location.hash = bakaReturnHash || '#/'; });
  }
  else { $app.innerHTML = '<p class="empty-state">404 — 未识别路径</p>'; }

  // 介绍文字（作品简介 / 角色简介 / 社团简介）：超过三行折叠，点「展开」看剩下文字。
  // 等一帧让布局稳定后再测量行数，避免拿到旧布局导致误判。
  // 作品列表同样在此时分页：一次只展示三行，点「展开更多」再加载三行。
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => { applyClamp3($app); initPagedLists($app); });
  } else { applyClamp3($app); initPagedLists($app); }

  // 子页面：等首屏图片就绪再揭开「少女祈祷中」遮罩；首屏由根加载页已处理好，直接揭开。
  // 图片始终在 DOM 中渲染好（仅被遮罩盖住），就绪即揭开，绝不把没加载好的页面亮给用户。
  if (!isFirst) {
    await waitForPageImages($app);
    hideRouteLoading();
  }
}

// 路由入口：正常渲染 + 返回导航时恢复离开时的滚动位置（分类标签已在各渲染函数内应用）
async function route() {
  await routeInner();
  if (backNav) {
    backNav = false;
    const st = pageState[location.hash || '#/'];
    if (st && st.scrollTop && typeof window.scrollTo === 'function') {
      // 等一帧让浏览器完成布局，再跳回离开时的位置
      requestAnimationFrame(() => window.scrollTo(0, st.scrollTop));
    }
  }
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

// 返回顶端按钮：点击平滑滚动到页面顶部（全局固定，所有页面生效）
const backTopBtn = document.getElementById('backTop');
if (backTopBtn) {
  backTopBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}
// 教训baka 按钮：固定在返回顶端按钮正上方；点击直达冻结页，揍完跳回原页面
const bakaBtn = document.getElementById('bakaBtn');
if (bakaBtn && bakaBtn.addEventListener) {
  bakaBtn.addEventListener('click', () => {
    if (location.hash === '#/baka') return; // 已在冻结页则不再重复进入
    bakaReturnHash = location.hash || '#/';
    location.hash = '#/baka';
  });
}

window.addEventListener('hashchange', route);
route();

// 分类 Tab（作品分类 / 收藏分类）切换后，刚变可见的面板要补一次分页计算：
// 面板隐藏时量不出「一行几列」，只能等它显示出来再决定三行是多少张卡。
document.addEventListener('click', e => {
  const t = (e.target && e.target.closest) ? e.target.closest('.og-tab, .fav-tab') : null;
  if (t) setTimeout(() => initPagedLists(document), 0);
});
// 窗口尺寸变化会改变「一行几列」→ 重新按三行分页，避免展开行数错乱
let lmResizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(lmResizeTimer);
  lmResizeTimer = setTimeout(() => initPagedLists(document, true), 200);
});
