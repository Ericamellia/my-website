# -*- coding: utf-8 -*-
"""
B 站东方视频同步脚本（Day 17）

它解决什么问题：
    GET /api/hot 要返回「当日真实热搜」，数据不能凭空造，得从 B 站取。
    这个脚本负责「取 + 清洗 + 落成 SQL」，跑一次就产出一份可导入数据库的数据。

为什么不在接口里实时调 B 站：
    ① 慢：一次搜索要 1–3 秒，接口每次请求都等这么久，体验很差；
    ② 脆：B 站偶尔风控/超时，接口跟着挂；
    ③ 不可复现：接口返回的东西没留痕，出问题没法查。
    所以拆成「同步任务」——定时把数据搬进自己的库，接口只读库，又快又稳。
    这是「数据同步 / ETL」最典型的形态：外部数据源 → 定时拉取 → 落库 → 接口读库。

取数策略（双通道）：
    通道 A「近期热门」：order=totalrank（综合排序），拿当前综合热度最高的一批；
    通道 B「后起之秀」：order=dm（按弹幕），拿讨论度高的，作为补充。
    合并去重后按播放量排序，取前 N 条。

相关性过滤（关键，不做会混进大量噪声）：
    实测发现纯搜索「东方」会混入「东方树叶」「东方明珠」「东方曜（王者荣耀）」
    「东方红」等无关内容，所以必须过滤，两道门槛都要过：
      门槛一（硬性）：标题或 UP 主名含东方关键词（東方/东方/Touhou/幻想乡/具体作品名）；
      门槛二（加分）：分区属于东方内容常见分区，或标题含东方角色名。
    注意「東方」是繁体，B 站老视频大量用繁体，必须一起匹配。

用法：
    python db/sync_hot.py              # 取 30 条，写入 db/seed-hot.sql
    python db/sync_hot.py --limit 50   # 取 50 条
    python db/sync_hot.py --dry-run    # 只打印，不写文件
"""
import argparse
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bili_client import search_video  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'db', 'seed-hot.sql')

# ---------------------------------------------------------------------------
# 相关性关键词。为什么要这么细：只要「东方」两个字会命中大量同名干扰项
# （东方树叶饮料、东方明珠塔、王者荣耀英雄东方曜、歌曲东方红…），
# 所以用「东方 + 具体信号」的组合来判定。
# ---------------------------------------------------------------------------
# 属于「东方」的强信号：命中即判定为东方内容（可靠，几乎不会误伤）
STRONG_KW = [
    '東方project', '东方project', '東方プロジェクト',
    # 作品名（简繁都要，B 站老视频大量用繁体）
    '东方红魔乡', '東方紅魔郷', '东方妖妖梦', '東方妖々夢',
    '东方永夜抄', '東方永夜抄', '东方风神录', '東方風神録',
    '东方地灵殿', '東方地霊殿', '东方星莲船', '東方星蓮船',
    '东方神灵庙', '東方神霊廟', '东方辉针城', '东方绀珠传', '東方紺珠伝',
    '东方天空璋', '东方鬼形兽', '东方虹龙洞', '东方兽王园', '东方锦上京',
    '东方幻想乡', '東方幻想郷', '东方怪绮谈', '东方梦时空',
    # 角色名（数据保底）
    '博丽灵梦', '博麗霊夢', '雾雨魔理沙', '霧雨魔理沙',
    '十六夜咲夜', '西行寺幽幽子', '八云紫', '八雲紫',
    '芙兰朵露', 'フランドール', '魂魄妖梦', '魂魄妖夢',
    '琪露诺', 'チルノ', '帕秋莉', '东风谷早苗', '东风谷', '村纱水蜜',
    # 二创/官方活动与作品
    'bad apple', 'badapple', '东方华灯宴', '東方華灯宴',
    '幻想万华镜', '幻想万華鏡', '东方lostword', '东方归言录',
    '东方夜雀食堂', '东方月神夜', '东方非想天则', '东方凭依华',
    '上海アリス幻乐団', '上海爱丽丝幻乐团', 'zun', 'fumo', '油库里',
    # 通用英文/圈子词
    'touhou', 'toho',
    'tho',  # 东方线下展会 Touhou Only，如「武汉tho」「苏州THO」
    '東方',  # 繁体「東方」+ 后面接任意「乡/曲/MMD」等，配合下面的弱信号校验
]

