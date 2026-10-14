# Day 28｜结营日：交付 28 天作品 v1.0

> 日期：2026-10-14
> 今日要掌握：**28 天里你最大的一个认知改变是什么？**
> 板块顺序：① 验收官检测 ② 核心流程重复检测 ③ 交付清单清点 ④ 结营复盘

---

## 0. 今日概览

| 项 | 结果 |
|---|---|
| 验收范围 | **全部按公网验收**（用户选择） |
| 验收清单 | 自拟等效清单（原任务书的「附录 J」在本项目不存在） |
| 有证据项 | **24 PASS · 1 PARTIAL · 0 FAIL** |
| 核心流程重复检测 | **13/13 观测点两遍完全一致**（幂等） |
| 交付清单 | 24 项有 · 1 项待发布 · 2 项有缺口 |
| 复盘 | 已完成（`retro.md`） |
| 交付截图 | 两张（验收清单打勾 + 公网作品 URL 含地址栏） |
| 余力加练 | 新增 `acceptance-check` 一键验收体检 Skill |
| **挖出的关键问题** | **F1：前端收藏 UI 与云端真库是两套数据**（网络抓包铁证） |

---

## 1. 关于「附录 J」

任务清单要求「附录 J 清单逐项能当场打开或展示」。核查结果：

- 全仓库检索 `附录 J` → **0 结果**
- 历史对话检索 → **查不到**
- 问用户 → 回答「**那是什么**」

**结论**：本项目没有名为「附录 J」的文件，判断为任务书模板的通用编号。
因此**由我按项目现状拟一份等效验收清单**（`docs/day28/acceptance.md`），
覆盖公网可访问 / 真实读写持久化 / 接口契约 / Skill / 核心流程 / 缺项标记六个维度，
并按用户选择**全部按公网验收**。

---

## 2. 板块① 验收官检测

主文档：`docs/day28/acceptance.md`

### 2.1 A 类 · 公网可访问（5/5 PASS）

| 项 | 结果 |
|---|---|
| 首页 | HTTP 200，9145 字节 |
| 静态资源 | `style.css` 200（57186B）、`app.js` 200（127325B） |
| `/api/health` | `ok:true`，`checks.dataSource: "rest"` |
| 六个业务接口 | health / hot / favorites / works / circles / originals **全部 200** |

### 2.2 B 类 · 真实读写 + 持久化（8/8 PASS）

用 `evidence/accept_probe.py` 自动跑，**验完自动清理**：

| 步骤 | 结果 |
|---|---|
| 读基线 | `count=7`，`source=rest` |
| 写入 | `POST` → **201**，新行 `id=87`，真实 `createdAt` |
| 写后读 | `count 7 → 8`，新行在列表首位 |
| **持久化复核** | 间隔 6 秒独立读取，`count` 仍为 8，**行内容一致** |
| 数据源 | 4 个接口 `source` **全部** `"rest"`，无兜底 |
| 防重复 | 重复 POST → **409**「你已经收藏过 art-2 了」 |
| 清理 | `DELETE` → 200，`count` 回到 7，id 列表与基线一致 |
| Day 27 修复项 | `/api/works` 中 `"circle": "COOL&CREATE"` 有值 |

### 2.3 C 类 · 接口契约与错误处理（6 PASS / 1 PARTIAL）

| 项 | 结果 |
|---|---|
| `PATCH /api/favorites` | 405 |
| `/api/nonexistent-xyz` | 501 `not_implemented` |
| `POST {}` | 400 `missing_work_id` + 中文提示 |
| `POST {"workId":"!!!bad!!!"}` | 400 `invalid_work_id_format` + 中文提示 |
| 错误不漏内部细节 | 3 条路径扫描堆栈/连接串 → **命中 0** |
| `DELETE` 不存在的 id | 404 `favorite_not_found`（幂等） |
| **`405` 是否带 `Allow` 响应头** | **PARTIAL** —— allow 在 JSON body 里，未写入响应头 |

**关于 C7**：RFC 7231 §6.5.5 要求 405 应带 `Allow` 头。当前实现在 body 里给
`{"allow":["GET","HEAD","POST"]}`，**前端读得到，功能无影响**。
如实记为 PARTIAL，不夸大也不忽略。

### 2.4 D 类 · Skill 可用性（4/4 PASS）

