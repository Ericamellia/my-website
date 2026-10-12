# day23.md｜上线红线三件套：密钥排查 · 忽略规则 · 错误提示统一

> **今天要掌握的一句话**：你把哪句裸报错改成了人话？改前改后分别是什么？
>
> **一句话答案**：
> 改前——接口一崩，用户拿到的是 `rest_query_failed`、`connect ECONNREFUSED 127.0.0.1:5432`、
> 甚至 `[object Object]` 这种东西；改后——同一处故障回的是
> **「数据暂时取不到，可能是后台正在维护。请稍后再试一次。」**
> 关键不在「换成中文」，而在**把内部细节从响应体里挪走、只留在服务端日志**。

---

## 0. 今天的三个板块（按优先级）

| # | 板块 | 性质 | 状态 |
|---|---|---|---|
| ① | 密钥排查 | **上线红线**（优先级最高） | ✅ 完成 |
| ② | `.env` 与忽略规则检查 | 同上，一体两面 | ✅ 完成 |
| ③ | 三类错误提示统一 | 用户体验 + 信息安全 | ✅ 完成 |

**今天刻意不做**：不引入复杂异常处理框架；不改任何业务逻辑（接口形状一律不变）。

---

## 1. 板块①：密钥排查（红线）

### 1.1 担忧是什么

「仓库里会不会不小心躺着一把能进真库的钥匙？」——如果会，**任何人 clone 下来就能
绕过所有权限直接读写生产数据**。这是上线前必须清零的一项。

### 1.2 排查方法

**扫描范围**：`git ls-files`（只扫**被跟踪**的文件 —— 因为只有这些才真的会进仓库）。
用工作区全量扫会把 `.env`（本地文件，不进仓库）也算进去，反而看不清真实风险。

**正则设计（这里是关键，我第一次写错了）**：

```
❌ 错的：eyJhbG|eyJ[A-Za-z0-9_-]{10,}|service_role|sk-[A-Za-z0-9]{20,}
✅ 对的：(eyJhbG|eyJ[A-Za-z0-9_-]{20,})|(API_?KEY|apikey|secret|token)["']?\s*[:=]\s*["']?[A-Za-z0-9_-]{20,}
```

**为什么第一版是错的**：`service_role` 这个词在代码注释和文档里出现，是在**警告
「严禁进前端/仓库」**。把「警告文字」判成「密钥」，会得到 10 条全误报的结论，
真正的风险反而被淹没。

**正确判据**：密钥是**值**，长得像「键 = 20 位以上长串」。所以正则必须匹配
**键值形态**，而不是散落的词。

### 1.3 结果

```
被跟踪文件总数            : 645
密钥「值」特征命中行数    : 0        ← 关键
.env 被跟踪数             : 0
历史提交里出现过 .env     : 无
```

**补充结论（一个容易误判的点）**：

环境 ID `ericamellia24-d2gk0ftukc71292c5` **不是密钥**，是**资源标识**。
前端必须知道它才能拼出接口地址，设计上就是公开的（像「你家门牌号」而不是「你家钥匙」）。
它出现在 12 个被跟踪文件里（含 `deploy/public/verify/app.js`），**保留不动**。

**唯一的真风险点是文档里的占位示例**：`RUN.md` 原来写
`CLOUDBASE_API_KEY=eyJhbGciOi...`，虽然只是省略号占位，但它**长得像真 Key 的开头**，
扫描器会命中。已改为 `<在控制台创建后复制粘贴，是一段很长的字符串>`。

> 教训：**文档里不要贴 Key 的前几位当示例**。哪怕只是开头，也会污染扫描结果，
> 让「0 条」变成「1 条」，「红线达标」变成「需要人工解释」。

### 1.4 复现方式

```bash
bash docs/day23/evidence/secret-scan.sh
# 结果存档：docs/day23/evidence/secret-scan-result.txt
```

---

## 2. 板块②：`.env` 与忽略规则

