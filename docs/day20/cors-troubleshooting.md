# 跨域排查记录（Day 20）

> 今日要掌握：**跨域那一下，你是怎么认出问题出在哪的？**
> 本文就是这个问题的完整答案 —— 含一次**反直觉的实测结论**。
>
> **一句话总结**：CloudBase 上同一个云函数有**两条长得像、但不是一回事**的通道。
> 用错通道 → 一路撞 401/403（因为那是管理端 API）；
> 用对通道 → 开箱即用、无需凭证、CORS 已开。**"认出问题出在哪"的关键，是先认出"我调的是哪条通道"。**

---

## 零、最终结论（先说答案）

| 通道 | 地址形态 | 要凭证吗 | CORS | 用途 |
|---|---|---|---|---|
| ① **管理端 API 网关** | `{envId}.api.tcloudbasegateway.com/v1/functions/{name}?webfn=true` | ✅ **必须**（service_role / 登录态） | ✅ 有 | 服务端 / CLI |
| ② **云函数 HTTP 访问服务** | `{envId}.service.tcloudbase.com/api/health` | ❌ **不需要** | ✅ `*` | **浏览器前端** |

**前端必须用 ②**。用 ① 会给浏览器塞管理员密钥，或者被 401/403 挡死。

---

## 一、现场：让浏览器直连云函数

### 改动前的结构

```
浏览器 ──相对路径 /api/health──▶ 发布平台 Node 服务（同源，不会有跨域）
```

前端用的是 `/api/health` 这种相对路径，域名一致 → **同源，永远不触发跨域**。
所以「跨域问题」在改造前根本不会出现。

### 改动后的结构（Day 20）

```
浏览器 ─┬─ /api/hot、/api/favorites ─▶ 发布平台 Node 服务（同源）
        │
        └─ https://{envId}.service.tcloudbase.com/api/health
                                        └▶ 云函数（**跨域**，无需凭证）
```

`app.js` 里两个基址，一眼看出区别：

```js
var API_BASE = '';                                                     // 本站，同源
var FN_BASE  = 'https://' + TCB_ENV_ID + '.service.tcloudbase.com/api/health';  // 云函数，跨域
```

---

## 二、走过的弯路：先撞了「管理端 API 网关」

最初把 `FN_BASE` 写成了：

```
https://{envId}.api.tcloudbasegateway.com/v1/functions/api-health?webfn=true
```

然后开始了一段**连环排查**，每一步的错误码都在移动，但**始终过不去**：

| 凭证 | 状态码 | 错误码 | 说明 |
|---|---|---|---|
| 不带 | 401 | `MISSING_CREDENTIALS` | 没带凭证 |
| Publishable Key | **403** | `EXCEED_AUTHORITY` | 凭证有效、但权限不够 |
| service_role API Key | 200 | —— | 管理员身份才通 |

### 决定性证据：请求「不存在的函数」也报 401

```bash
curl "https://{envId}.api.tcloudbasegateway.com/v1/functions/this-does-not-exist-xyz?webfn=true"
# → {"code":"MISSING_CREDENTIALS", ...}   而不是 "函数不存在"
```

如果拦人的是「函数级身份认证」，网关应该**先找到函数**再报它不存在；
现在它**连函数都没查**就拦下了 → 说明是**通道级的凭证要求**。

**这一步是整场排查的转折点**：它证明了「无论怎么改单个函数的开关都没用」，
因为**这条通道本身就不是给匿名调用准备的**。

`401 → 403` 是进步不是退步：401 = "你没证明身份"，403 = "身份认了，但不允许"。

官方对 `EXCEED_AUTHORITY` 的原文：

> 执行了超出当前角色或用户权限的操作，比如**用匿名用户访问需要登录权限的资源（比如云函数等）**
> —— https://docs.cloudbase.net/error-code/service/EXCEED_AUTHORITY

### 还被「几层开关」绕晕过

排查中一度以为要改「HTTP 网关 → 身份认证」开关，但用户反馈**那个开关本来就是关的**，
而实测依然 401 → 说明**根本不是那一层**。

CloudBase 这里确实有多层权限概念，容易混淆：

| 层级 | 位置 | 作用 |
|---|---|---|
| ① HTTP 网关「身份认证」 | HTTP 网关 → 路由行 | 要求请求带凭证 |
| ② 云函数安全规则 `invoke` | 云函数 → 权限控制 | 按身份决定能否调用（**仅对客户端 SDK 调用生效**） |
| ③ 函数代码 | —— | 业务逻辑 |

**问题的实质不是"哪层开关没关"，而是"通道选错了"。** 换通道后，三层全都不用动。

---

## 三、走通：换成「云函数 HTTP 访问服务」

`cloudbaserc.json` 里 Day 15 就配好了 http 触发器：

```json
"triggers": [{ "type": "http", "path": "/api/health", "method": "GET" }]
```

它对应的公网地址是 **`{envId}.service.tcloudbase.com/api/health`**。实测：

```bash
curl "https://{envId}.service.tcloudbase.com/api/health"
```

```
HTTP/1.1 200 OK
access-control-allow-origin: *                    ← 跨域全开
x-cloudbase-upstream-status-code: 200             ← 真进函数了
x-cloudbase-upstream-type: Tencent-SCF_HTTP

{ "ok": true, "service": "touhou-search", "env": "ericamellia24-...", ... }
```

**✅ 无需任何凭证、CORS 已开、200。**

### 一个容易被吓到的细节：OPTIONS 返回 405

```bash
curl -X OPTIONS "https://{envId}.service.tcloudbase.com/api/health"
# → 405 Method Not Allowed（但 access-control-allow-origin: * 照常返回）
```

