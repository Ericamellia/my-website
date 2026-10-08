# -*- coding: utf-8 -*-
"""
从 my-app/data/*.json 生成 db/seed.sql（Day 16 种子脚本）

目标数据库：CloudBase PostgreSQL
用法：
    python db/gen_seed.py

产出：db/seed.sql —— 26 条社团 + 30 条作品，幂等（可重复执行不报错）
幂等做法：INSERT ... ON CONFLICT (主键) DO UPDATE（PostgreSQL 幂等语法）
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'my-app', 'data')
OUT = os.path.join(ROOT, 'db', 'seed.sql')


def q(v):
    """把 Python 值转成 PostgreSQL 字面量。"""
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s.strip() == '':
        # 空字符串一律按 NULL 处理：源数据里有 followers:"" 这种情况，
        # 直接插 '' 会让整数列报错（invalid input syntax for type integer）
        return 'NULL'
    # PG 标准转义：单引号写成两个单引号；反斜杠无特殊含义（standard_conforming_strings=on）
    s = s.replace("'", "''")
    return "'" + s + "'"


def qj(v):
    """JSONB 专用：转成 JSON 字符串字面量，再显式 cast 成 jsonb。"""
    if v is None:
        return 'NULL'
    s = json.dumps(v, ensure_ascii=False).replace("'", "''")
    return "'" + s + "'::jsonb"


def qi(v):
    """整数专用：空串/非数字 → NULL，保证整数列不报错。"""
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, int):
        return str(v)
    s = str(v).strip()
    if s == '' or not s.lstrip('-').isdigit():
        return 'NULL'
    return s


lines = []
lines.append('-- ============================================================================')
lines.append('-- 东方同人搜索 · 种子数据（Day 16）')
lines.append('-- ============================================================================')
lines.append('-- 本文件由 db/gen_seed.py 自动生成，请勿手工编辑。')
lines.append('-- 目标数据库：CloudBase PostgreSQL')
lines.append('-- 数据源：my-app/data/circles.json + music/doujin/game/art/video.json')
lines.append('-- 幂等：全部使用 INSERT ... ON CONFLICT ... DO UPDATE，可重复执行不报错。')
lines.append('-- 执行顺序：先 circles 后 works（works 有外键指向 circles）。')
lines.append('-- ============================================================================')
lines.append('')

# ---------------- 表 1：circles ----------------
circles = json.load(open(os.path.join(DATA, 'circles.json'), encoding='utf-8'))
lines.append('-- ----------------------------------------------------------------------------')
lines.append(f'-- 表 1：circles　社团/作者　共 {len(circles)} 条')
lines.append('-- ----------------------------------------------------------------------------')
for c in circles:
    tp = c.get('top_platform') or {}
    tp = tp if isinstance(tp, dict) else {}
    cols = ['name', 'name_en', 'intro', 'source_url', 'avatar',
            'top_platform', 'followers', 'platform_url']
    vals = [
        q(c.get('name')),
        q(c.get('name_en')),
        q(c.get('intro')),
        q(c.get('source_url')),
        q(c.get('avatar')),
        q(tp.get('name')),
        qi(tp.get('followers')),
        q(tp.get('url')),
    ]
    upd = ', '.join(f'"{k}"=EXCLUDED."{k}"' for k in cols[1:])
    lines.append(
        f"INSERT INTO circles ({', '.join('\"' + k + '\"' for k in cols)}) "
        f"VALUES ({', '.join(vals)}) ON CONFLICT (name) DO UPDATE SET {upd};"
    )
lines.append('')

# ---------------- 表 2：works ----------------
CATS = ['music', 'doujin', 'game', 'art', 'video']
works = []
for cat in CATS:
    for it in json.load(open(os.path.join(DATA, f'{cat}.json'), encoding='utf-8')):
        works.append((cat, it))

lines.append('-- ----------------------------------------------------------------------------')
lines.append(f'-- 表 2：works　作品　共 {len(works)} 条')
lines.append('-- work_id = 「板块-原id」，避免五个板块 id 从 1 开始互相撞车')
lines.append('-- ----------------------------------------------------------------------------')
for cat, w in works:
    work_id = f"{cat}-{w.get('id')}"
    cols = ['work_id', 'category', 'name', 'circle_name', 'creator', 'year',
            'characters', 'tags', 'popularity', 'views', 'cover', 'source_url',
            'description', 'netease_url', 'video_type', 'video_platform',
            'video_url', 'bvid', 'original_title']
    vals = [
        q(work_id),
        q(cat),
        q(w.get('name')),
        q(w.get('circle')),
        q(w.get('creator')),
        qi(w.get('year')),
        qj(w.get('characters')),
        qj(w.get('tags')),
        qi(w.get('popularity')),
        qi(w.get('views') if w.get('views') is not None else 0),
        q(w.get('cover')),
        q(w.get('source_url')),
        q(w.get('description')),
        q(w.get('netease_url')),
        q(w.get('type')),          # JSON 里叫 type，表里叫 video_type
        q(w.get('platform')),      # JSON 里叫 platform，表里叫 video_platform
        q(w.get('url')),           # JSON 里叫 url，表里叫 video_url
        q(w.get('bvid')),
        q(w.get('original_title')),
    ]
    upd = ', '.join(f'"{k}"=EXCLUDED."{k}"' for k in cols[1:])
    lines.append(
        f"INSERT INTO works ({', '.join('\"' + k + '\"' for k in cols)}) "
        f"VALUES ({', '.join(vals)}) ON CONFLICT (work_id) DO UPDATE SET {upd};"
    )

lines.append('')
lines.append('-- ----------------------------------------------------------------------------')
lines.append('-- 验证：每张表应至少 5 行')
lines.append('--   SELECT COUNT(*) FROM circles;   -- 期望 26')
lines.append('--   SELECT COUNT(*) FROM works;     -- 期望 30')
lines.append('-- ----------------------------------------------------------------------------')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')

print(f'✅ 已生成 {OUT}')
print(f'   circles: {len(circles)} 条')
print(f'   works:   {len(works)} 条  （' + ', '.join(f'{c}:{sum(1 for x in works if x[0] == c)}' for c in CATS) + '）')
print(f'   文件大小: {os.path.getsize(OUT)} 字节')