| Skill | 结果 |
|---|---|
| `preflight-check` | 独立执行 → 7 项全过，退出码 0 |
| （同上）不是「永远通过」的摆设 | Day 25 已验证：注入假密钥 → 报 FAIL；移除后全绿 |
| `filter-interaction-check` | 三态全过（有结果 7 / 无结果 0 且有提示 / 清空回 `#/`） |
| 用法文档化 | README 有专节 |

---

## 3. 板块② 核心流程重复检测

用 CDP 驱动真实浏览器，**同一流程跑两遍**，对比 13 个观测点。

**流程**：首页 → 切板块 → 点卡片进详情页 → 点收藏 → 回收藏页

```
---- 第 1 遍 ----                    ---- 第 2 遍 ----
首页卡片数      = 6                   首页卡片数      = 6      ✅
music 卡片数    = 6                   music 卡片数    = 6      ✅
详情页标题      = ハルトマンの妖怪少女   详情页标题      = 同左    ✅
详情页有收藏按钮 = true                 详情页有收藏按钮 = true   ✅
收藏后按钮态    = ...is-faved          收藏后按钮态    = ...is-faved ✅
收藏页条目数    = 1                    收藏页条目数    = 1      ✅
收藏页标题计数  = 我的收藏 (1)          收藏页标题计数  = 我的收藏 (1) ✅
收藏页星标数    = 1                    收藏页星标数    = 1      ✅

两遍不一致项：0  →  PASS（幂等）
```

**结论**：核心流程可稳定复现，**无随机性、无状态残留**。

### 3.1 ★ 调试过程：三次「看起来是 bug」，三次都不是

这一轮排错本身比结论更有价值，如实记录：

| # | 现象 | 一开始的判断 | 真相 |
|---|---|---|---|
| 1 | 第 2 遍点收藏后收藏页变 0 条 | 疑似收藏功能有 bug | **我的脚本缺陷**：清了 `localStorage` 但没重置 app.js **内存变量 `favs`** → 第 2 遍点的其实是「取消收藏」 |
| 2 | 搜索「清空恢复」后 visible=0 | 疑似清空不生效 | **我的检测逻辑错**：搜索会跳 `#/search/xxx` 路由，清空后回到 `#/`（首页），首页本就没有 `.work-item` |
| 3 | 收藏页「1 条却渲染 2 张卡」 | 疑似重复计数 | **正常设计**：收藏页有 6 个面板（全部 + 5 分类），同一张卡在多个面板各渲染一次；标题计数 `我的收藏 (1)` 是正确的 |
| 4 | 搜索无结果时 `#no-result` 没显示 | 疑似空状态缺失 | **找错了元素**：搜索页用的是 `.search-empty`（主题文案「你想要的知识或许在幻想乡境界之外哦」），只有列表页用 `#no-result` |

**修法**：把检测逻辑从「绑死某个选择器」改成「按概念判定」——
比如「无结果时屏幕上有没有可见提示文案」，而不是「`#no-result` 是否显示」。

**但第 5 个不是虚惊，是真问题**（见 §3.2）。

### 3.2 ★★ F1：前端收藏 UI 与云端真库是两套数据（真实发现）

**现象**：点「收藏」按钮，真库计数不变。

**验证方式**（带对照组的网络抓包，`evidence/net_proof.py`）：

| 组 | 操作 | `/api/favorites` 写请求数 |
|---|---|---|
| **测试组** | 点击 `.detail-cta-fav` | **0** |
| **对照组** | 手动 `fetch('/api/favorites?limit=1')` | **1**（证明抓包没失灵） |

**根因**（读代码确认）：

```js
// app.js:426-433
try { favs = JSON.parse(localStorage.getItem('touhou_favs') || '[]'); } catch (e) {}
const saveFavs = () => { localStorage.setItem('touhou_favs', JSON.stringify(favs)); };
const isFav = (module, id) => favs.some(f => f.module === module && f.id === id);
// app.js:444-465 点击事件：只做 toggleFav() + classList.toggle()，没有任何 fetch
// app.js:1743 收藏页：favs.map(...) —— 读的也是本地 favs
```

→ **全链路零网络请求。** 而 Day 17–22 实现的 `/api/favorites` 增删改查
（POST 201 / 409、PATCH、DELETE 200/404）**在 B 类验收里全部实测通过** ——
**接口没问题，是前端没接上。**