### 2.1 现状核查

| 检查项 | 命令 | 结果 |
|---|---|---|
| `.env` 是否被跟踪 | `git ls-files --error-unmatch .env` | 报错=未跟踪 ✅ |
| `.env` 是否被忽略 | `git check-ignore -v .env` | `.gitignore:5:*.env` ✅ |
| `.env.local` / `.env.production` | `git check-ignore -v` | `.gitignore:4:.env.*` ✅ |
| `deploy/.env` | `git check-ignore -v` | `.gitignore:5:*.env` ✅ |
| 历史提交是否含 `.env` | `git log --all --diff-filter=A --name-only` | 无 ✅ |

### 2.2 补的短板：配置模板

**问题**：不给模板，别人（或未来的自己）clone 下来不知道要配哪几个变量，容易瞎猜、
容易配错，甚至有人会「先把值硬编码进代码试试」。

**做法**：新建 `.env.example` —— **只列键名 + 说明，值全部留空**。

```
① CloudBase HTTP API（走真库，写入持久）
   CLOUDBASE_ENV_ID=
   CLOUDBASE_API_KEY=          # 控制台创建，service_role 权限，严禁提交
② PostgreSQL 直连（本地开发用）
   DATABASE_URL=
   PG_URL=
   PG_NO_SSL=
③ 端口
   PORT=3000
```

### 2.3 一个踩到的坑：`.env.*` 会误伤 `.env.example`

`.gitignore` 里原本有 `.env.*` 这条规则（为的是挡住 `.env.local` / `.env.production`），
但它**顺手把 `.env.example` 也忽略了** —— 模板根本提交不上去。

**修法**：加一条 negation 例外。

```gitignore
.env.*
!.env.example      ← 捞回模板
```

**判断是否生效时还有个二次坑**：`git check-ignore -v .env.example` 即使返回**命中**，
命中的也可能是 **`!` 开头的 negation 规则**（意为「没被忽略」）。
所以**不能只看命令有没有输出**，要看输出的规则行是不是以 `!` 开头：

```
$ git check-ignore -v .env.example
.gitignore:9:!.env.example	.env.example
             ↑ 这个 ! 表示「例外生效、文件可提交」
```

---

## 3. 板块③：三类错误提示统一

### 3.1 问题：为什么「报错」需要统一

改之前，不同的失败路径各自 `sendJson` 拼响应，结果用户看到的五花八门：

| 崩在哪 | 用户看到的东西 | 问题 |
|---|---|---|
| REST 查询失败 | `{"error":"rest_query_failed"}` | 英文内部代号，人看不懂 |
| pg 连不上 | `connect ECONNREFUSED 127.0.0.1:5432` | **泄漏内网地址和端口** |
| 某些异常 | `{"message":"[object Object]"}` | 完全没有意义的字符串 |

一句话：**代码在跟用户说「行话」，甚至把自己的家底（IP、端口、堆栈）念出来了。**

### 3.2 三类错误的分法（按「谁的锅」）

| 类别 | 谁的锅 | 状态码 | 该说什么 |
|---|---|---|---|
| ① 入参校验 | 调用方 | 400 | 哪一步写错了 + 怎么改（带示例） |
| ② 资源不存在 | 调用方 | 404 | 什么没找到（带上 id/编号） |
| ③ 服务端异常 | **我们** | 5xx | 「请稍后再试」，**不暴露任何内部细节** |

分法的价值：前两类是**帮用户改**，第三类是**我们认错但别把家底抖出去**。

### 3.3 实现：一张翻译表 + 六个函数

在 `deploy/server.js` 里加了一层「错误翻译层」（约 60 行，无第三方依赖）：

