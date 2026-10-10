# RUN.md｜东方同人搜索 本地运行说明

> Day 7 MVP 运行存档。纯静态站（无后端、无数据库、无构建步骤），只需要一个静态文件服务器。

## 1. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| Python | 3.x（任意现代版本） | 只用标准库 `http.server`，无需 pip 安装任何包 |
| 浏览器 | Chrome / Edge 等现代浏览器 | 需支持 fetch / ES6 模板字符串 |

## 2. 启动命令

> **重要提示（2026-10-08 实测）**：本地预览服务是**会话级**的 —— 进程随启动它的会话结束而消失。
> 所以「打不开」通常是**服务没在跑**，不是配置问题。重启命令见下。
> 8000 端口历史上被残留进程占用（连得上但无响应），**请直接用 8001**。

```bash
cd "C:\Users\25394\WorkBuddy\2026-09-18-00-29-07"
"C:\Users\25394\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m http.server 8001 --bind 127.0.0.1
```

启动成功的标志：终端输出

```
Serving HTTP on 127.0.0.1 port 8001 (http://127.0.0.1:8001/) ...
```

> ⚠️ 不要关闭这个终端窗口，关了服务就停。
> ⚠️ 若提示端口被占用（`OSError: [Errno 10048]`），换成 8002 等空闲端口，下面地址也跟着改。

### 判断服务是否在跑

```bash
netstat -ano | grep ":8001.*LISTENING"     # 有输出=在跑；无输出=没跑
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/my-app/   # 期望 200
```

若 `netstat` 只看到 `TIME_WAIT` / `SYN_SENT` 而没有 `LISTENING`，说明服务已停止，重新执行上面的启动命令即可。

### 打不开时优先试 127.0.0.1

某些环境下 `localhost` 会走系统代理（返回 **502 Bad Gateway**），而 `127.0.0.1` 直连本机可绕开代理。
**两个都试一遍**，能确定是代理问题还是服务问题。

## 3. 访问地址

| 页面 | URL |
|---|---|
| **根加载页**（先播「少女祈祷中」再进入） | http://127.0.0.1:8001/index.html |
| **首页** | http://127.0.0.1:8001/my-app/ |
| 同人音乐 | http://127.0.0.1:8001/my-app/#/music |
| 同人漫画 | http://127.0.0.1:8001/my-app/#/doujin |
| 同人游戏 | http://127.0.0.1:8001/my-app/#/game |
| 同人视频 | http://127.0.0.1:8001/my-app/#/video |
| ZUN 原曲 | http://127.0.0.1:8001/my-app/#/original |
| 作品详情（示例） | http://127.0.0.1:8001/my-app/#/music/1 |
| 角色反查（示例） | http://127.0.0.1:8001/my-app/#/character/博丽灵梦 |

## 4. 改了代码看效果（重要）

**每次改动 `app.js` / `style.css` 后，必须做两件事：**

1. 把 `my-app/index.html` 里引用的版本号加一：`app.js?v=4` → `app.js?v=5`
2. 浏览器用 **Ctrl + F5** 强制刷新

> 原因：`python -m http.server` 不发 `Cache-Control` 头，浏览器会用启发式缓存继续加载旧 JS，出现「改了没生效」的假象（Day 7 实际踩过）。

## 5. 常见问题

| 症状 | 原因 | 解法 |
|---|---|---|
| 双击 `index.html` 打开后一直「加载中」 | `file://` 协议下 fetch 被浏览器 CORS 拦截 | 必须用 http server（见第 2 节），不要直接双击文件 |
| **页面打不开 / 一直转圈 / 502** | **服务进程已随会话结束消失**（最常见） | 见第 2 节「判断服务是否在跑」，重新启动；地址优先用 `127.0.0.1` |
| 页面显示「数据加载失败：…」 | 服务没启动 / 端口不对 / 目录不对 | 核对终端是否还在跑、URL 端口是否一致 |
| 视频封面显示成色块 | B站图床防盗链或网络波动（已加 `referrerpolicy="no-referrer"` 降级） | 属预期降级，不裂图；网络正常时会显示真实封面 |
| 中文乱码 | 文件编码不对 | 全部文件统一 UTF-8（当前已是） |

## 5·补 数据库（Day 16 起）

数据层脚本在 `db/` 目录，目标库是 **CloudBase PostgreSQL**。

