# Day 28｜手机端顶栏压缩 + 左右划页切换板块 + B站移动端风格调优

> 2026-10-13 · 承接 Day 27「移动端布局问题」清单
>
> **本文档含两轮改动**：
> - **28a**：顶栏压缩成一行 + 左右划页切换（初版，顶栏 36px）
> - **28b**：按反馈调整 —— 顶栏回调到 48px、搜索框改小为胶囊、其余参考 B 站移动端

---

## 一、需求

### 1.1 第一轮（28a）

用户原话：

> 将手机页面顶栏上下宽度改小，改为左右划页切换

经确认，需求拆为两点：

| # | 需求 | 确认结果 |
|---|---|---|
| 1 | 「左右划页切换」指什么 | **两者都要**：顶栏导航横向滑动 **+** 内容区左右滑动切板块 |
| 2 | 顶栏的返回/首页/搜索框怎么处理 | **搜索框移到内容区顶部** |

### 1.2 第二轮（28b）

用户原话：

> 顶栏大一点，搜索框小一点，其他前端参考 b 站移动端

| # | 需求 | 做法 |
|---|---|---|
| 1 | 顶栏大一点 | 36px → **48px**（对齐 B 站移动端顶栏高度） |
| 2 | 搜索框小一点 | 改为 **34px 高圆角胶囊**、13px 字号、浅灰底 `#f1f2f3`、放大镜内置 |
| 3 | 其他参考 B 站移动端 | 内容区白底、标题加大加粗、卡片圆角无边框轻阴影、**导航当前项粉色下划线** |

---

## 二、问题现状（改动前）

Day 27 用手机宽度（390×844）走查时发现：手机端顶栏是 **2~3 行高**，因为：

```css
@media (max-width: 720px) {
  header .container { flex-direction: column; gap: 8px; }  /* 改成上下排列 */
  nav { flex-wrap: wrap; justify-content: center; gap: 8px; }  /* 导航换行 */
  .nav-item { width: auto; height: auto; ... padding: 4px 8px; }
  .nav-item .nav-label { position: static; ... }   /* 文字常显 → 占宽 */
}
```

**结果**：8 个导航（音乐/漫画/游戏/视频/图/原作/B站必看/我的收藏）+ 搜索框 + 标题全堆在顶栏，顶栏高度 = 搜索框行 + 2 行导航 ≈ 110px+，**吃掉手机首屏近 1/6**。

---

## 三、改法

### 3.1 CSS（`deploy/public/style.css`）

**顶栏压成严格一行**：

| 项 | 改前 | 改后 |
|---|---|---|
| `.container` 方向 | `column`（上下堆叠） | `row`（单行） |
| `header` padding | `4px 0` | `2px 0` |
| `header .container` padding | 继承 `.container` 的 `24px 16px` | **`0 6px`**（关键：去掉 24px 上下内边距） |
| `h1` 标题 | `12px` 不限制宽度 | `11px` + `max-width:84px` + 省略号 |
| 返回/首页按钮 | 30px | 26px |
| 顶栏搜索框 | 显示 | `display:none`（已移到内容区） |

**导航改成横向滑动条**：

```css
nav {
  flex-wrap: nowrap;              /* 不换行 */
  justify-content: flex-start;
  overflow-x: auto;               /* 横向滚动 */
  scroll-snap-type: x proximity;  /* 滑动吸附 */
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;          /* 隐藏滚动条 */
  opacity / mask-image: linear-gradient(...)  /* 右侧渐隐，暗示可滑 */
}
.nav-item { flex: 0 0 auto; width: 32px; height: 32px; }
.nav-item .nav-label { display: none; }   /* 手机端无 hover，标签隐藏 */
```

**内容区搜索条**（新增）：

```css
.content-search { display: none; margin: 10px 0 4px; }   /* 桌面隐藏 */
@media (max-width: 720px) { .content-search { display: flex; ... } }
```

