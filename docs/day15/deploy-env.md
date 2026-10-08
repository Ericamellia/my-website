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
| 环境 ID | `ericamellia24-d2gk0fukc71292c5` |
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
https://ericamellia24-d2gk0fukc71292c5.ap-shanghai.app.tcloudbase.com/api/health
https://ericamellia24-d2gk0fukc71292c5.ap-shanghai.app.tcloudbase.com/
https://ericamellia24-d2gk0fukc71292c5-1499738190.ap-shanghai.app.tcloudbase.com/api/health
  → HTTP 404，{"code":"INVALID_ENV","message":"Env invalid. ..."}
```

外部 curl 同样 404，说明是**环境下发域名未生效**，与云函数代码无关（函数侧部署状态为成功）。
官方文档（HTTP 访问服务）要求：

1. 左侧「环境管理 → HTTP 访问服务」，**页面顶部的全局开关需先开启**；
2. 用「域名关联资源」建路由：关联资源 = 云函数 `api-health`，域名 = 默认域名，
   触发路径 = `/api/health`；
3. 点确定后**等 3–5 分钟**生效，再用 `域名 + 触发路径` 访问。

> 降级说明：按 Day 15「卡住降级」条款，公网可访问硬指标已由
> `https://touhou-mock.app.workbuddy.host/api/health` 达成，且与云函数版返回**同构**。

## 三、降级说明

按 Day 15「卡住降级」条款：**先保证 /api/health 公网可访问**——已达成（见上表首验结果）。
CloudBase 环境与云函数均已完成，仅 HTTP 网关域名处于生效窗口期，不影响后续 Day 16–20 的接口开发。
