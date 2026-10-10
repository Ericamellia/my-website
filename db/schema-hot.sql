-- ============================================================================
-- 东方同人搜索 · 表 4：hot_videos（Day 17 新增）
-- ============================================================================
-- 本文件是 db/schema.sql 里 hot_videos 那一段的独立副本，方便单独粘贴执行。
-- 已经整份跑过 db/schema.sql 的话，本文件不用再跑（内容重复但幂等，跑了也没事）。
--
-- 这张表存什么：
--   从 B 站同步回来的「东方相关视频热搜榜」。它是一张**同步表 / 缓存表**，
--   不是用户产生的内容 —— 数据由 db/sync_hot.py 定期覆盖式刷新。
--
-- 为什么单独建表而不塞进 works：
--   works 是「我们的作品库」（人工整理、字段稳定、永久保留）；
--   hot_videos 是「外部平台的热度快照」（机器抓取、随时变化、可整体覆盖）。
--   两者生命周期完全不同：清理热搜榜不应该动到作品库。混在一起以后必然打架。
--
-- 为什么有 board 字段：
--   榜单有两种语义，实测发现必须分开，否则「当日热搜」会被历史老视频淹没：
--     fresh = 当日/昨日新发布（按发布时间倒序）
--     hot   = 历史热门（按播放量倒序）
--   一张表用 board 区分，接口按 board 查，前端可做 Tab 切换。
--
-- 为什么 bvid 是主键：
--   bvid 是 B 站视频的全局唯一编号（如 BV1xx411c79H），
--   天然去重键 —— 同步脚本重复跑不会产生重复行。
--
-- 为什么 pubdate 用 BIGINT 而不是 TIMESTAMPTZ：
--   B 站返回的是 Unix 时间戳（秒）。原样存 BIGINT 有个好处：
--   以后要换成别的时间格式不用改表结构，且前端 new Date(ts*1000) 直接用。
--   代价是 SQL 里看时间要 to_timestamp(pubdate)，可接受。
-- ============================================================================

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