### 3.2 HTML（`deploy/public/index.html`）

在 `</header>` 与 `<main>` 之间插入搜索框备用容器：

```html
<div class="content-search container" id="contentSearchBar" hidden></div>
```

> **为什么用「备用容器 + 节点搬移」而不是复制一个 input**：
> 全站有 **6 处** 用 `document.getElementById('globalSearch')` 取搜索框。
> 复制会得到两个同 id 元素，`getElementById` 行为不确定 → 搜索功能会随机坏。
> 搬移保证**全站永远只有一个 `#globalSearch`**，那 6 处逻辑一行都不用改。

### 3.3 JS（`deploy/public/app.js`）

**① 搜索框按屏幕宽度在两个容器间搬移**：

```js
const MOBILE_MQ = window.matchMedia('(max-width: 720px)');

function placeGlobalSearch() {
  const wrap = document.querySelector('header .header-search-wrap');
  const bar = document.getElementById('contentSearchBar');
  const isMobile = MOBILE_MQ.matches;
  if (isMobile) {
    if (wrap.parentElement !== bar) bar.appendChild(wrap);
    bar.hidden = false;
  } else {
    const headerContainer = document.querySelector('header .container');
    if (headerContainer && wrap.parentElement !== headerContainer) {
      headerContainer.insertBefore(wrap, headerContainer.querySelector('nav'));
    }
    bar.hidden = true;
  }
}
MOBILE_MQ.addEventListener('change', placeGlobalSearch);  // 旋转/缩放自动切换
window.addEventListener('resize', placeGlobalSearch);     // 兜底
placeGlobalSearch();
```

**② 左右滑动切板块**（只在 5 个作品板块的列表页生效）：

```js
const SWIPE_MODULES = ['music', 'doujin', 'game', 'video', 'art'];

function currentSwipeModule() {
  const p = (location.hash.slice(1) || '/').split('?')[0].split('/').filter(Boolean);
  if (p.length === 1 && SWIPE_MODULES.includes(p[0])) return p[0];  // 只认列表页
  return null;   // 详情页 / add 页排除
}

// touchstart 记起点，touchend 算位移
const MIN_X = 60;   // 横向最小位移
const MAX_Y = 40;   // 纵向容差：超过判定为「滚动」而非「切板块」

// 左滑(dx<0) → 下一个板块；右滑(dx>0) → 上一个；首尾不循环
```

**设计要点**：

| 点 | 说明 |
|---|---|
| `MAX_Y=40` 纵向容差 | 防止「竖着滚动页面」被误判成切板块 —— **最关键的一条** |
| 只在列表页生效 | 详情页左右滑不切板块（避免读文章时误跳） |
| 首尾不循环 | 到「音乐」再右滑无动作，符合直觉 |
| 改动极小 | 全部走 `location.hash`，**复用现有路由**，不新增渲染逻辑 |

---

## 四、验证

脚本：`docs/day28/evidence/verify_mobile_nav.py`（CDP `Emulation.setDeviceMetricsOverride` 390×844）

| # | 检查 | 结果 |
|---|---|---|
| A | 顶栏高度 | **36px**（改前 ≈110px），单行 ✅ |
| A | 导航可视宽 / 总宽 | 243 / 263（改前 164 / 286）✅ |
| A | 搜索框在内容区 | `searchInContentBar: true` ✅ |
| B | 导航横向可滑 | `maxScrollLeft: 20`，8 个图标 ✅ |
| C1 | 进 `#/music` | 标题「同人音乐」✅ |
| **C2** | **左滑** | `#/music` → **`#/doujin`**（同人漫画）✅ |
| **C3** | **再左滑** | → **`#/game`**（同人游戏）✅ |
| **C4** | **右滑** | → **`#/doujin`**（正确回退）✅ |
| **D** | **纵向滑动（dy=-400）** | 保持 `#/music`，**不误触** ✅ |
| E | 桌面 1280px | 搜索框回顶栏，内容区搜索条隐藏 ✅ |

