# api-contract.md｜东方同人搜索 接口契约（Day 21）

> 本文件是前后端之间的**唯一接口约定**。已落地：`GET /api/health`（Day 15）、
> `GET /api/hot` 与 `GET /api/favorites`（Day 17）、`POST /api/favorites`（Day 18）。
> Day 19 打通 **HTTP API 真库数据源**（写入持久化）；Day 21 把数据访问层拆分重构 + 修通云函数网关，
> 两次改动**接口形状均未变**。
> 其余接口在本文件里先占位（写明现状与返回），真实实现排在 Day 22+。

| 项 | 值 |
|---|---|
| 契约版本 | `1.1.0` |
| 更新日期 | 2026-10-10 |
| 公网地址（mock 版） | `https://touhou-mock.app.workbuddy.host` |
| 本地地址 | `http://127.0.0.1:3000`（`PORT` 可覆盖） |
| 数据格式 | JSON，`Content-Type: application/json; charset=utf-8` |
| 时间格式 | ISO 8601 UTC，例：`2026-09-30T17:31:48.704Z` |

---

## 0. 通用约定（所有接口都适用）

1. **请求与响应一律 JSON**，字段名用 `lowerCamelCase`，字符编码 UTF-8。
2. **成功**用 HTTP 2xx；**失败**用对应 4xx/5xx，且响应体必须包含 `ok: false`。
3. **统一错误体**：

```json
{
  "ok": false,
  "error": "machine_readable_code",
  "message": "给人看的一句话说明（可选）"
}
```

4. **健康检查不缓存**：`/api/health` 恒带 `Cache-Control: no-store`，避免看到旧结果。
5. **跨域**：Day 15 阶段允许所有来源（`Access-Control-Allow-Origin: *`），
   Day 16 起改为站点域名白名单，契约会同步更新。
6. **状态码对照**：

| 状态码 | 含义 | 何时出现 |
|---|---|---|
| 200 | 成功 | 正常返回数据（读接口） |
| 201 | 已创建 | **写接口成功新建了一条记录**（Day 18 起） |
| 304 | 未修改 | 仅在启用协商缓存的接口上（health 不用） |
| 400 | 请求参数错误 | 缺参数 / 参数格式不对 / body 不是合法 JSON |
| 404 | 资源不存在 | 路径或 id 找不到 |
| 405 | 方法不允许 | 例：对 health 发 POST；响应体会带 `allow` 列出该路径支持的方法 |
| 409 | 冲突 | **重复提交**（同一用户重复收藏同一作品，Day 18 起） |
| 413 | 请求体过大 | body 超过 64KB 上限（Day 18 起） |
| 501 | 尚未实现 | 契约已定义但后端还没写 |
| 500 | 服务端错误 | 未捕获异常 |

> **为什么 409 不复用 400**：400 的意思是「你这条请求本身写错了，改一改再来」；
> 409 的意思是「请求没写错，但它和现有数据冲突了」。前端据此刻画不同提示 ——
> 400 引导用户改输入，409 提示「已收藏过」并把已有记录展示出来。

---

## 1. `GET /api/health` — 健康检查（已实现 ✅）

**用途**：确认「服务活着、能对外返回 JSON」。这是第一个上公网的接口，
用来验证 DNS → 网关 → 服务进程整条链路是通的，不查数据库、不调外部依赖，保证毫秒级返回。

### 请求

```
GET /api/health HTTP/1.1
Host: touhou-mock.app.workbuddy.host
```

- 方法：`GET`（`HEAD` 也接受）
- 参数：**无**
- 鉴权：**无**

### 响应 200

