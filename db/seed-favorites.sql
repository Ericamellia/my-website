-- ============================================================================
-- 东方同人搜索 · favorites 示例收藏数据（Day 17）
-- ============================================================================
-- 执行前提：先跑 db/schema-favorites.sql 建好 favorites 表（依赖 works 表已存在）
-- 幂等：ON CONFLICT (user_id, work_id) DO UPDATE，可重复执行不报错
-- 说明：Day 17 无登录体系，user_id 统一用 local 占位
-- ============================================================================

-- 共 7 条示例收藏
-- music-1  ハルトマンの妖怪少女
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'music-1', '东方同人音乐入门必听，循环一整周') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- music-2  チルノのパーフェクトさんすう教室
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'music-2', '社团代表作，编曲很稳') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- doujin-1  - Bibliotheca - 劇毒少女 publication number V
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'doujin-1', '画风对味，四格节奏舒服') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- game-1  东方月神夜（Touhou Luna Nights）
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'game-1', '东方玩法还原度很高') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- art-1  LAST WORDS
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'art-1', '立绘细节惊艳，收藏参考') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- video-1  Bad Apple!! feat. nomico（影绘PV）
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'video-1', 'Bad Apple 影绘，永不过时') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;
-- video-2  魔理沙は大変なものを盗んでいきました
INSERT INTO favorites (user_id, work_id, note) VALUES ('local', 'video-2', '手书叙事强，值得二刷') ON CONFLICT (user_id, work_id) DO UPDATE SET note = EXCLUDED.note;

-- 验证：
--   SELECT COUNT(*) FROM favorites;   -- 期望 7
--   SELECT f.id, f.work_id, w.name, f.note FROM favorites f
--     JOIN works w ON w.work_id = f.work_id ORDER BY f.created_at DESC;

