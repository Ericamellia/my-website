# -*- coding: utf-8 -*-
"""核查 works 表 video 分类的 video_url / bvid / original_title 有没有值。"""
import json, urllib.request, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
ENV = {}
with open(os.path.join(ROOT, '.env'), 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % ENV['CLOUDBASE_ENV_ID']
KEY = ENV['CLOUDBASE_API_KEY']


def get(table, select, extra=''):
    url = BASE + table + '?select=' + select + extra
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + KEY})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


rows = get('works', 'work_id,category,name,video_url,video_platform,video_type,bvid,original_title',
           '&category=eq.video&order=work_id.asc')
print('=' * 78)
print('works 表里 category=video 的 6 条：')
print('=' * 78)
for r in rows:
    print('%-10s %-26s url=%-46s bvid=%s' % (
        r['work_id'], (r['name'] or '')[:24], str(r['video_url'])[:46], r['bvid']))
print()

# 对比本地 video.json
local = json.load(open(os.path.join(ROOT, 'my-app', 'data', 'video.json'), encoding='utf-8'))
print('本地 video.json 的 url：')
for x in local:
    print('  id=%-3s url=%-48s bvid=%s' % (x['id'], str(x.get('url'))[:48], x.get('bvid')))