# 弱信号词：「幻想乡」这类词单独出现不足以判定（实测会误命中时政主播「红色幻想乡」），
# 必须与「东方内容特征」共现才算数。
WEAK_KW = ['幻想乡', '幻想鄉', 'gensokyo']

# 东方内容特征词：用于校验弱信号（如「幻想乡」+「灵梦/弹幕/符卡」才算东方）
TOUHOU_MARKERS = [
    '灵梦', '霊夢', '魔理沙', '咲夜', '妖梦', '妖夢', '幽幽子', '紫',
    '芙兰', '芙蘭', '琪露诺', 'チルノ', '早苗', '美铃', '美鈴', 'pad长',
    '弹幕', '彈幕', '符卡', '符札', 'spell card', 'danmaku',
    '东方', '東方', 'touhou', '同人', 'mmd', 'tho',
    '红魔乡', '紅魔郷', '永夜抄', '妖妖梦', '妖々夢', '风神录', '風神録',
    '地灵殿', '地霊殿', '神灵庙', '神霊廟', '月神夜', '华灯宴', '華灯宴',
]

# 分区白名单：东方内容高频出现的分区，命中则加权排前
GOOD_TYPES = {
    '同人·手书', 'MMD·3D', '音MAD', 'MAD·AMV', '音乐综合', '演奏',
    '单机游戏', '音游', '动画综合', 'MV', '绘画', '宅舞', '翻唱', 'VOCALOID',
}

# 分区黑名单：这些分区基本不可能是东方同人内容，直接排除
# ⚠「小剧场」「人文历史」「财经商业」实测会混入时政/财经内容（「红色幻想乡」是个时政主播）
BAD_TYPES = {
    '特摄', '财经商业', '人文历史', '影视综合', '网络游戏', '仿妆cos',
    '小剧场', '资讯', '科学科普', '军事', '环球', '社会', '时事',
}

# UP 主黑名单：实测这些 UP 主名字含「幻想乡」但内容是时政，必须排除
BAD_AUTHORS = ['红色幻想乡', '红色幻想鄉']

# 时政/无关主题黑名单：标题里出现这些词，基本与东方无关，直接排除
# （实测「红色幻想乡」这个时政主播的视频标题常带「局势」「也门」「动员」等词）
BAD_TOPIC_KW = [
    '也门', '巴基斯坦', '特朗普', '美国', '以色列', '伊朗', '俄乌', '普京',
    '川普', '拜登', '内塔尼亚胡', '中东', '加沙', '哈马斯', '选情', '大选',
    '股市', '汇率', '美联储', '关税', '外交', '军方', '军演', '前线', '撤军',
]


