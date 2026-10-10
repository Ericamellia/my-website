# Day 15 部署环境信息（实测记录）

记录时间：2026-10-01 01:35（GMT+8）

## 一、已上线服务（公网可访问）

| 项 | 值 |
|---|---|
| 应用名 | 东方同人搜索 Mock 版 |
| 公网域名 | `touhou-mock.app.workbuddy.host` |
| 入口页面 | https://touhou-mock.app.workbuddy.host/ |
| 健康接口 | https://touhou-mock.app.workbuddy.host/api/health |
| 部署形态 | http-service（Node 单端口服务） |
| 运行时 | Node `v22.13.1` |
| 网关 | CloudStudio Gateway（`Server: CloudStudio Gateway`） |
| 沙箱 ID | `e4f189fe74fe4c039a11df893dd24841` |
| 首验时间 | 2026-09-30T17:31:48Z（= 北京时间 10-01 01:31） |
| 首验结果 | `/api/health` → HTTP 200，`ok:true`；`/` → HTTP 200；`/app.js` → HTTP 200 |
| 复验时间 | 2026-10-08 09:47（GMT+8），隔一周后再测仍 200 + `ok:true`，服务持续在线 |

## 一·补 交付截图（本目录）

| 截图 | 内容 |
|---|---|
| `day15-health-json.png` | 真实浏览器窗口打开 `/api/health`，地址栏 + 返回的 JSON |
| `day15-frontend.png` | 公网前端 mock 版页面（含健康状态卡实时结果） |
| `day15-console.png` | 部署环境信息页 `env-info.html`（CloudBase 环境 ID / 额度 / 到期日期已实测填入） |

## 二、CloudBase 环境信息（**已开通**，2026-10-08 补齐）

| 项 | 值 |
|---|---|
| 环境 ID | `ericamellia24-d2gk0ftukc71292c5` |
| 地域 | 上海（ap-shanghai） |
| 计费模式 | 免费体验版（3000 资源点/月，单环境，不可加购/按量） |
| 剩余额度 | 0 / 3000 点已用（仅冷启动消耗） |
| 到期日期 | `2027-04-08`（单次续期 6 个月，不自动续） |
| 云函数 | `api-health`（函数 ID `tam-dbzoo3qi`）· Node.js 18.15 · 监听 9000 · 部署成功 |
| 控制台截图 | `docs/day15/day15-console.png` |

已同步写入 `cloudbase/cloudbaserc.json`（`envId` 填真实值，runtime 对齐 Node.js 18.15）。

## 二·补 HTTP 网关域名问题（INVALID_ENV）

云函数部署成功后，访问默认域名仍返回错误，实测三条 URL 结果一致：

```
https://ericamellia24-d2gk0ftukc71292c5.ap-shanghai.app.tcloudbase.com/api/health
https://ericamellia24-d2gk0ftukc71292c5.ap-shanghai.app.tcloudbase.com/
https://ericamellia24-d2gk0ftukc71292c5-1499738190.ap-shanghai.app.tcloudbase.com/api/health
  → HTTP 404，{"code":"INVALID_ENV","message":"Env invalid. ..."}
```

### 排查时间线（2026-10-08）

| 时间 | 动作 / 观察 | 结论 |
|---|---|---|
| 10:04:34 | 控制台「默认域名」Tab 出现域名记录（域名启用=开） | **`-1499738190` 确属默认域名组成部分**，非网关内部编号（此前判断有误，已修正） |
| 10:38 | 外部 curl 三种域名形态 | 全部 404 `INVALID_ENV` |
| 10:40 | 复查控制台：域名已启用、路由表格**为空** | 判定路由未落库 |
| 10:42 | 用户重新添加路由 → 表格出现 `/api/health → api-health`（云函数HTTP、跨域开、身份认证关、路径透传未开） | 路由配置正确、已落库 |
| 10:42:19 | 再测 3 次 | 仍全 404 `INVALID_ENV`，响应头 `server: tcbgw` |
| 10:44:31 | 测 `/`、`/api`、`/health`、`/api/health/` 四个路径 | **全部同一 `INVALID_ENV`** |
| 10:44 | 查看右上角「3 个事项」 | 仅日志未开 / IP 限频建议 / 续期活动——**均非阻断项** |
| 10:44 | 查看云函数详情 | 类型 HTTP 云函数、Node 18.15、状态**正常**、监听 9000——**函数侧无异常** |

### 关键判断

- **不是路径匹配问题**：路径不匹配应返回路由层 404，而不是最外层统一的 `INVALID_ENV`；
  连根路径都回同一错误，说明网关**没有把请求往环境里转**。
- **不是全局开关问题**：控制台可见 HTTP 网关开关为蓝色（已开启）。
- **不是云函数问题**：函数状态正常、端口正确、部署成功。
- **指向**：`INVALID_ENV` 字面定义为「环境 ID 非法 / 不存在 / 已隔离」，
  网关是从域名反解环境 ID 的，当前「域名 → 环境」映射未建立。
  环境创建于 10-08 10:04，映射可能仍在下发窗口期内。

