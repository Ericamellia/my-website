# Day 26｜正式发布 v1.0 + 完成一次真实回滚演练

> 第 4 周 · 2026-10-13
> **今天要掌握：回滚演练花了多久？真出事你敢不敢用这套流程？**

---

## 一、今日板块与完成情况

| 板块 | 内容 | 状态 |
|---|---|---|
| ① | 确认可回退历史 | ✅ 完成 |
| ② | 发布 v1.0 | ✅ 完成 |
| ③ | 静态托管回退演练 | ✅ 完成 |
| ④ | 恢复 v1.0 | ✅ 完成 |
| 余力 | 回滚手册加「什么情况必须回滚」判断表 | ✅ 完成（`docs/rollback.md` §1） |

**结论先行**：**纯回退 53 秒；线上坏掉到线上恢复 59 秒。这套流程敢用。**

---

## 二、板块①：确认可回退历史

### 2.1 打锚点

回退的前提是有锚点。发布前先打**附注 tag**：

```bash
git tag -a v1.0 -m "v1.0：首次正式发布 —— 三通道数据源 + 发布前检查 Skill"
git push origin v1.0
```

| 项 | 值 |
|---|---|
| 标签 | `v1.0`（附注标签） |
| 指向 | `ab82075` Day 25｜发布前检查 Skill |
| 已推送 | ✅ `git push origin v1.0` |

**为什么要用附注 tag（`-a`）而不是轻量 tag**：附注 tag 是 git 对象，带作者、日期、说明，`git show v1.0` 能看到完整信息。回滚锚点是有意义的里程碑，值得记录「为什么打这个点」。

**坑**：`git push` **默认不推 tag**，必须 `git push origin v1.0` 单独推一次。

### 2.2 确认可回退历史

```bash
$ git log --oneline -6
ab82075 Day 25｜发布前检查 Skill：故意注入假密钥验证它不虚报通过
46fb7b2 Day 24｜修重复收藏把作品名弄丢的 Bug
40578e0 Day 23｜余力加练：请求日志 + 回补降级通道写操作验证
e4800b5 Day 23｜密钥排查清零 + 三类错误都改说人话
c6d4353 chore｜.gitignore 忽略 __pycache__，移除误提交的 .pyc
ff047c3 Day 22｜余力加练补：软删除 HTTP 端到端验证 19/19
```

**可回退历史 = 15+ 条提交**，任意一条都可以作为回退目标。

### 2.3 确认发布形态

| 项 | 值 | 含义 |
|---|---|---|
| 发布目录 | `deploy/`（240 文件，17MB） | 回退只需恢复这个目录 |
| 发布方式 | WorkBuddy sites（`workbuddy_sites_deploy`） | **链接固定，重新发布 = 覆盖** |
| 线上链接 | `https://touhou-mock.app.workbuddy.host/` | 回退前后链接不变 |

**关键认知**：因为发布链接固定，「回退」不需要新建站点 —— 只要把本地目录恢复成旧版本再重新发布，链接自动指向旧版本。**这就是静态托管回退的全部本质。**

---

## 三、板块②：发布 v1.0

### 3.1 发布前检查（发现并修复了一个真问题）

跑 `preflight-check`，**① 密钥泄漏项报失败，命中 8 行**。

排查结果：这 8 行**全部是 Day 25 我自己留下的污染** —— 写文档/脚本/SKILL.md 时贴的**假密钥示例**：

```
CLOUDBASE_API_KEY=<一串看起来像 JWT 的假密钥，此处不原样复现>
```

> **注意**：这里**故意不写出那串的原文**。写下这段说明时我一开始把它原样抄了进来，
> 结果 `preflight-check` 又一次报 ① 失败 —— **描述污染的文字本身又成了污染**。
> 教训：**讲规则时不要复现违规内容**，用占位符代替。

**这是个真问题**：假密钥虽然在功能上无害，但（a）会让检查脚本误报，（b）**万一被当成真密钥的范例被人抄走，很危险**，（c）污染仓库。

**根本修复（三处）**：

