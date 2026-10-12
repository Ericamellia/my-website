# Day 21 路线B｜建表 + 导数据 执行指引

> **这是「超出今日清单」的工作**（今日清单写明「不做新功能」）。
> 目的：把 `my-app` 的三类本地数据搬进 CloudBase 真库，让 my-app 也能连真库。
>
> 文件都在 `docs/day21/sql/chunks/`，**按编号顺序逐个粘贴**到 CloudBase 控制台的 SQL 编辑器。

---

## 为什么要分 19 次粘

Day 17 踩过一个坑：**控制台 SQL 编辑器粘贴长文本会被截断**（当时 43KB 的 seed 只显示前 11 行，
报错 `syntax error at or near "BV..."`，极具误导性）。

所以这次**单块控制在 4KB 以内**，最长的 `04-characters-1.sql` 也才 3.9KB。

---

## 执行顺序

| 顺序 | 文件 | 内容 | 预期结果 |
|---|---|---|---|
| 1 | `01-schema.sql` | 建 4 张表 | `CREATE TABLE` ×4 |
| 2 | `02-og-categories.sql` | 原作分类 5 条 | `INSERT 0 5` |
| 3–6 | `03-original-games-1~4.sql` | 原作作品，共 39 条 | 累计 `INSERT 0 39` |
| 7–18 | `04-characters-1~12.sql` | 角色，共 112 条 | 累计 `INSERT 0 112` |
| 19 | `05-originals-1.sql` | 原曲 6 条 | `INSERT 0 6` |

> 每个文件里可能含多个 `INSERT`（按 10 条一块）。**整块复制粘贴即可**。

---

## 每步怎么做

1. 打开 CloudBase 控制台 → 你的环境 → **SQL 编辑器 / PostgreSQL 管理**
2. 打开 `chunks/` 里对应编号的文件（用记事本 / VSCode）
3. **全选 → 复制 → 粘进 SQL 编辑器**
4. 点「运行查询」
   - 若弹「检测到潜在问题 / 破坏性操作」→ 点「**运行查询**」继续（Day 17 记录过，这不是错误）
5. 看结果里的提示（`CREATE TABLE` / `INSERT 0 N`）

**粘完一块再粘下一块**，不要 19 个一起粘。

---

## 全部完成后，用这段 SQL 自检

```sql
SELECT 'original_game_categories' AS 表, COUNT(*) FROM original_game_categories
UNION ALL SELECT 'original_games',  COUNT(*) FROM original_games
UNION ALL SELECT 'characters',      COUNT(*) FROM characters
UNION ALL SELECT 'originals',       COUNT(*) FROM originals;
```

**期望结果**：

| 表 | 期望行数 |
|---|---|
| `original_game_categories` | **5** |
| `original_games` | **39** |
| `characters` | **112** |
| `originals` | **6** |

---

## 常见问题

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `syntax error at or near "..."`，且报错位置**指向下一条** | 上一个粘贴被截断 | 重新粘那一块，确认编辑器里**内容完整**（能滚到最后看到 `ON CONFLICT ...`） |
| `relation "xxx" already exists` | 这块之前执行过了 | 无害，`CREATE TABLE IF NOT EXISTS` 会跳过；确认数据没重复即可 |
| `duplicate key value violates unique constraint` | 同一条数据粘了两次 | 用自检 SQL 对行数；多了就删重复行 |
| 报「检测到潜在问题」 | 控制台对破坏性操作的确认 | 点「运行查询」继续 |

---

## 为什么要建这 4 张表（而不是直接用 works）

- `works` 表已有 30 条，**用 `category` 字段分五类**（music/doujin/game/video/art）→ 覆盖 my-app 的**作品**数据
- `circles` 表已有 26 条 → 覆盖 **社团**
- **缺**的是 `original_games`（原作 39）、`characters`（角色 112）、`originals`（原曲 6）
  → 本次补建；另加 `original_game_categories`（原作分类 5 条，给原作页做分组）