> 降级说明：按 Day 15「卡住降级」条款，公网可访问硬指标已由
> `https://touhou-mock.app.workbuddy.host/api/health` 达成，且与云函数版返回**同构**。

---

## 二·补2　⚠️ 上述判断已被 Day 21 推翻（更正记录）

**Day 21 结清了这笔账。上面「关键判断」里有两处是错的**，此处更正并保留原文作对照：

| Day 15 的判断 | Day 21 的更正 |
|---|---|
| ❌「域名 → 环境」映射未建立 | **错。** 真因是**环境 ID 少写一个 `t`**（`d2gk0fu…` → `d2gk0ftu…`）。修正后 `api.tcloudbasegateway.com` 直接可用 |
| ❌「映射可能仍在下发窗口期内，等着就好」 | **错。** 这不是等待能解决的问题。真正的第二层原因是**函数类型与代码形态不匹配 + 缺 `scf_bootstrap`** |

### Day 21 完整排查链

| 阶段 | 现象 | 判读 |
|---|---|---|
| envId 修正后 | 默认域名仍 404；HTTP API 调用 → `400 FUNCTIONS_PARAM_INVALID` | 网关**已认得环境+函数** |
| 补 `?webfn=true` | 响应头 `x-cloudbase-upstream-status-code: 443`、`timecost: 430ms` | 请求**真进了函数**，上游回 443 = **端口不通** |
| 读控制台截图 | **函数类型 = HTTP 云函数**、**监听端口 = 9000**、描述 Hello World | 铁证 |
| 上传 zip 报错 | `ResourceNotFound.EntryFile ... filename not matched: scf_bootstrap` | **缺启动脚本** |
| 补 `scf_bootstrap` 后 | **200 OK** + 完整 JSON | ✅ 通 |

### 真因（两层）

1. **函数类型 ≠ 代码形态**
   控制台把 `api-health` 登记为「**HTTP 云函数**」（要求跑一个监听 9000 的 Web 服务），
   而 Day 15 的代码是 `exports.main = async (event, context) => {...}` —— 那是「**自定义函数**」的写法，
   **没有任何端口在监听** → 上游 443。

2. **缺 `scf_bootstrap`**
   HTTP 云函数必须有一个**精确命名为 `scf_bootstrap`**（无扩展名）的启动脚本，容器靠它拉起服务。
   Day 15 压根没这个文件，所以部署包永远起不来。

### `scf_bootstrap` 四条硬性要求（都是踩过的坑）

| # | 要求 | 踩坑后果 |
|---|---|---|
| 1 | 文件名精确为 `scf_bootstrap`（无扩展名） | 报 `filename not matched: scf_bootstrap` |
| 2 | **必须 LF 换行符** | CRLF → `exec format error` |
| 3 | 必须可执行权限（`chmod +x`） | 无法执行 |
| 4 | Node 二进制路径必须匹配运行时 | 路径错 → 启动失败 |

本函数（Nodejs18.15）的启动脚本：

```bash
#!/bin/bash
export PORT=9000
cd "$(dirname "$0")"
exec /var/lang/node18/bin/node index.js
```

> Node 运行时路径映射：`Nodejs20.19` → `/var/lang/node20/bin/node`；
> `Nodejs18.15` → `/var/lang/node18/bin/node`；`Nodejs16.13` → `/var/lang/node16/bin/node`。

### 对照：两种云函数的区别（Day 15 混淆的根源）

| | 自定义函数（Event） | **HTTP 云函数**（本项目） |
|---|---|---|
| 入口 | `exports.main(event, context)` | `app.listen(9000)` 的 Web 服务 |
| 是否需要监听端口 | ❌ 不需要 | ✅ **必须监听 9000** |
| 是否需要 `scf_bootstrap` | ❌ 不需要 | ✅ **必须有** |
| 调用方式 | SDK / 定时器 / 事件 | HTTP 请求 |

### 最终验证（Day 21，全部通过）

```
POST https://{envId}.api.tcloudbasegateway.com/v1/functions/api-health?webfn=true
  -H "Authorization: Bearer {API_KEY}" -H "Content-Type: application/json"
  -d '{"path":"/api/health","method":"GET"}'
```

| 请求 | 结果 |
|---|---|
| `GET` | **200** + `ok:true` / `env` 正确 / `node v18.15.0` / `uptimeSec` |
| `POST` | **405** + `method_not_allowed` + `allow: [GET, HEAD]` |
| `HEAD` | **200** + 空 body |

> 注：调用 HTTP 云函数时**必须带 `?webfn=true`**，否则按普通云函数调用，网关回
> `400 FUNCTIONS_PARAM_INVALID`。


## 三、降级说明

按 Day 15「卡住降级」条款：**先保证 /api/health 公网可访问**——已达成（见上表首验结果）。
CloudBase 环境与云函数均已完成，仅 HTTP 网关域名处于生效窗口期，不影响后续 Day 16–20 的接口开发。