| 函数 | 职责 |
|---|---|
| `ERROR_DIALOGUE` | 翻译表：内部错误码 → `{status, error, message}` |
| `errCodeOf(err)` | 从异常里取稳定代号（兜底：`err.code \|\| err.error`） |
| `errDetailOf(err)` | 拼**给日志用**的完整细节（code / message / detail / 堆栈首帧） |
| `safeStringify(v)` | 拼日志时的序列化兜底，防止循环引用再抛一次 |
| `toUserError(err)` | 查表；查不到 → 兜底 `500 internal_error` |
| `sendUserError(req,res,where,err,opts)` | 记日志 + 回人话，**一处收口** |

**翻译表**：

```js
const ERROR_DIALOGUE = {
  DATA_MISSING: { status: 503, error: 'data_unavailable',
                  message: '数据暂时取不到，可能是后台正在维护。请稍后再试一次。' },
  REST_FAILED:  { status: 502, error: 'upstream_failed',
                  message: '后端数据服务没有正常响应，请稍后再试。' },
  PG_FAILED:    { status: 502, error: 'database_failed',
                  message: '数据库连接不上，请稍后再试。' },
  WRITE_FAILED: { status: 500, error: 'write_failed',
                  message: '写入没有成功，请稍后再试一次。' }
};
// 查不到 → { status: 500, error: 'internal_error',
//             message: '服务出了点问题，请稍后再试。我们已经记下这次异常。' }
```

**核心原则**：

> **详情只进服务端日志，响应体只给人话。**

```js
function sendUserError(req, res, where, err, opts) {
  const t = toUserError(err);
  const status  = (opts && opts.status)  || t.status;
  const errorCode = (opts && opts.error) || t.error;
  const message   = (opts && opts.message) || t.message;
  console.error('[error] ' + new Date().toISOString() + ' ' + where +
    ' -> ' + status + ' ' + errorCode + ' | ' + errDetailOf(err) +
    (opts && opts.extra ? ' | extra=' + safeStringify(opts.extra) : ''));
  sendJson(res, status, { ok: false, error: errorCode, message: message });
  //                      ↑ 响应体里没有 code= / at= / 堆栈 / 路径
}
```

### 3.4 替换了哪 10 处

原先散在各 handler 里的 `catch` 裸报错，**全部换成 `sendUserError` 收口**：

| 位置 | 接口 | 类别 |
|---|---|---|
| L349 | `GET /api/hot` | ③ |
| L370 | `GET /api/favorites` | ③ |
| L465 | `POST /api/favorites` | ③（额外记 `logWrite`） |
| L513 | `GET /api/works` | ③ |
| L531 | `GET /api/circles` | ③ |
| L549 | `GET /api/original-games` | ③ |
| L567 | `GET /api/characters` | ③ |
| L585 | `GET /api/originals` | ③ |
| L681 | `PATCH /api/favorites/:id` | ③ |
| L744 | `DELETE /api/favorites/:id` | ③ |

**故意保留不动的一处**：`GET /api/works` 的 `invalid_category` 分支仍然自己
`sendJson(400)` —— 因为它的 `message` 本来就已经是**有意义的人话**
（「category 只能是：music / doujin / game / video / art」），
硬套进翻译层反而要多写一条特例表。

### 3.5 顺手修掉的一个 bug（替换过程中发现）

`handleOriginalGames(req, res)` 的函数签名**没有 `urlPath` 参数**，
但错误分支里写了 `urlPath.split('?')[0]`。

后果：这个接口一旦出错，会抛 `ReferenceError: urlPath is not defined`，
**错误处理本身先崩了** —— 用户拿到的就不是人话，而是连接被掐断。

修法：`where` 直接写死 `'GET /api/original-games'`（这个路径固定，本来也没有
查询串要解析）。同时全量核对了一遍所有 handler 的签名与引用，确认没有同类问题。

---

## 4. 实测：三类错误的中文提示

> 完整原始输出：`docs/day23/evidence/error-messages-verify.txt`
> 第三类单独实验：`docs/day23/evidence/error-data-missing-verify.txt`

### 第一类｜入参校验（400）