```json
{
  "ok": true,
  "service": "touhou-search",
  "env": "mock",
  "version": "1.0.0",
  "time": "2026-09-30T17:31:48.704Z",
  "uptimeSec": 17,
  "node": "v22.13.1",
  "checks": {
    "http": "ok",
    "static": "ok"
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | boolean | 固定 `true`。**前端只认这一个字段**判断服务是否正常 |
| `service` | string | 服务名，固定 `touhou-search` |
| `env` | string | 环境标识：`mock`（本部署）/ CloudBase 环境 ID（云函数，本环境为 `ericamellia24-d2gk0ftukc71292c5`）/ `local` |
| `version` | string | 契约版本，与本文件顶部一致 |
| `time` | string | 服务端当前时间，ISO 8601 UTC |
| `uptimeSec` | number | 进程已运行秒数（云函数场景是**实例**存活秒数，冷启动后归零） |
| `node` | string | Node 运行时版本，排查环境问题时用 |
| `checks` | object | 子项自检结果，见下 |

`checks` 子项：

| 字段 | 取值 | 说明 |
|---|---|---|
| `http` | `ok` | HTTP 层能正常响应 |
| `static` | `ok` / `missing` / `n/a` | 静态目录是否就绪；云函数版不托管静态资源，恒为 `n/a` |

### 响应 405（方法不对）

```json
{ "ok": false, "error": "method_not_allowed", "allow": ["GET", "HEAD"] }
```

### 前端用法

```js
fetch('/api/health', { cache: 'no-store' })
  .then(r => r.json())
  .then(d => console.log(d.ok ? '服务正常' : '服务异常'));
