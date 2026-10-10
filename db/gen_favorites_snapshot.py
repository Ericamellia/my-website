# -*- coding: utf-8 -*-
"""
生成 deploy/data/favorites.json —— 收藏列表的 JSON 快照（Day 17）

为什么需要它：
    公网上的 deploy/server.js 连不到 CloudBase PostgreSQL（跨沙箱），
    所以 GET /api/favorites 在没有数据库连接串时，读这份快照。
    快照内容与 db/seed-favorites.sql 灌进库里的数据**同源同批**。

数据怎么来的：
    收藏记录在 db/seed-favorites.sql 里（work_id + note），
    作品详情（name/circle/cover…）在 my-app/data/*.json 里，
    这里把两边 JOIN 起来，生成接口直接可用的结构。

用法：python db/gen_favorites_snapshot.py
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'deploy', 'data', 'favorites.json')
DEFAULT_USER = 'local'


def load_works():
    """把 my-app/data/{板块}.json 里的作品按 work_id 建索引（与 works 表口径一致）。"""
    idx = {}
    for cat in ['music', 'doujin', 'game', 'art', 'video']:
        p = os.path.join(ROOT, 'my-app', 'data', f'{cat}.json')
        if not os.path.exists(p):
            continue
        for w in json.load(io.open(p, encoding='utf-8')):
            wid = f"{cat}-{w.get('id')}"
            idx[wid] = {
                'workId': wid,
                'category': cat,
                'name': w.get('name', ''),
                'circle': w.get('circle') or '',
                'creator': w.get('creator') or '',
                'year': w.get('year'),
                'cover': w.get('cover') or '',
                'tags': w.get('tags') or [],
                'characters': w.get('characters') or [],
                'description': w.get('description') or '',
                'sourceUrl': w.get('source_url') or '',
            }
    return idx


def load_favorites():
    """从 db/seed-favorites.sql 里解析出收藏记录。"""
    p = os.path.join(ROOT, 'db', 'seed-favorites.sql')
    t = io.open(p, encoding='utf-8').read()
    rows = []
    for ln in t.split('\n'):
        if not ln.startswith('INSERT INTO favorites'):
            continue
        m = re.search(
            r"VALUES \('([^']*)', '([^']*)', (?:'((?:[^']|'')*)'|NULL)\)", ln)
        if not m:
            continue
        rows.append({
            'userId': m.group(1),
            'workId': m.group(2),
            'note': (m.group(3) or '').replace("''", "'"),
        })
    return rows


works = load_works()
favs = load_favorites()

items = []
for i, f in enumerate(favs, 1):
    w = works.get(f['workId'])
    if not w:
        print(f'  ⚠ 跳过 {f["workId"]}：works 数据里没有这个 work_id')
        continue
    items.append({
        'id': i,
        'userId': f['userId'],
        'note': f['note'],
        **w,
    })

snap = {
    'userId': DEFAULT_USER,
    'count': len(items),
    'items': items,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fp:
    json.dump(snap, fp, ensure_ascii=False, indent=2)
    fp.write('\n')

print(f'✅ 已生成 {OUT}（{os.path.getsize(OUT)} 字节，{len(items)} 条收藏）')
for it in items:
    print(f"   #{it['id']}  {it['workId']:10s}  {it['name'][:30]}")