### 4.1 截图

| 文件 | 内容 |
|---|---|
| `day28-1-音乐列表-顶栏压缩.png` | 手机端顶栏 36px 单行 + 内容区搜索条 |
| `day28-2-左滑到漫画.png` | 左滑后切到「同人漫画」 |
| `day28-3-右滑回漫画.png` | 右滑回退验证 |
| `day28-4-桌面顶栏搜索框.png` | 桌面端零回归（搜索框仍在顶栏） |

---

## 五、绕过的一个坑

### 5.1 桌面端搜索框"看起来消失了"（虚惊一场）

用 `Page.captureScreenshot(captureBeyondViewport=True)` 截桌面图时，**顶栏中间的搜索框渲染不出来**，一度以为改坏了。

**排查过程**：写诊断脚本读 DOM 真实状态 ——

```json
{
  "parent": "container",
  "inputRect": {"x":517,"y":36,"w":208,"h":27},
  "inputStyles": {"display":"block","visibility":"visible","opacity":"1",
                  "bg":"rgb(255, 255, 255)"},
  "headerRect": {"w":1265,"h":100}
}
```

**搜索框完全正常**：有尺寸、可见、白底、在顶栏容器内。

**结论**：是 **`captureBeyondViewport` 截图时的合成问题**，不是代码问题。改用**真实窗口截图**（不加 `captureBeyondViewport`）后，搜索框正常显示。

> **教训**：**DOM 数据是硬证据，截图是软证据**。当两者矛盾时，先信 DOM —— 直接量 `getBoundingClientRect` + `getComputedStyle`，别盯着截图猜。

### 5.2 桌面顶栏 100px 是原有行为（不是我改的）

诊断发现桌面顶栏 100px，原因是 `header .container` 继承了 `.container` 的 `padding: 24px 16px`。

**用 `git show HEAD:deploy/public/style.css` 核对，确认这是 Day 10 起的原有行为**，不在本次需求范围（用户说的是「手机页面」），故桌面端保持原样。

> **教训**：发现"不合理的既有行为"时，先 `git show HEAD:` 确认是不是自己引入的，再决定要不要动 —— 避免顺手改成越界改动。

---

## 四、第二轮（28b）：B 站移动端风格调优

### 4.1 顶栏回调到 48px

```css
header { padding: 0; }
header .container {
  flex-direction: row; gap: 6px; padding: 0 10px;
  height: 48px; align-items: center;   /* ★ 关键：显式高度 = B 站顶栏高度 */
}
header h1 { font-size: 12px; max-width: 96px; }
header .home-link { width: 30px; height: 30px; }
```

导航项也从 `32px` 回到 **`38×48px`**（撑满顶栏高度，点击热区更大）：

```css
.nav-item { width: 38px; height: 48px; border-radius: 0; }
```

### 4.2 搜索框改小为「胶囊」

```css
/* 胶囊外壳：图标 + 输入框都在里面 */
.content-search .header-search-wrap {
  display: flex; align-items: center; gap: 6px;
  height: 34px;              /* 比顶栏矮 14px */
  max-width: 320px;          /* 约 70% 屏宽（390px 下实测 272px） */
  padding: 0 14px 0 12px;
  border-radius: 999px;      /* 全圆角 = 胶囊 */
  background: #f1f2f3;       /* B 站式浅灰底 */
}
.content-search .header-search-wrap:focus-within {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(236,143,165,.35);
}
/* 输入框自身完全透明，视觉全交给外壳 */
.content-search .header-search {
  flex: 1 1 auto; min-width: 0; height: 100%;
  font-size: 13px; padding: 0;
  border: none; border-radius: 0;
  background: transparent;
  box-shadow: none !important;   /* 聚焦高亮交给外壳 */
}
```

**为什么把圆角/背景放在外壳而不是 input 上**：图标要**在胶囊内部**。如果 input 自己是胶囊，图标只能放外面 → 视觉上图标和框分离（第一版就是这样，看起来发散）。

