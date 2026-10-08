# 云函数代码逐段讲解（Day 15 余力加练）

> 讲解对象：`cloudbase/functions/api-health/index.js`
> 同一份契约的另一版实现是 `deploy/server.js`（已跑在公网），两者返回体完全一致，最后一段会对比差异。

---

## 第 0 段：文件头与三个常量

```js
'use strict';
const STARTED_AT = Date.now();
const SERVICE = 'touhou-search';
const VERSION = '1.0.0';
```

| 代码 | 作用 | 为什么这么写 |
|---|---|---|
| `'use strict'` | 开启严格模式 | 变量必须先声明、this 不再默认指向全局，能把低级错误提前暴露 |
| `STARTED_AT` | 记下**这个文件被加载**的时刻 | 云函数冷启动时模块只初始化一次，用它算 uptime（实例活了多久） |
| `SERVICE` / `VERSION` | 服务名与契约版本 | 直接出现在返回 JSON 里，一眼看出连的是哪个服务、哪版契约 |

⚠️ 注意 `STARTED_AT` 是**模块级**的：实例复用时它不会重置，所以 `uptimeSec` 反映的是「这个实例活了多久」，不是「这次请求花了多久」。

---

## 第 1 段：云函数入口

```js
exports.main = async (event = {}, context = {}) => { ... }
```

- CloudBase 规定：云函数的入口是 `exports.main`。配置里写 `handler: "index.main"`，就是「index.js 的 main」。
- `event`：调用方传进来的东西。HTTP 触发时，里面是这次请求的信息（路径、方法、头、查询串、body）。
- `context`：运行时环境信息，通常能拿到环境 ID、函数配置、请求 ID 等。
- 两个参数都给了默认 `{}`：直接本地调试（不带参数调用）时也不会因为读 `undefined` 的属性而崩。
- `async`：允许内部用 `await`，也为以后接数据库/外部调用留好位置。

---

## 第 2 段：取环境 ID

```js
const env =
  (context && (context.envId || (context.namespace && context.namespace.envId))) ||
  process.env.TCB_ENV ||
  process.env.SCF_NAMESPACE ||
  'cloudbase';
```

- 目的：把「我在哪个环境跑」写进返回里，方便排查（连错环境是部署期最常见的坑）。
- 用 `||` 串了四级兜底：上下文 → 环境变量 → 再一个环境变量 → 字符串常量。
- 每层都先判空（`context && ...`），避免在不支持的运行时里抛异常。

---

## 第 3 段：读请求方法与路径

```js
const http = event.httpContext || {};
const method = (http.httpMethod || event.method || 'GET').toUpperCase();
const path = http.path || event.path || '/api/health';
```

- HTTP 触发时，CloudBase 把请求信息放在 `event.httpContext`（不同版本字段名会有出入，所以兼容 `event.method`）。
- `toUpperCase()`：HTTP 方法理论上是大写，但网关/调试工具可能传小写，统一一下再比较。
- 同样给了默认值——**不是 HTTP 触发**（比如定时触发器、控制台直接测试）时，函数照样能跑出一份正常返回，不会 500。

---

## 第 4 段：方法不对就明确拒绝

```js
if (method !== 'GET' && method !== 'HEAD') {
  return {
    statusCode: 405,
    headers: jsonHeaders(),
    body: JSON.stringify({ ok: false, error: 'method_not_allowed', allow: ['GET', 'HEAD'] }, null, 2)
  };
}
```

- 健康检查只读，只接受 `GET` / `HEAD`。
- 关键点：**用 405 而不是 200**。如果什么请求都回 200，前端就没法判断「接口到底是不是正常」——健康检查的意义在于能诚实地报错。
- 错误体带 `allow` 字段，告诉调用方哪些方法可用（契约里也写明了这一条）。

---

## 第 5 段：组装返回内容

```js
const payload = {
  ok: true,
  service: SERVICE,
  env: env,
  version: VERSION,
  time: new Date().toISOString(),
  uptimeSec: Math.round((Date.now() - STARTED_AT) / 1000),
  node: process.version,
  path: path,
  checks: { http: 'ok', static: 'n/a' }
};
```

- `ok`：前端**只认这一个字段**判断服务是否正常，其它字段都是给人看的诊断信息。
- `time`：ISO 8601 UTC，方便和本机时间对账（时区问题一眼看出来）。
- `uptimeSec`：用第 0 段记的时间算差值，说明实例存活多久；冷启动后归零是正常现象。
- `checks`：子项自检。这里故意**不查库、不调外部服务**——健康检查必须永远快、永远不因为依赖挂掉而误报。
- `static: 'n/a'`：云函数不托管静态资源，如实写 n/a，不假装 ok。

---

## 第 6 段：云函数的 HTTP 响应结构

```js
return {
  statusCode: 200,
  headers: jsonHeaders(),
  body: JSON.stringify(payload, null, 2)
};
```

这是 CloudBase 云函数走 **HTTP 访问服务**时约定的三件套：

| 字段 | 含义 |
|---|---|
| `statusCode` | HTTP 状态码 |
| `headers` | 响应头（必须含 `Content-Type`，否则浏览器当纯文本） |
| `body` | **必须是字符串**——`JSON.stringify` 不能省，返回对象会被当成 `[object Object]` |

`JSON.stringify(payload, null, 2)` 里的 `null, 2` 是「缩进 2 空格」，让浏览器里直接打开也是排版好的 JSON，方便肉眼检查。

---

## 第 7 段：统一响应头

```js
function jsonHeaders() {
  return {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*'
  };
}
```

- `Content-Type` 带 `charset=utf-8`：中文不乱码。
- `Cache-Control: no-store`：**健康检查绝不缓存**，否则看到的是几分钟前的旧结果，等于没检查。
- `Access-Control-Allow-Origin: *`：Day 15 阶段先放开，方便手机、本地各种来源调试；Day 16 会按站点域名收白名单。

抽成函数是为了 405 和 200 两处共用，避免哪天改了一处忘了另一处。

---

## 第 8 段：和已上线的 `deploy/server.js` 有什么不一样

| 对比项 | 云函数版（未部署，待 CloudBase 开通） | Node 服务版（已上线公网） |
|---|---|---|
| 入口 | `exports.main(event, context)` | `http.createServer((req,res)=>…)` |
| 返回方式 | 返回 `{statusCode, headers, body}` 对象 | `res.writeHead()` + `res.end()` |
| `env` | 环境 ID（如 `touhou-search-1x2y3z`） | `mock` |
| `checks.static` | `n/a`（不托管静态） | `ok`（托管 `public/`） |
| 还能做什么 | 只处理 `/api/health` | 额外托管 mock 前端页面；其它 `/api/*` 返回 501 |

**这就是为什么先写契约**：两版返回同一个 JSON，前端把 baseURL 从 mock 域名换成云函数域名即可，前端代码一行都不用改。

---

## 部署后怎么验证（三步）

1. 控制台 → 云函数 → `api-health` → 触发管理 → 确认 HTTP 路径是 `/api/health`、方法 `GET`。
2. 浏览器打开 `<默认域名>/api/health`，看到 `ok: true` 且 `env` 是真实环境 ID。
3. 把 `docs/api-contract.md` §4 里的 `env` 示例值换成真实环境 ID，契约与线上保持一致。
