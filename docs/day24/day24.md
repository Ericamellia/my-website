# day24.md｜修一个真实 Bug：重复收藏把作品名弄丢了

> **今天要掌握的一句话**：你是怎么排除掉其他原因、锁定真正原因的？
>
> **一句话答案**：
> 最像元凶的那个**不是元凶**。我先怀疑的是 `rest.isUniqueViolation()`（它把任何 409 都
> 当「重复收藏」），并且用真库证明了它确实会把外键违规 `23503` 误判成 `23505`；
> 但**实测打到 HTTP 接口时它根本碰不到** —— `workExists()` 前置检查先把「作品不存在」
> 挡成了 404。真正让用户看见的，是另一个更朴素的问题：
> **重复收藏分支的 SQL 少 JOIN 了一张表，把作品名读成了空**。

---

## 0. 今天的四个板块（按用户给的顺序）

| # | 板块 | 状态 |
|---|---|---|
| ① | 复现 Bug —— 找到并稳定复现 | ✅ |
| ② | 定位 —— 排除其他原因，锁定根因 | ✅ |
| ③ | 修复 | ✅ |
| ④ | 验证留证（含两张截图） | ✅ |
| ⑤ | 余力加练 —— 修第二个低优先级 Bug | ✅ |

**今天刻意不做**：不把两个 Bug 混在一次修复里提交 —— 主 Bug（名字丢失）与
余力 Bug（`isUniqueViolation`）**分开改、分开验证、分开提交**，
这样出问题能单独回退，也便于看清每处改动各自的证据。

---

## 1. 板块①：复现 Bug

### 1.1 现场是什么

接口 `POST /api/favorites` 收藏一个作品。第一次返回 `201 created`，条目里
`name / tags / characters / description` 都在。**同一个作品再收藏一次**（触发
`409 duplicate`），返回的条目里 `name` 变成 **`"(作品已下架)"`**、`tags` 变成 `[]`。

用户视角：**同一张收藏卡片，点两次收藏，第二次作品名就没了。**

### 1.2 稳定复现（可重复）

```bash
python docs/day24/evidence/verify_bug_duplicate_join.py
```

实测输出（存档 `bug-repro-before-fix.txt`）：

```
测试作品 workId=art-1  name=LAST WORDS

① 第一次收藏（201 created）
   data.name = 'LAST WORDS'
   data.tags = ['妖妖梦', '东方Project']
  [PASS] 第一次收藏成功
  [PASS] 第一次条目带真实作品名

② 第二次收藏同一作品（409 duplicate）
   data.name = '(作品已下架)'      ← ❌ 名字丢了
   data.tags = []
  [PASS] 重复收藏被识别
  [FAIL] 重复分支也返回真实作品名 (得到 '(作品已下架)'，期望 'LAST WORDS')
  [FAIL] 重复分支 name 不是「(作品已下架)」

结果：3 PASS / 2 FAIL
```

**关键点**：这不是偶发。同一个作品、同一台机器、连跑两次，第二次必现。
一个「能稳定复现」的 Bug 才值得修 —— 否则改了也不知道好没好。

### 1.3 报错原文（截图①）

`bug-1-控制台报错原文.png` —— 渲染成 DevTools 控制台的样子，内容来自真实响应。
图上能直接看到同一个 `art-1`：
- 第一次 201：`"name": "LAST WORDS"`
- 第二次 409：`"name": "(作品已下架)"`

---

## 2. 板块②：定位 —— 怎么排除其他原因

这是今天的重点。定位不是「看一眼就懂了」，而是**把候选原因一条条摆出来，用实验打掉**。

### 2.1 候选原因清单

