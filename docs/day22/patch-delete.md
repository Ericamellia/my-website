# PATCH / DELETE 与「删除为什么更容易出事」（Day 22）

> 今天把收藏的**「改」和「删」**做出来，至此四类操作（增查改删）闭环完整。
> 本文重点回答清单里那个问题：**删除为什么比新增更容易出事？我把确认加在了哪？**

---

## 一、今天做了什么

| 接口 | 作用 | 状态 |
|---|---|---|
| `PATCH /api/favorites/:id` | 改收藏备注（只允许改 `note`） | 新增 ✅ |
| `DELETE /api/favorites/:id` | 取消收藏（真删） | 新增 ✅ |
| `POST /api/favorites` | 新增收藏 | 已有（Day 18） |
| `GET /api/favorites` | 读收藏列表 | 已有（Day 17） |

**闭环验证**：`POST` 增 → `GET` 查 → `PATCH` 改 → `DELETE` 删 → `GET` 再查（该条消失）。
脚本 `docs/day22/evidence/verify_crud_cycle.py` 跑 14 项断言，全部通过。

---

## 二、核心问题：删除为什么比新增更容易出事？

关键在于**「可逆性不对称」**：

| | 新增（POST） | 删除（DELETE） |
|---|---|---|
| **做错了会怎样** | 多了一条，再删掉就行 | 数据**真没了**，救不回来 |
| **影响范围** | 只多出一行 | 可能连带影响别处（外键 `ON DELETE CASCADE`） |
| **重复执行** | 撞唯一约束被挡住（安全） | 第二次是 0 行 —— **分不清「删过了」还是「id 写错了」** |
| **用户意图** | 点了就是想要 | 可能是误点、可能是手滑粘了错的 id |
| **失败可见性** | 多了东西，看得见 | **少东西很难发现**（静默失败） |

最后一行是最要命的：新增失败，你一眼就看到列表里没有它；
删除失败（或者删错了），页面上什么都没少，你可能几天后才发现。

---

## 三、我在哪加了「确认」

删除这个动作，从**用户的手**到**数据库的行**，一共经过三道关：

```
用户点击
   │
   ├─ 第 1 道：前端二次确认 ──────────── window.confirm("确定要删除吗？")
   │            （拦住「手滑」）
   │
   ├─ 第 2 道：服务端「先查后删」────────── 先 SELECT 出整条 → 再 DELETE
   │            用「查到了没有」决定 404 还是 200
   │            （拦住「id 写错了但假装成功」）
   │
   └─ 第 3 道：响应里回传被删数据 ───────── 前端能显示「已取消《XXX》」
                也是误删后唯一的凭证
                （拦住「删了但不知道删了什么」）
```

### 第 1 道 · 前端二次确认

在验证页 `deploy/public/verify/app.js` 里：

```js
document.getElementById('btnDelete').addEventListener('click', function () {
  var id = document.getElementById('cId').value.trim();
  if (!id) return alert('请先填一个 id');
  crudState.id = Number(id);
  // ★ 二次确认：点一下不会直接删，先问一次
  if (!window.confirm('确定要删除 id=' + id + ' 这条收藏吗？\n（真删，删完库里就没了）')) return;
  doCrud('DELETE', '/api/favorites/' + id, null, '删');
});
```

注意确认文案里写的是**「真删，删完库里就没了」**，不是笼统的「确定删除？」——
把后果说清楚，用户才有机会判断这是不是他想要的。
（这也是为什么软删除值得做：有了它这里就能写「可在回收站找回」。）

### 第 2 道 · 服务端「先查后删」（最关键的一道）

在 `deploy/db/index.js` 的 `deleteFavoriteFromRest()` 里：

```js
// 第 ① 步：先查。带 JOIN 一次把整条（含作品详情）读出来，
// 既是「存不存在」的判断，也是「删的是哪一条」的凭证。
const found = await rest.restRequest('GET', 'favorites', {
  query: { select: '...,works(...)', id: 'eq.' + id, limit: '1' }
});
const row = (found.data && found.data[0]) || null;
if (!row) {
  return { source: 'rest', deleted: false, notFound: true, item: null };  // → 404
}
const victim = flattenRestFavRow(row);   // ★ 先算好凭证，再删 —— 删完就查不到了

// 第 ② 步：真删。filter 只按 id，不带别的条件（避免误删别人的数据）
const del = await rest.restRequest('DELETE', 'favorites', { query: { id: 'eq.' + id } });
```

**为什么不能「先删再看影响几行」**：那样也能判 404，但**拿不到被删的内容**，
就没办法在响应里告诉用户「删掉的是哪一条」，第 3 道关就没了。

### 第 3 道 · 响应里回传被删数据

```json
{
  "ok": true,
  "action": "deleted",
  "message": "已取消收藏",
  "data": { "id": 3, "workId": "video-1", "name": "Bad Apple!! feat. nomico（影绘PV）", "..." : "…" }
}
```

真删不可逆，响应里这份 `data` 是**唯一的凭证** ——
前端据此显示「已取消收藏《Bad Apple》」，误删时也有内容可以重新 `POST` 回来。

---

## 四、另一个关键决定：404 而不是 200

删除最容易出的事故是**误以为删掉了**。
id 写错（把 `7` 打成 `77`）如果也回 `200`，调用方会以为「已取消」，
那条收藏还好好躺在库里 —— 这种**静默失败比直接报错危险得多**。

所以：**该 id 不存在 → `404 favorite_not_found`**。

```
DELETE /api/favorites/77   （77 不存在）
→ 404  { "ok": false, "error": "favorite_not_found", "message": "没有找到 id=77 的收藏，可能已经被取消了" }
```