def clean_title(t):
    """去掉搜索结果里高亮用的 <em> 标签，并还原 HTML 实体。"""
    if not t:
        return ''
    t = t.replace('<em class="keyword">', '').replace('</em>', '')
    t = (t.replace('&amp;', '&').replace('&quot;', '"')
          .replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'"))
    return t.strip()


def is_touhou(item):
    """
    判断一条 B 站搜索结果是不是东方内容。
    返回 (是否通过, 命中理由)。

    三道门槛：
      ① 分区/UP 主黑名单：命中直接判否（实测「小剧场」分区全是时政，
         UP 主「红色幻想乡」名字含幻想乡但讲的是国际局势）；
      ② 强信号词命中 → 通过；
      ③ 只命中弱信号词（如「幻想乡」）时必须与东方特征词共现 → 才通过。
    """
    title = clean_title(item.get('title', ''))
    author = item.get('author', '') or ''
    ttype = item.get('typename', '') or ''
    hay = (title + ' ' + author).lower()

    # 门槛①：黑名单直接排除
    if ttype in BAD_TYPES:
        return False, ''
    if any(b in author for b in BAD_AUTHORS):
        return False, ''
    # 标题带时政词的一律排除（这些词的东方相关性为零）
    if any(k in title for k in BAD_TOPIC_KW):
        return False, ''

    # 门槛②：强信号
    hits = [k for k in STRONG_KW if k.lower() in hay]
    if hits:
        bonus = '分区命中' if ttype in GOOD_TYPES else '仅标题命中'
        return True, f'{hits[0]}/{bonus}'

    # 门槛③：弱信号 + 特征词共现
    weak = [k for k in WEAK_KW if k.lower() in hay]
    if weak:
        marks = [m for m in TOUHOU_MARKERS if m.lower() in hay]
        if len(marks) >= 1:
            bonus = '分区命中' if ttype in GOOD_TYPES else '仅标题命中'
            return True, f'{weak[0]}+{marks[0]}/{bonus}'

    return False, ''


def clean_text(s, limit=None):
    """
    把外部文本洗成可以安全写进 SQL 单行的字符串。

    为什么必须做这件事（Day 17 实际踩坑）：
        B 站的视频简介是富文本，经常带换行符（\n / \r\n）。
        如果直接原样塞进 INSERT 语句，这条语句会被物理断成多行，
        PG 解析时字符串无法正确闭合，直接报
        `syntax error at or near "BV..."` —— 但报错位置指向的是下一条 INSERT，
        极具误导性，很难定位。所以所有来自外部的长文本都必须先「压平」。
    """
    if not s:
        return ''
    # 换行/制表符统一压成空格（不是删掉，避免两个词粘在一起）
    s = str(s).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # 连续空白合并成一个
    s = re.sub(r'\s{2,}', ' ', s)
    s = s.strip()
    if limit:
        s = s[:limit]
    return s


def to_row(item, reason):
    """把 B 站返回项转成我们自己的结构（所有文本字段已压平）。"""
    return {
        'bvid': item.get('bvid', ''),
        'title': clean_text(clean_title(item.get('title', '')), 200),
        'author': clean_text(item.get('author', ''), 100),
        'mid': item.get('mid'),
        'play': int(item.get('play') or 0),
        'danmaku': int(item.get('video_review') or 0),
        'favorites': int(item.get('favorites') or 0),
        'duration': clean_text(item.get('duration', ''), 16),
        'typename': clean_text(item.get('typename', ''), 32),
        'pubdate': int(item.get('pubdate') or 0),
        'cover': _https(item.get('pic', '')),
        'description': clean_text(clean_title(item.get('description', '')), 200),
        'reason': reason,
    }


def _https(u):
    """
    统一把图片 URL 变成 https 绝对地址。

    B 站搜索接口返回的封面有两种坑：
      ① 老数据是 http:// 开头 —— 页面是 https 时会被浏览器当混合内容拦掉；
      ② 新数据是 // 开头的协议相对地址（如 //i1.hdslb.com/...）——
         直接拿去当 <img src> 浏览器能补全，但存进数据库后前端拿到的就是
         「看起来像相对路径」的残 URL，容易在 SSR/其他端出问题。
    所以这里统一补成 https:// 全量地址。
    """
    if not u:
        return ''
    if u.startswith('//'):
        return 'https:' + u
    if u.startswith('http://'):
        return 'https://' + u[len('http://'):]
    return u


def fetch_channel(keyword, order, pages=2, sleep=0.7):
    """拉一个通道的多页搜索结果。"""
    out = []
    for p in range(1, pages + 1):
        try:
            d = search_video(keyword, order=order, page=p)
        except Exception as e:
            print(f'    ⚠ 第 {p} 页失败：{e}')
            break
        if d.get('code') != 0:
            print(f'    ⚠ 第 {p} 页返回 code={d.get("code")} {d.get("message")}')
            break
        res = (d.get('data') or {}).get('result') or []
        out.extend(res)
        if len(res) < 20:
            break
        time.sleep(sleep)
    return out


def collect(keywords, order, pages=2):
    """按一组关键词收集 + 过滤 + 去重，返回符合条件的结果列表。"""
    seen = {}
    for kw in keywords:
        got = fetch_channel(kw, order, pages=pages)
        kept = 0
        for it in got:
            bv = it.get('bvid')
            if not bv:
                continue
            ok, reason = is_touhou(it)
            if not ok:
                continue
            prev = seen.get(bv)
            # 同一视频保留「理由更优」那条（分区命中 > 仅标题命中）
            if prev is None or (prev['reason'].endswith('仅标题命中') and reason.endswith('分区命中')):
                seen[bv] = to_row(it, reason)
                kept += 1
        print(f'    {kw}: 收到 {len(got)} 条 → 东方内容 {kept} 条')
        time.sleep(0.5)
    return list(seen.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=20, help='每个榜单保留条数')
    ap.add_argument('--dry-run', action='store_true', help='只打印不写文件')
    args = ap.parse_args()

    today_str = time.strftime('%Y-%m-%d')
    print(f'▶ 同步日期：{today_str}（GMT+8）\n')

    # ---- 通道 A：当日新发布（对应「当日热搜」）----
    # 用 order=pubdate 拿最新发布的，再用相关性过滤洗掉噪声。
    # 当日新视频播放量天然很低（刚发布），所以不能按播放排序，
    # 按「发布时间倒序」展示才是「当日最新」的正确语义。
    print('▶ 通道 A：当日新发布（order=pubdate）')
    fresh = collect(
        ['东方project', '東方Project', '东方红魔乡', '东方永夜抄', '幻想乡', '东方'],
        'pubdate', pages=2)
    # 只要今天的 + 昨天的（跨零点场景，今天刚开始时昨天的新视频也算「最新」）
    yday = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
    fresh = [r for r in fresh if time.strftime('%Y-%m-%d', time.localtime(r['pubdate'])) in (today_str, yday)]
    fresh.sort(key=lambda r: r['pubdate'], reverse=True)
    fresh = fresh[:args.limit]
    print(f'    → 当日+昨日，按发布时间倒序取 {len(fresh)} 条\n')

    # ---- 通道 B：历史热门（对应「热度榜」）----
    # 用 order=totalrank（综合排序）拿当前综合热度最高的一批，按播放量排序。
    print('▶ 通道 B：历史热门（order=totalrank）')
    hot = collect(
        ['东方project', '東方Project', '东方红魔乡', '东方永夜抄'],
        'totalrank', pages=2)
    hot.sort(key=lambda r: (r['play'], r['danmaku']), reverse=True)
    hot = hot[:args.limit]
    print(f'    → 按播放量排序取 {len(hot)} 条\n')

    # ---- 打印预览 ----
    for board, rows, label in [('fresh', fresh, '当日新发布'), ('hot', hot, '历史热门')]:
        print(f'=== 榜单「{label}」 {len(rows)} 条 ===')
        for i, r in enumerate(rows, 1):
            day = time.strftime('%m-%d %H:%M', time.localtime(r['pubdate']))
            print(f"{i:2d}. 播{r['play']:>9} 弹{r['danmaku']:>7} | {day} | {r['typename'][:8]:9s} | {r['title'][:36]}")
        print()

    if args.dry_run:
        print('[dry-run] 未写文件')
        return

    # ---------------- 生成 SQL ----------------
    def q(v):
        """
        转成 SQL 字面量。

        双保险：即使上游漏了压平，这里也把换行/制表符替换掉，
        避免一条 INSERT 被物理断行、导致 PG 报「下一条语句语法错误」的迷惑性提示。
        """
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        s = str(v).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        s = re.sub(r'\s{2,}', ' ', s).strip()
        return "'" + s.replace("'", "''") + "'"

    now_iso = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    total = len(fresh) + len(hot)

    L = []
    L.append('-- ============================================================================')
    L.append('-- 东方同人搜索 · 热搜同步数据（Day 17）')
    L.append('-- ============================================================================')
    L.append('-- 本文件由 db/sync_hot.py 自动生成，请勿手工编辑。')
    L.append('-- 数据源：B 站搜索接口（wbi 签名）· 相关性过滤后分区排序')
    L.append(f'-- 同步时间：{now_iso}（GMT+8）')
    L.append(f'-- 条数：{total}（当日新发布 {len(fresh)} + 历史热门 {len(hot)}）')
    L.append('--')
    L.append('-- 幂等：ON CONFLICT (bvid) DO UPDATE，可重复执行不报错')
    L.append('-- 执行位置：CloudBase 控制台 → SQL 数据库 → SQL 编辑器')
    L.append('-- ============================================================================')
    L.append('')
    L.append('-- 依赖 hot_videos 表，见 db/schema-hot.sql（首次执行需先建表）')
    L.append('')

    def emit(rows, board):
        L.append(f'-- ----------------------------------------------------------------------------')
        L.append(f'-- 榜单：{board}　共 {len(rows)} 条')
        L.append(f'-- ----------------------------------------------------------------------------')
        for i, r in enumerate(rows, 1):
            L.append(f"-- {i}. 播{r['play']} 弹{r['danmaku']} · {r['title'][:40]}")
            L.append(
                'INSERT INTO hot_videos (bvid, board, title, author, mid, play, danmaku, '
                'favorites, duration, typename, pubdate, cover, description, source, rank_no, synced_at) VALUES ('
                f"{q(r['bvid'])}, {q(board)}, {q(r['title'])}, {q(r['author'])}, {q(r['mid'])}, "
                f"{q(r['play'])}, {q(r['danmaku'])}, {q(r['favorites'])}, {q(r['duration'])}, "
                f"{q(r['typename'])}, {q(r['pubdate'])}, {q(r['cover'])}, {q(r['description'])}, "
                f"'bilibili', {i}, NOW()) "
                'ON CONFLICT (bvid) DO UPDATE SET '
                'board = EXCLUDED.board, title = EXCLUDED.title, author = EXCLUDED.author, '
                'play = EXCLUDED.play, danmaku = EXCLUDED.danmaku, '
                'favorites = EXCLUDED.favorites, pubdate = EXCLUDED.pubdate, '
                'cover = EXCLUDED.cover, description = EXCLUDED.description, '
                'rank_no = EXCLUDED.rank_no, synced_at = EXCLUDED.synced_at;'
            )
        L.append('')

    emit(fresh, 'fresh')
    emit(hot, 'hot')

    all_bvids = [r['bvid'] for r in fresh + hot]
    L.append('-- 只保留本次同步到的条目，清掉上一轮的旧榜（避免榜单越滚越长）')
    L.append(f'DELETE FROM hot_videos WHERE bvid NOT IN ({", ".join(q(b) for b in all_bvids)});')
    L.append('')
    L.append('-- 验证：')
    L.append(f'--   SELECT COUNT(*) FROM hot_videos;                          -- 期望 {total}')
    L.append("--   SELECT board, COUNT(*) FROM hot_videos GROUP BY board;    -- fresh/hot 各若干")
    L.append('--   SELECT rank_no, play, title FROM hot_videos WHERE board = ')
    L.append("--     'fresh' ORDER BY rank_no LIMIT 5;")
    L.append('')

    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print(f'✅ 已生成 {OUT}（{os.path.getsize(OUT)} 字节，{total} 条）')

    # ---------------- 生成 JSON 快照（给公网接口用）----------------
    # 为什么还要一份 JSON：
    #   公网上的 deploy/server.js 跑在另一个沙箱里，连不到 CloudBase 的 PostgreSQL。
    #   所以接口提供两级数据源：
    #     - 有数据库连接串（PG_URL）时 → 直连真库（本地开发 / 未来云端同环境）
    #     - 没有连接串时 → 读这份 JSON 快照（公网降级，数据与库同源同批）
    #   这样「接口 → 真库」和「接口 → 公网可访问」两个目标都能达成。
    SHOT = os.path.join(ROOT, 'deploy', 'data', 'hot.json')

    def snapshot_rows(rows, board):
        out = []
        for i, r in enumerate(rows, 1):
            out.append({
                'bvid': r['bvid'],
                'board': board,
                'rank': i,
                'title': r['title'],
                'author': r['author'],
                'mid': r['mid'],
                'play': r['play'],
                'danmaku': r['danmaku'],
                'favorites': r['favorites'],
                'duration': r['duration'],
                'typename': r['typename'],
                'pubdate': r['pubdate'],
                'cover': r['cover'],
                'description': r['description'],
                'url': f"https://www.bilibili.com/video/{r['bvid']}",
            })
        return out

    snap = {
        'source': 'bilibili',
        'syncedAt': time.strftime('%Y-%m-%dT%H:%M:%S+08:00', time.localtime()),
        'syncedDate': time.strftime('%Y-%m-%d', time.localtime()),
        'counts': {'fresh': len(fresh), 'hot': len(hot)},
        'fresh': snapshot_rows(fresh, 'fresh'),
        'hot': snapshot_rows(hot, 'hot'),
    }
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    with open(SHOT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'✅ 已生成 {SHOT}（{os.path.getsize(SHOT)} 字节）')


if __name__ == '__main__':
    main()