| # | 候选原因 | 怎么验证 | 结论 |
|---|---|---|---|
| A | `rest.isUniqueViolation()` 把外键违规当成唯一冲突 | 对真库直接发请求，看两种 409 的错误码 | 缺陷存在，但**当前不可达**（见 2.2） |
| B | 重复分支的 SQL 少 JOIN `works` 表 | 对比该分支的 select 与 `fetchFavFullFromRest` 的 select | ★ **真元凶** |
| C | `toFavItem()` 映射函数写错了 | 读代码：它只是「没有就兜底」 | 排除 —— 它是**受害者**不是凶手 |
| D | 数据本身坏了（`art-1` 真被下架） | 直接查库 / GET 列表看这条 | 排除 —— 同一条数据第一次读得到 |
| E | 前端缓存了旧响应 | 直接用 curl 打接口，绕开浏览器 | 排除 —— 裸接口就复现 |

### 2.2 候选 A：看着最像，其实不是

`deploy/db/rest.js:78-82`：

```js
function isUniqueViolation(status, data) {
  if (status === 409) return true;                    // ← 一刀切
  if (data && typeof data === 'object' &&
      String(data.code || '').indexOf('23505') !== -1) return true;
  return false;
}
```

`status === 409` 直接 return，**后面那行按错误码判断的代码形同虚设**。
我写脚本对真库实测（`repro_fk_409.py`）：

| 场景 | HTTP | PostgREST 错误码 | `isUniqueViolation()` |
|---|---|---|---|
| 唯一冲突 | 409 | `DATABASE_23505` | `True` ✅ |
| **外键违规** | **409** | **`DATABASE_23503`** | **`True` ❌ 误判** |

**结论**：这个缺陷是**真的**（PostgREST 对外键违规也回 409）。但它能不能伤到用户，
取决于有没有别的闸门挡在前面 —— 于是有了决定性的一步：

### 2.3 决定性实验：外键违规能不能走到这一步？

`deploy/server.js:handleFavoritesPost` 的注释写了处理顺序：

```
4. 作品存不存在  → 404 work_not_found      ← 这道闸门
5. 落库；撞唯一约束 → 409 already_favorited  ← 误判发生在这
```

我把服务跑起来，直接 POST 一个不存在的作品（`verify_position.py`）：

```
场景1：POST music-999999（不存在）
  HTTP 404  error=work_not_found
  message: 作品 music-999999 不存在，请先确认 workId 是否正确
```

**`workExists()` 老老实实返回了 false，走了 404，压根没碰到 `isUniqueViolation`。**

**这一步是今天最大的收获**：一个「逻辑上确实错」的函数，在**当前调用路径下不可达**。
如果我图省事按第一直觉改 `isUniqueViolation`，会得到一个「修了但用户什么也没感觉到」的假修复 ——
而真正的 Bug 还留在原地。

> 教训：**「代码里有缺陷」≠「用户遇到的 Bug」**。必须证明缺陷**真的会到达用户**，
> 才算锁定根因。排除掉候选 A，是定位成立的前提。

### 2.4 根因：重复分支的 SQL 少 JOIN

对比同文件的两处查询：

```js
// ✅ 正常路径 fetchFavFullFromRest()（第 324-331 行）—— 带 JOIN
select: 'id,user_id,work_id,note,created_at,' +
        'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)'

// ❌ 重复分支（修复前，第 302-310 行）—— 漏了 works(...)
select: 'id,user_id,work_id,note,created_at'
```

`mappers.toFavItem()` 是这么写的（`mappers.js:93`）：

```js
name: r.name || '(作品已下架)',
```

它拿不到 `r.name` 就兜底成 `"(作品已下架)"`。
**两条路径的 select 不一致** —— 一条带作品详情，一条只查收藏表本身。

**根因一句话**：重复收藏分支读回已有条目时，只查了 `favorites` 表没连 `works` 表，
导致作品字段全丢，被映射函数兜底成 `(作品已下架)`。

### 2.5 为什么「排除」这么重要

如果只做 2.2（证明 `isUniqueViolation` 有缺陷）就动手，会：
1. 改一个用户感知不到的 3 行代码；
2. 提交一个「Day 24 修复」的 commit；
3. **把真正的 Bug 留在线上继续丢名字**。

