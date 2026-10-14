# Day 28 验收清单（结营）

> 验收日：2026-10-14（Day 28）
> 验收范围：**全部按公网验收**（用户 Day 28 明确选择）
> 公网地址：`https://touhou-mock.app.workbuddy.host/`
> 表格列：**验收项 / 状态 / 证据**
> 状态取值：`PASS`（通过）· `PARTIAL`（部分达成，注明缺口）· `FAIL`（未达成）

---

## 关于「附录 J」的说明

任务清单要求「附录 J 清单逐项能当场打开或展示」。经核查：

- 全仓库检索 `附录 J` / `Appendix J` → **无任何结果**
- 历史对话检索 → **查不到该清单内容**
- 用户回答：**「那是什么」**

**结论**：本项目**不存在**名为「附录 J」的文件。判断为任务书模板中的通用编号，
与本项目无对应关系。因此**由我按项目现状拟定一份等效验收清单**（即本文档），
覆盖结营应验的全部维度，并按用户选择**全部按公网验收**。

---

## 一、A 类 · 公网可访问（地基项）

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| A1 | 公网首页可打开（https） | **PASS** | `GET /` → **HTTP 200**，9145 字节（`accept_probe_log.txt` 同批 curl） |
| A2 | 静态资源全部可加载 | **PASS** | `GET /style.css` → 200（57186B）；`GET /app.js` → 200（127325B） |
| A3 | 健康接口存活 | **PASS** | `GET /api/health` → 200，`ok:true` / `service:touhou-search` / `uptimeSec` 随时间递增 |
| A4 | 数据源通道正确 | **PASS** | health 返回 `checks.dataSource: "rest"`（真库通道，非快照兜底） |
| A5 | 六个业务接口全部可达 | **PASS** | `/api/health`、`/api/hot`、`/api/favorites`、`/api/works`、`/api/circles`、`/api/originals` 均 **200** |

---

## 二、B 类 · 真实读写 + 持久化（地基项）

> 全部打真库，用 `docs/day28/evidence/accept_probe.py` 自动跑，验完自动清理。

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| B1 | 真实读：收藏列表 | **PASS** | `GET /api/favorites?limit=50` → 200，`source:"rest"`，`count:7` |
| B2 | 真实写：新增收藏 | **PASS** | `POST /api/favorites {workId:"art-2"}` → **HTTP 201**，返回完整记录 `id:87` + 真实 `createdAt` |
| B3 | 写入真的落库（计数 +1） | **PASS** | 写后读回 `count 7 → 8`，新行 `id 87` 出现在列表首位 |
| B4 | **刷新后持久化**（跨请求、跨时间） | **PASS** | 间隔 6 秒独立读取，`count` 仍为 8，新行内容完整（`workId=art-2` / `note` / `createdAt` 一致） |
| B5 | 数据源确为 rest 真库 | **PASS** | 4 个接口的 `source` 字段**全部**为 `"rest"`，无一条走 snapshot 兜底 |
| B6 | 防重复提交闸门 | **PASS** | 重复 POST 同一条 → **HTTP 409**，中文提示「你已经收藏过 art-2 了，不用重复提交」 |
| B7 | 测试数据清理、恢复基线 | **PASS** | `DELETE /api/favorites/87` → 200，复核 `count=7`、`id=[7,6,5,4,3,2,1]` 与基线完全一致 |
| B8 | Day 27 修复项在公网生效 | **PASS** | `/api/works` 响应中 `"circle": "COOL&CREATE"` 有值（修复前为全空） |

**小计：8/8 PASS**

---

## 三、C 类 · 接口契约与错误处理

