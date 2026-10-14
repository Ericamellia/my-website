# 东方Project同人作品查询站

面向中文东方爱好者（想随手查查的那类，不是维基编辑）的轻量同人作品查询站。
精选小数据集 + 查得爽的搜索体验，不追求收录量。

- 定位与需求：`PRD.md`（做什么、做到什么程度算完成）
- 技术设计与数据流：`TECH_DESIGN.md`
- 本地运行 / 部署 / 数据库：`RUN.md`
- 协作规则：`AGENTS.md`

## 目录结构

```
my-app/         前端站点（HTML + CSS + JS，软路由）
deploy/         服务端（Node，零依赖）+ 数据访问层（三通道）
db/             数据库脚本（建表 / 种子 / 同步）
skills/         可复用的检查 Skill（本项目自用，随仓库提交）
docs/           每日开发文档与证据
```

## 快速开始（本地）

```bash
# 前端（静态站）
python -m http.server 8001 --bind 127.0.0.1
# 打开 http://127.0.0.1:8001/my-app/

# 服务端（接口 + 真库）
cd deploy && PORT=3000 node server.js
```

详细说明见 `RUN.md`（含端口占用、代理坑、数据源优先级三态）。

---

## 可复用 Skill

`skills/` 下是本项目沉淀的检查工具。每个都是「能手动跑出结果、有明确通过判据」的脚本。

### preflight-check —— 发布前检查

**什么时候用**：准备 `git push` / 发布上线**之前**；改了前端 JS/CSS 之后；怀疑仓库混进了密钥。

```bash
# 完整检查（含公网接口）
bash skills/preflight-check/check.sh

# 没网时跳过公网检查
bash skills/preflight-check/check.sh --offline

# 改了前端 JS/CSS 时加上：检查版本号有没有升
bash skills/preflight-check/check.sh --staged-version
```

**退出码**：`0` = 全过；`1` = 有项没过（可直接在 CI 里卡发布）。

**检查项**：

| # | 检查项 | 通过判定 |
|---|---|---|
| ① | 密钥泄漏 | 被跟踪文件里密钥「值」特征命中 **0 行** |
| ② | `.env` 不进仓库 | 被跟踪的 `.env` 数 = **0** |
| ③ | `.env.example` 能提交 | 未被忽略（或命中 `!` 例外） |
| ④ | 公网接口可达 | `/api/health`、`/api/hot`、`/api/favorites` 均 **200** |
| ⑤ | 错误不漏内部细节 | 错误响应体不含堆栈 / 连接串特征 |
| ⑥ | 前端版本号已升 | `app.js?v=N` 的 N **大于**上一提交（仅 `--staged-version`） |

换域名时不用改脚本：

```bash
PREFLIGHT_SITE=https://你的域名 bash skills/preflight-check/check.sh
```

**为什么值得跑**：这里的每一项都对应本项目**真实踩过的坑** ——
文档里写 Key 占位被扫描器命中（Day 23）、改了 `app.js` 忘升版本号吃缓存（Day 7）、
公网报错漏内部细节（Day 23）。详见 `skills/preflight-check/SKILL.md`。

**注意**：它不是「永远报通过」的摆设 —— 它被验证过会**报红**：
往被跟踪文件里注入一行假密钥，① 会从 `[PASS]` 变 `[FAIL]` 并打印出那一行；
移除后恢复全绿。验证过程见 `skills/preflight-check/RUN_LOG.md`。

### filter-interaction-check —— 列表筛选交互检查

**什么时候用**：新增或改动筛选控件（搜索框、下拉筛选、分类 Tab）之后。

检查筛选的三件事是否都成立：有结果能筛出来、没结果有提示不白屏、清空能完整恢复；
顺带体检可访问性（label 关联、空状态读屏、键盘可达）。

详见 `skills/filter-interaction-check/SKILL.md`。

### acceptance-check —— 结营 / 发布后整体验收体检

**什么时候用**：发布上线**之后**复验；改过后端接口做回归；结营或交接时确认交付物齐全；
怀疑「代码推了但线上没部署」。

一条命令跑完五类：公网可访问 → **真实读写 + 持久化** → 接口契约与错误处理 →
本地交付物完整 → 版本号一致性。

```bash
bash skills/acceptance-check/check.sh              # 完整（含写库测试）
bash skills/acceptance-check/check.sh --skip-write # 只读，不动生产数据
bash skills/acceptance-check/check.sh --offline    # 纯离线
```

**退出码**：`0` = 全过；`1` = 有 FAIL。

和 `preflight-check` 的分工：**前者管「推之前别带脏东西」，后者管「推之后整体是不是好的」。**
它会真的写一条测试数据验持久化，但**注册了 trap 兜底清理**（任何退出路径都会删掉）。

详见 `skills/acceptance-check/SKILL.md`。

