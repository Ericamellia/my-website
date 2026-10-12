'use strict';
/**
 * 数据访问层 · 形状转换与入参校验
 * ------------------------------------------------------------------
 * 这一层是「数据形状的唯一真相」：
 *   三条通道（rest / pg / snapshot）返回的原始行结构各不相同
 *   （snake_case 列名、嵌套 JOIN、驼峰快照字段），
 *   全部在这里收敛成**同一个对外形状**，接口层就不用关心数据从哪来。
 *
 * 含这些函数：
 *   - toHotItem()   热搜榜行 → 对外形状
 *   - toFavItem()   收藏行   → 对外形状
 *   - snapshotRowToDbShape()  快照驼峰字段 → 数据库列名
 *   - validateFavoriteInput() 写接口入参校验
 *   - toWorkItem() / toCircleItem() / toOriginalGameItem()
 *     toCharacterItem() / toOriginalItem()
 *                —— Day 21 新增：把 my-app 作品站要的 5 类数据
 *                   从「数据库列名」转成「my-app 前端 JSON 形状」
 */

/** 把热搜榜的行/快照项统一成对外的字段结构。 */
function toHotItem(r) {
  return {
    bvid: r.bvid,
    board: r.board,
    rank: r.rank_no,
    title: r.title,
    author: r.author,
    mid: r.mid,
    play: Number(r.play) || 0,
    danmaku: Number(r.danmaku) || 0,
    favorites: Number(r.favorites) || 0,
    duration: r.duration,
    category: r.typename,
    pubdate: Number(r.pubdate) || 0,
    publishedAt: r.pubdate ? new Date(Number(r.pubdate) * 1000).toISOString() : null,
    cover: r.cover,
    description: r.description,
    url: r.bvid ? 'https://www.bilibili.com/video/' + r.bvid : null
  };
}

/** 统计各榜条数（items 已按 limit 截断，所以这里最多是 limit）。 */
function countByBoard(items, limit) {
  let fresh = 0, hot = 0;
  items.forEach(function (it) {
    if (it.board === 'fresh') fresh++;
    else if (it.board === 'hot') hot++;
  });
  return { fresh: fresh, hot: hot, total: items.length, limit: limit };
}

/**
 * 把「快照里的驼峰字段」转成「数据库列名」。
 *
 * 为什么要这一步：toFavItem() 是按数据库行（snake_case）来读取的，
 * 快照里的数据是驼峰（workId/userId）。两条路径想返回**同一个形状**，
 * 就得在这里对齐一次，否则快照路径会漏掉 workId、userId、circle 这几个字段。
 */
function snapshotRowToDbShape(r) {
  return {
    id: r.id,
    user_id: r.userId,
    work_id: r.workId,
    note: r.note,
    created_at: r.createdAt,
    category: r.category,
    name: r.name,
    circle_name: r.circle,
    creator: r.creator,
    year: r.year,
    cover: r.cover,
    tags: r.tags,
    characters: r.characters,
    description: r.description,
    source_url: r.sourceUrl
  };
}

/** 把收藏行统一成对外结构（works 的字段是 NULL 也要能兜住）。 */
function toFavItem(r) {
  let tags = r.tags;
  let chars = r.characters;
  if (typeof tags === 'string') { try { tags = JSON.parse(tags); } catch (e) { tags = []; } }
  if (typeof chars === 'string') { try { chars = JSON.parse(chars); } catch (e) { chars = []; } }
  return {
    id: r.id,
    userId: r.user_id,
    workId: r.work_id,
    note: r.note,
    createdAt: r.created_at ? new Date(r.created_at).toISOString() : null,
    category: r.category,
    name: r.name || '(作品已下架)',
    circle: r.circle_name,
    creator: r.creator,
    year: r.year,
    cover: r.cover,
    tags: tags || [],
    characters: chars || [],
    description: r.description,
    sourceUrl: r.source_url
  };
}