**影响**：换浏览器 / 清缓存 → 收藏全丢；多设备不同步；
写进真库的数据页面上永远看不到。

**处理**：按用户决定 —— **今日只如实记录，不改**（任务清单明确「今日不做影响最终验收的新功能」）。
已单独建 `docs/day28/todo-f1-fav-decouple.md`，写清根因、影响面、三步修复思路与验收标准。

---

## 4. 板块③ 交付清单清点

主文档：`docs/day28/delivery-checklist.md`

| 类别 | 状况 |
|---|---|
| 代码与运行物 | 7 / 7 有（前端 + 服务端 + 三通道数据层 + DB 脚本 + 兜底数据） |
| 文档 | 10 / 10 有（PRD / TECH_DESIGN / RUN / AGENTS / README / research + api-contract / rollback + 21 份日文档） |
| Skill | 3 / 3 有（preflight-check / filter-interaction-check / **acceptance-check 今日新增**） |
| 线上交付 | 2 / 3 —— **Day 28 移动端改造待发布** |
| Git 交付 | 48 个提交，规范 `Day X｜一句话`；**缺 Day 11 / 13 / 14**（历史缺口，如实保留） |
| 证据文件 | `docs/**/evidence/` 共 **2992** 个 |

---

## 5. 板块④ 结营复盘

主文档：`docs/day28/retro.md`

**用户给出的答案**：**「真心觉得 AI 能力比我以前想象中强多了」**

复盘围绕这条展开，用 28 天里**真实发生过的四个瞬间**支撑：

1. **Day 27 社团名 Bug** —— 列名是 `circle` 不是 `circle_name`，
   而且**写不存在的列名反而能读到真值、改成"正确的"列名会导致 502**。这种反直觉的坑靠猜一定会踩。
2. **Day 28 两次识破「截图骗人」** —— 搜索框"消失"、顶栏"跑到文档中部"，
   两次都先量 DOM / 像素数据再动手。**沉淀成规则：DOM 数据是硬证据，截图是软证据。**
3. **Day 25 给自己的工具做反向验证** —— 故意注入假密钥，验证 `preflight-check` 会报红，
   而不是个「永远说通过」的摆设。
4. **Day 22 主动想到「删错了怎么办」** —— 把 DELETE 改成软删除，用户没要求。

**复盘的核心结论**：

> 28 天前我以为 AI 是个更快的键盘；28 天后我发现它是个**会自己找证据、会推翻自己、
> 会沉淀经验的搭档** —— 前提是我把「什么算做对了」说清楚。

也如实写了**人的那一半不可替代**：验收标准得人来定（附录 J 这事就是例子）、
方向得人来给（「顶栏大一点、参考 B 站」这种取舍 AI 猜不出来）、它需要被规则卡住（AGENTS.md）。

---

## 6. 交付截图

| 文件 | 内容 |
|---|---|
| `evidence/day28-截图1-验收清单逐项打勾.png` | 五类清单逐项打勾（绿勾 / 黄圈 / 红叉三态清楚）+ 底部汇总 |
| `evidence/day28-截图2-公网作品URL.png` | **含地址栏** `https://touhou-mock.app.workbuddy.host` + 完整首页（顶栏 / 搜索框 / 分类卡片） |
| `evidence/day28-截图2b-公网作品-板块页.png` | 地址栏 `.../#/music` + 「同人音乐」板块 + 排序控件 |

### 6.1 ★ 截图技术踩坑（都值得记下来）

**坑 1：CDP 截图拍不到地址栏**

`Page.captureScreenshot` 只能截**网页内容**，浏览器 UI（地址栏、标签栏）不在内。
→ **改用 Windows `PrintWindow` 系统级窗口截图**（`ctypes` 调 `user32.PrintWindow` + `PW_RENDERFULLCONTENT`）。

**坑 2：PrintWindow 抓到「有地址栏但内容空白」**

原因是 Edge 默认**硬件加速**，GPU 合成的内容不在 GDI 表面上。
→ **加 `--disable-gpu --disable-gpu-compositing --disable-software-rasterizer --in-process-gpu`**
让页面走软件渲染。文件从 23KB 变成 **485KB**，内容就出来了。

**坑 3：按 PID 找不到浏览器窗口**

Edge 是多进程架构，`Popen` 起的是浏览器主进程，但窗口可能挂在别的进程上
→ `EnumWindows` 按 pid 匹配**全军覆没**。
→ **改为按窗口标题关键词 + 类名（`Chrome_WidgetWin_1`）查找**。