| 文件 | 用途 |
|---|---|
| `db/schema.sql` | 建表（**4 张表**：`circles` / `works` / `favorites` / `hot_videos`），幂等，可重复执行 |
| `db/schema-favorites.sql` | 只建 `favorites` 表（Day 17 单独执行用；跑过整份 schema.sql 就不用跑） |
| `db/schema-hot.sql` | 只建 `hot_videos` 表（Day 17） |
| `db/seed.sql` | 种子数据全文（26 社团 + 30 作品），幂等 |
| `db/seed-part1-circles.sql` | 仅社团 26 条（分批导入用，控制台单次粘贴量有限） |
| `db/seed-part2-works.sql` | 仅作品 30 条（**必须在 part1 之后执行**，有外键依赖） |
| `db/seed-favorites.sql` | 收藏示例数据 7 条（Day 17 新增，**依赖 works 已存在**） |
| `db/sync_hot.py` | 拉 B 站真实东方视频，生成 `db/seed-hot.sql`（Day 17 热搜同步） |
| `db/seed-hot.sql` | 热搜同步产物：当日真实 B 站数据 40 条，幂等 |
| `db/fresh-part1~4.sql` / `db/hot-part1~4.sql` | 上者的切块版（每块 5 条，给控制台分段粘贴用） |
| `db/gen_seed.py` | 从 `my-app/data/*.json` 重新生成 `seed.sql`（改了 JSON 就重跑这个） |
| `db/gen_favorites_snapshot.py` | 生成 `deploy/data/favorites.json`（Day 17，收藏快照） |
| `db/gen_works_snapshot.py` | 生成 `deploy/data/works.json`（Day 18，作品快照，写接口校验用） |

**导入顺序（全新环境）**：
`schema.sql` → `seed-part1-circles.sql` → `seed-part2-works.sql` → `seed-favorites.sql` → `seed-hot.sql`

**增量场景（Day 16 已建好 circles/works）**：
`schema-favorites.sql` → `seed-favorites.sql` → `schema-hot.sql` → `seed-hot.sql`

**执行位置**：CloudBase 控制台 → SQL 数据库 → SQL 编辑器。
⚠️ 单个文件建议 < 5KB，否则控制台粘贴可能被静默截断（见 `db/*-part*.sql` 的分块做法）。

详细设计说明见 `docs/day16/data-model.md`（数据模型）、`docs/day17/read-api.md`（读接口）、
`docs/api-contract.md`（接口契约，含 Day 18 的 `POST /api/favorites`）。

## 5·补2 本地起服务（Day 17 起）

```bash
# 在项目根的 deploy/ 目录执行
PORT=3000 node server.js
```

**数据源优先级（Day 19 起三态）**：

| 优先级 | 条件 | 数据源 | 写入持久？ | `source` 字段 |
|---|---|---|---|---|
| ① | 配了 `CLOUDBASE_ENV_ID` + `CLOUDBASE_API_KEY` | **HTTP API（PostgREST）真库** | ✅ **持久** | `rest` |
| ② | 配了 `PG_URL` / `DATABASE_URL` 且装了 `pg` | pg 直连真库 | ✅ 持久 | `database` |
| ③ | 以上都没有 | `deploy/data/*.json` 快照 | ❌ 不持久 | `snapshot` |

- **本地开发**：没有 ① 的 Key 时自动走 ② 或 ③，互不影响。
- **公网版**：配 ① 走 HTTP API，**不需要装 `pg`**（发布平台 pre-check 会拒绝含 `pg` 的项目）。
- 凭证放在**项目根 `.env`**（已被 `.gitignore` 忽略），`server.js` 内置零依赖加载器读取。

**数据访问层代码结构（Day 21 重构）**：

```
deploy/db/
├── index.js      业务查询 + 通道选路（优先级 ①→②→③）
├── config.js     环境变量 → 连接参数
├── pg.js         通道②：PostgreSQL 直连（pg 驱动）
├── rest.js       通道①：HTTP API（PostgREST）
├── snapshot.js   通道③：JSON 快照（降级）
└── mappers.js    行 → 对外形状（三条通道收敛成同一形状）
```

`server.js` 只 `require('./db')`，永远不知道数据从哪来。
详见 `docs/day21/data-layer-refactor.md`。

### 配置 HTTP API（Day 19）

1. 控制台 → 环境管理 → **API Key 配置** → 「服务端 API Key」→ 创建
2. 把 **环境 ID** 和 **API Key** 写进项目根 `.env`：

```env
CLOUDBASE_ENV_ID=ericamellia24-d2gk0ftukc71292c5
CLOUDBASE_API_KEY=eyJhbGciOi...
```

> ⚠️ **环境 ID 必须从控制台「复制」取得**，不要手打、不要从截图读。
> 曾因少写一个 `t`（`d2gk0fu…` vs `d2gk0ftu…`）导致整条通道报 `INVALID_ENV`，
> 排查了很久——这类 23 字符随机串肉眼极易看错。

> ⚠️ `API Key` 是 `service_role` 权限（绕过 RLS），**只能放服务端环境变量**，
> 严禁写进前端代码、严禁提交到仓库。

- 启动日志会打印当前数据源，一眼可见
- 共 4 个接口：`GET /api/health`、`GET /api/hot`、`GET /api/favorites`、`POST /api/favorites`

## 6. 未来部署（GitHub Pages）

本地跑通后，部署只需把仓库推到 GitHub，在仓库 Settings → Pages 选 `main` 分支即可。

注意：站点在 `my-app/` 子目录，Pages 默认指向根目录，届时需要二选一：
- 方案 A：仓库根加一个跳转页（指向 `/my-app/`）
- 方案 B：把 Pages 配置改为 GitHub Actions 指定 `my-app/` 目录

（此项留到 Day 21+ 部署时再定，今日不做。）