/* ============================================================
 * Day 21 新增：my-app 作品站的 5 类数据映射
 * ------------------------------------------------------------
 * 为什么需要这一组：
 *   my-app 原本读的是「打包好的本地 JSON」（my-app/data/*.json），
 *   字段形状是**前端自己定的驼峰/短名**；而真库里是**数据库列名**。
 *   两者不一致的地方必须在**这里一处**收敛掉，
 *   否则前端读不到字段（表现为「页面空白但接口 200」）。
 *
 * 三类不一致的处理方式：
 *   ① 换名：DB 下划线 → 前端驼峰
 *        circle_name → circle、source_url → sourceUrl、playable_in → playableIn
 *   ② 拆解：DB 的复合主键 → 前端要的板块内数字 id
 *        work_id "music-1" → id 1（同时保留 workId 原文供收藏接口用）
 *   ③ 拼装：DB 的平铺列 → 前端要的嵌套对象
 *        top_platform + followers + platform_url → top_platform:{name,followers,url}
 * ============================================================ */

/** 数组字段兜底：DB 的 text[] 已经是数组，快照里也可能是 JSON 字符串，统一成数组。 */
function asArray(v) {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string') {
    try {
      const p = JSON.parse(v);
      return Array.isArray(p) ? p : [];
    } catch (e) {
      return [];
    }
  }
  return [];
}

/** 对象字段兜底（moegirl 是 jsonb，快照里可能是字符串）。 */
function asObject(v) {
  if (v && typeof v === 'object' && !Array.isArray(v)) return v;
  if (typeof v === 'string') {
    try {
      const p = JSON.parse(v);
      return (p && typeof p === 'object' && !Array.isArray(p)) ? p : null;
    } catch (e) {
      return null;
    }
  }
  return null;
}

/**
 * ★ 核心转换：work_id "music-1" → 前端要的 id 1
 *
 * 为什么必须拆：my-app 前端用的是**板块内数字 id**
 *   （music.json 里第一条就是 {"id": 1, ...}），
 *   而且所有比较都写成 data[module].find(x => x.id === Number(id)) —— 
 *   **永远先按板块筛，再在板块内比数字**，从不跨板块比。
 *   所以只要还原出后缀数字，前端一行代码都不用改。
 *
 * 兜底：万一 work_id 不含 "-"（异常数据），退化成用原串，
 *       至少不会让整个接口挂掉。
 */
function workIdToLocalId(workId) {
  const s = String(workId == null ? '' : workId);
  const i = s.lastIndexOf('-');
  if (i === -1) return s;
  const n = Number(s.slice(i + 1));
  return Number.isFinite(n) ? n : s;
}

/**
 * works 表中一行 → my-app 前端某个板块 JSON 的数组元素形状。
 *
 * 注意 video 板块多几个专属字段（type/platform/bvid/original_title/video_url），
 * 其余板块这几列在库里是 NULL，返回 null 不影响前端（前端本来也没有这几个 key）。
 */
function toWorkItem(r) {
  return {
    id: workIdToLocalId(r.work_id),   // 前端用：板块内数字
    workId: r.work_id,                // 保留原串：收藏接口要的是 music-1
    category: r.category,
    name: r.name,
    circle: r.circle_name,
    creator: r.creator,
    year: r.year,
    characters: asArray(r.characters),
    tags: asArray(r.tags),
    popularity: Number(r.popularity) || 0,
    views: Number(r.views) || 0,
    cover: r.cover,
    source_url: r.source_url,
    netease_url: r.netease_url || null,
    description: r.description,
    // video 板块专属（其余为 null）
    type: r.video_type || null,
    platform: r.video_platform || null,
    original_title: r.original_title || null,
    // ★ url 与 video_url 都给：库里列名是 video_url，
    //   而 my-app 前端读的是 w.url（视频详情页的「前往 B 站观看」链接）。
    //   两个名字同时返回，前端不用改、库里字段也保持原样。
    url: r.video_url || null,
    video_url: r.video_url || null,
    bvid: r.bvid || null
  };
}

/**
 * circles 表中一行 → circles.json 的元素形状。
 * 关键：DB 把「主平台」拆成三列，前端要的是一个嵌套对象 —— 这里拼回去。
 */
function toCircleItem(r) {
  return {
    name: r.name,
    name_en: r.name_en,
    intro: r.intro,
    source_url: r.source_url,
    avatar: r.avatar,
    top_platform: r.top_platform
      ? {
          name: r.top_platform,
          followers: Number(r.followers) || 0,
          url: r.platform_url || null
        }
      : null
  };
}

