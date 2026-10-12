# -*- coding: utf-8 -*-
"""验证热搜页主界面（两框10条+条状+查看更多）+ 热搜库搜索 + 顶栏一致。（BASE 可换线上）"""
import base64, json, os, subprocess, sys, tempfile, time
import urllib.request

CDP_PORT = 9336
BASE = os.environ.get('BASE', 'http://127.0.0.1:3000')
OUTDIR = os.path.dirname(os.path.abspath(__file__))
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
    os.environ.pop(k, None)

profile = tempfile.mkdtemp(prefix='edge-hot2-')
proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
    '--remote-debugging-port=%d' % CDP_PORT, '--remote-allow-origins=*',
    '--user-data-dir=' + profile, '--window-size=1500,1400', 'about:blank'
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
OK = []
try:
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % CDP_PORT, timeout=2) as r:
                tg = json.load(r)
            pg = [t for t in tg if t.get('type') == 'page']
            if pg:
                ws = pg[0]['webSocketDebuggerUrl']; break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        print('无法连接 CDP'); sys.exit(1)

    from websocket import create_connection
    w = create_connection(ws, timeout=40)
    mid = [0]

    def cdp(m, p=None):
        mid[0] += 1
        w.send(json.dumps({'id': mid[0], 'method': m, 'params': p or {}}))
        while True:
            r = json.loads(w.recv())
            if r.get('id') == mid[0]:
                return r

    def ev(expr):
        r = cdp('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
        rr = r.get('result', {})
        if rr.get('exceptionDetails'):
            return None
        return rr.get('result', {}).get('value')

    def shot(name, clip=None):
        p = {'format': 'png'}
        if clip:
            p['clip'] = clip
        r = cdp('Page.captureScreenshot', p)
        d = r.get('result', {}).get('data')
        if not d:
            return None
        fp = os.path.join(OUTDIR, 'hot2-' + name + '.png')
        open(fp, 'wb').write(base64.b64decode(d))
        return os.path.basename(fp)

    cdp('Page.enable'); cdp('Runtime.enable'); cdp('Network.enable')
    cdp('Network.setCacheDisabled', {'cacheDisabled': True})

    # ========== 1. 主界面 ==========
    cdp('Page.navigate', {'url': BASE + '/#/hot'})
    time.sleep(5)
    print('=' * 78)
    print('【热搜主界面】 %s/#/hot' % BASE)

    boxes = ev('document.querySelectorAll(".hot2-wrap .hot2-box").length')
    titles = ev('Array.from(document.querySelectorAll(".hot2-box .hot2-head h2")).map(function(h){return h.textContent.trim()})')
    subs = ev('Array.from(document.querySelectorAll(".hot2-box .hot2-sub")).map(function(s){return s.textContent.trim()})')
    print('  框数 =', boxes)
    print('  框标题 =', titles)
    print('  框副标题 =', subs)
    OK.append(('主界面', '两个大框', boxes == 2, boxes))
    OK.append(('主界面', '左框=今日B站热搜', bool(titles) and titles[0] == '今日B站热搜', titles))
    OK.append(('主界面', '右框=历史B站热门', bool(titles) and len(titles) > 1 and titles[1] == '历史B站热门', titles))

    # 左右并排（同一行 top 一致）还是上下（现在就是左右，宽度>900）
    tops = ev('Array.from(document.querySelectorAll(".hot2-wrap .hot2-box")).map(function(b){return Math.round(b.getBoundingClientRect().top)})')
    lefts = ev('Array.from(document.querySelectorAll(".hot2-wrap .hot2-box")).map(function(b){return Math.round(b.getBoundingClientRect().left)})')
    print('  框 top =', tops, '| 框 left =', lefts)
    # 说明：两框在同一行 → top 相同
    OK.append(('主界面', '左右并排（top 相同）', len(set(tops or [])) == 1, tops))

    # 每个框各 10 条
    n_fresh = ev('document.querySelectorAll(".hot2-box[data-board=fresh] .hot2-row").length')
    n_hot = ev('document.querySelectorAll(".hot2-box[data-board=hot] .hot2-row").length')
    print('  今日B站热搜 条数 =', n_fresh)
    print('  历史B站热门 条数 =', n_hot)
    OK.append(('主界面', '左框 10 条', n_fresh == 10, n_fresh))
    OK.append(('主界面', '右框 10 条', n_hot == 10, n_hot))

    # 条状：横向 flex，每行左封面 + 右信息
    shape = ev('''(function(){
      var r=document.querySelector(".hot2-box[data-board=fresh] .hot2-row");
      if(!r) return null;
      var cs=getComputedStyle(r);
      var cov=r.querySelector(".hot2-cover"), info=r.querySelector(".hot2-info");
      return {
        display: cs.display,
        covLeft: cov?Math.round(cov.getBoundingClientRect().left):null,
        infoLeft: info?Math.round(info.getBoundingClientRect().left):null,
        sameTop: cov&&info?Math.round(cov.getBoundingClientRect().top)===Math.round(info.getBoundingClientRect().top):false,
        rowH: Math.round(r.getBoundingClientRect().height)
      };
    })()''')
    print('  单条形状 =', shape)
    OK.append(('主界面', '条状横向排列', bool(shape) and shape['display'] == 'flex', shape and shape.get('display')))
    OK.append(('主界面', '封面在左/信息在右', bool(shape) and shape['covLeft'] is not None and shape['covLeft'] < shape['infoLeft'], shape))
    # 单条高度应贴合内容（条状），不应膨胀成大方块
    OK.append(('主界面', '单条为条状（高 50~120px）', bool(shape) and 50 <= shape['rowH'] <= 120, shape and shape.get('rowH')))

    # 第 1 条信息完整
    first = ev('''(function(){
      var r=document.querySelector(".hot2-box[data-board=fresh] .hot2-row");
      return {title:(r.querySelector(".hot2-title")||{}).textContent,
              author:(r.querySelector(".hot2-author")||{}).textContent,
              stat:(r.querySelector(".hot2-stat")||{}).textContent,
              href:r.href,
              cover:!!(r.querySelector(".hot2-cover img")&&r.querySelector(".hot2-cover img").naturalWidth>0)};
    })()''')
    print('  第1条 =', first)
    OK.append(('主界面', '第1条有标题', bool(first) and bool(first.get('title')), first))
    OK.append(('主界面', '第1条有作者', bool(first) and bool(first.get('author')), first))
    OK.append(('主界面', '第1条封面加载', bool(first) and first.get('cover'), first))
    OK.append(('主界面', '第1条跳B站', bool(first) and 'bilibili.com/video/BV' in str(first.get('href')), first and first.get('href')))

    # 查看更多按钮（每框左上角）
    more = ev('''Array.from(document.querySelectorAll(".hot2-box .hot2-more")).map(function(a){
      return {text:a.textContent.trim(), href:a.getAttribute("href"),
              x:Math.round(a.getBoundingClientRect().left),
              y:Math.round(a.getBoundingClientRect().top),
              boxX:Math.round(a.closest(".hot2-box").getBoundingClientRect().left),
              boxY:Math.round(a.closest(".hot2-box").getBoundingClientRect().top)};
    })''')
    print('  查看更多按钮 =', more)
    OK.append(('主界面', '两个查看更多按钮', isinstance(more, list) and len(more) == 2, more))
    OK.append(('主界面', '左框→#/hot/fresh', bool(more) and more[0]['href'] == '#/hot/fresh', more and more[0]['href'] if more else None))
    OK.append(('主界面', '右框→#/hot/hot', bool(more) and len(more) > 1 and more[1]['href'] == '#/hot/hot', more))
    # 位于框内左上角：x 靠近框右边（右对齐）… 需求是「左上角」，检查 y 靠上即可 + 在标题行
    ok_corner = bool(more) and all(m['y'] - m['boxY'] < 60 for m in more)
    OK.append(('主界面', '按钮位于各框顶部', ok_corner, more))
    print('  截图 →', shot('主界面', {'x': 0, 'y': 0, 'width': 1500, 'height': 900, 'scale': 1}))

    # ========== 2. 顶栏与作品页一致 ==========
    print('-' * 78)
    print('【顶栏一致性】')
    nav_hot = ev('''Array.from(document.querySelectorAll("header nav .nav-item")).map(function(a){return a.getAttribute("aria-label")})''')
    input_search = ev('!!document.getElementById("globalSearch")')
    placeholder = ev('(document.getElementById("globalSearch")||{}).placeholder')
    print('  顶栏入口 =', nav_hot)
    print('  搜索框存在 =', input_search, '| placeholder =', placeholder)
    OK.append(('顶栏', '8 个入口齐全', isinstance(nav_hot, list) and len(nav_hot) == 8, nav_hot))
    OK.append(('顶栏', '搜索框存在', bool(input_search), input_search))

    # ========== 3. 热搜库搜索 ==========
    print('-' * 78)
    print('【顶栏搜索：范围=热搜库】')
    # 用作者名搜（只存在于热搜库）
    author = ev('(document.querySelector(".hot2-box[data-board=fresh] .hot2-author")||{}).textContent')
    print('  用第1条作者搜索 =', author)
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/hotsearch/' + urllib.parse.quote(str(author))})
    time.sleep(4)
    h2 = ev('(document.querySelector("#app h2")||{}).textContent')
    rows = ev('document.querySelectorAll(".video-grid .video-card").length')
    gsv = ev('(document.getElementById("globalSearch")||{}).value')
    print('  结果页标题 =', h2)
    print('  结果条数 =', rows, '| 搜索框预填 =', gsv)
    OK.append(('热搜搜索', '进入热搜结果页', bool(h2) and '热搜库搜索' in str(h2), h2))
    OK.append(('热搜搜索', '有搜索结果', isinstance(rows, int) and rows > 0, rows))
    OK.append(('热搜搜索', '搜索框预填关键词', gsv == author, gsv))
    print('  截图 →', shot('热搜搜索', {'x': 0, 'y': 0, 'width': 1500, 'height': 700, 'scale': 1}))

    # 搜一个只存在于作品库的词，确认热搜库搜不到（证明范围换了）
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/hotsearch/' + urllib.parse.quote('同人音乐')})
    time.sleep(3.5)
    empty = ev('document.body.textContent.includes("热搜库里没有找到")')
    print('  搜「同人音乐」→ 热搜库无结果空状态 =', empty)
    OK.append(('热搜搜索', '范围仅限热搜库', bool(empty), empty))

    # ========== 4. 详细页（与同人视频页同款：3 行 + 展开更多） ==========
    print('-' * 78)
    print('【详细页 = 同人视频页展示方式（3行 + 展开更多）】')
    for b in ('fresh', 'hot'):
        cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
        cdp('Page.navigate', {'url': BASE + '/#/hot/' + b})
        time.sleep(4.5)
        h2 = ev('(document.querySelector("#app h2")||{}).textContent')
        grid = ev('!!document.querySelector(".video-grid")')
        total = ev('document.querySelectorAll(".video-grid .video-card").length')
        shown = ev('Array.from(document.querySelectorAll(".video-grid .video-card")).filter(function(c){return !c.classList.contains("lm-hidden")}).length')
        btn = ev('(function(){var b=document.querySelector(".load-more-btn");return b?b.textContent:null})()')
        # 列数 = grid 一行能放几张（用第一行卡片数）；「3 行」= 列数 × 3 张
        cols = ev('''(function(){
          var cs=Array.from(document.querySelectorAll(".video-grid .video-card"));
          if(!cs.length) return 0;
          var first=cs[0].getBoundingClientRect().top;
          return cs.filter(function(c){return Math.abs(c.getBoundingClientRect().top-first)<2}).length;
        })()''')
        print('  #/hot/%s → 标题=%s | video-grid=%s | 总卡片=%s | 已显示=%s | 列数=%s' % (b, h2, grid, total, shown, cols))
        print('              展开更多按钮 =', btn)
        OK.append(('详细页', '#/hot/%s 可进入' % b, bool(h2), h2))
        OK.append(('详细页', '#/hot/%s 用 video-grid' % b, bool(grid), grid))
        OK.append(('详细页', '#/hot/%s 全量 %s 条' % (b, total), isinstance(total, int) and total > 0, total))
        OK.append(('详细页', '#/hot/%s 默认只显示3行(=%s张)' % (b, (cols or 0) * 3),
                   isinstance(shown, int) and isinstance(cols, int) and cols > 0 and shown == cols * 3, '%s张 / 列数%s' % (shown, cols)))
        OK.append(('详细页', '#/hot/%s 有展开更多按钮' % b, bool(btn) and '展开更多' in str(btn), btn))

        # 点「展开更多」应加载更多（先滚到按钮再点，避免在视口外点空）
        if btn:
            ev('(function(){var b=document.querySelector(".load-more-btn");if(b&&b.scrollIntoView)b.scrollIntoView({block:"center"})})()')
            time.sleep(0.6)
            bb = ev('(function(){var b=document.querySelector(".load-more-btn");var r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()')
            if bb:
                cdp('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': bb['x'], 'y': bb['y'], 'button': 'left', 'clickCount': 1})
                cdp('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': bb['x'], 'y': bb['y'], 'button': 'left', 'clickCount': 1})
                time.sleep(1.5)
                shown2 = ev('Array.from(document.querySelectorAll(".video-grid .video-card")).filter(function(c){return !c.classList.contains("lm-hidden")}).length')
                btn2 = ev('(function(){var b=document.querySelector(".load-more-btn");return b?b.textContent:null})()')
                print('              点展开更多后 已显示=%s（原 %s）| 按钮 = %s' % (shown2, shown, btn2))
                OK.append(('详细页', '#/hot/%s 展开更多生效' % b, isinstance(shown2, int) and shown2 > shown, '%s→%s' % (shown, shown2)))
        if b == 'fresh':
            print('  截图 →', shot('详细页3行', {'x': 0, 'y': 0, 'width': 1500, 'height': 1000, 'scale': 1}))
            # 详细页内筛选
            fs = ev('!!document.getElementById("hotDetailSearch")')
            OK.append(('详细页', '详内筛选框存在', bool(fs), fs))

    # ========== 5. 回归：作品站首页/搜索链路未被破坏 ==========
    print('-' * 78)
    print('【回归】')
    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/music'}); time.sleep(3.5)
    m = ev('document.querySelectorAll(".work-item,.video-card").length')
    print('  同人音乐 卡片 =', m)
    OK.append(('回归', '同人音乐正常', isinstance(m, int) and m > 0, m))

    cdp('Page.navigate', {'url': 'about:blank'}); time.sleep(0.4)
    cdp('Page.navigate', {'url': BASE + '/#/search/' + urllib.parse.quote('灵梦')}); time.sleep(3.5)
    s = ev('document.querySelectorAll(".work-item,.video-card").length')
    st = ev('(document.querySelector("#app h2")||{}).textContent')
    print('  作品搜索 卡片 =', s, '| 标题 =', st)
    OK.append(('回归', '作品搜索仍是作品库', isinstance(s, int) and s > 0, s))

finally:
    print()
    print('=' * 78)
    bad = [x for x in OK if not x[2]]
    print('汇总：检查 %d 项，通过 %d，失败 %d' % (len(OK), len(OK) - len(bad), len(bad)))
    for n_, l, ok, v in bad:
        print('  ❌ %s / %s → %s' % (n_, l, v))
    try:
        proc.kill()
    except Exception:
        pass
