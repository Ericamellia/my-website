# -*- coding: utf-8 -*-
"""端到端验证：my-app 页面走真库接口能拿到完整数据。

做法：
  1. 起 Node 服务（deploy/，提供 /api/*）
  2. 用 Python 模拟 app.js 的 loadData()：
     依次请求 9 个接口，按前端要的形状组装
  3. 断言：9 类数据的条数 + 关键字段与本地 JSON 一致
  4. 特别验证：video 的 url 字段（原来是坑）、original_games 两层包装、characters 拆层
"""
import json, urllib.request, os, subprocess, sys, io, time, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'deploy')
NODE = r'C:\Users\25394\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
PORT = 8095
BASE = 'http://127.0.0.1:%d' % PORT

ENV = dict(os.environ)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    ENV.pop(k, None)

proc = subprocess.Popen([NODE, 'server.js'], cwd=DEPLOY,
                        env=dict(ENV, PORT=str(PORT)),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(50):
    try:
        socket.create_connection(('127.0.0.1', PORT), timeout=1).close()
        break
    except Exception:
        time.sleep(0.3)


def fetch(path):
    """模拟 app.js 的 fetchJson。"""
    with urllib.request.urlopen(BASE + path, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


try:
    # ===== 1. 完全按 app.js 的 loadFromApi() 逻辑组装 =====
    WORK_MODULES = ['music', 'doujin', 'game', 'video', 'art']
    data = {}
    for m in WORK_MODULES:
        data[m] = fetch('/api/works?category=' + m).get('data') or []
    data['originals'] = fetch('/api/originals').get('data') or []
    og = fetch('/api/original-games')
    data['original_games'] = {'categories': og.get('categories') or [], 'games': og.get('games') or []}
    data['characters'] = fetch('/api/characters').get('characters') or []
    data['circles'] = fetch('/api/circles').get('data') or []

    # ===== 2. 与本地 JSON 对拍 =====
    local = {}
    for k in ['music', 'doujin', 'game', 'video', 'art', 'originals', 'circles']:
        local[k] = json.load(open(os.path.join(ROOT, 'my-app', 'data', k + '.json'), encoding='utf-8'))
    og_l = json.load(open(os.path.join(ROOT, 'my-app', 'data', 'original_games.json'), encoding='utf-8'))
    local['original_games'] = og_l
    local['characters'] = json.load(open(os.path.join(ROOT, 'my-app', 'data', 'characters.json'), encoding='utf-8'))['characters']

    print('=' * 80)
    print('端到端验证：my-app 从真库接口取数，与本地 JSON 对拍')
    print('=' * 80)
    print()
    print('%-18s %-8s %-8s %s' % ('数据类型', '接口条数', '本地条数', '结果'))
    print('-' * 80)
    all_ok = True
    for k in ['music', 'doujin', 'game', 'video', 'art', 'originals', 'circles', 'characters']:
        a, b = len(data[k]), len(local[k])
        ok = a == b
        all_ok &= ok
        print('%-18s %-8s %-8s %s' % (k, a, b, '✓' if ok else '❌'))
    og_a, og_b = len(data['original_games']['games']), len(local['original_games']['games'])
    ca, cb = len(data['original_games']['categories']), len(local['original_games']['categories'])
    ok = og_a == og_b and ca == cb
    all_ok &= ok
    print('%-18s %-8s %-8s %s' % ('original_games', '%d/%d' % (og_a, ca), '%d/%d' % (og_b, cb),
                                  '✓ (games/categories)' if ok else '❌'))

    # ===== 3. 逐板块第 1 条全字段对拍 =====
    print()
    print('=' * 80)
    print('逐板块第 1 条：接口 vs 本地 JSON（只列前端真正会读的字段）')
    print('=' * 80)
    for k in ['music', 'doujin', 'game', 'video', 'art']:
        a, b = data[k][0], local[k][0]
        keys = ['id', 'name', 'circle', 'creator', 'year', 'cover', 'source_url', 'description',
                'popularity', 'views', 'type', 'platform', 'url', 'bvid', 'original_title']
        diff = []
        for kk in keys:
            if kk not in b:
                continue          # 本地没这个字段就不比（如 music 没有 url）
            if a.get(kk) != b.get(kk):
                diff.append('%s: 接口=%r 本地=%r' % (kk, a.get(kk), b.get(kk)))
        print('%-8s 对比 %d 个字段 → %s' % (k, len([x for x in keys if x in b]),
                                          '全部一致 ✓' if not diff else '❌ ' + '; '.join(diff)))
        if diff:
            all_ok = False

    # ===== 4. 重点验证 3 个曾经的坑 =====
    print()
    print('=' * 80)
    print('重点验证（这三个是改造前发现的坑）')
    print('=' * 80)
    v = data['video'][0]
    print('① video 的 url 字段（前端读 w.url 做「前往B站观看」链接）')
    print('   接口返回 url =', v.get('url'))
    print('   本地 url     =', local['video'][0].get('url'))
    print('   →', '✓ 一致' if v.get('url') == local['video'][0].get('url') else '❌ 不一致')
    print()
    print('② original_games 的两层包装（前端读 data.original_games.games）')
    print('   接口 data.original_games.games[0].title =', data['original_games']['games'][0].get('title'))
    print('   接口 data.original_games.categories 条数 =', len(data['original_games']['categories']))
    print('   →', '✓ 结构正确' if data['original_games']['games'] and data['original_games']['categories'] else '❌')
    print()
    print('③ characters 拆掉外层（前端读 data.characters 当数组）')
    ch = data['characters'][0]
    print('   接口 data.characters 是数组吗 =', isinstance(data['characters'], list))
    print('   [0] =', json.dumps({k: ch[k] for k in ['id', 'name', 'playableIn'] if k in ch}, ensure_ascii=False))
    print('   有 playableIn 驼峰字段吗 =', 'playableIn' in ch)
    print('   →', '✓' if isinstance(data['characters'], list) and 'playableIn' in ch else '❌')

    print()
    print('=' * 80)
    print('总判定：', '✅ 全部通过，页面前端可无缝切到真库' if all_ok else '❌ 有差异，见上')
    print('=' * 80)

finally:
    proc.kill()