/** original_games 表中一行 → original_games.json 的 games[] 元素形状。 */
function toOriginalGameItem(r) {
  return {
    id: r.id,
    th: r.th,
    title: r.title,
    subtitle: r.subtitle,
    category: r.category,
    year: r.year,        // 库中是 TEXT：单年 "1996" 或区间 "2005–2007"，前端两种都能渲染
    cover: r.cover,
    tag: r.tag
  };
}

/** characters 表中一行 → characters.json 的 characters[] 元素形状。 */
function toCharacterItem(r) {
  return {
    id: r.id,
    name: r.name,
    name_en: r.name_en,
    games: asArray(r.games),
    playableIn: asArray(r.playable_in),   // DB playable_in → 前端 playableIn
    twilight_art: r.twilight_art,
    moegirl: asObject(r.moegirl),
    source_url: r.source_url
  };
}

/** originals 表中一行 → originals.json 的元素形状（字段名本来就一致）。 */
function toOriginalItem(r) {
  return {
    id: r.id,
    title: r.title,
    game: r.game,
    track_no: r.track_no,
    description: r.description
  };
}

/**
 * 校验并规范写入参数。**在入库之前**挡住错误输入，是防脏数据的第一道闸门。
 *
 * 为什么校验要放在数据层而不是接口层：
 *   三条通道（rest / pg / snapshot）都要过同一套校验，放这里三方自动共用，不会漏。
 *
 * @returns {{ok:true, value:{userId,workId,note}} | {ok:false, error:string, message:string}}
 */
function validateFavoriteInput(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'invalid_body', message: '请求体必须是一个 JSON 对象' };
  }

  // ---- workId：必填 + 类型 + 格式 + 长度 ----
  const rawWorkId = body.workId;
  if (rawWorkId === undefined || rawWorkId === null || rawWorkId === '') {
    return { ok: false, error: 'missing_work_id', message: '缺少必填字段 workId（要收藏的作品编号，例如 music-1）' };
  }
  if (typeof rawWorkId !== 'string') {
    return { ok: false, error: 'invalid_work_id', message: 'workId 必须是字符串，例如 music-1' };
  }
  const workId = rawWorkId.trim();
  if (!/^[a-z]+-[a-z0-9]+$/i.test(workId)) {
    return {
      ok: false,
      error: 'invalid_work_id_format',
      message: 'workId 格式不对，应形如「板块-编号」，例如 music-1、video-2'
    };
  }
  if (workId.length > 32) {
    return { ok: false, error: 'invalid_work_id', message: 'workId 长度不能超过 32 个字符' };
  }

  // ---- userId：选填，默认 local（还没有登录体系） ----
  let userId = 'local';
  if (body.userId !== undefined && body.userId !== null && body.userId !== '') {
    if (typeof body.userId !== 'string') {
      return { ok: false, error: 'invalid_user_id', message: 'userId 必须是字符串' };
    }
    userId = body.userId.trim();
    if (userId.length === 0 || userId.length > 64) {
      return { ok: false, error: 'invalid_user_id', message: 'userId 长度需在 1–64 个字符之间' };
    }
  }

  // ---- note：选填，长度上限与表定义（VARCHAR(255)）保持一致 ----
  let note = null;
  if (body.note !== undefined && body.note !== null && body.note !== '') {
    if (typeof body.note !== 'string') {
      return { ok: false, error: 'invalid_note', message: 'note 必须是字符串' };
    }
    note = body.note.trim();
    if (note.length > 255) {
      return { ok: false, error: 'invalid_note', message: 'note 长度不能超过 255 个字符' };
    }
    if (note.length === 0) note = null;
  }

  return { ok: true, value: { userId: userId, workId: workId, note: note } };
}

