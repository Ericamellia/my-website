# -*- coding: utf-8 -*-
"""查看 works 表真实结构与分类分布。"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENV_PATH = os.path.join(ROOT, 'deploy', '.env')

env = {}
with open(ENV_PATH, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env['CLOUDBASE_ENV_ID']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(q):
    req = urllib.request.Request(base + q)
    req.add_header('Authorization', 'Bearer ' + env['CLOUDBASE_API_KEY'])
    with opener.open(req, timeout=25) as r:
        return json.load(r)


print('=== works 表：单条结构 ===')
rows = get('works?select=*&limit=1')
if rows:
    print(json.dumps(rows[0], ensure_ascii=False, indent=2))

print('\n=== works 表：按 category 分组计数 ===')
allrows = get('works?select=category')
from collections import Counter
c = Counter(r.get('category') for r in allrows)
for k, v in c.most_common():
    print('  %-10s %d' % (k, v))
print('  合计 %d' % len(allrows))

print('\n=== circles 表：单条结构 ===')
cr = get('circles?select=*&limit=1')
if cr:
    print(json.dumps(cr[0], ensure_ascii=False, indent=2))
