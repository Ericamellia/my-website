-- ============================================================================
-- 东方同人搜索 · 表 3：favorites（Day 17 单独执行用）
-- ============================================================================
-- 本文件是 db/schema.sql 里 favorites 那一段的独立副本，方便单独粘贴执行。
-- 已经整份跑过 db/schema.sql 的话，本文件不用再跑（内容重复但幂等，跑了也没事）。
--
-- 执行前提：works 表已存在（favorites.work_id 有外键指向 works.work_id）
-- 执行方式：CloudBase 控制台 → SQL 数据库 → SQL 编辑器 → 整段粘贴执行
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 表 3：favorites　收藏表（Day 17 新增）
-- ----------------------------------------------------------------------------
-- 存什么：「谁收藏了哪个作品」。Day 17 只读（GET /api/favorites 返回收藏列表），
--   写入接口（POST /api/favorites）排在 Day 18，所以今天这张表先建好灌示例数据。
--
-- 为什么有 id 又要有 work_id：
--   id 是自增代理键，专门做「同一条收藏的唯一标识」，方便以后取消收藏时精确定位；
--   work_id 是业务外键，指向 works.work_id，说明收藏的是哪件作品。
--   两者职责不同，不能合并。
--
-- 为什么 work_id 用 VARCHAR(32) 而不是 BIGINT：
--   works 表主键本身就是 VARCHAR(32)（格式「板块-原id」如 music-1），
--   外键类型必须与被引用列完全一致，否则 PG 建表直接报错。
--
-- 为什么 user_id 给默认值 'local'：
--   Day 17 还没有登录体系（Day 22+ 才做），先用固定值占位，
--   等接入用户系统后把默认值去掉、改为必填即可，历史数据不会因此失效。
--
-- 为什么 (user_id, work_id) 要唯一：
--   同一个人对同一件作品只应有一条收藏记录，加唯一约束后，
--   未来的写入接口可以用 ON CONFLICT (user_id, work_id) DO NOTHING 天然幂等。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS favorites (
  id          BIGSERIAL     NOT NULL,               -- 自增主键（代理键）
  user_id     VARCHAR(64)   NOT NULL DEFAULT 'local', -- 用户标识（Day 17 固定 local）
  work_id     VARCHAR(32)   NOT NULL,               -- 收藏的作品，关联 works.work_id
  note        VARCHAR(255),                         -- 收藏备注（可选，一句话）
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(), -- 收藏时间
  CONSTRAINT pk_favorites PRIMARY KEY (id),
  CONSTRAINT uq_favorites_user_work UNIQUE (user_id, work_id),
  -- 外键：作品改名跟着改；作品被删则连带删掉这条收藏（收藏离不开作品）
  CONSTRAINT fk_favorites_work FOREIGN KEY (work_id)
    REFERENCES works (work_id) ON UPDATE CASCADE ON DELETE CASCADE
);

COMMENT ON TABLE  favorites             IS '收藏表：存「谁收藏了哪个作品」。Day 17 只读，写入接口 Day 18';
COMMENT ON COLUMN favorites.id          IS '自增主键（代理键）。取消收藏时用它精确定位';
COMMENT ON COLUMN favorites.user_id     IS '用户标识。Day 17 无登录体系，固定 local 占位';
COMMENT ON COLUMN favorites.work_id     IS '收藏的作品，外键 → works.work_id（如 music-1）';
COMMENT ON COLUMN favorites.note        IS '收藏备注。可选，一句话说明为什么收藏';
COMMENT ON COLUMN favorites.created_at  IS '收藏时间，列表默认按它倒序';

-- 索引：列表接口按用户查收藏、按时间倒序，是最典型的两条查询路径
CREATE INDEX IF NOT EXISTS idx_favorites_user    ON favorites (user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_created ON favorites (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorites_work    ON favorites (work_id);
