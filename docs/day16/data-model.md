# Day 16 · 数据模型说明（两张表怎么设计、靠什么关联）

> 课程：21 天建站 · Day 16｜第 3 周
> 目标数据库：CloudBase PostgreSQL（SQL 数据库 → PostgreSQL 管理）
> 建表脚本：`db/schema.sql`　种子脚本：`db/seed.sql`（生成器 `db/gen_seed.py`）

---

## 一、今天要掌握的问题

### Q1：两张表分别存什么？

| 表 | 存什么 | 一句话 | 现有数据来源 | 条数 |
|---|---|---|---|---|
| **`circles`** | **「谁做的」** | 社团 / 作者档案 | `my-app/data/circles.json` | 26 |
| **`works`** | **「做了什么」** | 全部作品（五板块合并） | `music/doujin/game/art/video.json` | 30 |

**为什么是这两张表**：整个站点的数据本质上是「社团产出作品」这一种关系。
- 站点的「社团查询页」「作者页」需要社团维度的信息（简介、头像、平台粉丝数）→ `circles`
- 站点的「列表页」「详情页」「搜索」「收藏」全部围绕作品 → `works`

### Q2：靠哪个字段关联？

```
works.circle_name  →  circles.name
```

**为什么用社团名字符串关联，而不是数字 `circle_id`**：

1. 现有数据（`circles.json`）里社团的唯一标识**本来就是名字**，作品里也是用 `"circle": "COOL&CREATE"` 这样的字符串引用；
2. 直接用 `name` 做主键，**不需要额外维护一份 id ↔ 名字的映射表**；
3. 已经核验过关：30 条作品引用的 **26 个社团，`circles` 表里全部存在**，没有孤儿记录。

**关联关系图**：

```
┌────────────────────┐              ┌─────────────────────────────┐
│      circles       │              │           works             │
├────────────────────┤              ├─────────────────────────────┤
│ name        PK  ◄──┼──────────────┼── circle_name  (FK)         │
│ name_en            │   1      N   │ work_id           PK        │
│ intro              │              │ category  (五板块)          │
│ avatar             │              │ name                        │
│ top_platform       │              │ creator / year              │
│ followers          │              │ characters  (JSONB 数组)   │
│ platform_url       │              │ tags        (JSONB 数组)   │
└────────────────────┘              │ cover / source_url / ...    │
                                    └─────────────────────────────┘
      一个社团 ──产出──▶ 多个作品
```

---

## 二、两个关键设计决策及理由

### 决策 1：五个板块合并成一张 `works` 表，而不是建五张表

五个 JSON（music / doujin / game / art / video）的字段 **95% 重合**，只有极少数专属字段不同：

| 字段 | music | doujin | game | art | video |
|---|---|---|---|---|---|
| `id / name / circle / creator / year` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `characters / tags / popularity` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `cover / source_url / description / views` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `netease_url` | ✅ | — | — | — | — |
| `type / platform / url / bvid / original_title` | — | — | — | — | ✅ |

**合并方案**：一张表 + `category` 字段区分板块，专属字段直接列为普通列（其它板块填 NULL）。

**收益**：搜索、收藏、列表这些**跨板块**功能只需查一张表；接口不用按板块分叉。
**代价**：少数列稀疏（如 `bvid` 只有 6 行有值）—— 对 30 条数据的规模完全可接受。

### 决策 2：主键用 `work_id`（板块前缀 + 原 id），不用原始 `id`

五个板块的 `id` **都从 1 开始**（music 有 1-6，doujin 也有 1-6），直接做主键会撞车。

所以拼成 `{板块}-{原id}`：
- `music-1`、`music-2` … `music-6`
- `video-1` … `video-6`
- 共 30 个全局唯一键

好处：**可读**（一眼看出属于哪个板块）、**可反推**（拆字符串就得到来源）、**不撞车**。

---

## 三、字段类型选择理由（余力加练：字段注释）

### `circles`（9 列）

