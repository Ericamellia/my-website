# 公网持久化验证记录（Day 21）

> 目标：让**公网线上的服务**不再读 `deploy/data/*.json` 快照，而是读写 CloudBase 真库，
> 从而做到「重启/换机数据不丢」。
> 结论：✅ **已达成**。线上 `dataSource` 从 `snapshot` 切到 `rest`，写入落库并通过独立通道验证。

---

## 一、问题的起点：线上的三种数据源

服务启动时会按优先级自动选一条通道（详见 `docs/day21/data-layer-refactor.md`）：

| 优先级 | 通道 | 触发条件 | 是否持久 |
|---|---|---|---|
| ① | `rest`（HTTP API / PostgREST） | `CLOUDBASE_ENV_ID` + `CLOUDBASE_API_KEY` | ✅ 持久 |
| ② | `database`（pg 直连） | `PG_URL` / `DATABASE_URL` | ✅ 持久 |
| ③ | `snapshot`（JSON 快照） | 以上都没有 | ❌ 一发布就重置 |

发布前线上是 `snapshot` —— **因为线上拿不到凭证**。所以核心任务只有一句话：
**把 CloudBase 凭证送到线上进程里。**

---

## 二、为什么不用「平台环境变量」

原本最干净的做法是在发布平台的「环境变量配置」里填凭证。但用户在
**设置 → 数据管理 → 应用管理** 页面截图确认：

> 无「环境变量」/「配置」/「设置」类似按钮，数据库图标且显示云服务未启动。

**该功能不存在。** 于是走退路。

---

## 三、退路方案：随代码一起上传 `deploy/.env`

`server.js` 内置了一个**零依赖的 `.env` 加载器**（第 29–53 行），会按顺序读两个位置：

```js
const candidates = [
  path.join(__dirname, '.env'),           // deploy/.env   ← 用这个
  path.join(__dirname, '..', '.env')      // 项目根 .env
];
```

所以把 `deploy/.env` 跟着 `deploy/` 目录一起发布，进程启动时就会把它读进 `process.env`。

**关键顺序**：`server.js` 第 29 行先跑 `.env` 加载器，**第 55 行才** `require('./db')` ——
所以 `db/config.js` 里读 `process.env` 时凭证已经就位。

### 3.1 三个安全前置检查

| 检查项 | 命令 / 依据 | 结果 |
|---|---|---|
| 不进 Git 仓库 | `git check-ignore -v deploy/.env` | ✅ `.gitignore:5:*.env  deploy/.env` |
| 不被当静态文件暴露 | `server.js` 的 `serveStatic` 有 `if (!filePath.startsWith(ROOT)) return 403`，`ROOT = deploy/public/` | ✅ `.env` 在 `deploy/` 根，不在托管范围内 |
| 本地能读到 | 复刻加载器后 `db.hasRestApi()` | ✅ `true` |

---

## 四、执行与验证

### 4.1 本地先验（改动前）

```bash
cp .env deploy/.env          # 凭证就位
```

按 `server.js` 的顺序加载后：

```
hasRestApi = true
hasDatabase = false
ENV_ID = ericamellia24-d2gk0ftukc71292c5
```

本地起服务 `PORT=3100`：

```
GET /api/health      → dataSource: rest      ✅
GET /api/hot         → source: rest, 6 条    ✅
GET /api/favorites   → source: rest, 7 条    ✅
POST {}              → 400 missing_work_id   ✅
PUT                  → 405                   ✅
```

### 4.2 发布（覆盖线上）

- 目标：`https://touhou-mock.app.workbuddy.host/`（链接不变，内容被替换）
- 目录：`deploy/`（含新加的 `deploy/.env`）

### 4.3 线上验证（三条闸门 + 落库）

| # | 用例 | 期望 | 实际 |
|---|---|---|---|
| 1 | `GET /api/health` | `dataSource: rest` | ✅ **rest**（原为 snapshot） |
| 2 | `GET /api/favorites` | 7 条真库基线 | ✅ `ids=[7,6,5,4,3,2,1]` |
| 3 | `POST {workId:"music-999"}` | 404 作品不存在 | ✅ 404 `work_not_found` |
| 4 | `POST {workId:"BV1xh…"}` | 400 格式错 | ✅ 400 `invalid_work_id_format` |
| 5 | `POST {workId:"video-1"}` | 409 重复收藏 | ✅ 409 `already_favorited`，**回显了真库记录 id=6** |
| 6 | `POST {workId:"art-2"}` | 201 写入成功 | ✅ **201，id=20** |

第 5 条尤其有说服力：409 的响应体里带出了 `"userId": "local"` 的**真实库行**，
证明线上读的就是 CloudBase，不是本地快照。

### 4.4 决定性证据：独立通道确认落库

用**本地直连 CloudBase 的 REST API**（完全绕开发布平台）查 `id=20`：

```bash
curl "https://{ENV_ID}.api.tcloudbasegateway.com/v1/rdb/rest/favorites?id=eq.20" \
  -H "Authorization: Bearer {API_KEY}"
```

返回：

```json
[
  {
    "id": 20,
    "user_id": "local",
    "work_id": "art-2",
    "note": "Day21 公网持久化验证",
    "created_at": "2026-10-10T14:19:03.799345+08:00"
  }
]
```

时间戳 `14:19:03+08:00` 与线上写入返回的 `06:19:03Z` **完全对应**。

> **这就闭环了**：线上写入 → 云端数据库真实落库 → 与沙箱进程无关。
> 服务重启、换机器、重新发布，这条数据都还在。

### 4.5 清理与恢复基线

```bash
DELETE .../favorites?id=eq.20   → 204
复查 id=eq.20                   → []
```

线上最终状态：

```
1. health  → ok=True,  dataSource=rest
2. hot     → ok=True,  source=rest, 6 条
3. favs    → ok=True,  source=rest, 7 条, ids=[7,6,5,4,3,2,1]   ← 基线已恢复
4. POST {} → 400
5. POST 不存在作品 → 404
6. PUT     → 405
7. GET /   → 200（静态页正常）
```

---

## 五、这次真正学到什么

1. **「持久化」的判据不是「写进去了」，而是「换一条独立通道还能查到」。**
   只看线上 POST 返回 201 不足以证明；必须绕开写入方，用另一条路去读。
2. **`.env` 随代码上传是可行退路，但前提是三道锁**：不进 Git、不被静态托管、加载顺序正确。
3. **`console.log` 在发布平台不回传，要诊断线上必须用 `console.error`**（见 `data-layer-refactor.md` 第七节）。
4. **凭证放服务端 ≠ 安全**，还要确认它不会被当成静态资源下载。
   本项目的解法是静态根目录白名单（`ROOT = deploy/public/`），`.env` 天然在范围外。
