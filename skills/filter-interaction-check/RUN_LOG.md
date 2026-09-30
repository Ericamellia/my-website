# filter-interaction-check 调用记录

Skill 位置：`skills/filter-interaction-check/SKILL.md`（项目内，随仓库提交）

## 2026-10-01（Day 12）第 1 次调用

- **被测页面**：`http://127.0.0.1:8001/my-app/#/music`（同人音乐列表，搜索框 + 原曲下拉）
- **调用方式**：Skill 工具真实调用（`filter-interaction-check`）→ 按其步骤执行 `templates/filter-check.html`
- **执行环境**：`python -m http.server 8001`（项目根），Edge 无头 `--dump-dom` 读取交互后 DOM

### 三种情况实测输出

| 情况 | visible | filteredOut | 空状态显示 | 结论 |
|---|---|---|---|---|
| 初始 | 6 | 0 | false | 通过 |
| 有结果（搜「灵梦」） | 1 | 5 | false | 通过 |
| 无结果（搜「zzzz」） | 0 | 6 | **true** | 通过（有提示，不是白屏） |
| 清空恢复 | 6 | 0 | false | 通过（全部回来） |

### 附带：原曲下拉筛选

- 逐项命中：`001=0, 002=0, 003=0, 004=0, 005=0, 006=0`
- 结论：**数据侧问题，不是代码 bug** —— `data/music.json` 里 6 部作品的 `original` 字段全为 `null`（未标注原曲），所以任何选项都筛不出东西；筛选后空状态正确显示、清空可恢复，代码逻辑正常。
- 待办：给音乐作品补 `original` 字段后该下拉才真正可用。

### 可访问性加练结论

| 检查项 | 结果 |
|---|---|
| 搜索框有可被读屏识别的名字 | 通过（本次补了 `aria-label`） |
| 空状态可被播报 | 通过（本次补了 `role="status"` + `aria-live="polite"`） |
| 下拉与说明文字关联 | 通过（`<label>原曲筛选: <select>` 包裹） |
| 结果/按钮有可读文本 | 通过 |

本次为可访问性补的改动：`my-app/app.js` 中两处搜索框加 `aria-label`、两处空状态区块加 `role="status" aria-live="polite"`（版本号随之升到 `app.js?v=83`）。

### 证据文件（已随仓库提交）

- 筛选后页面截图（含地址栏、筛选条件与结果）：`docs/day12/day12-filter-result.png`
- Skill 文件截图（文件名可见）：`docs/day12/day12-skill-file.png`
- 交互后 DOM：`C:\Users\25394\shots\dom_filter3.html`

截屏方式说明：无头截图没有地址栏，所以这两张是**真实窗口截图** —— 启动 Edge 打开
`http://127.0.0.1:8001/my-app/#/music?q=灵梦`（地址栏带筛选词，页面自动筛选），
再用 ctypes + GDI 抓屏并手写 PNG 保存；SKILL.md 那张是记事本打开后抓屏（标题栏为 `SKILL.md - Notepad`）。