| # | 修法 | 效果 |
|---|------|------|
| 1 | 脚本里 `FAKE_LINE` 改为**运行时拼接**：`'ey' + 'JhbGciOiJIUzI1NiIs' + ...` | 源码里不出现连续长串，但运行时仍能触发扫描 |
| 2 | 证据文件 `save()` 写盘前**脱敏**：正则替换为 `<假密钥>` | 证据文件里不落地真串 |
| 3 | 文档/证据文件**手工脱敏** | 已提交的历史也清掉 |

修复后重跑三步验证：**① 命中 0 行 / ② 命中 1 行转红 / ③ 命中 0 行 —— 全 PASS**。

> **这个插曲本身很有价值**：发布前检查不是走过场 —— 它真的在发布前拦住了一个问题。虽然这次拦的是「自己的污染」，但流程证明有效。

### 3.2 发布

`preflight-check` 7 项全过后发布：

| 项 | 值 |
|---|---|
| 链接 | `https://touhou-mock.app.workbuddy.host/` |
| 验证 | `verified: true` |
| 形态 | `http-service`（Node 静态服务） |

### 3.3 公网验收

```
首页            HTTP 200（9010 字节）
/api/health     HTTP 200
/api/hot        HTTP 200
/api/works?category=music  HTTP 200
/api/circles    HTTP 200

health 返回：
  "version": "1.0.0"
  "checks": { "http": "ok", "static": "ok", "dataSource": "rest" }
```

**`dataSource: "rest"`** —— 走的是 CloudBase 真库，不是降级快照。

---

## 四、板块③：静态托管回退演练

### 4.1 演练设计

要**真实**，不能只是嘴上说说。所以：**先故意上线一个坏版本，再把它回退掉。**

| 步骤 | 动作 |
|---|---|
| 1 | 制造坏版本：改 `deploy/` 三个文件（版本号 → `1.0.1-rollback-drill`，首页加红色「坏版本」横幅） |
| 2 | 发布坏版本 → 模拟「线上出事了」 |
| 3 | 回退：`git checkout v1.0 -- deploy/` |
| 4 | 重新发布 → 恢复线上 |

### 4.2 坏版本的三处改动

```bash
$ git status --short deploy/
 M deploy/package.json          # 1.0.0 → 1.0.1-rollback-drill
 M deploy/server.js             # VERSION 1.0.0 → 1.0.1-rollback-drill
 M deploy/public/index.html     # + 顶部红色「坏版本」横幅

$ git diff --stat deploy/
 deploy/public/index.html | 3 +++
 deploy/server.js         | 2 +-
 deploy/package.json      | 2 +-
 3 files changed, 5 insertions(+), 2 deletions(-)
```

**为什么选「可见的横幅」而不是「隐蔽的 bug」**：演练要能**肉眼验收**。横幅红了就是坏了，横幅没了就是好了 —— 不需要额外查询就能判断。

### 4.3 坏版本上线（T2）

```bash
$ curl -s https://touhou-mock.app.workbuddy.host/api/health | grep version
  "version": "1.0.1-rollback-drill",     ← 线上已坏

$ curl -s https://touhou-mock.app.workbuddy.host/ | grep -o rollback-drill
rollback-drill                            ← 页面横幅在
```

### 4.4 回退（一条命令）

```bash
$ git checkout v1.0 -- deploy/
$ echo $?
0

$ git status --short deploy/
(无输出 —— 发布目录已与 v1.0 完全一致)

$ git diff v1.0 --stat -- deploy/
(无输出 —— 与锚点零差异)

$ grep -n "VERSION = " deploy/server.js
70:const VERSION = '1.0.0'          ← 已回到 v1.0
```

**`git status` 和 `git diff` 都空输出 = 恢复到位** —— 这是最硬的证据，不需要靠肉眼比对。

### 4.5 ★ 耗时记录

| 阶段 | 时间点 | 耗时 |
|---|---|---|
| T0 演练开始 | 09:34:40 | — |
| T1 坏版本就绪 | 09:35:16 | ① 36 秒 |
| T2 坏版本上线 | 09:36:36 | ② 1 分 20 秒 |
| T3 执行回退命令 | 09:36:42 | ③ **6 秒** |
| T4 恢复完成 | 09:37:34 | ④ **53 秒** |