**坑 4：`--window-size` 参数会让启动失败**

截图脚本一开始带了 `--window-size=1240,1500`，浏览器起不来也不报错。
→ 去掉后正常。**报错信息缺失时，用「二分法砍参数」定位。**

**坑 5：GDI 调用可能让 Python 进程直接崩溃**

`PrintWindow` 出错时进程会静默死掉，`finally` 里的日志一个都写不出来。
→ **改成增量写日志**（每步 `append` 落盘），崩溃后仍能看到最后到哪一步。

---

## 7. 余力加练：`acceptance-check` 一键验收体检 Skill（今日新增）

把今天人肉跑的 A~E 五类验收**打包成一个脚本**，下次改完代码一条命令复验。

**五类检查**：

| 类 | 内容 |
|---|---|
| A | 公网首页 / 静态资源 / health / 六接口 200；数据源是 `rest` |
| B | 读基线 → 写入 201 → 计数 +1 → **间隔 4 秒复读（持久化）** → 409 → 清理 |
| C | 405 / 501 / 400×2 / 错误不漏细节 / DELETE 幂等 / 405 是否带 `Allow` |
| D | 10 个交付物是否齐全 |
| E | **本地与线上的 `app.js?v=N` 是否一致**（抓「推了但没部署」） |

**首跑结果**：**32 PASS · 0 FAIL · 2 WARN**，退出码 0。

两个 WARN 都是真实且应该存在的：
- C7（405 未带 Allow 头，规范瑕疵）
- E（线上版本落后 v99 vs v97，未部署）

### 7.1 ★ 写这个脚本时自己踩的坑（已修）

第一版我写了**两次 POST**（一次取 body、一次取状态码），**两次都写成功了**，
但清理时只删掉第一条 → **真库残留一条脏数据（`id=87`）**。

**修法两条**：
1. **只发一次请求** —— 用 `curl -w $'\n__CODE__%{http_code}'` 同时拿回 body 和状态码
2. **加 `trap cleanup EXIT INT TERM` 兜底** —— 任何退出路径（含报错、Ctrl+C）都会删掉自己写的数据

> 这个坑很典型：**「验证别人的东西」比「写功能」更容易出脏数据**，
> 因为验证脚本本身也需要被验证。已写进 `SKILL.md`。

---

## 8. 完成标准自检

| 标准 | 状态 | 说明 |
|---|---|---|
| 附录 J 清单逐项能当场打开或展示 | **PASS（等效）** | 附录 J 不存在 → 自拟等效清单，逐项实测，全部有证据 |
| 验收官检测通过 | **PASS** | 24 PASS / 1 PARTIAL / 0 FAIL；地基项全过 |
| 复盘写完 | **PASS** | `retro.md` 六节，含用户答案 + 4 个真实锚点 |

### 今日不做项遵循情况

| 约束 | 遵循 |
|---|---|
| 「今日不做：任何影响最终验收的新功能」 | ✅ 余力加练只加了**独立脚本**（`acceptance-check`），不碰前端/后端逻辑 |
| 「F1 只如实记录，不改」 | ✅ 已建独立待办文档，未改一行业务代码 |

---

## 9. 缺项如实标记（F 类）

| # | 项目 | 状态 | 说明 |
|---|---|---|---|
| F1 | 前端收藏 UI 与真库两套数据 | **FAIL** | 见 §3.2，已建待办 |
| F2 | Day 11 / 13 / 14 无提交记录 | **FAIL** | 历史缺口，无法补做 |
| F3 | M1 移动端悬浮按钮遮挡卡片 | **FAIL** | Day 27 暴露，未修 |
| F4 | M2 移动端页脚文字重叠 | **FAIL** | Day 27 暴露，未修 |
| F5 | C7 405 未带 `Allow` 响应头 | **PARTIAL** | 功能无影响 |
| F6 | 暗色模式（PRD N5）未做 | **FAIL** | 非 MVP，记录在案 |
| F7 | 数据扩容 / 作曲者筛选 / 题材标签未做 | **FAIL** | PRD「Day 21 收尾」清单，未执行 |
| F8 | 真正的第三方真人试用未做 | **FAIL** | Day 27 是 AI 代跑降级方案 |
| F9 | Day 28 移动端改造未发布 | **FAIL（待补）** | 用户明确「之后再发布」 |