> 对照 `docs/api-contract.md`，逐项实测边界行为。

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| C1 | 方法不匹配 → 405 | **PASS** | `PATCH /api/favorites` → **405**，body 含 `allow:["GET","HEAD","POST"]` |
| C2 | 不存在的路径 → 501 | **PASS** | `GET /api/nonexistent` → **501**，`{"error":"not_implemented"}`（契约定义如此） |
| C3 | 缺必填字段 → 400 + 中文提示 | **PASS** | `POST {}` → **400**，`missing_work_id`，「缺少必填字段 workId（要收藏的作品编号，例如 music-1）」 |
| C4 | 格式非法 → 400 + 中文提示 | **PASS** | `POST {"workId":"not-exist-999"}` → **400**，`invalid_work_id_format`，提示正确格式 |
| C5 | 错误响应不漏内部细节 | **PASS** | 3 条错误路径扫描堆栈 / 连接串 / 密码特征 → **命中 0** |
| C6 | DELETE 幂等（删不存在的 id） | **PASS** | `DELETE /api/favorites/999999` → **404**，`favorite_not_found`，不抛异常 |
| C7 | 405 响应带 `Allow` 头 | **PARTIAL** | `allow` 信息**在 JSON body 中**，但**未写入 HTTP 响应头**。RFC 7231 §6.5.5 要求 405 应带 `Allow` 头。**不影响任何功能**（前端读 body 即可），属规范细节瑕疵，如实记录 |

**小计：6 PASS / 1 PARTIAL**

---

## 四、D 类 · Skill 可用性

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| D1 | `preflight-check` 能跑出结果 | **PASS** | 独立执行 → **7 项全过、失败 0 项、退出码 0** |
| D2 | `preflight-check` 不是「永远通过」的摆设 | **PASS** | 已在 Day 25 验证：注入假密钥 → ① 从 PASS 变 FAIL 并打印命中行；移除后恢复全绿（`skills/preflight-check/RUN_LOG.md`） |
| D3 | `filter-interaction-check` 三态可用 | **PASS** | 有结果 `visible=7` / 无结果 `visible=0` 且提示文案可见 / 清空后回 `#/`（`flow_double_check_log.txt`） |
| D4 | 两个 Skill 用法已写进 README | **PASS** | `README.md` §「可复用 Skill」，含用法、退出码、检查项表、为什么值得跑 |

**小计：4/4 PASS**

---

## 五、E 类 · 核心流程（重复检测）

> 用 CDP 驱动真实浏览器，同一流程跑 **两遍**，对比 13 个观测点是否完全一致（幂等性）。

**流程**：首页 → 切板块 → 点卡片进详情页 → 点收藏 → 回收藏页查看

| 观测点 | 第 1 遍 | 第 2 遍 | 一致 |
|---|---|---|---|
| 首页加载 | ok | ok | ✅ |
| 首页卡片数 | 6 | 6 | ✅ |
| 切到 music 板块 | ok | ok | ✅ |
| music 卡片数 | 6 | 6 | ✅ |
| 进详情页 music/1 | ok | ok | ✅ |
| 详情页标题 | ハルトマンの妖怪少女 | 同左 | ✅ |
| 详情页有收藏按钮 | true | true | ✅ |
| 点收藏 | clicked | clicked | ✅ |
| 收藏后按钮态 | `...is-faved` | `...is-faved` | ✅ |
| 回收藏页 | ok | ok | ✅ |
| 收藏页条目数（全部面板） | 1 | 1 | ✅ |
| 收藏页标题计数 | 我的收藏 (1) | 我的收藏 (1) | ✅ |
| 收藏页星标数（全部面板） | 1 | 1 | ✅ |

**结论：13/13 观测点两遍完全一致 → PASS（幂等）**

---

## 六、F 类 · 缺项如实标记

> 原则：**没做到的直接标 FAIL/PARTIAL，不粉饰、不模糊处理。**

