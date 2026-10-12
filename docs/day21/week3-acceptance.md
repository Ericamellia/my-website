# 第 3 周验收表（Day 15–21）

> 验收日：2026-10-10（Day 21）
> 验收范围：**公网版**（CloudBase 真库）— `https://touhou-mock.app.workbuddy.host/`
> 表格列：**验收项 / 状态 / 证据**
> 状态取值：`PASS`（通过）· `FAIL`（未达成）· `N/A`（本周不含此项）

---

## 一、周验收表

### A. 公网可访问（地基项）

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| A1 | 公网首页可打开（https） | **PASS** | `GET https://touhou-mock.app.workbuddy.host/` → **HTTP 200**（`docs/day21/evidence/week3-verify.txt` 第 1 节） |
| A2 | 云函数公网入口存活 | **PASS** | `GET ...service.tcloudbase.com/api/health` → **HTTP 200**，`ok:true` / `env` 正确 / `uptimeSec` 随时间递增（同上日志第 2 节） |
| A3 | 前端直连云函数不报跨域 | **PASS** | 页面 `#hUrl` 显示公网地址；Day 20 CDP 抓包：该地址 `200`，远端 IP `124.223.146.214` ≠ 本站 IP（`docs/day20/evidence/day20-network-evidence.png`） |
| A4 | 线上资源版本号已升（防缓存） | **PASS** | 线上 HTML 内 `app.js?v=5`、`style.css?v=5` |

### B. 真实读写（地基项）

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| B1 | 真实读：收藏列表 | **PASS** | `GET /api/favorites?limit=20` → **200**，`source:"rest"`，`count:7`（日志第 3 节） |
| B2 | 真实读：热搜列表 | **PASS** | `GET /api/hot?board=fresh&limit=12` → **200**，`source:"rest"`（日志第 3 节） |
| B3 | 真实写：新增收藏 | **PASS** | `POST /api/favorites {workId:"art-2"}` → **HTTP 201**，返回含 `createdAt` 的完整记录（日志第 4 节） |
| B4 | 写入真的落到库里 | **PASS** | 写后读回 `count 7 → 8`，新增行 `#27 art-2`，`source:"rest"`（日志第 4 节） |
| B5 | 数据源是 rest 真库（不是快照） | **PASS** | 全部接口返回体均带 `"source":"rest"`；直连 PostgREST 可读到同一行 |
| B6 | 测试数据清理、恢复基线 | **PASS** | 直连 PostgREST `DELETE id=27` → **200**；复核 `count=7`，`ids=[1..7]`（日志第 5、6 节） |

### C. 第三周核心能力

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| C1 | 云函数 + HTTP 网关的 INVALID_ENV 已修通 | **PASS** | Day 19 commit `ee7a935`；根因 = envId 少一个 `t`（`docs/day21/public-persistence.md`） |
| C2 | 数据访问层已拆分（真库 / 快照双路径可切） | **PASS** | Day 21 commit `6baa46b`；`docs/day21/data-layer-refactor.md` + `data-layer-diagram.svg` |
| C3 | 线上切到 rest 真库通道 | **PASS** | Day 21 commit `41129b2`；B5 的 `source:"rest"` 即其运行结果 |
| C4 | 服务端密钥不进代码/不进提交 | **PASS** | `deploy/.env` 被 `.gitignore` 忽略（`.gitignore` 第 5–6 行 `.env.*` / `*.env`，命令验证 `git check-ignore -v`）；`git status` 无 `.env` |
| C5 | 防重复提交闸门在线有效 | **PASS** | ① 我自测：重复 POST `music-1` → **409 `already_favorited`**（日志第 4 节首段）；② **第三方在页面上实操作**：对已存在的 `doujin-2` 点「发起 POST 写入」→ 返回 **409 · 已收藏过 doujin-2**（`docs/day21/evidence/peer-409-doujin2.png`） |

### D. 第三周交付的一致性

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| D1 | 接口契约与实际行为一致 | **PASS** | `docs/api-contract.md`；本次实测的 200/201/409 与契约 §4 一致 |
| D2 | 文档随代码同步更新 | **PASS** | `docs/day20/cors-troubleshooting.md`、`docs/day21/*.md` 均随对应 commit 提交 |
| D3 | commit 规范（`Day X｜一句话`） | **PASS** | 第 3 周 9 个 commit 全部符合（`git log --oneline`） |

---

## 二、缺项如实标记（FAIL / 未执行）

> 原则：没做到的直接标 FAIL，不粉饰、不模糊处理。

| # | 项目 | 状态 | 说明 |
|---|---|---|---|
| F1 | **`DELETE /api/favorites/:id` 接口未实现** | **FAIL** | 本周只有读+写，没有删。实测 `DELETE /api/favorites/27` → **501 Not Implemented**。起因是 PRD 6.1 砍掉了「收藏管理」，删除未进 MVP。清理测试数据只能直连 PostgREST。**记录到下周**：若需要前端自助取消收藏，须补该接口 + 契约。 |
| F2 | **Day 13 / Day 14 无交付记录** | **FAIL** | `git log` 查无 Day 11–14 的 commit。第 2 周末尾（Day 12 自建 Skill 之后）到 Day 15 之间**无产出记录**。属历史缺项，本表如实记录；无法补做，仅存档。 |
| F3 | **应用层无删除能力 = 无法自助清数据** | **FAIL** | 与 F1 同源。测试写入的数据只能靠 service_role 直连清，普通前端用户做不到。**记录到下周**。 |
| F4 | **本周未做移动端/多浏览器回归** | **FAIL** | PRD N3 要求「375px 移动端不错乱」「Chrome/Edge/Firefox 可用」，第 3 周聚焦后端打通，**未执行**该项回归。**记录到下周**。 |
| F5 | **暗色模式（N5）未做** | **FAIL** | PRD 第 113 行记「非 MVP，Day 21 前完成」——**未完成**。属遗留项。 |
| F6 | **数据扩到百条级、作曲者筛选、同人志题材标签未做** | **FAIL** | PRD 第 159 行「Day 21 收尾」清单，因 Day 21 实际用于验收日，**未执行**。**记录到下周**。 |

---

## 三、小结

| 分类 | PASS | FAIL |
|---|---|---|
| A 公网可访问 | 4 | 0 |
| B 真实读写 | 6 | 0 |
| C 第三周核心能力 | 5 | 0 |
| D 一致性 | 3 | 0 |
| **小计（有证据项）** | **18** | **0** |
| 缺项如实标记 | —— | **6** |

**结论**：本周的两项地基（公网可访问、真实读写）**全部 PASS 且证据可复现**；
核心能力（真库打通、数据层拆分、线上切 rest）**全部 PASS**。
**6 项 FAIL 全部集中于「非本周主线的遗留功能」**（删除接口、历史空缺、移动端回归、暗色模式、数据扩容），
已在第二节逐条记录原因，留待下周处理——**未做即标 FAIL，不以「基本完成」模糊**。