顺带得到**幂等性**：同一个 id 连删两次，第一次 `200`、第二次 `404`，
**不报 500、也不假装成功**。所以重复调用是安全的。

> 这点和 `POST` 正好相反：`POST` 重复会多插一行，靠数据库唯一约束挡成 `409`。
> `DELETE` 天然幂等，不需要额外约束。

---

## 五、PATCH 这边的两个讲究

### 1. 只收 `note`，传别的字段直接报错

```js
const unknown = keys.filter(function (k) { return k !== 'note'; });
if (unknown.length > 0) {
  return { ok: false, error: 'unknown_field',
           message: '暂不支持修改字段：' + unknown.join('、') +
                    '。PATCH 只能改 note（改 workId 请删除后重新收藏）' };
}
```

**为什么不静默忽略**：调用方传了 `{"workId":"music-1"}` 却收到 `200`，
会以为自己改成功了 —— 这是最坑的一类 bug。明确报错并告诉他正确路径（DELETE + POST）。

**为什么 `workId` 不能改**：改 `workId` 等于「这条收藏换成收藏另一件作品」，
语义上是**删了再建**（要重新过唯一约束、重新记创建时间）。
伪装成 PATCH 会让调用方误以为「时间没变、id 没变」，是以后出 bug 的源头。

### 2. 空 body 也是错

```js
if (keys.length === 0) {
  return { ok: false, error: 'empty_patch',
           message: '请求体是空的，至少要给出一个要修改的字段（目前支持：note）' };
}
```

`PATCH {}` 是「发了请求但什么都没说」，回 `400` 而不是假装成功。

---

## 六、验证结果

### 闭环验证（`verify_crud_cycle.py`，14/14 通过）

```
① POST 新增 art-2        → 201，id=46
② GET                    → 查得到这条（共 8 条）
③ PATCH 改备注           → 200；再 GET 确认库里真变新值，且 createdAt 未变
④ DELETE                 → 200，响应带回被删那条完整数据
⑤ GET                    → 该条消失（8 → 7 条）
⑥ 再 DELETE 同一个 id    → 404（幂等）
★ 收尾对比               → 跑前 7 条 = 跑后 7 条，一条没动
```

### 页面截图（`shot_crud_pages.py`）

| 截图 | 证明什么 |
|---|---|
| `patch-改前改后对比.png` | 改前 note → **改后 note**（绿高亮），接口返回 `action: "updated"`，探针显示「✓ 仍在库里 —— note=新值」 |
| `delete-删除后消失.png` | `DELETE` 返回 `action: "deleted"` + 被删数据；探针显示「✗ 已从 GET 返回中消失（共 7 条）—— 删除生效」 |

> 截图脚本会**自己造一条测试数据**来操作（不碰库里真实数据），
> 跑完把它删掉，并逐条比对确认「原有数据一条没动」。
> 为什么不拿已有记录做实验：删掉后即使补一条新的回来，**原 id 也已永久消失**，
> 「跑完和跑前一致」就成了假话。

---

## 七、改动文件清单

| 文件 | 改动 |
|---|---|
| `deploy/db/mappers.js` | 新增 `validateFavoriteId()`、`validateFavoriteUpdate()` |
| `deploy/db/index.js` | 新增 `updateFavorite()`（+3 通道）、`deleteFavorite()`（+3 通道） |
| `deploy/server.js` | 新增 `matchFavoritesId()`、`handleFavoritesPatch()`、`handleFavoritesDelete()`；路由分派 + 启动日志 |
| `deploy/public/verify/index.html` | 新增 PATCH / DELETE 验证区（含改前/改后对比条） |
| `deploy/public/verify/app.js` | 新增 `doCrud()` / `refreshFavProbe()` / `pickFavorite()` 与三个按钮绑定 |
| `deploy/public/verify/style.css` | 新增 `.crud-compare` 等样式 |
| `docs/api-contract.md` | 新增 §5 §6 两节完整定义；契约版本 `1.1.0` → `1.2.0`；变更记录补一行；章节顺延 |
| `docs/day22/` | 本文档 + `evidence/` 两个脚本、两份输出、两张截图 |

---

## 八、今日不做（清单明确排除）

- **批量操作** —— 不做
- **用户系统** —— 不做（`userId` 仍固定 `local`）
- **软删除（`is_deleted`）** —— 排在余力加练，今天不做

---

## 九、余力加练：软删除要怎么加（尚未实施）

硬删除的致命伤是**不可逆**。软删除的思路是：**不真动数据，只打标记**。

```sql
-- 1) 表加一列
ALTER TABLE favorites ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- 2) 读的时候跳过已删的
SELECT ... FROM favorites WHERE user_id = $1 AND is_deleted = FALSE;

-- 3) 「删除」改成打标记
UPDATE favorites SET is_deleted = TRUE WHERE id = $1;

-- 4) 「恢复」就是把它改回来
UPDATE favorites SET is_deleted = FALSE WHERE id = $1;
```

要注意的连带问题（这也是为什么它值得单独一轮做）：

1. **唯一约束会打架**：`UNIQUE (user_id, work_id)` 在软删除后仍占位 ——
   删掉再重新收藏同一作品会撞约束。要么把约束改成
   `UNIQUE (user_id, work_id) WHERE is_deleted = FALSE`（部分索引），
   要么「重新收藏」时把旧行改回来。
2. **所有查询都要加过滤**：目前 `favorites` 有 3 条查询路径（REST / pg / 快照），
   漏掉任何一处，已删数据就会漏出来。
3. **数据会越积越多**：真删不需要清理，软删除需要定期物理清理旧的已删行。