---

## 10. 改动文件清单

> 详见文末提交说明。原则：**不改业务代码**，只加验收产物、文档与独立 Skill。

| 文件 | 说明 | 属哪天 |
|---|---|---|
| `docs/day28/acceptance.md` | **新建** 结营验收清单（六类，含 F 类缺项） | Day 28 |
| `docs/day28/delivery-checklist.md` | **新建** 交付清单清点 | Day 28 |
| `docs/day28/retro.md` | **新建** 结营复盘 | Day 28 |
| `docs/day28/todo-f1-fav-decouple.md` | **新建** F1 待办（根因 + 修复思路） | Day 28 |
| `docs/day28/day28.md` | **新建** 本文档 | Day 28 |
| `docs/day28/evidence/accept_probe.py` + `_log.txt` | **新建** B 类验收探针 | Day 28 |
| `docs/day28/evidence/flow_double_check.py` + `_log.txt` | **新建** D1/E 类：搜索三态 + 核心流程两遍对比 | Day 28 |
| `docs/day28/evidence/net_proof.py` + `_log.txt` | **新建** F1 铁证（带对照组的抓包） | Day 28 |
| `docs/day28/evidence/diag_fav.py` + `_log.txt` | **新建** F1 诊断 | Day 28 |
| `docs/day28/evidence/diag_flow.py` + `_log.txt` | **新建** 流程逐步骤快照 | Day 28 |
| `docs/day28/evidence/diag_empty.py` + `_log.txt` | **新建** 空状态实现核查 | Day 28 |
| `docs/day28/evidence/shot1.py` / `shot2.py` | **新建** 截图脚本 | Day 28 |
| `docs/day28/evidence/acceptance-report.html` | **新建** 验收清单可视化报告 | Day 28 |
| `docs/day28/evidence/day28-截图1-*.png` | **新建** 交付截图 1 | Day 28 |
| `docs/day28/evidence/day28-截图2-*.png` | **新建** 交付截图 2（含地址栏） | Day 28 |
| `docs/day28/evidence/day28-截图2b-*.png` | **新建** 交付截图 2b（板块页） | Day 28 |
| `skills/acceptance-check/check.sh` | **新建** 余力加练：一键验收体检 | Day 28 |
| `skills/acceptance-check/SKILL.md` | **新建** 同上文档 | Day 28 |
| `skills/acceptance-check/RUN_LOG.txt` | **新建** 实跑日志（32 PASS / 0 FAIL） | Day 28 |
| `README.md` | **改** 加 `acceptance-check` 专节 | Day 28 |
| `skills/preflight-check/check.sh` | **改** 修两个毛病：④ 加 3 次重试（防瞬时抖动假失败）；⑥ 路径从 `my-app/` 修正到 `deploy/public/`（原来一直是瞎的） | Day 28 |
| `skills/preflight-check/RUN_LOG.md` | **改** 追加第 2 次调用记录（含上述两个修复） | Day 28 |

**未改动的部分**：`deploy/public/*`（前端）、`deploy/server.js`（后端）、
`deploy/db/*`（数据层）—— 一行业务代码都没动。

---

## 11. 顺手修的两个 bug（`preflight-check`）

跑发布前检查时，它自己暴露了两个问题 —— **正好印证了「工具也需要被验证」**：

**bug 1：单次网络抖动被判成 FAIL（假失败）**

首跑报 `④ 公网 /api/health HTTP 000000（期望 200）`，
但**手动连续复测 3 次都是 200** —— 是瞬时抖动。
根因：单次探测、无重试。

→ 新增 `http_code_retry()`，每接口**最多试 3 次**（间隔 2 秒），
只有连续失败才判 FAIL。

> **教训：不带重试的网络检查 = 会误报的检查 = 迟早被无视。**

**bug 2：⑥ 版本号检查一直是「瞎的」**

第 140 行读的是 `my-app/index.html`，但本项目前端实际在 `deploy/public/index.html`。
路径写错 → 取值永远是空 → **这个检查从 Day 25 写下起就没真正生效过**。

→ 改为按优先级 `deploy/public/index.html` → `my-app/index.html` → `index.html` 查找，
并打印「检查文件：xxx」；取不到值改成明确 FAIL（而不是静默通过）。

**修复后**：`preflight-check` **7 项全过，退出码 0**。

