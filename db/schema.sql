-- ============================================================================
-- 东方同人搜索 · 数据库表结构（Day 16 起，Day 17 扩充）
-- ============================================================================
-- 目标数据库：CloudBase PostgreSQL（SQL 数据库 → PostgreSQL 管理）
-- 表数量：4 张 —— circles（社团）/ works（作品）/ favorites（收藏）/ hot_videos（热搜）
-- 关联字段：
--   works.circle_name     → circles.name
--   favorites.work_id     → works.work_id
--   hot_videos 独立（外部平台同步表，不与其他表关联）
--
-- 执行方式：CloudBase 控制台 → SQL 数据库 → SQL 编辑器 → 粘贴执行
-- 幂等性：全部使用 CREATE TABLE IF NOT EXISTS，可重复执行不报错
--
-- 单表独立文件（只想补某张表时用）：
--   db/schema-favorites.sql（表 3）· db/schema-hot.sql（表 4）
--
-- PostgreSQL 版本要点（与 MySQL 的差异）：
--   ① 不用反引号，标识符用双引号或直接裸写
--   ② 没有 ENGINE / CHARSET 子句（PG 默认 UTF-8）
--   ③ KEY xxx 索引要单独写 CREATE INDEX，不能写在建表语句里
--   ④ 注释用 COMMENT ON COLUMN 单独语句（比 MySQL 内联 COMMENT 更规范）
--   ⑤ JSON 用 JSONB（二进制存储、可建 GIN 索引、支持 @> 包含查询）
--   ⑥ 自增主键用 BIGSERIAL（不是 MySQL 的 AUTO_INCREMENT）
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 表 1：circles　社团 / 作者表
-- ----------------------------------------------------------------------------
-- 存什么：「谁做的」。一个社团产出多个作品，是 works 的「一方」。
-- 主键为什么是 name：现有数据 circles.json 里社团的唯一标识就是名字，
--   作品表也是靠字符串名字引用社团，用 name 做主键可避免额外维护一份 id 映射。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS circles (
  name            VARCHAR(128)  NOT NULL,          -- 社团/作者名（主键）
  name_en         VARCHAR(128),                    -- 英文名/罗马音
  intro           TEXT,                            -- 社团简介，1–3 句中文
  source_url      VARCHAR(512),                    -- 资料源页 URL（THBWiki 等）
  avatar          VARCHAR(255),                    -- 社团头像路径
  top_platform    VARCHAR(32),                     -- 主要活动平台
  followers       INTEGER,                         -- 该平台粉丝数
  platform_url    VARCHAR(512),                    -- 平台主页 URL
  created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),  -- 入库时间
  CONSTRAINT pk_circles PRIMARY KEY (name)
);

COMMENT ON TABLE  circles              IS '社团/作者表：存「谁做的」，被 works.circle_name 引用';
COMMENT ON COLUMN circles.name         IS '社团/作者名（主键）。如 COOL&CREATE、劇毒少女';
COMMENT ON COLUMN circles.name_en      IS '英文名/罗马音。如 A-One、Team Ladybug';
COMMENT ON COLUMN circles.intro        IS '社团简介，1–3 句中文。长度不定故用 TEXT';
COMMENT ON COLUMN circles.source_url   IS '资料源页 URL（THBWiki 等）。可能含中文，故给 512';
COMMENT ON COLUMN circles.avatar       IS '社团头像路径。如 assets/circles/A-One.jpg';
COMMENT ON COLUMN circles.top_platform IS '主要活动平台。如 bilibili / pixiv / steam';
COMMENT ON COLUMN circles.followers    IS '该平台粉丝数。无平台信息时为 NULL，故允许空';
COMMENT ON COLUMN circles.platform_url IS '平台主页 URL。如 B 站空间链接';
COMMENT ON COLUMN circles.created_at   IS '入库时间，便于排查数据批次';

-- 按英文名查询（角色/社团检索页会用到）
CREATE INDEX IF NOT EXISTS idx_circles_name_en ON circles (name_en);