| 场景 | `error` | `message`（用户看到的） |
|---|---|---|
| 缺 workId | `missing_work_id` | 缺少必填字段 workId（要收藏的作品编号，例如 music-1） |
| workId 格式错 | `invalid_work_id_format` | workId 格式不对，应形如「板块-编号」，例如 music-1、video-2 |
| PATCH 空 body | `empty_patch` | 请求体是空的，至少要给出一个要修改的字段（目前支持：note） |
| 非法 JSON | `invalid_json` | 请求体不是合法的 JSON，请检查格式（引号、逗号、括号） |
| 分类传错 | `invalid_category` | category 只能是：music / doujin / game / video / art |

### 第二类｜资源不存在（404）

| 场景 | `error` | `message` |
|---|---|---|
| PATCH 不存在的 id | `favorite_not_found` | 没有找到 id=99999 的收藏，可能已经被取消了 |
| DELETE 不存在的 id | `favorite_not_found` | 同上 |
| 作品不存在 | `work_not_found` | 作品 music-999999 不存在，请先确认 workId 是否正确 |

### 第三类｜服务端异常（5xx）★

**怎么造**：临时移走 `deploy/data/circles.json`，并**强制服务降级到快照通道**，
请求 `/api/circles` → 快照读不到文件 → 抛 `DATA_MISSING`。

**用户看到的**（HTTP 503）：

```json
{ "ok": false, "error": "data_unavailable",
  "message": "数据暂时取不到，可能是后台正在维护。请稍后再试一次。" }
```

**服务端日志里才有的**：

```
[error] 2026-10-12T12:22:51.852Z GET /api/circles -> 503 data_unavailable
  | code=DATA_MISSING | message=circles_data_unavailable
  | at=at Object.dataMissing (...\deploy\db\snapshot.js:44:13)
```

↑ 对照一下：`DATA_MISSING`、`snapshot.js:44`、文件路径 **全都在日志里、全都不在响应里**。
这就是「详情只进日志」的证据。

**对照组**：同一台服务上 `/api/health` 仍返回 200（`dataSource: "snapshot"`），
说明**只有坏掉那条路在报错**，不是整个服务崩了。

### 全接口回归（10/10 PASS）

改错误处理最怕「顺手把正常路径也改坏了」。所以提交前跑了一遍全接口回归：

```
===== 正常路径回归（应为 200）=====
  [PASS] GET /api/health                HTTP 200
  [PASS] GET /api/hot                   HTTP 200
  [PASS] GET /api/favorites             HTTP 200
  [PASS] GET /api/works?category=music  HTTP 200
  [PASS] GET /api/circles               HTTP 200
  [PASS] GET /api/original-games        HTTP 200
  [PASS] GET /api/characters            HTTP 200
  [PASS] GET /api/originals             HTTP 200

===== 错误路径回归（应为 4xx）=====
  [PASS] GET /api/works?category=nope   HTTP 400
  [PASS] PATCH /api/favorites/99999     HTTP 405
```

原始输出：`docs/day23/evidence/regression-verify.txt`

---

## 5. 一个关键的环境坑：怎么才能强制降级到快照通道

第一次实验失败了：明明用 `env -u CLOUDBASE_ENV_ID -u CLOUDBASE_API_KEY` 清掉了
环境变量，服务**还是走 REST 通道**（`source: "rest"`），返回 200 而不是错误。

**根因**：`server.js` 顶部有一个**零依赖的 `.env` 加载器**（Day 19 写的，为了避免
引入 `dotenv` 依赖）。它的逻辑是：

```js
if (process.env[key] === undefined) process.env[key] = val;   // ← 只在「未定义」时才写入
```

所以 `env -u` 把变量**删掉**（变成 `undefined`）之后，加载器又把 `.env` 里的值
**读回来了** —— 清了等于没清。

**解法**：不解 `.env`，而是传**空串**（空串 ≠ `undefined`，加载器就不会覆盖）：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY \
    CLOUDBASE_ENV_ID= CLOUDBASE_API_KEY= DATABASE_URL= PG_URL= \
    PORT=3010 node deploy/server.js
