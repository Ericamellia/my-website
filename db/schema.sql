-- ============================================================================
-- 东方同人搜索 · 数据库表结构（Day 16）
-- ============================================================================
-- 目标数据库：CloudBase PostgreSQL（SQL 数据库 → PostgreSQL 管理）
-- 表数量：2 张核心表 —— circles（社团）/ works（作品）
-- 关联字段：works.circle_name  →  circles.name
--
-- 执行方式：CloudBase 控制台 → SQL 数据库 → SQL 编辑器 → 粘贴执行
-- 幂等性：全部使用 CREATE TABLE IF NOT EXISTS，可重复执行不报错
--
-- PostgreSQL 版本要点（与 MySQL 的差异）：
--   ① 不用反引号，标识符用双引号或直接裸写
--   ② 没有 ENGINE / CHARSET 子句（PG 默认 UTF-8）
--   ③ KEY xxx 索引要单独写 CREATE INDEX，不能写在建表语句里
--   ④ 注释用 COMMENT ON COLUMN 单独语句（比 MySQL 内联 COMMENT 更规范）
--   ⑤ JSON 用 JSONB（二进制存储、可建 GIN 索引、支持 @> 包含查询）
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