```

mock 版首页顶部那张「健康状态卡」就是这么调的，会把返回的 JSON 原样显示出来。

---

## 2. `GET /api/hot` — 热搜榜（已实现 ✅ Day 17）

**用途**：返回 B 站东方同人视频的两个榜单 —— 当日新发布（`fresh`）与历史热门（`hot`）。

### 请求

```
GET /api/hot?board=fresh&limit=20
```

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `board` | 否 | `all` | `fresh` 当日新发布 / `hot` 历史热门 / `all` 两榜都要 |
| `limit` | 否 | `20` | 每榜返回条数，上限 100（超过按 100 处理） |

### 响应 200

```json
{
  "ok": true,
  "endpoint": "/api/hot",
  "source": "snapshot",
  "board": "fresh",
  "limit": 2,
  "syncedAt": "2026-10-10T11:29:49+08:00",
  "syncedDate": "2026-10-10",
  "counts": { "fresh": 2, "hot": 0, "total": 2, "limit": 2 },
  "data": [
    {
      "bvid": "BV1Lvpt6YEex",
      "board": "fresh",
      "rank": 1,
      "title": "成都THO11 大地に咲く旋律 一场幻想乡的梦",
      "author": "雷电灵风RaidenWind",
      "mid": 12345678,
      "play": 35,
      "danmaku": 0,
      "favorites": 2,
      "duration": "3:22",
      "category": "日常",
      "pubdate": 1791602220,
      "publishedAt": "2026-10-09T14:37:00.000Z",
      "cover": "https://i1.hdslb.com/bfs/archive/xxx.jpg",
      "description": "……",
      "url": "https://www.bilibili.com/video/BV1Lvpt6YEex"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | boolean | 固定 `true` |
| `source` | string | 数据来源，三态：`rest` = HTTP API 真库（Day 19 起，**写入持久**）；`database` = pg 直连真库；`snapshot` = 读 `deploy/data/hot.json` 快照（写入不持久） |
| `counts` | object | 本次返回的各榜条数 |
| `data[].rank` | number | 榜内名次（1 开始） |
| `data[].publishedAt` | string | 由 `pubdate` 换算出的 ISO 8601 时间 |
| `data[].url` | string | B 站播放页地址 |

---

## 3. `GET /api/favorites` — 收藏列表（已实现 ✅ Day 17）

**用途**：返回某个用户的收藏，**JOIN `works` 表**把作品名/社团/封面一并带出，前端不用再发第二次请求。

### 请求

```
GET /api/favorites?userId=local&limit=50
```

| 参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `userId` | 否 | `local` | 用户标识（Day 18 还没有登录体系，固定 `local`） |
| `limit` | 否 | `50` | 返回条数上限 200 |

### 响应 200

```json
{
  "ok": true,
  "endpoint": "/api/favorites",
  "source": "snapshot",
  "userId": "local",
  "limit": 50,
  "count": 8,
  "data": [
    {
      "id": 8,
      "userId": "local",
      "workId": "art-2",
      "note": "Day18 写入验证",
      "createdAt": "2026-10-10T04:15:40.726Z",
      "category": "art",
      "name": "やくも ゆかり",
      "circle": "wukloo",
      "creator": "wukloo",
      "year": 2016,
      "cover": "assets/art/art2.jpg",
      "tags": ["东方Project"],
      "characters": ["八云紫"],
      "description": "……",
      "sourceUrl": "https://www.pixiv.net/artworks/59572603"
    }
  ]
}
```

---

## 4. `POST /api/favorites` — 新增一条收藏（已实现 ✅ Day 18）

**用途**：给某个作品加一条收藏。这是本站**第一个写接口**，所以它必须自带两道闸门：

| 闸门 | 防什么 | 怎么做 | 失败返回 |
|---|---|---|---|
| ① 入参校验 | 错误输入 | 入库**之前**逐字段检查（必填/类型/格式/长度） | `400` + 中文提示 |
| ② 唯一约束 | 重复提交 | 数据库 `UNIQUE (user_id, work_id)` + `ON CONFLICT DO NOTHING` | `409 already_favorited` |

> **为什么防重复必须靠数据库，不能只靠前端**：
> 前端禁用按钮挡不住网络自动重试、脚本直调、双开页面。
> 数据库唯一约束是最后一道、也是**原子**的一道 ——
> 实测 8 个请求并发提交同一条，结果恰好 1 个 `201` + 7 个 `409`，库里只有 1 行。

### 请求

```
POST /api/favorites
Content-Type: application/json

{ "workId": "art-2", "note": "画风对味" }
```

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `workId` | **是** | string | 作品编号，格式 `{板块}-{编号}`，如 `music-1`；长度 ≤ 32 |
| `userId` | 否 | string | 用户标识，默认 `local`；长度 1–64 |
| `note` | 否 | string | 收藏备注；长度 ≤ 255（与表定义 `VARCHAR(255)` 一致） |

### 响应 201（新建成功）

```json
{
  "ok": true,
  "endpoint": "/api/favorites",
  "action": "created",
  "source": "snapshot",
  "message": "收藏成功",
  "data": {
    "id": 8,
    "userId": "local",
    "workId": "art-2",
    "note": "Day18 写入验证",
    "createdAt": "2026-10-10T04:15:40.726Z",
    "category": "art",
    "name": "やくも ゆかり",
    "circle": "wukloo",
    "creator": "wukloo",
    "year": 2016,
    "cover": "assets/art/art2.jpg",
    "tags": ["东方Project"],
    "characters": ["八云紫"],
    "description": "……",
    "sourceUrl": "https://www.pixiv.net/artworks/59572603"
  }
}
```

**`data` 的形状与 `GET /api/favorites` 的 `data[]` 完全一致** ——
这样前端「新增成功后」可以直接把这条推进本地列表，不用再拉一次全量。

### 响应 409（重复提交）

```json
{
  "ok": false,
  "error": "already_favorited",
  "message": "你已经收藏过 art-2 了，不用重复提交",
  "data": { "id": 8, "workId": "art-2", "..." : "……（已有那条的完整内容）" }
}
```

`data` 里带上**已存在的那条**，前端可以据此直接高亮「这条你已经收藏过了」。

### 错误码一览

| 状态码 | `error` | 触发条件 | `message`（中文，直接给用户看） |
|---|---|---|---|
| 400 | `invalid_json` | body 不是合法 JSON | 请求体不是合法的 JSON，请检查格式（引号、逗号、括号） |
| 400 | `invalid_body` | body 不是对象（如传了数组或字符串） | 请求体必须是一个 JSON 对象 |
| 400 | `missing_work_id` | 缺 `workId` 或为空 | 缺少必填字段 workId（要收藏的作品编号，例如 music-1） |
| 400 | `invalid_work_id` | `workId` 不是字符串 / 超长 | workId 必须是字符串，例如 music-1 |
| 400 | `invalid_work_id_format` | `workId` 不符合 `{板块}-{编号}` | workId 格式不对，应形如「板块-编号」，例如 music-1、video-2 |
| 400 | `invalid_user_id` | `userId` 类型/长度不对 | userId 必须是字符串 / 长度需在 1–64 个字符之间 |
| 400 | `invalid_note` | `note` 类型不对 / 超 255 字 | note 必须是字符串 / note 长度不能超过 255 个字符 |
| 404 | `work_not_found` | `workId` 在本站不存在 | 作品 music-999 不存在，请先确认 workId 是否正确 |
| 405 | `method_not_allowed` | 用了 GET/HEAD/POST 以外的方法 | 响应体带 `allow: ["GET","HEAD","POST"]` |
| 409 | `already_favorited` | 该用户已收藏过该作品 | 你已经收藏过 art-2 了，不用重复提交 |
| 413 | `body_too_large` | body 超过 64KB | 请求体过大，不能超过 64KB |
| 500 | `write_failed` / `insert_failed` | 落库异常 | 写入失败：…… |

### 校验顺序（为什么这样排）

```
1. 方法对不对            → 405   （最便宜，先挡）
2. body 能否解析成 JSON   → 400   （不碰数据库）
3. 字段齐不齐、格式对不对  → 400   （不碰数据库）
4. 作品存不存在           → 404   （查一次 works）
5. 落库；撞唯一约束       → 409   （最贵，最后做）
```

前三步都是**纯计算、不碰数据库**，所以脏请求根本打不到库上 ——
这是写接口的基本功：**把便宜的检查放在前面，把昂贵的操作放在最后。**

---

## 5. 尚未实现的接口（Day 19–20，占位）

> 现阶段调用下面任意路径，服务端统一返回 **501**：
> ```json
> { "ok": false, "error": "not_implemented", "path": "/api/works" }
> ```
> 之所以明确回 501 而不是 404，是为了让前端一眼区分「路径写错了」和「后端还没写」。

| 方法 | 路径 | 用途 | 计划 |
|---|---|---|---|
| GET | `/api/works` | 作品列表（分页 / 分类 / 排序） | Day 19 |
| GET | `/api/works/:id` | 作品详情 | Day 19 |
| GET | `/api/search` | 关键词搜索（作品名 / 作者 / 角色 / 标签） | Day 19 |
| GET | `/api/circles` | 社团 / 作者列表 | Day 20 |
| GET | `/api/originals` | ZUN 原曲列表 | Day 20 |
| PATCH | `/api/favorites/:id` | 改收藏备注 | 第 4 周 |
| DELETE | `/api/favorites/:id` | 取消收藏 | 第 4 周 |

这部分接口一旦开工，字段定义直接追加到本文件，并同步升 `契约版本`。

---

## 6. Mock 版说明（当前线上是什么）

- 线上 `https://touhou-mock.app.workbuddy.host` 跑的是 `deploy/` 下的 Node 服务：
  - `/api/health` → **真实接口**，返回如上 JSON；
  - 其它路径 → 托管 `deploy/public/` 的静态页面（mock 版首页）。
- 首页展示的作品数据是**前端写死的示例**（`deploy/public/app.js` 里的 `WORKS` 数组），
  不调用任何业务接口，也不代表真实站点内容。
- 切换到真实接口时，只需把 `WORKS` 换成 `fetch('/api/works')` 的结果，
  字段沿用 `title / author / tags / category`，前端渲染代码不用改。

---

## 7. CloudBase 云函数版（同一份契约）

目录 `cloudbase/functions/api-health/index.js` 是上面契约的云函数实现，
返回体与 §1 **完全一致**，只是换成 CloudBase 的响应结构：

```js
return { statusCode: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' }, body: JSON.stringify(payload) };
```

差异只有两点：

1. `env` 取自云函数上下文的环境 ID（不再是 `mock`）；
2. `checks.static` 恒为 `n/a`（云函数不托管静态资源，静态站走静态托管）。

HTTP 触发路径配置为 `/api/health`，见 `cloudbase/cloudbaserc.json`（`envId` 已填真实环境
`ericamellia24-d2gk0ftukc71292c5`）。

---

## 8. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-01（Day 15） | 初版。落地 `GET /api/health`，占位 6 个业务接口，明确 501 语义 |
| 2026-10-08（Day 15 续） | `env` 字段说明补真实环境 ID；`cloudbaserc.json` 落 `envId` 与 Nodejs18.15；记录 HTTP 网关 `INVALID_ENV` 排查与降级路径 |
| 2026-10-08（Day 16） | 数据层落地。新增 §9 数据库表结构（`circles` / `works`），业务接口的字段来源自此有据可依 |
| 2026-10-10（Day 17） | 补 §2 `GET /api/hot`、§3 `GET /api/favorites` 完整定义；契约版本升 `1.1.0`；新增 `favorites` / `hot_videos` 两张表说明 |
| 2026-10-10（Day 18） | 新增 §4 `POST /api/favorites`（第一个写接口）。明确两道闸门（入参校验 + 唯一约束）、错误码全表、校验顺序；状态码表补 `201` / `409` / `413` 及 409 与 400 的语义区别 |
| 2026-10-10（Day 19） | **接口形状未变**，只扩展数据源：`source` 字段增补 `rest`（HTTP API 真库，写入持久）。Day 15 起悬而未决的 `INVALID_ENV` 定位为**环境 ID 少写一个 `t`**，修正 `cloudbaserc.json` / README / 本文档等 12 处；§7 部署与数据源说明改写为三态优先级 |
| 2026-10-10（Day 21） | **接口形状未变**，只重构内部结构：数据访问层从单文件 `db.js`（737 行）拆为 `db/` 目录 6 个文件（详见 `docs/day21/data-layer-refactor.md`）。同时修通 **云函数网关**：Day 15 起 404 `INVALID_ENV` → 443（函数类型与代码不匹配 + 缺 `scf_bootstrap`）→ `200 OK`。9 项全接口回归通过 |

---

## 9. 数据库表结构（Day 16 起）

目标库：**CloudBase PostgreSQL**。建表脚本 `db/schema.sql`，种子数据 `db/seed.sql`。

详细设计说明（含类型选择理由、索引设计、验证结果）见 `docs/day16/data-model.md`。

### 6.1 两张核心表

| 表 | 存什么 | 主键 | 条数 |
|---|---|---|---|
| `circles` | 「谁做的」——社团 / 作者档案 | `name` | 26 |
| `works` | 「做了什么」——全部作品（五板块合并） | `work_id` | 30 |

**关联**：`works.circle_name` → `circles.name`（外键，`ON UPDATE CASCADE ON DELETE SET NULL`）

### 6.2 `circles` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | VARCHAR(128) | 主键。社团/作者名，如 `COOL&CREATE` |
| `name_en` | VARCHAR(128) | 英文名/罗马音 |
| `intro` | TEXT | 社团简介 |
| `source_url` | VARCHAR(512) | 资料源页 URL |
| `avatar` | VARCHAR(255) | 头像路径 |
| `top_platform` | VARCHAR(32) | 主要平台，如 `bilibili` |
| `followers` | INTEGER | 该平台粉丝数，可空 |
| `platform_url` | VARCHAR(512) | 平台主页 URL |
| `created_at` | TIMESTAMPTZ | 入库时间 |

### 6.3 `works` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `work_id` | VARCHAR(32) | 主键，格式 `{板块}-{原id}`，如 `music-1` |
| `category` | VARCHAR(16) | 板块：`music` / `doujin` / `game` / `art` / `video` |
| `name` | VARCHAR(255) | 作品名 |
| `circle_name` | VARCHAR(128) | **外键** → `circles.name` |
| `creator` | VARCHAR(128) | 作者/主催个人名 |
| `year` | SMALLINT | 发行年份 |
| `characters` | JSONB | 登场角色名数组 |
| `tags` | JSONB | 标签数组 |
| `popularity` | INTEGER | 热度值 |
| `views` | INTEGER | 站点浏览量，`NOT NULL DEFAULT 0` |
| `cover` | VARCHAR(512) | 封面路径或外链 |
| `source_url` | VARCHAR(512) | 原发布页 URL |
| `description` | TEXT | 简介 |
| `netease_url` | VARCHAR(512) | [仅 music] 网易云链接 |
| `video_type` | VARCHAR(64) | [仅 video] 视频类型 |
| `video_platform` | VARCHAR(32) | [仅 video] 视频平台 |
| `video_url` | VARCHAR(512) | [仅 video] 视频直链 |
| `bvid` | VARCHAR(32) | [仅 video] B站视频号 |
| `original_title` | VARCHAR(255) | [仅 video] 原曲名 |
| `created_at` | TIMESTAMPTZ | 入库时间 |

> **命名注意**：JSON 源数据里的 `type` / `platform` / `url` 三个字段名，在表里改成了
> `video_type` / `video_platform` / `video_url` —— 因为它们是 video 板块专属，
> 加前缀后语义更清晰，也避开了通用词做列名。

### 9.4 各接口的字段来源

| 接口 | 主要读哪张表 | 状态 |
|---|---|---|
| `GET /api/health` | 不查库 | ✅ Day 15 |
| `GET /api/hot` | `hot_videos`（按 `board` 分组、`rank_no` 排序） | ✅ Day 17 |
| `GET /api/favorites` | `favorites` **LEFT JOIN** `works` | ✅ Day 17 |
| `POST /api/favorites` | `favorites`（INSERT，冲突检测靠 `uq_favorites_user_work`） | ✅ Day 18 |
| `GET /api/works` | `works`（按 `category` 筛选，按 `popularity` / `year` 排序） | Day 19 |
| `GET /api/works/:id` | `works` + JOIN `circles`（详情页要显示所属社团） | Day 19 |
| `GET /api/search` | `works`（`name` 模糊 + `characters` / `tags` 的 JSONB 包含查询） | Day 19 |
| `GET /api/circles` | `circles` | Day 20 |
| `GET /api/originals` | 原曲表（待建） | Day 20 |

### 9.5 `favorites` 表为什么能防重复（Day 18 的依赖）

Day 18 的 `POST /api/favorites` 之所以能做到「重复提交被拒」，靠的是 Day 17 建表时就埋好的这条约束：

```sql
CONSTRAINT uq_favorites_user_work UNIQUE (user_id, work_id)
```

写入语句配合 `ON CONFLICT (user_id, work_id) DO NOTHING`：
- 没冲突 → 插入成功，`RETURNING` 带回新行 → 接口返回 `201`
- 有冲突 → 插入 0 行（**不报错**）→ 接口查出已有那条，返回 `409 already_favorited`

**这就是「昨天设计的表结构，今天变成了接口能力」** ——
如果 Day 17 没加唯一约束，今天防重复就只能靠「先 SELECT 再 INSERT」，
而那样在并发下会漏（两个请求同时查到「不存在」，然后都插入）。