排除掉候选 A 之后，视线才落到「为什么名字会丢」—— 而这个名字丢失，
**在第一次收藏时并不存在**（第一次走的是带 JOIN 的 `fetchFavFullFromRest`）。

---

## 3. 板块③：修复

`deploy/db/index.js` 重复收藏分支，把 select 补成与 `fetchFavFullFromRest` 同款，
并把 JOIN 结果 `row.works` 压平后交给 `toFavItem`：

```js
const exist = await rest.restRequest('GET', 'favorites', {
  query: {
    select: 'id,user_id,work_id,note,created_at,' +
            'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
    user_id: 'eq.' + userId,
    work_id: 'eq.' + workId,
    is_deleted: 'eq.false',
    limit: '1'
  }
});
const row = (exist.data && exist.data[0]) || {};
const w = row.works || {};                      // ← PostgREST 把 JOIN 放在 row.works
return {
  source: 'rest', created: false, duplicate: true,
  item: mappers.toFavItem({
    id: row.id, user_id: row.user_id, work_id: row.work_id,
    note: row.note, created_at: row.created_at,
    category: w.category, name: w.name, circle_name: w.circle_name,
    creator: w.creator, year: w.year, cover: w.cover,
    tags: w.tags, characters: w.characters,
    description: w.description, source_url: w.source_url
  })
};
```

**改动量**：22 行增 / 2 行删，只动这一个分支，**接口形状、状态码、错误码全不变**。

> 为什么不干脆复用 `fetchFavFullFromRest(row.id)`？
> 因为那个函数是**按 id 再查一次**，会多打一次数据库。这里已经有 `row` 在手，
> 直接把 JOIN 结果压平更省一次往返。（两处形状保持一致，便于以后合并。）

---

## 4. 板块④：验证留证

### 4.1 修复后复测（同一个脚本，加 `--fix`）

```bash
python docs/day24/evidence/verify_bug_duplicate_join.py --fix
```

```
② 第二次收藏同一作品（409 duplicate）
   data.name = 'LAST WORDS'              ← ✅ 名字回来了
   data.tags = ['妖妖梦', '东方Project']
  [PASS] 重复分支也返回真实作品名
  [PASS] 重复分支 name 不是「(作品已下架)」

结果：5 PASS / 0 FAIL        （修复前是 3 PASS / 2 FAIL）
```

**修复前 3P/2F → 修复后 5P/0F**，同一个脚本、同一台机器，只有代码不同。

### 4.2 回归（确认没改坏别处）

```bash
python docs/day24/evidence/run_regression.py
```

- Day 22 的 CRUD 闭环脚本（原封不动跑）：**14/14 PASS**（增查改删闭环 + 跑前跑后库内条数一致）
- 只读接口冒烟：**10/10 PASS**（8 个正常接口 200 + 2 条错误路径 404/400）

存档：`regression-after-fix.txt`

### 4.3 两张截图

| 截图 | 内容 | 关键看什么 |
|---|---|---|
| `bug-1-控制台报错原文.png` | 修复前，重复收藏 | 同一 `art-1`：第一次 `name:"LAST WORDS"`，第二次 `name:"(作品已下架)"` |
| `bug-2-修复后正常运行.png` | 修复后，重复收藏 | 第二次 409 的 `data` 里 `name` 仍为 `"LAST WORDS"`，tags/characters 齐全 |

> 记一句：Day 24 的「F12 控制台报错原文」我用的是**渲染成 DevTools 样式、但内容来自
> 真实 HTTP 响应**的方式（无头浏览器不好直接截 DevTools 面板）。每行都来自刚跑出来的请求，
> 不是手写的。

---

## 5. 完成标准自检

