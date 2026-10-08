# api-contract.md｜东方同人搜索 接口契约（Day 15）

> 本文件是前后端之间的**唯一接口约定**。Day 15 只落地一个接口：`GET /api/health`。
> 其余接口在本文件里先占位（写明现状与返回），真实实现排在 Day 16–20，不在今天做。

| 项 | 值 |
|---|---|
| 契约版本 | `1.0.0` |
| 更新日期 | 2026-10-01 |
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
| 200 | 成功 | 正常返回数据 |
| 304 | 未修改 | 仅在启用协商缓存的接口上（health 不用） |
| 400 | 请求参数错误 | 缺参数 / 参数格式不对 |
| 404 | 资源不存在 | 路径或 id 找不到 |
| 405 | 方法不允许 | 例：对 health 发 POST |
| 501 | 尚未实现 | 契约已定义但后端还没写（Day 15 的 `/api/*` 除 health 外都走这个） |
| 500 | 服务端错误 | 未捕获异常 |

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
| `env` | string | 环境标识：`mock`（本部署）/ CloudBase 环境 ID（云函数，本环境为 `ericamellia24-d2gk0fukc71292c5`）/ `local` |
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

## 2. 尚未实现的接口（Day 16–20，占位）

> 现阶段调用下面任意路径，服务端统一返回 **501**：
> ```json
> { "ok": false, "error": "not_implemented", "path": "/api/works" }
> ```
> 之所以明确回 501 而不是 404，是为了让前端一眼区分「路径写错了」和「后端还没写」。

| 方法 | 路径 | 用途 | 计划 |
|---|---|---|---|
| GET | `/api/works` | 作品列表（分页 / 分类 / 排序） | Day 16–17 |
| GET | `/api/works/:id` | 作品详情 | Day 17 |
| GET | `/api/search` | 关键词搜索（作品名 / 作者 / 角色 / 标签） | Day 18 |
| GET | `/api/circles` | 社团 / 作者列表 | Day 18 |
| GET/POST | `/api/favorites` | 收藏读写 | Day 19 |
| GET | `/api/originals` | ZUN 原曲列表 | Day 19 |

这部分接口一旦开工，字段定义直接追加到本文件，并同步升 `契约版本`。

---

## 3. Mock 版说明（当前线上是什么）

- 线上 `https://touhou-mock.app.workbuddy.host` 跑的是 `deploy/` 下的 Node 服务：
  - `/api/health` → **真实接口**，返回如上 JSON；
  - 其它路径 → 托管 `deploy/public/` 的静态页面（mock 版首页）。
- 首页展示的作品数据是**前端写死的示例**（`deploy/public/app.js` 里的 `WORKS` 数组），
  不调用任何业务接口，也不代表真实站点内容。
- 切换到真实接口时，只需把 `WORKS` 换成 `fetch('/api/works')` 的结果，
  字段沿用 `title / author / tags / category`，前端渲染代码不用改。

---

## 4. CloudBase 云函数版（同一份契约）

目录 `cloudbase/functions/api-health/index.js` 是上面契约的云函数实现，
返回体与 §1 **完全一致**，只是换成 CloudBase 的响应结构：

```js
return { statusCode: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' }, body: JSON.stringify(payload) };
```

差异只有两点：

1. `env` 取自云函数上下文的环境 ID（不再是 `mock`）；
2. `checks.static` 恒为 `n/a`（云函数不托管静态资源，静态站走静态托管）。

HTTP 触发路径配置为 `/api/health`，见 `cloudbase/cloudbaserc.json`（`envId` 已填真实环境
`ericamellia24-d2gk0fukc71292c5`）。

---

## 5. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-01（Day 15） | 初版。落地 `GET /api/health`，占位 6 个业务接口，明确 501 语义 |
| 2026-10-08（Day 15 续） | `env` 字段说明补真实环境 ID；`cloudbaserc.json` 落 `envId` 与 Nodejs18.15；记录 HTTP 网关 `INVALID_ENV` 排查与降级路径 |
| 2026-10-08（Day 16） | 数据层落地。新增 §6 数据库表结构（`circles` / `works`），业务接口的字段来源自此有据可依 |

---

## 6. 数据库表结构（Day 16 起）

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

### 6.4 各接口的字段来源（Day 17 起参照）

| 接口 | 主要读哪张表 |
|---|---|
| `GET /api/works` | `works`（按 `category` 筛选，按 `popularity` / `year` 排序） |
| `GET /api/works/:id` | `works` + JOIN `circles`（详情页要显示所属社团） |
| `GET /api/search` | `works`（`name` 模糊 + `characters` / `tags` 的 JSONB 包含查询） |
| `GET /api/circles` | `circles` |
| `GET /api/favorites` | Day 19 再加收藏表 |
| `GET /api/originals` | Day 19 再加原曲表（当前 ZUN 原曲数据仍在 JSON 里） |
