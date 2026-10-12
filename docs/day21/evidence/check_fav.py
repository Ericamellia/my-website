# -*- coding: utf-8 -*-
"""Day 21 周验收：读回 favorites 并高亮本次新增行。"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'docs/day21/evidence/_fav_after.json'
d = json.load(open(path, encoding='utf-8'))
print('写后 count =', d.get('count'), ' source =', d.get('source'))
for it in d.get('data', []):
    note = it.get('note') or ''
    mark = ' <== 本次新增' if note.startswith('Day21') else ''
    print('  #%s %s%s' % (it.get('id'), it.get('workId'), mark))
