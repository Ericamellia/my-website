# 热搜数据导入 CloudBase 真库 · 操作清单

> 生成时间：2026-10-10 23:45（GMT+8）
> 触发原因：热搜详细页改成「一次 6 行 + 每次展开追加 6 行」，需要每榜 60 条数据支撑。
> 本次同步：**120 条**（当日热搜 60 + 历史热门 60）

---

## 一、先搞清楚：为什么必须手动导入

项目的数据访问层有**三条通道**，按优先级自动选择：

| 优先级 | 通道 | 触发条件 | 数据来源 |
|---|---|---|---|
| ① | `rest` | 配了 `CLOUDBASE_ENV_ID` + `CLOUDBASE_API_KEY` | CloudBase 真库（PostgREST） |
| ② | `pg` | 配了 `PG_URL` / `DATABASE_URL` | 真库（pg 直连） |
| ③ | `snapshot` | 以上都没配 | `deploy/data/*.json` 快照 |

**现状**：
- **本地开发**：走 ① `rest`，读的是 CloudBase 真库 → 真库里还是旧的 20 条/榜，所以本地看到的是旧数据。
- **公网部署**：沙箱连不到 CloudBase → 走 ③ `snapshot`，读 `deploy/data/hot.json` → **已经是最新的 60 条/榜**。

所以：
- 公网链接**已经能看到新数据**（快照已更新），不需要导入也能用。
- 但真库不导入的话，本地开发环境和真库会长期不一致，以后排查问题容易混淆。**建议导入**。

---

## 二、导入步骤（3 步）

### 步骤 1：打开 CloudBase SQL 编辑器

```
腾讯云 CloudBase 控制台
  → 选择环境（与 deploy/.env 里 CLOUDBASE_ENV_ID 对应）
  → 左侧菜单「数据库 / SQL 数据库」
  → 「SQL 编辑器」
```

### 步骤 2：粘贴执行 `db/seed-hot.sql`

**文件路径**：
```
C:\Users\25394\WorkBuddy\2026-09-18-00-29-07\db\seed-hot.sql
```

- 文件大小约 **125 KB**，包含 120 条 `INSERT`。
- **幂等**：`ON CONFLICT (bvid) DO UPDATE`，重复执行不报错，只会更新。
- 文件末尾有一条 `DELETE FROM hot_videos WHERE bvid NOT IN (...)`，
  会把不在本次榜单里的旧记录清掉（防止榜单越滚越长）。**这是预期行为。**

> ⚠️ 如果控制台对单次粘贴长度有限制，可以**分段执行**：
> 文件已按 `-- 榜单：fresh 共 60 条` / `-- 榜单：hot 共 60 条` 分成两段，
> 分两次粘贴即可。但 `DELETE` 那条**必须最后一次执行**（它依赖全部 INSERT 已完成）。

> 💡 如果是**首次**在某个环境建表，需要先执行 `db/schema-hot.sql` 建 `hot_videos` 表。
> 本项目当前环境已经建过表，直接跑 `seed-hot.sql` 即可。

### 步骤 3：验证

在同一个 SQL 编辑器里执行：

```sql
-- ① 总条数，期望 120
SELECT COUNT(*) FROM hot_videos;

-- ② 分榜条数，期望 fresh=60 / hot=60
SELECT board, COUNT(*) FROM hot_videos GROUP BY board ORDER BY board;

-- ③ 抽看当日榜前 5 条
SELECT rank_no, play, title FROM hot_videos
 WHERE board = 'fresh' ORDER BY rank_no LIMIT 5;

-- ④ 抽看历史热门榜前 5 条
SELECT rank_no, play, title FROM hot_videos
 WHERE board = 'hot' ORDER BY rank_no LIMIT 5;
```

---

## 三、导入后自检（本地）

导入完成后，本地开发环境（走 `rest` 真库通道）应该能看到 60 条：

```bash
# 在项目根目录
curl -s "http://127.0.0.1:3000/api/hot?board=fresh&limit=60" | head -c 200
```

预期返回 `"data"` 数组长度 60，且 `"source": "rest"`。

---

## 四、本次数据说明

- **同步脚本**：`db/sync_hot.py`（本次改动：扩大关键词池 + `--days` 参数）
- **执行命令**：
  ```bash
  python db/sync_hot.py --limit 60 --days 3
  ```
- **「当日热搜」口径变更**：从「今天+昨天」（2 天）放宽到 **近 3 天**。
  原因：东方圈日常投稿量有限，2 天窗口只能凑到 35 条，
  不足以支撑「首屏 6 行（24 条）+ 每次展开再补 6 行」的展示需求。
- **产出文件**：
  - `db/seed-hot.sql`（125 KB，120 条）→ 用于导入真库
  - `deploy/data/hot.json`（84 KB，120 条）→ 公网降级快照
  - `my-app/data/hot.json`（同内容，本地静态副本）

---

## 五、常见问题

**Q：导入后本地还是 20 条？**
A：检查 `deploy/.env` 和根目录 `.env` 里的 `CLOUDBASE_ENV_ID` / `CLOUDBASE_API_KEY`
是否配的是同一个环境；然后重启本地服务（server.js 启动时才读 env）。

**Q：能直接连库跑，不走控制台吗？**
A：可以——如果配了 `PG_URL`（pg 直连），用 `psql` 直接跑 `seed-hot.sql` 即可，
不必经过 `rest` 通道。本项目当前没配 `PG_URL`，走的是 CloudBase REST。

**Q：以后每次都要手动导入吗？**
A：是。这是「同步任务」的固有形态：脚本定时抓取 → 产出 SQL/快照 → 人工或定时任务落库。
若要做到全自动，需要把 `sync_hot.py` 部署成定时任务并接入数据库直连。