**这不影响浏览器**，因为原因是：

> 我们这个 GET 请求是**简单请求**（`GET` + 无自定义请求头）→ 浏览器**根本不发预检**，直接发 GET。

所以那个 405 只是个"如果真有人发 OPTIONS 才会看到"的边角情况，**不阻断任何真实流程**。
（如果将来要加自定义请求头，就会触发预检，那时才需要处理 OPTIONS。）

---

## 四、今日核心知识点：怎么"认出问题出在哪"

把整场排查抽象成一套**可复用的判断法**：

### 判据一：看 F12 Network 的 Response 面板

| | **真正的跨域失败** | **鉴权/权限失败** |
|---|---|---|
| Status | `(failed)` / 无状态码 | **有明确状态码**（401/403） |
| Response | **空的** | **有 JSON** |
| Console | 大红字 `blocked by CORS policy` | 无 CORS 红字 |
| JS `fetch` | 抛 `TypeError: Failed to fetch` | 正常 resolve，`r.status` 可读 |

> **一句话**：**Response 里有 JSON = 请求通了，是业务/权限问题；Response 全空 + CORS 红字 = 才是跨域问题。**

跨域问题的报错信息**极其贫乏**（浏览器出于安全不告诉 JS 真实原因），
所以**不能靠代码里的 `catch` 猜**，必须回 F12 看原始响应。

### 判据二：看错误码的"移动方向"

错误码**变了**就说明**前一层已经过了**：

```
401 MISSING_CREDENTIALS  →  403 EXCEED_AUTHORITY  →  200
（缺凭证）                    （权限不足）              （通过）
```

**每次错误码变化 = 排查有进展**，顺藤摸瓜就能找到卡点所在层。

### 判据三：请求"不存在的资源"，看它报什么

这是一个**通用技巧**：故意请求一个不存在的对象。

- 报 `404 资源不存在` → 说明**已通过前置校验**，问题在资源本身
- 报 `401/403` → 说明**前置校验就拦下了**，跟资源无关，问题在**通道/权限**

本次正是靠这招，判定出"拦人的是通道级凭证要求"，从而放弃改函数开关、转向换通道。

---

## 五、怎么证明"真的跨出去了"（浏览器内核级取证）

前面第三节是用 `curl` 证明云函数通道可达 —— 但 `curl` 是**命令行**发的请求，
严格说不能证明**浏览器**也在跨域直连。

### 尝试过、但不可靠的路子：模拟 F12 按键截图

用 `keybd_event` 模拟 `F12` 打开 DevTools 再截图，**失败**：

- Edge 首次打开 DevTools 会弹「打开 Microsoft Edge 开发人员工具？」引导框，**挡住面板**；
- 即使按 Esc/Enter 关掉引导框，DevTools 是**独立渲染进程**，模拟按键的时序极不稳定；
- 截出来的图要么没面板，要么就是那个引导框。

> 结论：**用模拟按键抢 DevTools 截图这条路，投入产出比极低，别走。**

### 走通的路子：CDP（DevTools Protocol）直接抓

靠 `--remote-debugging-port` + WebSocket 接进浏览器内核，**从协议层读真实网络记录**，
再用 `Page.captureScreenshot` 截图（不依赖任何窗口按键）。

```bash
# 关键：先清掉系统代理环境变量，否则连 127.0.0.1 的调试端口都会被代理拦成 502
# 启动参数必须带 --remote-allow-origins=*，否则 WebSocket 握手报 403 Forbidden
python cdp_net.py <url> <out.png>
```

脚本见 `docs/day20/evidence/cdp_net.py`。本次抓到的真实记录：

| 方法 | 请求 URL | 状态 | 远端 IP |
|---|---|---|---|
| GET | `https://touhou-mock.app.workbuddy.host/api/hot?board=fresh&limit=12` | 200 | `49.233.240.214` |
| GET | `https://touhou-mock.app.workbuddy.host/api/favorites?limit=20` | 200 | `49.233.240.214` |
| GET | **`https://ericamellia24-d2gk0ftukc71292c5.service.tcloudbase.com/api/health`** | **200** | **`124.223.146.214`** |

### 关键判读：IP 对不上，才叫真跨域

第三条的域名是 `*.service.tcloudbase.com`（云函数公网地址，**不是本站域名**），
远端 IP `124.223.146.214` 与本站 Node 服务 `49.233.240.214` **是两台不同的机器**。

> 若请求其实是走本站代理或本地 mock，IP 必然与本站一致。
> **IP 不同 = 浏览器真的把请求打到了云函数那台机器上。**

这条判据比"看起来像跨域"硬得多 —— 它是从浏览器内核层拿到的远端 IP。
证据图：`docs/day20/evidence/day20-network-evidence.png`。

---

## 六、本次改动清单（Day 20）

| 文件 | 改了什么 |
|---|---|
| `deploy/public/app.js` | 新增 `TCB_ENV_ID` / `API_BASE` / `FN_BASE` 三个配置；`loadHealth()` 改为直连**云函数 HTTP 访问服务**；业务接口显式拼 `API_BASE`；新增「最后更新时间」`setLastChecked()`（余力加练）；catch 分支补充跨域/鉴权区分提示 |
| `deploy/public/index.html` | health 卡改名为「云函数 api-health · 跨域直连」；新增 `#hUrl` 显示请求地址；新增 `#hLastChecked` + 「重新检查」按钮（余力加练）；版本号 `?v=4` → `?v=5` |
| `deploy/public/style.css` | 新增 `.lbl-tag` 样式（卡片通道标签） |
| `docs/day20/cors-troubleshooting.md` | 本文 |
| `docs/day20/evidence/` | CDP 取证脚本 + 网络请求证据图 |

