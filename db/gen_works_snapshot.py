# -*- coding: utf-8 -*-
"""
生成 deploy/data/works.json —— 作品表的 JSON 快照（Day 18）

为什么需要它：
    Day 18 的 POST /api/favorites 要判断「收藏的作品是否存在」，
    并且写入成功后要把作品详情（名称/社团/封面）带进返回体 —— 与 GET 返回体形状一致。
    公网版连不上库，所以把 works 表的数据做成快照。

数据怎么来的：
    my-app/data/{music,doujin,game,art,video}.json（站内作品源数据），
    按 work_id = "{板块}-{原id}" 展开，字段口径与 works 表一致。

用法：python db/gen_works_snapshot.py
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'deploy', 'data', 'works.json')

CATS = ['music', 'doujin', 'game', 'art', 'video']

items = []
for cat in CATS:
    p = os.path.join(ROOT, 'my-app', 'data', f'{cat}.json')
    if not os.path.exists(p):
        print(f'  ⚠ 跳过 {cat}：文件不存在')
        continue
    for w in json.load(io.open(p, encoding='utf-8')):
        items.append({
            'workId': f"{cat}-{w.get('id')}",
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
        })

# 与 works 表口径一致：按 work_id 排序，保证每次生成结果稳定
items.sort(key=lambda x: (x['category'], x['workId']))

snap = {
    '_origin': 'works 表快照（由 my-app/data/*.json 生成，字段口径与 works 表一致）',
    '_note': 'Day 18 的 POST /api/favorites 用它校验「作品是否存在」并带出作品详情。',
    'count': len(items),
    'items': items,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(snap, f, ensure_ascii=False, indent=2)
    f.write('\n')

from collections import Counter
print(f'✅ 已生成 {OUT}（{os.path.getsize(OUT)} 字节，{len(items)} 条作品）')
print('   分板块：', dict(Counter(x['category'] for x in items)))
for x in items[:5]:
    print(f"   {x['workId']:10s} {x['name'][:34]}")