### 4.3 导航当前项高亮（B 站 Tab 风格）

**CSS**：

```css
.nav-item.is-active { color: #ec8fa5; }
.nav-item.is-active::after {
  content: '';
  position: absolute; left: 50%; bottom: 2px;
  width: 18px; height: 2px; border-radius: 1px;
  background: #ec8fa5;
  transform: translateX(-50%);
}
```

**JS**（`app.js`，新增 `syncNavActive`）：

```js
const NAV_FOR_SEG = {
  music:'#/music', doujin:'#/doujin', game:'#/game', video:'#/video',
  art:'#/art', original:'#/original', hot:'#/hot', fav:'#/fav',
};

function syncNavActive(p) {
  const target = NAV_FOR_SEG[(p && p[0]) || ''] || null;
  document.querySelectorAll('header nav .nav-item').forEach(a => {
    a.classList.toggle('is-active', !!target && a.getAttribute('href') === target);
  });
  // ★ 当前项被滑出视野时带回可见范围 —— 只滚 nav 容器，绝不动页面滚动位置
  const nav = document.querySelector('header nav');
  const active = document.querySelector('header nav .nav-item.is-active');
  if (nav && active && nav.scrollWidth > nav.clientWidth) {
    const aL = active.offsetLeft, aR = aL + active.offsetWidth;
    const vL = nav.scrollLeft, vR = vL + nav.clientWidth;
    if (aL < vL) nav.scrollLeft = aL - 8;
    else if (aR > vR) nav.scrollLeft = aR - nav.clientWidth + 8;
  }
}
```

> **★ 这里特意没用 `scrollIntoView`**：`scrollIntoView` 会**同时滚动页面**，用户刚滑到列表中部时切板块，页面会被拽走。改成直接读写 `nav.scrollLeft`，只影响那条 Tab 条。

**生效范围**：`#/music` 与 `#/music/1`（详情页）都算「同人音乐」板块，高亮跟随；搜索/反查等无对应导航的页面不亮。

### 4.4 内容区参考 B 站

```css
main.container {
  background: #fff;                  /* 纯白内容区 */
  border-radius: 0;
  padding: 12px 12px 24px;
  min-height: calc(100vh - 48px);
}
main.container > h2 {                /* 页面标题：更大更粗 */
  font-size: 19px; font-weight: 700; color: #18191c; margin: 4px 0 12px;
}
.work-item, .video-card, .module-card {
  border: none;                      /* 去边框，改轻阴影 */
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.site-footer { margin-top: 20px; padding: 16px 12px; background: transparent; }
```

---

## 五、第二轮验证

脚本：`docs/day28/evidence/verify_mobile_nav.py`（CDP 390×844）

| # | 检查 | 结果 |
|---|---|---|
| A | 顶栏高度 | **48px**（28a 是 36px）✅ |
| A | 搜索框尺寸 | **272×34px**，`border-radius: 999px`，`13px`，底 `#f1f2f3` ✅ |
| A | 搜索框在内容区 | `searchInContentBar: true` ✅ |
| B | 导航高亮 | 进 `#/music` → `is-active`，粉色 `rgb(236,143,165)`，下划线 18px ✅ |
| B | 高亮唯一性 | `totalActive: 1`（同时只有一个高亮）✅ |
| C | 高亮跟随 | 切到 `#/video` → 高亮跟着变 ✅ |
| D | 滑动切板块 | 左滑 `#/music` → `#/doujin`，**高亮同步** ✅ |
| E | 桌面回归 | 搜索框仍在顶栏、内容区条隐藏、顶栏 100px ✅ |

### 5.1 截图