| 字段 | 类型 | 为什么选它 |
|---|---|---|
| `name` | `VARCHAR(128)` | 主键。社团名最长约 30 字符（含日文），128 留足余量；不用 TEXT 是因为主键需要可索引、有长度上限 |
| `name_en` | `VARCHAR(128)` | 与 name 同量级 |
| `intro` | `TEXT` | 简介 1–3 句中文，长度不定（长的超 100 字）。TEXT 无长度上限，且 PG 里 TEXT 与 VARCHAR 性能无差异 |
| `source_url` | `VARCHAR(512)` | URL 可能含**中文路径**（如 THBWiki 的 `/劇毒少女`），UTF-8 下一个中文占 3 字节，512 字符 ≈ 1.5KB 足够 |
| `avatar` | `VARCHAR(255)` | 本地相对路径，短，255 足够 |
| `top_platform` | `VARCHAR(32)` | 平台名很短（bilibili / pixiv / steam / Twitter） |
| `followers` | `INTEGER` | 粉丝数。**不用 BIGINT** —— 最大约 2.1×10⁹，任何平台粉丝数都远达不到；**允许 NULL** 因为有些社团没有平台账号 |
| `platform_url` | `VARCHAR(512)` | 同 source_url |
| `created_at` | `TIMESTAMPTZ` | **带时区**的时间戳。不用 `TIMESTAMP` 是因为后者不带时区，跨时区部署时会产生歧义；`NOT NULL DEFAULT NOW()` 保证自动填充 |

### `works`（20 列）

| 字段 | 类型 | 为什么选它 |
|---|---|---|
| `work_id` | `VARCHAR(32)` | 主键。最长形如 `doujin-6`（8 字符），32 留足余量 |
| `category` | `VARCHAR(16)` | 五个枚举值（music/doujin/game/art/video），最长 6 字符。**没用 PG 原生 ENUM 类型** —— 后续要加板块时 ENUM 修改麻烦，VARCHAR 更灵活 |
| `name` | `VARCHAR(255)` | 作品名可能含副标题（如 `- Bibliotheca - 劇毒少女 publication number V`），255 足够 |
| `circle_name` | `VARCHAR(128)` | **外键**。必须与 `circles.name` 类型完全一致，PG 才允许建外键约束 |
| `creator` | `VARCHAR(128)` | 个人名，与社团名同量级 |
| `year` | `SMALLINT` | 年份。**范围 ±32767 远超需要**（东方作品 1996 年起），比 INTEGER 省 2 字节 |
| `characters` | `JSONB` | 登场角色是**变长数组**（1–4 个不等）。用 JSONB 而非关联网表的理由：MVP 阶段数据量小、数组长度短，建关联表是过度设计。JSONB 可加 **GIN 索引**支持 `@>` 包含查询 |
| `tags` | `JSONB` | 同上 |
| `popularity` | `INTEGER` | 热度值，允许 NULL（部分作品无评估数据） |
| `views` | `INTEGER` | **`NOT NULL DEFAULT 0`** —— 计数场景不能是 NULL，否则 `views+1` 会变成 NULL |
| `cover` | `VARCHAR(512)` | 可能是本地路径，也可能是 **B站的完整外链 URL**（含长 hash），512 留足 |
| `source_url` | `VARCHAR(512)` | 原发布页，可能含中文 |
| `description` | `TEXT` | 简介，长度不定 |
| `netease_url` | `VARCHAR(512)` | [仅 music] |
| `video_type` / `video_platform` / `video_url` / `bvid` / `original_title` | 各异 | [仅 video] 专属字段。注意**避开了 MySQL 保留字**：JSON 里叫 `type`/`platform`/`url`，表里改名加 `video_` 前缀 |
| `created_at` | `TIMESTAMPTZ` | 同 circles |

**JSONB 而不是 JSON 的原因**：PG 里 `JSON` 是纯文本存储（每次访问都要重新解析），`JSONB` 是**二进制存储**（解析一次、可建索引、支持 `@>` `?` 等操作符）。查询性能差距明显，且我们的场景只写不读原文，JSONB 完胜。

---

## 四、索引设计

| 索引 | 表 | 服务的查询 |
|---|---|---|
| `idx_circles_name_en` | circles | 按英文名检索社团 |
| `idx_works_category` | works | **最高频**：列表页按板块筛选 |
| `idx_works_circle` | works | 社团查询页（查某社团的所有作品）；也是外键关联列 |
| `idx_works_year` | works | 按年份排序 |
| `idx_works_popularity` | works | 按热度排序 |
| `idx_works_tags` (GIN) | works | 标签包含查询 `tags @> '["红魔乡"]'` |
| `idx_works_characters` (GIN) | works | 角色包含查询 `characters @> '["博丽灵梦"]'` |

