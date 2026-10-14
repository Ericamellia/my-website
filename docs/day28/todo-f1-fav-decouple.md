# F1 待办：前端收藏 UI 与云端真库是两套数据

> 发现日：2026-10-14（Day 28 结营验收）
> 状态：**已定位根因，未修**（按用户决定：今日为验收日，不做影响验收的改动）
> 严重度：**中**（功能可用，但架构不一致；Day 17–22 的接口成果未在页面体现）

---

## 一、现象

在 Day 28 验收中发现：**页面上的「收藏」按钮点了以后，云端真库的收藏数不会变。**

| 观测 | 结果 |
|---|---|
| 点击详情页 `.detail-cta-fav` 按钮 | 网络请求数 **0**（Network 抓包） |
| 对照组：手动 `fetch('/api/favorites')` | 抓到 **1** 个请求（证明抓包有效） |
| 真库 `GET /api/favorites` 的 `count` | 点击前后**都是 7**，纹丝不动 |
| 按钮 class 变化 | `detail-cta-fav` ⇄ `detail-cta-fav is-faved`（本地翻转） |

---

## 二、根因

**两套收藏数据，互不相通。**

### 2.1 前端「我的收藏」= 纯 localStorage

`deploy/public/app.js`：

```js
// 第 426 行
try { favs = JSON.parse(localStorage.getItem('touhou_favs') || '[]'); } catch (e) {}
// 第 427 行
const saveFavs = () => { try { localStorage.setItem('touhou_favs', JSON.stringify(favs)); } catch (e) {} };
// 第 428 行
const isFav = (module, id) => favs.some(f => f.module === module && f.id === id);
// 第 429–433 行
const toggleFav = (module, id) => { ...; saveFavs(); };
```

- **详情页按钮**（第 437 行 `favBtn`）：`isFav(module, id)` 读的是内存变量 `favs`
- **收藏页**（第 1743 行 `renderFavs`）：`favs.map(...)` 读的也是 `favs`
- **点击事件**（第 444–465 行）：只做 `toggleFav()` + `classList.toggle()`，**没有任何 fetch/XHR**

→ **全链路零网络请求。**

### 2.2 云端真库 = `/api/favorites`

`deploy/server.js` 里实现完整：

| 方法 | 路径 | Day |
|---|---|---|
| GET | `/api/favorites` | 17 |
| POST | `/api/favorites` | 18 |
| PATCH | `/api/favorites/:id` | 22 |
| DELETE | `/api/favorites/:id` | 22 |

这四条**在 Day 28 的 B 类验收里全部实测通过**（201 / 409 / 200 / 404），
说明**接口本身没问题，是前端没接上**。

### 2.3 结论

> Day 17–22 花 6 天做的收藏 CRUD 后端能力，**页面上的收藏 UI 完全没使用**。
> 用户在页面上收藏的东西只存在自己浏览器里；换台电脑、清缓存就没了。
> 反之，任何写入真库的收藏，页面上也**永远看不到**。

---

## 三、影响面

| 影响 | 说明 |
|---|---|
| **数据不持久（跨设备/跨浏览器）** | 换浏览器、清 localStorage → 收藏全丢 |
| **多设备不同步** | 手机收藏的，电脑看不到 |
| **B 类验收的结果无法在页面上验证** | 我 POST 写入真库的 `art-2`（id=87），页面上看不到 |
| **Day 17–22 的成果被架空** | 后端接口完整可用，但产品上不体现 |
| 功能本身仍可用 | 单浏览器内收藏/取消/列表都正常，不报错 |

**不影响**：公网可访问、健康接口、真库读写、持久化（这些走的是服务端，B 类已验证）。

---

## 四、修复思路（三步）

### 步骤 1：收藏按钮改调接口（最小改动）

把 `toggleFav()` 的纯本地逻辑，改为「先调接口，成功后再更新本地状态」：

```js
async function toggleFavRemote(module, id, workId) {
  const on = isFav(module, id);
  if (on) {
    // 取消：需要知道真库里的行 id（不是 workId）
    await fetch('/api/favorites/' + dbIdOf(workId), { method: 'DELETE' });
  } else {
    const r = await fetch('/api/favorites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workId })
    });
    if (r.status === 409) return;   // 已收藏，幂等处理
  }
  // 接口成功后再同步本地缓存
  toggleFav(module, id);
}
```

**关键点**：
- 真库的 `id`（自增主键，如 87）≠ `workId`（如 `art-2`）→ 取消收藏需要**先拿到行 id**。
  而 `GET /api/favorites` 返回的数据里**同时有 `id` 和 `workId`**，所以要在收藏页渲染时把 `id` 记下来。
- 409 是**正常情况**（防重复），不应报错。

### 步骤 2：收藏页改为从接口读

`renderFavs()` 的 `favs.map(...)` 改为先 `fetch('/api/favorites')`，
用返回的 `data` 组装列表（返回体已含 `category` / `name` / `circle` 等字段，见 mappers.js）。

### 步骤 3：离线降级

沿用现有三通道思路：**接口不可用（快照通道 / 无网）时，退回 localStorage**，
并在界面上**如实提示**「当前为本地收藏，未同步到云端」。

---

## 五、验收标准（修完后）

| # | 项 | 判定 |
|---|---|---|
| 1 | 点收藏 → 有 POST 请求 | Network 抓到 `POST /api/favorites` |
| 2 | 真库计数 +1 | `GET /api/favorites` 的 `count` 变化 |
| 3 | 刷新后仍在 | reload 后收藏页仍显示该条 |
| 4 | 换浏览器仍看到 | 新 profile 打开，收藏页有数据 |
| 5 | 重复收藏 → 409 不报错 | UI 正常，不弹错误 |
| 6 | 取消收藏 → DELETE 生效 | 真库计数 -1 |

---

## 六、参考证据

| 文件 | 内容 |
|---|---|
| `docs/day28/evidence/net_proof_log.txt` | **铁证**：点收藏期间写请求 0 个；对照组 fetch 抓到 1 个 |
| `docs/day28/evidence/diag_fav_log.txt` | 点击前后真库 count（恒为 7）与按钮 class 对照 |
| `docs/day28/evidence/diag_flow_log.txt` | 逐步骤 URL / DOM 快照，确认 localStorage 与真库脱钩 |
| `docs/day28/acceptance.md` §F1 | 验收记录 |