| # | 项目 | 状态 | 说明 |
|---|---|---|---|
| F1 | **前端「我的收藏」与云端真库是两套数据** | **FAIL** | **本次验收最重要的发现**。页面上的收藏按钮（`.detail-cta-fav`）读写的是浏览器 `localStorage['touhou_favs']`，**全程不发任何 HTTP 请求**。网络抓包铁证：点击期间请求数 **0**；对照组手动 `fetch('/api/favorites')` 能抓到 **1** 个请求 → 排除抓包失灵。而「我的收藏」页（`renderFavs`）读的同样是本地 `favs`。**结论：Day 17–22 实现的 `/api/favorites` 增删改查（POST/PATCH/DELETE），页面收藏 UI 完全没有接入**；B 类验收中写入真库的照片，页面上永远看不到。证据：`net_proof_log.txt`、`diag_fav_log.txt` |
| F2 | **Day 11 / 13 / 14 无提交记录** | **FAIL** | `git log` 中 Day 1–10、12、15–28 均有提交，**缺 Day 11、13、14**。属历史缺项（Day 21 验收表 F2 已记录过一次），无法补做，如实存档 |
| F3 | **M1：移动端右下角悬浮按钮遮挡卡片内容** | **FAIL** | Day 27 手机流程实测暴露（`docs/day27/evidence/mobile-*.png`），至今未修 |
| F4 | **M2：移动端页脚文字重叠** | **FAIL** | 同上，Day 27 暴露，未修 |
| F5 | **C7：405 未带 `Allow` 响应头** | **PARTIAL** | 见 C7，功能无影响，属规范瑕疵 |
| F6 | **暗色模式（PRD N5）未做** | **FAIL** | PRD 记为「非 MVP，Day 21 前完成」—— 未完成，Day 21 已记，延续至今 |
| F7 | **数据扩到百条级 / 作曲者筛选 / 同人志题材标签未做** | **FAIL** | PRD 第 159 行「Day 21 收尾」清单，Day 21 用于验收日未执行，延续至今 |
| F8 | **真正的第三方真人试用未做** | **FAIL** | Day 27 是 **AI 代跑降级方案**（已在 `docs/day27/day27.md` 如实说明）。真人试用至今未完成 |
| F9 | **Day 28 移动端改造尚未发布到公网** | **FAIL（待补）** | 线上 `style.css?v=109` / `app.js?v=97`；本地已是 `v114` / `v99`。Day 28 的顶栏压缩 + 划页切换 + B站风格调优**未上线**。用户 Day 28 明确表示「之后再发布」，故此项按计划暂缓，**发布后应补回验** |

---

## 七、小结

| 分类 | PASS | PARTIAL | FAIL |
|---|---|---|---|
| A 公网可访问 | 5 | 0 | 0 |
| B 真实读写 + 持久化 | 8 | 0 | 0 |
| C 接口契约与错误处理 | 6 | 1 | 0 |
| D Skill 可用性 | 4 | 0 | 0 |
| E 核心流程（重复检测） | 1（13/13 观测点） | 0 | 0 |
| **小计（有证据项）** | **24** | **1** | **0** |
| F 缺项如实标记 | —— | —— | **9**（含 1 项 C7 已计入 PARTIAL） |

**结论**：

- **两项地基（公网可访问、真实读写持久化）全部 PASS，证据可复现、数据验完即清理。**
- **核心流程两遍完全一致，无随机性、无状态残留。**
- **两个自建 Skill 都能真跑出结果，且 `preflight-check` 经验证会「报红」而非虚报通过。**
- **7 项 FAIL 中，最重要的是 F1（前端收藏 UI 与真库脱钩）** —— 这是本次验收挖出的**架构层不一致**，
  不是小 bug。其余为历史缺项（F2）、移动端遗留（F3/F4）、未做需求（F6/F7/F8）、待发布（F9）。
- **未做即标 FAIL，不以「基本完成」模糊。**

---

## 附：验收用脚本与日志

| 文件 | 用途 |
|---|---|
| `evidence/accept_probe.py` + `accept_probe_log.txt` | B 类：真实读写 + 持久化（7 项） |
| `evidence/flow_double_check.py` + `flow_double_check_log.txt` | D1/D3 搜索三态 + E 类核心流程两遍对比 |
| `evidence/net_proof.py` + `net_proof_log.txt` | **F1 铁证**：点击收藏期间的网络请求抓包（含对照组） |
| `evidence/diag_fav.py` + `diag_fav_log.txt` | F1 诊断：点击前后真库 count 与按钮状态对照 |
| `evidence/diag_flow.py` + `diag_flow_log.txt` | 核心流程逐步骤的真实 URL / DOM 快照 |
| `evidence/diag_empty.py` + `diag_empty_log.txt` | 空状态实现核查（`.search-empty` vs `#no-result`） |