前五个是普通 B-tree 索引；后两个是 **GIN 索引**，专门服务 JSONB 数组的包含查询 —— 这正是「搜索接口按标签/角色筛选」要用的能力。

---

## 五、验证结果（Day 16 第④步）

### 行数验证

```sql
SELECT 'circles' AS 表名, COUNT(*) AS 行数 FROM circles
UNION ALL
SELECT 'works', COUNT(*) FROM works;
```

| 表 | 期望 | 实测 |
|---|---|---|
| circles | 26 | ✅ 26 |
| works | 30 | ✅ 30 |

### 关联验证（证明两张表真的连得起来）

```sql
SELECT w.work_id, w.name AS 作品, c.name AS 社团, c.followers AS 粉丝数
FROM works w
JOIN circles c ON w.circle_name = c.name
ORDER BY c.followers DESC NULLS LAST
LIMIT 5;
```

这条 JOIN 能跑出结果 = **外键关联通路成立**，Day 17 的读接口可以直接按这个模式写（一次 JOIN 拿到作品 + 所属社团信息）。

### 交付截图

| 截图 | 内容 |
|---|---|
| `docs/day16/day16-circles.png` | 数据编辑器打开 `circles` 表：表名 + 共 26 条记录 |
| `docs/day16/day16-works.png` | 数据编辑器打开 `works` 表：表名 + 共 30 条记录 |

---

## 六、幂等性说明（清单要求：seed.sql 重复执行不报错）

`db/seed.sql` 的每条语句都用 PostgreSQL 的幂等语法：

```sql
INSERT INTO circles (...) VALUES (...)
ON CONFLICT (name) DO UPDATE SET "name_en"=EXCLUDED."name_en", ...;
```

- **首次执行** → 插入新行
- **重复执行** → 命中主键冲突，转为 **UPDATE**（用 `EXCLUDED` 取本次提供的值覆盖）

所以无论跑多少次，结果都是「26 条 circles + 30 条 works」，不会报错、不会产生重复行。

---

## 七、过程记录：踩到的两个坑

### 坑 1：环境是 PostgreSQL，不是 MySQL

最初按 MySQL 写了 `schema.sql`（`ENGINE=InnoDB`、`KEY xxx` 内联索引、反引号、`ON DUPLICATE KEY UPDATE`）。
进控制台才发现环境提供的是 **PostgreSQL**（页面标题「PostgreSQL 管理」，URL 含 `/db/postgres/`）。

**差异对照**（这也是今天的额外收获）：

| 项 | MySQL | PostgreSQL |
|---|---|---|
| 标识符引号 | 反引号 `` ` `` | 双引号 `"` 或不加 |
| 表参数 | `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4` | 无（PG 默认 UTF-8） |
| 索引声明 | 建表语句内 `KEY idx_x (col)` | 独立 `CREATE INDEX IF NOT EXISTS ...` |
| 字段注释 | 内联 `COMMENT '...'` | 独立 `COMMENT ON COLUMN ... IS '...'` |
| JSON 类型 | `JSON` | `JSONB`（推荐，二进制存储 + 可建 GIN 索引） |
| UPSERT 语法 | `ON DUPLICATE KEY UPDATE` | `ON CONFLICT (键) DO UPDATE SET ... EXCLUDED.列` |
| 时间戳 | `TIMESTAMP` / `DATETIME` | `TIMESTAMPTZ`（带时区，推荐） |

### 坑 2：源数据里 `followers` 有空字符串

`circles.json` 里 AQUA STYLE、BlackEditionFX 等社团的 `top_platform.followers` 是 `""`（空串）。
直接插进整数列会报 `invalid input syntax for type integer`。

**修法**：在生成器 `db/gen_seed.py` 里加了专门的 `qi()` 函数处理整数列 —— 空串/非数字一律转 `NULL`。

---

## 八、今日不做（按清单明确排除）

- ❌ 写任何接口（Day 17 才开始）
- ❌ 改前端

`db/` 目录只负责「建表 + 种子数据」，是纯后端数据层的工作。