-- ----------------------------------------------------------------------------
-- 表 2：works　作品表
-- ----------------------------------------------------------------------------
-- 存什么：「做了什么」。五个板块（音乐/漫画/游戏/图/视频）合并为一张表，
--   靠 category 字段区分 —— 因为五个 JSON 的字段 95% 重合，
--   拆五张表会产生大量重复结构、跨板块搜索还要 UNION，反而更麻烦。
--
-- 主键为什么是 work_id 而不是 id：
--   五个板块各自都有从 1 开始的 id（music 有 1-6，doujin 也有 1-6），
--   直接拿原 id 做主键会撞车。所以用「板块前缀 + 原 id」拼成全局唯一键，
--   如 music-1、video-3。这样既保留可读性，又能从主键反推来源。
--
-- 关联字段为什么是 circle_name 而不是 circle_id：
--   现有数据里作品就是用社团名字符串引用的（"circle": "COOL&CREATE"），
--   且 circles 表主键就是 name，直接对应即可，无需再维护数字外键。
--   已核验：30 条作品引用的 26 个社团，circles 表全部存在，无孤儿记录。
--
-- 数组字段为什么用 JSONB：
--   characters（登场角色）与 tags（标签）都是变长列表，
--   长度不固定（1–4 个角色不等），单独建关联表对 MVP 阶段是过度设计。
--   存成 JSONB 后，后续搜索接口用 @> 或 jsonb_array_elements 即可查询。
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS works (
  work_id         VARCHAR(32)   NOT NULL,          -- 作品主键，格式「板块-原id」
  category        VARCHAR(16)   NOT NULL,          -- 板块
  name            VARCHAR(255)  NOT NULL,          -- 作品名
  circle_name     VARCHAR(128),                    -- 社团名，关联 circles.name
  creator         VARCHAR(128),                    -- 作者/主催个人名
  year            SMALLINT,                        -- 发行年份
  characters      JSONB,                           -- 登场角色名数组
  tags            JSONB,                           -- 标签数组
  popularity      INTEGER,                         -- 热度值
  views           INTEGER       NOT NULL DEFAULT 0,-- 站内浏览量
  cover           VARCHAR(512),                    -- 封面图路径或外链
  source_url      VARCHAR(512),                    -- 原发布页 URL
  description     TEXT,                            -- 1–2 句中文简介

  -- 板块专属字段：只为部分板块填充，其余板块为 NULL。
  -- 不拆表而是合并存放，代价是这几列稀疏，收益是查询接口无需按板块分叉。
  netease_url     VARCHAR(512),                    -- [仅 music] 网易云链接
  video_type      VARCHAR(64),                     -- [仅 video] 视频类型
  video_platform  VARCHAR(32),                     -- [仅 video] 视频平台
  video_url       VARCHAR(512),                    -- [仅 video] 视频直链
  bvid            VARCHAR(32),                     -- [仅 video] B站视频号
  original_title  VARCHAR(255),                    -- [仅 video] 原曲名

  created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

  CONSTRAINT pk_works PRIMARY KEY (work_id),
  -- 外键：社团改名跟着改；社团删除则置空而非删作品
  CONSTRAINT fk_works_circle FOREIGN KEY (circle_name)
    REFERENCES circles (name) ON UPDATE CASCADE ON DELETE SET NULL
);

COMMENT ON TABLE  works                 IS '作品表：存「做了什么」，五板块合并，靠 category 区分';
COMMENT ON COLUMN works.work_id         IS '作品主键，格式「板块-原id」。如 music-1、video-3';
COMMENT ON COLUMN works.category        IS '板块。music/doujin/game/art/video 五选一';
COMMENT ON COLUMN works.name            IS '作品名。可能较长（含副标题），故给 255';
COMMENT ON COLUMN works.circle_name     IS '社团名，关联 circles.name。部分作品无社团信息时为 NULL';
COMMENT ON COLUMN works.creator         IS '作者/主催个人名。如 有泉、あにら';
COMMENT ON COLUMN works.year            IS '发行年份。SMALLINT 足够（范围 ±32767），比 INTEGER 省 2 字节';
COMMENT ON COLUMN works.characters      IS '登场角色名数组。如 ["博丽灵梦","雾雨魔理沙"]';
COMMENT ON COLUMN works.tags            IS '标签数组。如 ["红魔乡","东方Project"]';
COMMENT ON COLUMN works.popularity      IS '热度值（人工评估/平台数据）。用于排序，不参与计算';
COMMENT ON COLUMN works.views           IS '站内浏览量。计数场景不能为 NULL，故给默认值 0';
COMMENT ON COLUMN works.cover           IS '封面图路径或外链。B站封面是完整 URL，故给 512';
COMMENT ON COLUMN works.source_url      IS '原发布页 URL（thwiki/pixiv/steam/B站）';
COMMENT ON COLUMN works.description     IS '1–2 句中文简介。可能超 255 字，故用 TEXT';
COMMENT ON COLUMN works.netease_url     IS '[仅 music] 网易云播放/搜索直达链接';
COMMENT ON COLUMN works.video_type      IS '[仅 video] 视频类型。如 影绘动画';
COMMENT ON COLUMN works.video_platform  IS '[仅 video] 视频平台。如 bilibili';
COMMENT ON COLUMN works.video_url       IS '[仅 video] 视频直链';
COMMENT ON COLUMN works.bvid            IS '[仅 video] B站视频号。如 BV1xx411c79H';
COMMENT ON COLUMN works.original_title  IS '[仅 video] 原曲名。如 Bad Apple!!（东方幻想乡）';
COMMENT ON COLUMN works.created_at      IS '入库时间';

