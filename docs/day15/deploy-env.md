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
| `day15-console.png` | 部署环境信息页 `env-info.html`（CloudBase 三项待本人开通后补齐） |

## 二、CloudBase 控制台信息（**待本人注册后补齐**）

Day 15 清单要求截图里出现「环境 ID、剩余额度、到期日期」，这三项只存在于腾讯云
CloudBase 控制台的**环境概览**页。该页面需要本人登录腾讯云账号（手机号 + 实名认证），
无法由他人代注册，因此本轮未取得，按下表补齐：

| 项 | 状态 | 怎么拿 |
|---|---|---|
| 环境 ID | ⬜ 待填 | 按 `cloudbase/README.md` 开通后，环境概览页顶部（形如 `touhou-search-1x2y3z`） |
| 剩余额度 | ⬜ 待填 | 同一页面「资源用量 / 免费额度」区 |
| 到期日期 | ⬜ 待填 | 同一页面「免费资源到期时间」 |

补齐后把三张控制台截图放进 `docs/day15/`，并在 `docs/api-contract.md` 的 §4 把
`env` 示例值换成真实环境 ID。

## 三、降级说明

按 Day 15「卡住降级」条款：**先保证 /api/health 公网可访问**——已达成（见上表首验结果）。
CloudBase 环境注册属于需本人操作的事项，代码与配置已备好（`cloudbase/` 目录），
开通后可一键部署，不影响后续 Day 16–20 的接口开发。