| 指标 | 耗时 |
|---|---|
| **纯回退操作（T3→T4）** | **53 秒** |
| **线上坏掉 → 线上恢复（T2→T4）** | **59 秒** |
| 全流程（T0→T4） | 2 分 55 秒 |

> ① ② 是演练为了造场景才需要的；真实事故里这两步不存在，所以**看 T2→T4 的 59 秒才是有效数字**。

---

## 五、板块④：恢复 v1.0

### 5.1 重新发布

回退后 `deploy/` 已是 v1.0 内容，重新发布即覆盖线上：

```
发布成功，链接 https://touhou-mock.app.workbuddy.host/
verified: true
```

### 5.2 线上验收

```bash
$ curl -s .../api/health | grep version
  "version": "1.0.0",                ← 已恢复

$ curl -s .../ | grep -c rollback-drill
0                                     ← 坏标记已从公网消失
```

**公网正常 ✅**

---

## 六、今天交的截图（三张，均含地址栏 + 页面）

| 截图 | 文件 | 内容 |
|---|---|---|
| v1.0 公网可访问 | `evidence/v1.0-公网可访问.png` | 地址栏 `https://touhou-mock.app.workbuddy.host` + 页面正常渲染 |
| 回滚前后的提交记录 | `evidence/回滚前后的提交记录.png` | 地址栏 + git 记录：锚点 → 坏版本（3 文件 M）→ 回退（退出码 0） |
| 回滚后页面仍正常 | `evidence/回滚后页面仍正常.png` | 地址栏 + 页面正常，坏版本横幅已消失 |

**辅助证据**：`evidence/v1.0-health-接口.png`（地址栏 + `health` 返回 JSON，`version: "1.0.0"`）

### 6.1 截图方法（踩坑记录）

要求「图里要有地址栏」，所以**不能用无头浏览器截图**（无头截图没有地址栏和浏览器外壳）。

**最终方案**：Edge 开真实窗口 → 用 Win32 `PrintWindow`（`PW_RENDERFULLCONTENT`）抓该窗口位图 → 写 BMP → 转 PNG。

**踩到的坑**：

| 坑 | 现象 | 修法 |
|---|---|---|
| venv Python 输出被吞 | 脚本静默无输出、退出码 0 | 关键信息写日志文件；或用 base 解释器 |
| PIL 只在 venv 里 | base 解释器 `ModuleNotFoundError: PIL` | 抓图脚本不依赖 PIL，直接写 BMP，另一步转 PNG |
| Edge 进程堆积 | 跑到最后有 **66 个** `msedge.exe`，新实例行为异常 | `PostMessage(WM_CLOSE)` 关主窗口后**子进程仍存活** → 定期 `taskkill /F /IM msedge.exe` |
| `SW_RESTORE` 覆盖尺寸 | `MoveWindow` 设 1900×1150 实际 1295×815 | **顺序**：先 `SW_RESTORE` 再 `MoveWindow` |
| 窗口尺寸不可控 | `--window-size` 和 `MoveWindow` 都受限（最大化/屏幕约束） | 改为**让内容适配窗口**（单列、`white-space:pre`、压字号），而非跟窗口较劲 |
| Edge 冷启动弹「还原页面」提示框 | 抓到 344×166 的小图 | 选窗口时按**面积最大**挑，且设最小面积阈值 |
| `SystemExit` 不被 `except Exception` 捕获 | 超时失败时无任何日志 | 顶层改捕 `BaseException` |

**教训**：**当一个手段反复失败时，不要在同一手段上加参数试 —— 要换手段**。我在这张截图上花了很久在调窗口尺寸，最后是靠「改内容适配窗口 + 拆成抓 BMP/转 PNG 两步」解决的。

### 6.2 收尾时的一个误判（值得记）

最终验收发现线上首页 **9145 字节**，而 `git show v1.0:deploy/public/index.html` 是 **9010 字节**，差 135 —— 我一度判定为「CRLF 污染」（Day 25 踩过的坑），还差点重新发布。

**真相**：这**不是污染，是正常行为**。