| 文件 | 内容 |
|---|---|
| `day28b-0-手机首屏-真实视口.png` | **手机首屏真实视口**：顶栏 48px + 胶囊搜索框 + 当前板块高亮 |
| `day28b-1-音乐-顶栏回调.png` | 音乐板块（整页） |
| `day28b-2-视频-高亮跟随.png` | 切到视频板块，高亮跟随 |
| `day28b-3-卡片风格.png` | B 站式卡片：圆角、无边框、轻阴影 |
| `day28b-4-桌面回归.png` | 桌面端零回归 |

---

## 六、★ 第二轮踩的坑：`captureBeyondViewport` 会让 sticky 顶栏错位

前几轮的整页截图里，**顶栏"跑到"了文档中部**，页面顶部出现大片空白。我一开始以为是「内容区顶部留白过多」（Day 27 的 M3），还去改 CSS。

**真相**：`Page.captureScreenshot({captureBeyondViewport: true})` 截的是**整个可滚动文档**，而 `header` 是 `position: sticky` —— 在这个模式下它被按"文档流位置"渲染，而不是"视口顶部"，于是出现在错误的 y 坐标。

**验证方式**：采样图像像素行 ——

```
y=0    (250,250,250)   ← 页面背景
y=160  (250,250,250)
y=200  (251,251,251)   ← 顶栏开始
y=240  (252,237,241)   ← 粉色顶栏
```

顶栏在 y≈200 而非 y=0，**证明是截图工具的问题，不是 CSS 的问题**。

**修法**：另写 `shot_viewport.py`，**不带 `captureBeyondViewport`**（只截当前视口），顶栏就正常在顶部了。

> **教训（与 Day 28a 同源）**：**截图是软证据，DOM/像素数据是硬证据**。
> Day 28a 是「DOM 说在、截图说不在」，这次是「截图说错位、实际没错位」——
> **两次都是截图骗人**。凡是"看起来不对"，先量数据再动手改 CSS。

---

## 七、待办（本次未动，如实记录）

| # | 问题 | 说明 |
|---|---|---|
| M1 | **右下角三个悬浮按钮遮挡卡片内容** | 手机端截图里「创作者/角色」被粉色图标压住。B 站移动端只保留 1 个小的回到顶部按钮，这里堆了 3 个（表情/向上/加号）。**属于功能调整，本次未动** |
| M2 | 页脚文字重叠 | Day 27 记录，仍未处理 |

---

## 八、改动文件清单（Day 28，含 28a + 28b 两轮）

| 文件 | 改动 | 属于哪天 |
|---|---|---|
| `deploy/public/style.css` | 手机端顶栏重做（48px 单行）+ 导航横向滑动 + 当前项高亮 + 胶囊搜索条 + B站式白底/卡片（+82 / -14 行） | **Day 28** |
| `deploy/public/index.html` | 加 `#contentSearchBar` 容器 | **Day 28** |
| `deploy/public/app.js` | 搜索框搬移 + 左右滑动切板块 + `syncNavActive` 导航高亮 | **Day 28** |
| `docs/day28/day28.md` | 本文档 | **Day 28** |
| `docs/day28/evidence/*` | 3 个验证/截图脚本 + 6 张截图 + 日志 | **Day 28** |

**版本号已升**（改 CSS/JS 必须升，防缓存，本次迭代过程曾用到 v110~v113）：
`style.css` **v109 → v114**、`app.js` **v97 → v99**。

---

## 九、发布前检查

`skills/preflight-check/check.sh` —— **7 项全过，退出码 0**。

---

## 十、与 Day 27 移动端清单的关系

Day 27 记录了 3 个移动端问题：

| 编号 | 问题 | 状态 |
|---|---|---|
| M3 | 顶部留白过多 | ✅ 已解决（顶栏从 110px 压到 48px；另查明 Day 27 看到的"留白"部分是截图工具假象，见 §6） |
| M1 | 悬浮图标遮挡正文 | ❌ 未处理（见 §7，属功能调整） |
| M2 | 页脚文字重叠 | ❌ 未处理 |

---

*Day 28 完成 · 2026-10-13*