| 完成标准 | 状态 | 证据 |
|---|---|---|
| 复现 | ✅ | `bug-repro-before-fix.txt`（3P/2F，稳定必现） |
| 定位 | ✅ | §2 排除表；`repro-fk-409-output.txt`（候选 A 实测）；`verify_position.py`（候选 A 不可达） |
| 修复 | ✅ | `deploy/db/index.js` +22/-2 |
| 验证 | ✅ | `bug-verify-after-fix.txt`（5P/0F）+ `regression-after-fix.txt`（14+10 全绿） |
| 两张截图 | ✅ | `bug-1-*.png` / `bug-2-*.png` |
| 余力加练 | ✅ | `deploy/db/rest.js` 修 `isUniqueViolation`；`is-unique-violation-fix.txt`（6P/0F）+ 全套回归复跑 |
| 修复已提交 | ⏳ | 待用户确认后提交 |

---

## 6. 余力加练：顺手修掉第二个低优先级 Bug

主任务收工后，把 §2.2 里实证过、但故意没夹带进主修复的 `isUniqueViolation()` 修掉。

### 6.1 改前 / 改后

```js
// ❌ 改前：任何 409 都算唯一冲突
function isUniqueViolation(status, data) {
  if (status === 409) return true;          // ← 一刀切
  if (data && ... indexOf('23505') !== -1) return true;
  return false;
}

// ✅ 改后：409 只是大类，必须再看错误码
function isUniqueViolation(status, data) {
  if (status !== 409) return false;
  const code = (data && typeof data === 'object') ? String(data.code || '') : '';
  if (code) return code.indexOf('23505') !== -1;
  return false;   // 409 但没带错误码 → 宁可当「不是唯一冲突」
}
```

### 6.2 前后对比（纯函数测试，`test_is_unique_violation.js`）

```
场景          status  错误码            修复前   修复后   期望
------------------------------------------------------------------------------
唯一冲突        409     DATABASE_23505    true    true    true    OK
外键违规        409     DATABASE_23503    true    false   false   OK   ← 关键对照
409 无码        409     -                 true    false   false   OK
400 无码        400     -                 false   false   false   OK
201 成功        201     -                 false   false   false   OK
其它码          422     DATABASE_23503    false   false   false   OK

修复后：6 PASS / 0 FAIL
```

**第 2 行是本次修复的价值点**：外键违规从「误判 `true`」变成「`false`」，
而第 1 行证明**真的唯一冲突仍然被正确识别** —— 收紧判断没有误伤正常路径。

### 6.3 改完必须回归

`rest.js` 是写路径的公共依赖，改完重跑全套：

- 主 Bug 验证：**5 PASS / 0 FAIL**（重复收藏仍被正确识别为 duplicate）
- Day 22 CRUD 闭环：**14/14 PASS**（含「再删一次 → 404 幂等」）
- 只读冒烟：**10/10 PASS**

**这里有一个容易翻车的点**：把「409 就算重复」收紧成「409 + 23505 才算」，
如果收错了，重复收藏会**漏判**成失败。所以 6.3 的第一项断言（重复收藏仍返回
`already_favorited`）**必须复跑**，不能只看纯函数测试就收工。


---

## 7. 改动文件清单

见收尾汇报（按用户要求，提交前先列清单等确认）。

---

## 8. 复现命令速查

```bash
# ① 复现（修复前）
python docs/day24/evidence/verify_bug_duplicate_join.py

# ② 定位的两个实验
python docs/day24/evidence/repro_fk_409.py        # 证明 isUniqueViolation 会把 23503 当 23505
python docs/day24/evidence/verify_position.py     # 证明它被 workExists 挡住、不可达

# ③/④ 修复后验证 + 回归
python docs/day24/evidence/verify_bug_duplicate_join.py --fix
python docs/day24/evidence/run_regression.py

# ⑤ 余力加练：isUniqueViolation 前后对比
node docs/day24/evidence/test_is_unique_violation.js

# 两张截图
python docs/day24/evidence/shot_day24.py
```

> 所有脚本都带超时、都清代理环境变量（本机 `HTTP_PROXY=127.0.0.1:53402` 会把
> `127.0.0.1` 的请求也塞进代理，Day 22 踩过）。