| 项 | 值 |
|---|---|
| 本机 PortableGit 系统级 `etc/gitconfig` | `core.autocrlf = true` |
| 项目 `.gitattributes` | `* text=auto` |
| 结果 | 仓库内存 **LF（9010 字节）** → 工作区自动转 **CRLF（9145 字节）** |
| 差值 | 135 行 × 1 字节（`\r`）= 135 |

`git status` 是**干净的** —— git 认为这是它期望的工作区形态。我先前用「二进制写 LF」反而制造了虚假的 `M` 状态，已 `git checkout` 还原。

**可复用的验证方法**（归一化后比较）：

```python
a = live.replace(b'\r\n', b'\n')
b = repo.replace(b'\r\n', b'\n')
assert a == b      # True = 内容真正一致，差异只在行尾
```

**最终结论**：线上与仓库 v1.0 **归一化后完全一致（`True`）**，坏标记 `0`。**线上就是干净的 v1.0。**

**教训**：`git diff` 为空但字节数不同时，**先查 `core.autocrlf` 和 `.gitattributes`，不要急着「修」**。另注意 `grep -c $'\r'` 在 Git Bash 下不可靠（会返 0），要用 Python 数 `d.count(b'\r')`。

---

## 七、回滚手册（`docs/rollback.md`）

按任务要求，**云函数回退和数据恢复只写进手册备查，不做实操**。

手册结构：

| 节 | 内容 |
|---|---|
| §0 | 一句话结论（敢用 + 前提） |
| §1 | **什么情况必须回滚**（判断表 · 余力加练） |
| §2 | 静态托管回退（主路径，含实测耗时） |
| §3 | 云函数回退（备查，未实操） |
| §4 | 数据恢复（备查，未实操） |
| §5 | 发布规范（打 tag 流程，防患于未然） |
| §6 | Day 26 演练记录 |
| §7 | 敢不敢用？诚实回答（含已知短板） |

### 7.1 余力加练：判断表（§1）

6 行判断表，按「严重度 → 处置」组织。核心口诀：

> **用户能不能正常用？** 不能 → 回滚；能但难看 → 热修；无感 → 记录。

三条**决策红线**（不用犹豫直接回滚）：首页 5 秒打不开 / 接口 5xx / 页面出现「坏版本」「测试」「TODO」。

### 7.2 手册里最诚实的一段（§7）

**敢用，但有三个前提**：必须有 tag 锚点 / 必须能重新发布 / 发现要够快。

**已知短板（如实记录）**：
- 无自动健康检查/告警 → 发现问题靠人
- 发布工具是唯一通道 → 单点依赖，无备用发布路径
- 数据层恢复（§4）**未实操过**，只是写了步骤

**下一步该补的**：给线上加定时健康检查 —— **这比优化 53 秒更有价值**。因为 53 秒是「知道要回退之后」的耗时；真实事故中，发现问题的耗时才是大头。

---

## 八、完成标准自检

| 标准 | 结果 |
|---|---|
| v1.0 公网可访问 | ✅ `https://touhou-mock.app.workbuddy.host/` 首页 200 |
| 且检查全过 | ✅ `preflight-check` 7 项全过（修复污染后） |
| 回滚演练有耗时记录 | ✅ 纯回退 53 秒 / 线上坏→恢复 59 秒 |
| 恢复后公网正常 | ✅ `health` 版本 `1.0.0`，坏标记 `0` |
| 三张截图（含地址栏） | ✅ 见 §6 |

---

## 九、复现命令（完整）

```bash
cd <项目根>

# ① 锚点
git tag -a v1.0 -m "v1.0：首次正式发布"
git push origin v1.0

# ② 发布前检查
bash skills/preflight-check/check.sh

# ③ 制造坏版本（演练）
#    改 deploy/package.json + deploy/server.js 版本号
#    在 deploy/public/index.html <body> 后加红色横幅
git status --short deploy/
# → 发布

# ④ 回退
git checkout v1.0 -- deploy/
git status --short deploy/           # 期望空
git diff v1.0 --stat -- deploy/      # 期望空
# → 重新发布

# ⑤ 验收
curl -s https://touhou-mock.app.workbuddy.host/api/health
curl -s https://touhou-mock.app.workbuddy.host/ | grep -c rollback-drill   # 期望 0
```

---

*Day 26 完成 · 2026-10-13*