```

`getRestEnvId()` 返回 `''` → `hasRestApi()` 为假 → 降级到 `snapshot` ✅

> 值得记住：**「删掉变量」和「把变量设成空」在 Node 里是两件事**。
> 前者是 `undefined`，会触发各种兜底/默认值注入；后者是「我明确告诉你没有」。

---

## 6. 今日完成标准自检

| 标准 | 结果 | 证据 |
|---|---|---|
| 全仓库搜不到密钥特征词 | ✅ 密钥值命中 **0** 条 | `evidence/secret-scan-result.txt` |
| `.env` 不在仓库且被忽略 | ✅ 跟踪 0 个 / 4 种 `.env.*` 全被忽略 / 历史无 | 同上 §4–§7 |
| 三类错误都返回中文提示 | ✅ 400 / 404 / 503 全部实测通过 | `evidence/error-messages-verify.txt` |

---

## 7. 改动文件清单

| 文件 | 改动 | 属于哪天的任务 |
|---|---|---|
| `deploy/server.js` | 加错误翻译层（6 个函数）+ 替换 10 处裸报错 + 修 `handleOriginalGames` 的 `urlPath` bug | **Day 23** |
| `.env.example` | **新建**。配置模板，值全空，只列键名与说明 | **Day 23** |
| `.gitignore` | 加 `!.env.example` 例外（否则模板被 `.env.*` 误伤） | **Day 23** |
| `RUN.md` | 把文档里的 `CLOUDBASE_API_KEY=eyJhbGciOi...` 占位示例改为不含 Key 特征的开头 | **Day 23** |
| `docs/api-contract.md` | §0 加第 7 条「错误提示统一」；状态码表补 502/503；变更记录加 Day 23 行；版本升 `1.3.0` | **Day 23** |
| `docs/day23/day23.md` | **新建**。本文档 | **Day 23** |
| `docs/day23/evidence/secret-scan.sh` | **新建**。密钥排查脚本（可复现） | **Day 23** |
| `docs/day23/evidence/secret-scan-result.txt` | **新建**。扫描结果存档 | **Day 23** |
| `docs/day23/evidence/error-messages-verify.txt` | **新建**。三类错误实测存档 | **Day 23** |
| `docs/day23/evidence/error-data-missing-verify.txt` | **新建**。第三类错误单独实验存档 | **Day 23** |

> 注：`.gitignore` 里的 `__pycache__/`、`*.pyc` 两条属 **Day 22 余力**（上一条提交
> `c6d4353` 已提交）；今天这次对 `.gitignore` 的改动只有 `!.env.example` 一条。

---

## 8. 遗留 / 未做

| 项 | 说明 | 归属 |
|---|---|---|
| `rest.isUniqueViolation` 判断过宽 | 现在用 `status === 409` 一刀切，会把**外键违规** `23503` 误判成**唯一冲突** `23505`。今天发现了但**没改**（超范围、且要动业务判断） | 待排期 |
| 余力加练：请求日志 | 加一条「时间 / 路径 / 结果」的简单请求日志 | Day 23 余力（见下） |
| 余力加练（可选）：回补 Day 22 降级未完成的 DELETE | 应用层 DELETE 已上线；但 day21 记录的「无自助删除能力」问题在降级通道下仍未覆盖 | Day 23 余力 |

---

## 9. 今天要交的截图（两张）

1. **全仓库搜密钥特征词 = 0 条** —— 跑 `bash docs/day23/evidence/secret-scan.sh`，
   把「命中行数 = 0」「.env 被跟踪数 = 0」「✅ 两项全 0，通过」那一段截下来。
2. **三类错误的中文提示** —— 跑完三类实测，把
   `docs/day23/evidence/error-messages-verify.txt` 里 400 / 404 / 503 各一段截下来。
