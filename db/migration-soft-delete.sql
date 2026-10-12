-- ============================================================================
-- 东方同人搜索 · 迁移：给 favorites 加软删除（Day 22 余力加练）
-- ============================================================================
-- 干什么：让 DELETE 不真删数据，只在行上打一个 is_deleted 标记，
--         查询时跳过已删的行。这样误删还能找回。
--
-- 执行前提：favorites 表已存在（Day 17 建过）
-- 执行方式：CloudBase 控制台 → SQL 数据库 → SQL 编辑器 → 整段粘贴执行
-- 幂等：可以重复执行（IF NOT EXISTS / IF EXISTS 都用上了）
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 第 1 步：加 is_deleted 列
-- ----------------------------------------------------------------------------
-- 为什么用 BOOLEAN NOT NULL DEFAULT FALSE：
--   · NOT NULL  —— 三个状态（真/假/NULL）里 NULL 最难处理（`WHERE NOT is_deleted`
--                  碰到 NULL 会得到 NULL 而不是 TRUE，行会莫名其妙消失）。
--                   只要两态就够，别给自己留坑。
--   · DEFAULT FALSE —— 已有的老数据自动变成「未删除」，不用手动回填。
--
-- 为什么默认值不像 created_at 那样麻烦：
--   加列时 PG 会为新老行都填上 FALSE，一条 UPDATE 都不用写。
-- ----------------------------------------------------------------------------
ALTER TABLE favorites
  ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN favorites.is_deleted IS
  '软删除标记（Day 22 余力加练）：TRUE = 已取消收藏但数据保留，可恢复。查询须过滤掉';

-- ----------------------------------------------------------------------------
-- 第 2 步：把「唯一约束」换成「部分唯一索引」★ 这一步是本迁移的关键
-- ----------------------------------------------------------------------------
-- 问题：原来的 uq_favorites_user_work UNIQUE (user_id, work_id) 是**全表生效**的。
--   软删除后，那条已删的行**还在表里**，唯一约束照样管它 ——
--   于是「取消收藏后想重新收藏同一作品」会直接撞约束（409），
--   用户看到的现象是「我明明删了，怎么还说我收藏过」。
--
-- 解法：改成**部分唯一索引**，只对 is_deleted = FALSE 的行生效。
--   已软删的行不参与唯一性判断，重新收藏就能插进去新行。
--
-- 注意：约束（CONSTRAINT）和索引（INDEX）在 PG 里不是一回事 ——
--   约束不能带 WHERE，所以这里必须先 DROP CONSTRAINT，再建部分索引。
-- ----------------------------------------------------------------------------
ALTER TABLE favorites DROP CONSTRAINT IF EXISTS uq_favorites_user_work;

CREATE UNIQUE INDEX IF NOT EXISTS uq_favorites_active
  ON favorites (user_id, work_id)
  WHERE is_deleted = FALSE;

COMMENT ON INDEX uq_favorites_active IS
  '同一用户对同一作品，只允许存在一条「未删除」的收藏；已软删的不参与判重（Day 22）';

-- ----------------------------------------------------------------------------
-- 第 3 步：索引也要跟着改（列表查询现在都带 is_deleted 过滤）
-- ----------------------------------------------------------------------------
-- 原来的 idx_favorites_user 是 (user_id) 单列索引。
-- 现在最典型的查询变成「某用户 + 未删除」，改成**部分索引**更省空间也更快：
-- 已删的行不进索引，索引体积只跟「还有效的收藏」成正比。
DROP INDEX IF EXISTS idx_favorites_user;

CREATE INDEX IF NOT EXISTS idx_favorites_user_active
  ON favorites (user_id)
  WHERE is_deleted = FALSE;

-- ----------------------------------------------------------------------------
-- 第 4 步：验证（执行完跑一下，应看到 is_deleted 列 + 两个部分索引）
-- ----------------------------------------------------------------------------
-- ① 看列
-- SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--  WHERE table_name = 'favorites' AND column_name = 'is_deleted';
--
-- ② 看索引（indexdef 里应该带 WHERE is_deleted = false）
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'favorites';
--
-- ③ 看数据（全部应是 f = 未删除）
-- SELECT id, work_id, note, is_deleted FROM favorites ORDER BY id;
