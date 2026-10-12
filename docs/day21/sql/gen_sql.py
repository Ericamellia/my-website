# -*- coding: utf-8 -*-
"""
Day 21 路线B：从 my-app/data/*.json 生成「建表 + 导数据」SQL。
产出 docs/day21/sql/ 下：
  - schema.sql            建 4 张表（含 original_game_categories）
  - seed-original-games.sql   （分块，防控制台截断）
  - seed-characters.sql       （分块）
  - seed-originals.sql
  - seed-og-categories.sql
成品：docs/day21/sql/ALL.sql（按顺序拼接，供一次粘贴）
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA = os.path.join(ROOT, 'my-app', 'data')
OUT = os.path.join(ROOT, 'docs', 'day21', 'sql')
os.makedirs(OUT, exist_ok=True)


def load(name):
    with open(os.path.join(DATA, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def q(v):
    """把任意值转成 SQL 字面量。字符串压平换行 + 单引号转义（Day17 教训）。"""
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, dict)):
        # 数组/对象 → jsonb 字面量
        s = json.dumps(v, ensure_ascii=False)
        return "'" + s.replace('\\', '\\\\').replace("'", "''") + "'::jsonb"
    s = str(v).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    s = ' '.join(s.split())
    return "'" + s.replace("'", "''") + "'"


def qtext_array(v):
    """字符串数组 → Postgres text[] 字面量。"""
    if not v:
        return "'{}'::text[]"
    items = ','.join('"' + str(x).replace('\\', '\\\\').replace('"', '\\"') + '"' for x in v)
    return "'{" + items + "}'::text[]"


# ---------------------------------------------------------------- schema
SCHEMA = """-- Day 21 路线B 建表：把 my-app 的三类本地数据搬进真库
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
"""

with open(os.path.join(OUT, 'schema.sql'), 'w', encoding='utf-8') as f:
    f.write(SCHEMA)

# ---------------------------------------------------------------- seeds
og = load('original_games')
chars = load('characters')['characters']
originals = load('originals')

# 分类
lines = ['-- original_game_categories（5 条）',
         'INSERT INTO original_game_categories (id, label, sort_order) VALUES']
vals = []
for i, c in enumerate(og['categories']):
    vals.append('(%s, %s, %d)' % (q(c['id']), q(c['label']), i))
lines.append(',\n'.join(vals) + '\nON CONFLICT (id) DO NOTHING;')
cat_sql = '\n'.join(lines) + '\n'
open(os.path.join(OUT, 'seed-og-categories.sql'), 'w', encoding='utf-8').write(cat_sql)


# 通用分块函数
def chunks(rows, size):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def write_chunked(path, header, insert_prefix, row_sqls, size=10):
    parts = [header]
    for idx, chunk in enumerate(chunks(row_sqls, size), 1):
        parts.append('-- 块 %d（%d 条）' % (idx, len(chunk)))
        parts.append(insert_prefix)
        parts.append(',\n'.join(chunk) + '\nON CONFLICT (id) DO NOTHING;')
        parts.append('')
    open(path, 'w', encoding='utf-8').write('\n'.join(parts) + '\n')
    return '\n'.join(parts) + '\n'


# 原作作品（year 统一按 TEXT 输出：单年也加引号）
og_rows = []
for g in og['games']:
    y = g.get('year')
    y_sql = q(str(y)) if y is not None else 'NULL'
    og_rows.append('(%s, %s, %s, %s, %s, %s, %s, %s)' % (
        q(g['id']), q(g.get('th')), q(g['title']), q(g.get('subtitle')),
        q(g.get('category')), y_sql, q(g.get('cover')), q(g.get('tag'))))
og_sql = write_chunked(
    os.path.join(OUT, 'seed-original-games.sql'),
    '-- original_games（39 条）',
    'INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES',
    og_rows, size=10)

# 角色
ch_rows = []
for c in chars:
    m = c.get('moegirl')
    m_sql = ('%s::jsonb' % q(json.dumps(m, ensure_ascii=False))) if isinstance(m, dict) else 'NULL'
    ch_rows.append('(%s, %s, %s, %s, %s, %s, %s, %s)' % (
        q(c['id']), q(c['name']), q(c.get('name_en')),
        qtext_array(c.get('games')), qtext_array(c.get('playableIn')),
        q(c.get('twilight_art')), m_sql, q(c.get('source_url'))))
ch_sql = write_chunked(
    os.path.join(OUT, 'seed-characters.sql'),
    '-- characters（112 条）',
    'INSERT INTO characters (id, name, name_en, games, playable_in, twilight_art, moegirl, source_url) VALUES',
    ch_rows, size=10)

# 原曲
or_rows = []
for o in originals:
    or_rows.append('(%s, %s, %s, %s, %s)' % (
        q(o['id']), q(o['title']), q(o.get('game')), q(o.get('track_no')), q(o.get('description'))))
or_sql = write_chunked(
    os.path.join(OUT, 'seed-originals.sql'),
    '-- originals（6 条）',
    'INSERT INTO originals (id, title, game, track_no, description) VALUES',
    or_rows, size=10)

# 拼接总文件
ALL = SCHEMA + '\n' + cat_sql + '\n' + og_sql + '\n' + ch_sql + '\n' + or_sql
open(os.path.join(OUT, 'ALL.sql'), 'w', encoding='utf-8').write(ALL)

print('已生成：')
for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    print('  %-28s %6d bytes' % (fn, os.path.getsize(p)))
print()
print('条数核对：categories=%d  original_games=%d  characters=%d  originals=%d'
      % (len(og['categories']), len(og['games']), len(chars), len(originals)))
