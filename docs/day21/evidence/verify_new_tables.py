# -*- coding: utf-8 -*-
"""Day 21 路线B：核对 4 张新表行数是否符合预期。"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env = {}
with open(os.path.join(ROOT, 'deploy', '.env'), encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env['CLOUDBASE_ENV_ID']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

expect = {
    'original_game_categories': 5,
    'original_games': 39,
    'characters': 112,
    'originals': 6,
}
rules = {
    'original_game_categories': 'id', 'original_games': 'id',
    'characters': 'id', 'originals': 'id',
}

print('%-26s %8s %8s  %s' % ('表', '期望', '实际', '结果'))
print('-' * 58)
allok = True
for t, exp in expect.items():
    req = urllib.request.Request(base + t + '?select=' + rules[t])
    req.add_header('Authorization', 'Bearer ' + env['CLOUDBASE_API_KEY'])
    try:
        with opener.open(req, timeout=25) as r:
            rows = json.load(r)
        n = len(rows)
        ok = (n == exp)
        allok = allok and ok
        print('%-26s %8d %8d  %s' % (t, exp, n, 'OK' if ok else '!! 不符'))
    except Exception as e:
        allok = False
        print('%-26s %8d %8s  ERR %s' % (t, exp, '-', str(e)[:30]))

print()
print('结论：', '全部符合 ✓' if allok else '有差异，见上表')
