# preflight-check 调用记录

Skill 位置：`skills/preflight-check/SKILL.md`（项目内，随仓库提交）
检查脚本：`skills/preflight-check/check.sh`

## 2026-10-13（Day 25）第 1 次调用 —— Skill 产出当天的自验

- **调用目的**：Skill 刚写好，实跑一遍证明它能用；并**故意留一个问题**验证它不会虚报通过。
- **执行环境**：项目根目录，`bash skills/preflight-check/check.sh`
- **被测目标**：本项目自身（公网地址 `https://touhou-mock.app.workbuddy.host`）

### 三步验证结果

| 步骤 | 操作 | 结果 | 退出码 |
|---|---|---|---|
| 1 | 正常态直接跑 | **通过 7 项，失败 0 项** ✅ | 0 |
| 2 | 往 `my-app/index.html` 注入一行假密钥 | **① 密钥泄漏 转 [FAIL]，命中 1 行** ✅ | 1 |
| 3 | 移除注入后重跑 | **恢复 通过 7 项，失败 0 项** ✅ | 0 |

**第 2 步查出来的那一行（原文摘录，注入值中部以 `<假密钥>` 代替，避免本文档自身被扫描器命中）**：

```
[FAIL] ① 密钥泄漏  命中 1 行 —— 明细如下：
       my-app/index.html:<meta name="x-preflight-probe" content="CLOUDBASE_API_KEY=<假密钥>">
```

→ 证明 `preflight-check` **不是永远报通过**：故障能把它逼红，而且它指出了**哪一行**。

### 各检查项本次结果

| # | 检查项 | 结果 |
|---|---|---|
| ① | 密钥泄漏 | PASS（0 行，干净） |
| ② | `.env` 未入库 | PASS（被跟踪数 = 0） |
| ③ | `.env.example` 可提交 | PASS（无规则命中） |
| ④ | 公网接口可达 | PASS（health / hot / favorites 均 200） |
| ⑤ | 错误不漏内部细节 | PASS（无堆栈/连接串特征） |
| ⑥ | 前端版本号 | 本次未查（没改前端 JS，未加 `--staged-version`） |

### 本次踩到的坑（已修进脚本/文档）

**Python 文本模式写文件会改换行符**：验证脚本第一版用 `open(..., 'r'/'w')` 注入再还原，
Windows 下 LF 被转成 CRLF，文件从 9010 字节涨到 9145 字节，
`git status` 出现「不明修改」（`git diff` 却是空的）。
→ 已改为**二进制模式** `open(..., 'rb'/'wb')` 读写，还原后工作区完全干净。

### 证据文件（`docs/day25/evidence/`）

- `preflight-查到问题.png` —— 注入假密钥后 ① 转红，并高亮打印出那一行
- `preflight-全绿.png` —— 移除后恢复全绿（对照）
- `step1-normal.txt` / `step2-injected.txt` / `step3-restored.txt` —— 三步完整输出
- `verify-summary.txt` —— 三步判定汇总
- `verify_preflight.py` / `shot_day25.py` —— 验证与截图脚本