-- 索引：列表页按板块筛选是最高频查询
CREATE INDEX IF NOT EXISTS idx_works_category   ON works (category);
CREATE INDEX IF NOT EXISTS idx_works_circle     ON works (circle_name);  -- 社团查询 / 关联查询
CREATE INDEX IF NOT EXISTS idx_works_year       ON works (year);         -- 按年份排序
CREATE INDEX IF NOT EXISTS idx_works_popularity ON works (popularity);   -- 按热度排序
-- JSONB 的 GIN 索引：让 tags @> '["红魔乡"]' 这类标签包含查询能走索引
CREATE INDEX IF NOT EXISTS idx_works_tags       ON works USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_works_characters ON works USING GIN (characters);


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


CREATE TABLE IF NOT EXISTS hot_videos (
  bvid         VARCHAR(32)   NOT NULL,          -- B站视频号，主键（天然去重键）
  board        VARCHAR(16)   NOT NULL DEFAULT 'hot', -- 榜单：fresh=当日新 / hot=历史热门
  title        VARCHAR(300)  NOT NULL,          -- 视频标题（B站标题最长可到 80 字，留足余量）
  author       VARCHAR(128),                    -- UP 主名字
  mid          BIGINT,                          -- UP 主 UID
  play         BIGINT        NOT NULL DEFAULT 0,-- 播放量
  danmaku      BIGINT        NOT NULL DEFAULT 0,-- 弹幕数
  favorites    BIGINT        NOT NULL DEFAULT 0,-- 收藏数
  duration     VARCHAR(16),                     -- 时长（B站给的是 "3:39" 格式，直接存字符串）
  typename     VARCHAR(32),                     -- B站分区名，如「同人·手书」
  pubdate      BIGINT,                          -- 发布日期（Unix 时间戳，秒）
  cover        VARCHAR(512),                    -- 封面图 URL（B站图床）
  description  TEXT,                            -- 视频简介（截断到 200 字）
  source       VARCHAR(32)   NOT NULL DEFAULT 'bilibili', -- 数据来源平台
  rank_no      SMALLINT,                        -- 在所属榜单里的名次（1 开始）
  synced_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(), -- 本次同步时间
  CONSTRAINT pk_hot_videos PRIMARY KEY (bvid)
);

COMMENT ON TABLE  hot_videos              IS '热搜榜同步表：B站东方视频快照，由 sync_hot.py 覆盖式刷新';
COMMENT ON COLUMN hot_videos.bvid         IS 'B站视频号，主键。如 BV1xx411c79H，天然去重键';
COMMENT ON COLUMN hot_videos.board        IS '榜单归属：fresh=当日/昨日新发布，hot=历史热门';
COMMENT ON COLUMN hot_videos.title        IS '视频标题（已去掉搜索结果的高亮标签）';
COMMENT ON COLUMN hot_videos.author       IS 'UP 主名字';
COMMENT ON COLUMN hot_videos.mid          IS 'UP 主 UID，用于跳到 UP 主主页';
COMMENT ON COLUMN hot_videos.play         IS '播放量。BIGINT 因为头部视频可上亿';
COMMENT ON COLUMN hot_videos.danmaku      IS '弹幕数，衡量讨论热度';
COMMENT ON COLUMN hot_videos.favorites    IS '收藏数';
COMMENT ON COLUMN hot_videos.duration     IS '时长。"3:39" 这种格式，原样存字符串';
COMMENT ON COLUMN hot_videos.typename     IS 'B站分区名。如 同人·手书 / MMD·3D / 单机游戏';
COMMENT ON COLUMN hot_videos.pubdate      IS '发布日期（Unix 时间戳，秒）。查询时用 to_timestamp(pubdate)';
COMMENT ON COLUMN hot_videos.cover        IS '封面图 URL（B站图床 i0.hdslb.com）';
COMMENT ON COLUMN hot_videos.description  IS '视频简介，已截断到 200 字';
COMMENT ON COLUMN hot_videos.source       IS '数据来源平台，当前恒为 bilibili';
COMMENT ON COLUMN hot_videos.rank_no      IS '在所属榜单里的名次，从 1 开始。接口默认按它排序';
COMMENT ON COLUMN hot_videos.synced_at    IS '本次同步时间，用于判断数据新鲜度';

-- 索引：接口最典型的查询是「按榜单取前 N 条」，所以 (board, rank_no) 联合索引
CREATE INDEX IF NOT EXISTS idx_hot_board_rank ON hot_videos (board, rank_no);
CREATE INDEX IF NOT EXISTS idx_hot_play       ON hot_videos (play DESC);      -- 按播放排序
CREATE INDEX IF NOT EXISTS idx_hot_pubdate    ON hot_videos (pubdate DESC);   -- 按时间排序
