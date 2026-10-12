-- Day 21 路线B 建表：把 my-app 的三类本地数据搬进真库
-- 说明：works / circles / favorites / hot_videos 已存在，这里只建缺的 4 张。
-- 复杂字段处理：数组 → text[]；对象（moegirl）→ jsonb。

-- 1. 原作分类（original_games.json → categories，仅 5 条）
CREATE TABLE IF NOT EXISTS original_game_categories (
  id          TEXT PRIMARY KEY,
  label       TEXT NOT NULL,
  sort_order  INTEGER,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 2. 原作作品（original_games.json → games，39 条）
-- 注意：year 用 TEXT 而非 INTEGER —— 8 条官方漫画是「连载年份区间」（如 2005–2007），
--      不是单一年份，强转整数会报 22P02。前端两种都能渲染。
CREATE TABLE IF NOT EXISTS original_games (
  id          TEXT PRIMARY KEY,          -- th01 / th06 ...
  th          TEXT,                       -- Th01
  title       TEXT NOT NULL,
  subtitle    TEXT,
  category    TEXT,                       -- old/new/fight/spin/manga
  year        TEXT,                       -- 单年 "1996" 或区间 "2005–2007"
  cover       TEXT,
  tag         TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 3. 角色（characters.json → characters，112 条）
CREATE TABLE IF NOT EXISTS characters (
  id            TEXT PRIMARY KEY,         -- reimu
  name          TEXT NOT NULL,
  name_en       TEXT,
  games         TEXT[],                   -- 登场作品 id 列表
  playable_in   TEXT[],                   -- 可作为自机的作品 id 列表
  twilight_art  TEXT,
  moegirl       JSONB,                    -- {intro, basic{...}}
  source_url    TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 4. 原曲（originals.json，6 条）
CREATE TABLE IF NOT EXISTS originals (
  id          TEXT PRIMARY KEY,          -- 001
  title       TEXT NOT NULL,
  game        TEXT,
  track_no    INTEGER,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);