/* ============================================================
 * Day 22 新增：PATCH / DELETE 的入参校验
 * ------------------------------------------------------------
 * 为什么 PATCH 要单独一套校验、不能复用 POST 那套：
 *   两者「必填」的东西完全不同 ——
 *     POST  必须有 workId（要新增哪件作品的收藏）；
 *     PATCH 只改**已有那条**的 note，workId 根本不该出现在请求里
 *            （改了 workId 等于「这条收藏改成收藏另一件作品」，那是删了再建，
 *              语义完全不同，属于不该允许的操作 → 明确拒绝）。
 *   PATCH 的必填项是**「至少给出一个要改的字段」**，
 *   一个字段都不给就 PATCH，是「发了请求但什么都没说」→ 400 而不是假装成功。
 * ============================================================ */

/**
 * 校验 /api/favorites/:id 里的 :id 段。
 *
 * 为什么必须校验：这个值会直接拼进 SQL / URL 查询串。
 * 不校验的话，`abc` 这种会被 PostgREST 当成非法过滤条件报 500，
 * 看起来像「服务端崩了」，其实是「你传错了」——要在这里提前挡成 400。
 */
function validateFavoriteId(rawId) {
  if (rawId === undefined || rawId === null || rawId === '') {
    return { ok: false, error: 'missing_id', message: '路径里缺少收藏 id，形如 /api/favorites/3' };
  }
  const s = String(rawId).trim();
  if (!/^\d+$/.test(s)) {
    return { ok: false, error: 'invalid_id', message: 'id 必须是正整数（收藏记录的自增主键），例如 3' };
  }
  const n = Number(s);
  if (!Number.isFinite(n) || n <= 0) {
    return { ok: false, error: 'invalid_id', message: 'id 必须是大于 0 的整数' };
  }
  return { ok: true, value: n };
}

/**
 * 校验 PATCH 的 body（改收藏备注）。
 *
 * 允许的字段只有一个：note。
 *   给了 note  → 改备注（空串 / null 都表示**清空备注**，不是「不改」）
 *   给别的字段 → 400 unknown_field，明确告诉调用方「这个字段改不了」，
 *                而不是静默忽略（静默忽略最坑：调用方以为改成功了）
 *
 * @returns {{ok:true, value:{note:*}} | {ok:false, error:string, message:string}}
 */
function validateFavoriteUpdate(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'invalid_body', message: '请求体必须是一个 JSON 对象，例如 {"note":"新备注"}' };
  }

  const keys = Object.keys(body);
  if (keys.length === 0) {
    return {
      ok: false,
      error: 'empty_patch',
      message: '请求体是空的，至少要给出一个要修改的字段（目前支持：note）'
    };
  }

  // 只允许 note —— 其余字段（workId / userId / id…）一律拒绝并说明原因
  const unknown = keys.filter(function (k) { return k !== 'note'; });
  if (unknown.length > 0) {
    return {
      ok: false,
      error: 'unknown_field',
      message: '暂不支持修改字段：' + unknown.join('、') +
        '。PATCH 只能改 note（改 workId 请删除后重新收藏）'
    };
  }

  // note：null / 空串 = 清空备注；字符串则限长 255（与表定义 VARCHAR(255) 一致）
  let note = null;
  if (body.note !== undefined && body.note !== null) {
    if (typeof body.note !== 'string') {
      return { ok: false, error: 'invalid_note', message: 'note 必须是字符串，或传 null 表示清空备注' };
    }
    note = body.note.trim();
    if (note.length > 255) {
      return { ok: false, error: 'invalid_note', message: 'note 长度不能超过 255 个字符' };
    }
    if (note.length === 0) note = null;   // 空串归一成 null，与 POST 的处理保持一致
  }

  return { ok: true, value: { note: note } };
}

module.exports = {
  toHotItem: toHotItem,
  countByBoard: countByBoard,
  toFavItem: toFavItem,
  snapshotRowToDbShape: snapshotRowToDbShape,
  validateFavoriteInput: validateFavoriteInput,
  // Day 22 新增：PATCH / DELETE 校验
  validateFavoriteId: validateFavoriteId,
  validateFavoriteUpdate: validateFavoriteUpdate,
  // Day 21 新增：my-app 作品站 5 类数据
  workIdToLocalId: workIdToLocalId,
  toWorkItem: toWorkItem,
  toCircleItem: toCircleItem,
  toOriginalGameItem: toOriginalGameItem,
  toCharacterItem: toCharacterItem,
  toOriginalItem: toOriginalItem
};
