'use strict';
/**
 * 数据访问层 · 统一出口（业务查询）
 * ------------------------------------------------------------------
 * 这一层是**接口与数据库之间唯一的门**：
 *   server.js 只 require 这个文件，永远不知道数据是从哪来的。
 *
 * ┌──────────────────────────────────────────────────────────────┐
 * │  接口层 (server.js)                                          │
 * │        ↓  getHot() / getFavorites() / addFavorite() …       │
 * │  ┌────────────────────────────────────────────────────────┐ │
 * │  │  本文件 = 选路器（决定走哪条通道）                      │ │
 * │  │    hasRestApi() → rest.js      （HTTP API，真库，持久）│ │
 * │  │    hasDatabase() → pg.js       （pg 直连，真库）       │ │
 * │  │    否则          → snapshot.js （JSON 快照，降级）     │ │
 * │  └────────────────────────────────────────────────────────┘ │
 * │        ↓  mappers.js 统一收敛成同一形状                      │
 * └──────────────────────────────────────────────────────────────┘
 *
 * 三条通道的**优先级**：HTTP API > pg 直连 > 快照。
 * 每条的「有没有条件用」由 config.js 的环境变量决定。
 */

const config = require('./config');
const pg = require('./pg');
const rest = require('./rest');
const snap = require('./snapshot');
const mappers = require('./mappers');

/* ============================================================
 * GET /api/hot —— 热搜榜
 * ============================================================ */

/**
 * 读热搜榜。
 *
 * @param {object} opt
 *   - board: 'fresh'（当日新发布）| 'hot'（历史热门）| 'all'|''（两榜都要）
 *   - limit: 每榜返回条数上限（默认 20，最大 100）
 * @returns {Promise<{source:string, board:string, limit:number, items:Array, counts:object}>}
 */
async function getHot(opt) {
  const board = (opt && opt.board) || 'all';
  let limit = parseInt((opt && opt.limit) || '20', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 20;
  if (limit > 100) limit = 100;                 // 上限兜底，防止被拉爆

  if (rest.hasRestApi()) return getHotFromRest(board, limit);
  if (pg.hasDatabase()) return getHotFromPg(board, limit);
  return getHotFromSnapshot(board, limit);
}

/** ① HTTP API 通道。 */
async function getHotFromRest(board, limit) {
  const q = {
    select: 'bvid,board,title,author,mid,play,danmaku,favorites,duration,typename,pubdate,cover,description,source,rank_no',
    order: board === 'all' ? 'board.asc,rank_no.asc' : 'rank_no.asc',
    limit: String(board === 'all' ? limit * 2 : limit)
  };
  if (board !== 'all') q.board = 'eq.' + board;

  const res = await rest.restRequest('GET', 'hot_videos', { query: q });
  if (res.status !== 200) throw rest.restFailed('rest_hot_failed', res.data);

  const items = (res.data || []).map(mappers.toHotItem);
  return {
    source: 'rest',
    board: board,
    limit: limit,
    counts: mappers.countByBoard(items, limit),
    items: items
  };
}

/** ② pg 直连通道。 */
async function getHotFromPg(board, limit) {
  // board=all 时两榜合并查，用 board 字段区分；ORDER BY 里带上 board 保证分组有序
  const sql = board === 'all'
    ? `SELECT bvid, board, title, author, mid, play, danmaku, favorites,
              duration, typename, pubdate, cover, description, source, rank_no
         FROM hot_videos
        ORDER BY board, rank_no
        LIMIT $1`
    : `SELECT bvid, board, title, author, mid, play, danmaku, favorites,
              duration, typename, pubdate, cover, description, source, rank_no
         FROM hot_videos
        WHERE board = $1
        ORDER BY rank_no
        LIMIT $2`;
  const params = board === 'all' ? [limit * 2] : [board, limit];
  const rows = await pg.query(sql, params);
  const items = rows.map(mappers.toHotItem);
  return {
    source: 'database',
    board: board,
    limit: limit,
    counts: mappers.countByBoard(items, limit),
    items: items
  };
}

/** ③ 快照降级通道。 */
async function getHotFromSnapshot(board, limit) {
  const s = snap.readSnapshot('hot.json');
  if (!s) throw snap.dataMissing('hot_data_unavailable');

  let items = [];
  if (board === 'fresh' || board === 'all') {
    items = items.concat((s.fresh || []).slice(0, limit));
  }
  if (board === 'hot' || board === 'all') {
    items = items.concat((s.hot || []).slice(0, limit));
  }
  return {
    source: 'snapshot',
    board: board,
    limit: limit,
    syncedAt: s.syncedAt || null,
    syncedDate: s.syncedDate || null,
    counts: mappers.countByBoard(items, limit),
    items: items
  };
}

/* ============================================================
 * GET /api/favorites —— 收藏列表
 * ============================================================ */

/**
 * 读收藏列表。
 *
 * @param {object} opt
 *   - userId: 用户标识，默认 'local'
 *   - limit:  返回条数上限（默认 50，最大 200）
 */
async function getFavorites(opt) {
  const userId = (opt && opt.userId) || 'local';
  let limit = parseInt((opt && opt.limit) || '50', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 50;
  if (limit > 200) limit = 200;

  if (rest.hasRestApi()) return getFavoritesFromRest(userId, limit);
  if (pg.hasDatabase()) return getFavoritesFromPg(userId, limit);
  return getFavoritesFromSnapshot(userId, limit);
}

/** ① HTTP API 通道。 */
async function getFavoritesFromRest(userId, limit) {
  // PostgREST 的 JOIN 靠「嵌套 select」表达：works(category,name,...)
  // 返回时 works 是一个对象（外键是单条），要拍平回 GET 的形状。
  //
  // ★ Day 22 软删除：必须过滤 is_deleted。
  //   PostgREST 的布尔过滤写成 is_deleted=eq.false（不是 is.false）——
  //   eq. 用在布尔列上同样有效，且比 is. 更不容易写错。
  const res = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      user_id: 'eq.' + userId,
      is_deleted: 'eq.false',          // ← 软删除过滤：已取消的收藏不出现在列表里
      order: 'created_at.desc,id.desc',
      limit: String(limit)
    }
  });
  if (res.status !== 200) throw rest.restFailed('rest_favorites_failed', res.data);

  const items = (res.data || []).map(flattenRestFavRow);
  return { source: 'rest', userId: userId, limit: limit, count: items.length, items: items };
}

/** 把 REST 返回的「嵌套 works」拍平成数据库行形状。 */
function flattenRestFavRow(r) {
  const w = r.works || {};
  return mappers.toFavItem({
    id: r.id, user_id: r.user_id, work_id: r.work_id,
    note: r.note, created_at: r.created_at,
    category: w.category, name: w.name, circle_name: w.circle_name,
    creator: w.creator, year: w.year, cover: w.cover,
    tags: w.tags, characters: w.characters,
    description: w.description, source_url: w.source_url
  });
}

/** ② pg 直连通道。 */
async function getFavoritesFromPg(userId, limit) {
  // JOIN works 把作品名/社团/封面一起带出来，前端不用再发一次请求
  // ★ Day 22 软删除：WHERE 里必须带上 is_deleted = FALSE，否则已取消的会漏出来
  const sql = `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
                      w.category, w.name, w.circle_name, w.creator, w.year,
                      w.cover, w.tags, w.characters, w.description, w.source_url
                 FROM favorites f
                 LEFT JOIN works w ON w.work_id = f.work_id
                WHERE f.user_id = $1 AND f.is_deleted = FALSE
                ORDER BY f.created_at DESC, f.id DESC
                LIMIT $2`;
  const rows = await pg.query(sql, [userId, limit]);
  const items = rows.map(mappers.toFavItem);
  return { source: 'database', userId: userId, limit: limit, count: items.length, items: items };
}

/** ③ 快照降级通道。 */
async function getFavoritesFromSnapshot(userId, limit) {
  const s = snap.readSnapshot('favorites.json');
  if (!s) throw snap.dataMissing('favorites_data_unavailable');

  // ★ 软删除：快照路径同样要跳过已删的（且要兼顾老数据没有 isDeleted 字段的情况）
  const items = (s.items || [])
    .filter(function (r) { return r.isDeleted !== true; })
    .slice(0, limit)
    .map(function (r) {
    return {
      id: r.id,
      userId: r.userId,
      workId: r.workId,
      note: r.note,
      createdAt: null,
      category: r.category,
      name: r.name,
      circle: r.circle,
      creator: r.creator,
      year: r.year,
      cover: r.cover,
      tags: r.tags || [],
      characters: r.characters || [],
      description: r.description,
      sourceUrl: r.sourceUrl
    };
  });
  return { source: 'snapshot', userId: userId, limit: limit, count: items.length, items: items };
}

/* ============================================================
 * POST /api/favorites —— 新增一条收藏
 * ============================================================ */

/**
 * 新增一条收藏。
 *
 * 两道闸门：
 *   ① 入参校验 —— 见 mappers.validateFavoriteInput()，入库前挡住错误输入；
 *   ② 唯一约束 —— favorites 表的 UNIQUE (user_id, work_id)，
 *      重复提交不会多插一行，而是被识别为「已收藏过」，返回 duplicate:true。
 *
 * 为什么不能只靠前端禁用按钮防重复：
 *   网络自动重试、脚本直接调用、双开页面都能绕过前端。
 *   唯一可靠的位置是数据库约束 —— 原子，并发下也不会漏。
 *
 * @returns {Promise<{source, created:boolean, duplicate:boolean, item:object}>}
 */
async function addFavorite(input) {
  const userId = input.userId;
  const workId = input.workId;
  const note = input.note;

  if (rest.hasRestApi()) return addFavoriteToRest(userId, workId, note);
  if (pg.hasDatabase()) return addFavoriteToPg(userId, workId, note);
  return addFavoriteToSnapshot(userId, workId, note);
}

/** ① HTTP API 通道（真正写进真库，持久化）。 */
async function addFavoriteToRest(userId, workId, note) {
  // ★ Day 22 软删除带来的一个必须处理的场景：
  //   「取消收藏 → 又想收藏同一作品」。
  //   这时表里躺着一条 is_deleted=TRUE 的旧行。两种做法：
  //     A. 再插一条新的（旧行留着）→ 表会越积越多，且要处理「两条同作品」
  //     B. 把旧行**复活**（is_deleted=FALSE + 覆盖 note）
  //   这里选 B：favorites 的语义是「谁收藏了哪个作品」，
  //   同一个人对同一作品本质上只该有一条 —— 历史记录不是这张表该管的事。
  //   好处还有：部分唯一索引 uq_favorites_active 不会被旧行干扰。
  const revived = await rest.restRequest('PATCH', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at',
      user_id: 'eq.' + userId,
      work_id: 'eq.' + workId,
      is_deleted: 'eq.true',            // 只找「已软删」的那条来复活
      limit: '1'
    },
    prefer: 'return=representation',
    body: { is_deleted: false, note: note, created_at: new Date().toISOString() }
  });

  if (revived.status === 200 && Array.isArray(revived.data) && revived.data.length > 0) {
    // 复活成功：补全作品详情后返回，形状与 GET 一致
    const rid = revived.data[0].id;
    const fullR = await fetchFavFullFromRest(rid);
    return { source: 'rest', created: true, duplicate: false, item: fullR };
  }

  // 没有可复活的旧行 → 正常插入
  // POST + Prefer: return=representation
  //   → 201 返回插入后的整行（含数据库生成的 id、created_at）
  //   → 409 + DATABASE_23505 撞唯一索引 uq_favorites_active，即「已收藏过」
  const res = await rest.restRequest('POST', 'favorites', {
    query: { select: 'id,user_id,work_id,note,created_at' },
    prefer: 'return=representation',
    body: { user_id: userId, work_id: workId, note: note }
  });

  if (rest.isUniqueViolation(res.status, res.data)) {
    // 撞唯一约束：把已有那条读回来，告诉调用方「已收藏过」而不是报错
    // ★ 必须限定 is_deleted=eq.false —— 未删除的那条才是「已收藏过」的那个
    //
    // ★ Day 24 修复：这里的 select 漏了 works(...) JOIN。
    //   只取 favorites 的 5 个基础字段时，toFavItem() 读不到 r.name / r.tags，
    //   就会兜底成 name="(作品已下架)"、tags=[]。
    //   后果：同一个作品，第一次收藏返回真实作品名，
    //   再点一次（走到这个分支）名字却变成「(作品已下架)」——名字凭空消失。
    //   修法与 fetchFavFullFromRest() 保持一致：把 works(...) 一起 select 出来。
    const exist = await rest.restRequest('GET', 'favorites', {
      query: {
        select: 'id,user_id,work_id,note,created_at,' +
                'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
        user_id: 'eq.' + userId,
        work_id: 'eq.' + workId,
        is_deleted: 'eq.false',
        limit: '1'
      }
    });
    const row = (exist.data && exist.data[0]) || {};
    // PostgREST 把 JOIN 结果放在 row.works 下，压平后再交给 toFavItem（与 fetchFavFullFromRest 同款）
    const w = row.works || {};
    return {
      source: 'rest', created: false, duplicate: true,
      item: mappers.toFavItem({
        id: row.id, user_id: row.user_id, work_id: row.work_id,
        note: row.note, created_at: row.created_at,
        category: w.category, name: w.name, circle_name: w.circle_name,
        creator: w.creator, year: w.year, cover: w.cover,
        tags: w.tags, characters: w.characters,
        description: w.description, source_url: w.source_url
      })
    };
  }

  if (res.status !== 201) throw rest.restFailed('rest_insert_failed', res.data);

  // 插入成功：再查一次（带 JOIN）把作品详情补全，让返回体与 GET 条目同形状
  const inserted = (res.data && res.data[0]) || {};
  return { source: 'rest', created: true, duplicate: false, item: await fetchFavFullFromRest(inserted.id, inserted) };
}

/** 按 id 读一条收藏（带 JOIN），形状与 GET 条目一致。rest 通道多处复用。 */
async function fetchFavFullFromRest(id, fallbackRow) {
  const full = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      id: 'eq.' + id,
      limit: '1'
    }
  });
  const r0 = (full.data && full.data[0]) || {};
  const fallback = fallbackRow || {};
  const w = r0.works || {};
  return mappers.toFavItem({
    id: r0.id !== undefined ? r0.id : fallback.id,
    user_id: r0.user_id || fallback.user_id,
    work_id: r0.work_id || fallback.work_id,
    note: r0.note !== undefined ? r0.note : fallback.note,
    created_at: r0.created_at || fallback.created_at,
    category: w.category, name: w.name, circle_name: w.circle_name,
    creator: w.creator, year: w.year, cover: w.cover,
    tags: w.tags, characters: w.characters,
    description: w.description, source_url: w.source_url
  });
}

/** ② pg 直连通道。 */
async function addFavoriteToPg(userId, workId, note) {
  // ★ 先看有没有「已软删」的同一行 —— 有就复活它，不再插新行（与 rest 通道同一套语义）
  const revived = await pg.query(
    `UPDATE favorites
        SET is_deleted = FALSE, note = $3, created_at = NOW()
      WHERE user_id = $1 AND work_id = $2 AND is_deleted = TRUE
      RETURNING id, user_id, work_id, note, created_at`,
    [userId, workId, note]
  );
  if (revived.length > 0) {
    // 复活成功：JOIN 作品详情后返回，形状与 GET 一致
    return { source: 'database', created: true, duplicate: false,
             item: await fetchFavFullFromPg(revived[0].id) };
  }

  // RETURNING 让 INSERT 一次性把插入后的整行带回，不用再查一次
  //
  // ★ Day 22 软删除后 ON CONFLICT 的写法必须改：
  //   原来 `ON CONFLICT (user_id, work_id)` 对应的是**全表唯一约束**；
  //   现在唯一性由**部分索引** uq_favorites_active 保证，
  //   PG 要求用「带 WHERE 的推断子句」才能匹配到那个部分索引：
  //       ON CONFLICT (user_id, work_id) WHERE is_deleted = FALSE
  //   写法不对的话，PG 会报「there is no unique or exclusion constraint
  //   matching the ON CONFLICT specification」——这个坑必须踩过一次才知道。
  const sql = `INSERT INTO favorites (user_id, work_id, note)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, work_id) WHERE is_deleted = FALSE DO NOTHING
               RETURNING id, user_id, work_id, note, created_at`;
  const rows = await pg.query(sql, [userId, workId, note]);

  if (rows.length === 0) {
    // 撞唯一索引：没插进去，但不算错误 —— 去把已有那条读回来告诉调用方
    // 只找未删除的那条（已删的刚才已经尝试复活过了，走到这里说明没有）
    const exist = await pg.query(
      `SELECT id, user_id, work_id, note, created_at
         FROM favorites WHERE user_id = $1 AND work_id = $2 AND is_deleted = FALSE`,
      [userId, workId]
    );
    return { source: 'database', created: false, duplicate: true, item: mappers.toFavItem(exist[0]) };
  }

  return { source: 'database', created: true, duplicate: false,
           item: await fetchFavFullFromPg(rows[0].id) };
}

/** 按 id 读一条收藏（带 JOIN），形状与 GET 条目一致。pg 通道复用。 */
async function fetchFavFullFromPg(id) {
  const full = await pg.query(
    `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
            w.category, w.name, w.circle_name, w.creator, w.year,
            w.cover, w.tags, w.characters, w.description, w.source_url
       FROM favorites f
       LEFT JOIN works w ON w.work_id = f.work_id
      WHERE f.id = $1`,
    [id]
  );
  return mappers.toFavItem(full[0]);
}

/** ③ 快照降级通道：用文件里的数据模拟同一套语义（先查重，再追加）。 */
async function addFavoriteToSnapshot(userId, workId, note) {
  const s = snap.readSnapshot('favorites.json');
  if (!s) throw snap.dataMissing('favorites_data_unavailable');
  const items = s.items || [];

  // Day 22 余力：先找「活着的那条」判重；再找「已软删的那条」复活。
  // 顺序不能反 —— 如果同一 (user, work) 同时存在活行和软删行（历史脏数据），
  // 优先认活行，避免复活时把活行挤成两条。
  const dup = items.find(function (r) {
    return r.userId === userId && r.workId === workId && r.isDeleted !== true;
  });
  if (dup) {
    return {
      source: 'snapshot',
      created: false,
      duplicate: true,
      item: mappers.toFavItem(mappers.snapshotRowToDbShape(dup))
    };
  }

  const soft = items.find(function (r) {
    return r.userId === userId && r.workId === workId && r.isDeleted === true;
  });
  if (soft) {
    // 复活：沿用原来那行（id / createdAt 都换新，当作一次新的收藏）
    soft.isDeleted = false;
    soft.note = note;
    soft.createdAt = new Date().toISOString();
    s.items = items;
    s.count = items.length;
    snap.writeSnapshot('favorites.json', s);
    return {
      source: 'snapshot',
      created: true,
      duplicate: false,
      item: mappers.toFavItem(mappers.snapshotRowToDbShape(soft))
    };
  }

  // 作品必须存在（对应真库路径的外键约束，快照路径手工补上同等的检查）
  const works = snap.readSnapshot('works.json');
  let detail = null;
  if (works && Array.isArray(works.items)) {
    detail = works.items.find(function (w) { return w.workId === workId; }) || null;
  }

  const nextId = items.reduce(function (m, r) { return Math.max(m, Number(r.id) || 0); }, 0) + 1;
  const row = Object.assign(
    {
      id: nextId,
      userId: userId,
      workId: workId,
      note: note,
      createdAt: new Date().toISOString()
    },
    detail || {}
  );
  items.push(row);
  s.items = items;
  s.count = items.length;

  snap.writeSnapshot('favorites.json', s);

  return {
    source: 'snapshot',
    created: true,
    duplicate: false,
    item: mappers.toFavItem(mappers.snapshotRowToDbShape(row))
  };
}

/* ============================================================
 * Day 22 新增：PATCH /api/favorites/:id —— 修改一条收藏
 * ------------------------------------------------------------
 * 今天只开放改一个字段：note（备注）。
 *
 * 为什么改 workId 被拒绝（而不是顺手支持）：
 *   「把这条收藏改成收藏另一件作品」不是一个修改动作，而是
 *   **删掉旧的那条 + 新建一条**（因为它要重新过唯一约束、重新记时间）。
 *   把它伪装成 PATCH 会让调用方误以为「时间没变、id 没变」，
 *   而这种语义歧义正是以后出 bug 的源头 → 明确拒绝，让他走 DELETE + POST。
 * ============================================================ */

/**
 * 改一条收藏（目前只有 note 可改）。
 *
 * 各通道的「存在性判定」是本接口的重点：
 *   PATCH 影响的永远是**一行**。如果改完返回「0 行」，
 *   说明这个 id 在库里不存在 —— 要如实回 404，而不是假装成功。
 *
 * @returns {Promise<{source, updated:boolean, notFound:boolean, item:object|null}>}
 */
async function updateFavorite(id, patch) {
  if (rest.hasRestApi()) return updateFavoriteToRest(id, patch);
  if (pg.hasDatabase()) return updateFavoriteToPg(id, patch);
  return updateFavoriteToSnapshot(id, patch);
}

/** ① HTTP API 通道。 */
async function updateFavoriteToRest(id, patch) {
  // PostgREST 的 PATCH：过滤条件写在 query 上，要改的字段放在 body 里。
  // Prefer: return=representation → 200 直接返回改完之后的整行（改到 0 行则返回 []）。
  const res = await rest.restRequest('PATCH', 'favorites', {
    query: { id: 'eq.' + id, is_deleted: 'eq.false', select: 'id,user_id,work_id,note,created_at' },
    prefer: 'return=representation',
    body: { note: patch.note }
  });
  if (res.status !== 200 && res.status !== 204) throw rest.restFailed('rest_update_failed', res.data);

  const rows = Array.isArray(res.data) ? res.data : [];
  if (rows.length === 0) {
    // 0 行 = 这个 id 不存在（或已被软删）。**不能**当成「改成功但没变化」——
    // 后者 PostgREST 也会返回那一行（值相同也是 1 行），所以 0 行只可能是没找到。
    return { source: 'rest', updated: false, notFound: true, item: null };
  }

  // 再查一次（带 JOIN）把作品详情补齐，让返回体与 GET 条目同形状
  const full = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      id: 'eq.' + id,
      limit: '1'
    }
  });
  const r0 = (full.data && full.data[0]) || {};
  const w = r0.works || {};
  return {
    source: 'rest',
    updated: true,
    notFound: false,
    item: mappers.toFavItem({
      id: r0.id !== undefined ? r0.id : rows[0].id,
      user_id: r0.user_id || rows[0].user_id,
      work_id: r0.work_id || rows[0].work_id,
      note: r0.note !== undefined ? r0.note : rows[0].note,
      created_at: r0.created_at || rows[0].created_at,
      category: w.category, name: w.name, circle_name: w.circle_name,
      creator: w.creator, year: w.year, cover: w.cover,
      tags: w.tags, characters: w.characters,
      description: w.description, source_url: w.source_url
    })
  };
}

/** ② pg 直连通道。 */
async function updateFavoriteToPg(id, patch) {
  // RETURNING 把改完的行直接带回；没改到任何行 → 空数组 → 404
  // （带 is_deleted = FALSE：软删掉的行不参与修改，从用户视角它已经不存在）
  const rows = await pg.query(
    'UPDATE favorites SET note = $1 WHERE id = $2 AND is_deleted = FALSE ' +
    'RETURNING id, user_id, work_id, note, created_at',
    [patch.note, id]
  );
  if (rows.length === 0) {
    return { source: 'database', updated: false, notFound: true, item: null };
  }

  // 补齐作品详情，返回形状与 GET 一致
  const full = await pg.query(
    `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
            w.category, w.name, w.circle_name, w.creator, w.year,
            w.cover, w.tags, w.characters, w.description, w.source_url
       FROM favorites f
       LEFT JOIN works w ON w.work_id = f.work_id
      WHERE f.id = $1`,
    [id]
  );
  return { source: 'database', updated: true, notFound: false, item: mappers.toFavItem(full[0]) };
}

/** ③ 快照降级通道。 */
async function updateFavoriteToSnapshot(id, patch) {
  const s = snap.readSnapshot('favorites.json');
  if (!s) throw snap.dataMissing('favorites_data_unavailable');

  const items = s.items || [];
  // 快照里的 id 可能是字符串，统一按数字比。
  // 软删掉的行视同不存在（与真库路径的 is_deleted = FALSE 对齐）
  const row = items.find(function (r) {
    return Number(r.id) === Number(id) && r.isDeleted !== true;
  });
  if (!row) {
    return { source: 'snapshot', updated: false, notFound: true, item: null };
  }

  row.note = patch.note;             // 只改 note，其余字段原样保留
  snap.writeSnapshot('favorites.json', s);

  return {
    source: 'snapshot',
    updated: true,
    notFound: false,
    item: mappers.toFavItem(mappers.snapshotRowToDbShape(row))
  };
}

/* ============================================================
 * Day 22 新增：DELETE /api/favorites/:id —— 取消一条收藏
 * ------------------------------------------------------------
 * 「删除为什么比新增更容易出事」——这层的回答是**先查后删**：
 *
 *   删除必须回答两个问题，而新增不用：
 *     ① 删到了吗？（影响 0 行 = 这 id 本来就不存在 → 404，不能假装成功）
 *     ② 删掉的是哪一条？（要在响应里把被删的那条**原样带回**，
 *        这样前端能显示「已取消收藏《XXX》」，也是误删后唯一的凭证）
 *
 *   所以流程固定为：先 SELECT 把整条读出来 → 再 DELETE →
 *   用「读到了没有」决定 404 还是 200。
 *   反过来「先删再看删了几行」也能判 404，但拿不到被删的内容，
 *   没法在响应里告诉用户删掉的是哪一条。
 *
 * ⚠️ 现在是**软删除**（余力加练已实施）：
 *   不再物理 DELETE，改成把 is_deleted 置为 TRUE。
 *   好处：删错了还能找回、删除不破坏外键引用链、以后能出「回收站」。
 *   代价：所有读路径都必须记得加过滤（3 条查询 + PATCH 都已加），
 *        且原来 UNIQUE(user_id, work_id) 会让「删后重新收藏」撞约束 ——
 *        已换成部分唯一索引 `... WHERE is_deleted = FALSE`（见 db/migration-soft-delete.sql）。
 *
 *   但「先查后删」的顺序**不变**：仍然要先 SELECT 出整条当凭证，
 *   再把它标记成已删除；用「读到了没有」决定 404 还是 200。
 *   软删除改变的是「删的动作」，不改变「删除要回答的那两个问题」。
 * ============================================================ */

/**
 * 删一条收藏。
 *
 * @returns {Promise<{source, deleted:boolean, notFound:boolean, item:object|null}>}
 */
async function deleteFavorite(id) {
  if (rest.hasRestApi()) return deleteFavoriteFromRest(id);
  if (pg.hasDatabase()) return deleteFavoriteFromPg(id);
  return deleteFavoriteFromSnapshot(id);
}

/** ① HTTP API 通道。 */
async function deleteFavoriteFromRest(id) {
  // 第 ① 步：先查。带 JOIN 一次把整条（含作品详情）读出来，
  // 既是「存不存在」的判断，也是「删的是哪一条」的凭证。
  // 带 is_deleted = eq.false：已经软删过的行视同不存在 → 二次删也是 404（顺带获得幂等语义）
  const found = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      id: 'eq.' + id,
      is_deleted: 'eq.false',
      limit: '1'
    }
  });
  if (found.status !== 200) throw rest.restFailed('rest_delete_lookup_failed', found.data);

  const row = (found.data && found.data[0]) || null;
  if (!row) {
    return { source: 'rest', deleted: false, notFound: true, item: null };
  }
  // 先把要返回的凭证形状算好，再标记删除
  const victim = flattenRestFavRow(row);

  // 第 ② 步：软删。filter 只按 id + is_deleted = false，
  // 保证不会误标别人的数据、也不会重复标记已删的行。
  // ⚠️ 不碰 created_at / note —— 「什么时候收藏的」和「备注写了什么」
  //    都留着，将来做「回收站 / 恢复」时用得上。
  const del = await rest.restRequest('PATCH', 'favorites', {
    query: { id: 'eq.' + id, is_deleted: 'eq.false' },
    prefer: 'return=representation',
    body: { is_deleted: true }
  });
  if (del.status !== 200 && del.status !== 204) {
    throw rest.restFailed('rest_delete_failed', del.data);
  }

  return { source: 'rest', deleted: true, notFound: false, item: victim };
}

/** ② pg 直连通道。 */
async function deleteFavoriteFromPg(id) {
  // 第 ① 步：先查（JOIN 作品详情），拿到「删的是哪一条」。
  // 带 f.is_deleted = FALSE：已软删的行视同不存在 → 二次删 404
  const found = await pg.query(
    `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
            w.category, w.name, w.circle_name, w.creator, w.year,
            w.cover, w.tags, w.characters, w.description, w.source_url
       FROM favorites f
       LEFT JOIN works w ON w.work_id = f.work_id
      WHERE f.id = $1 AND f.is_deleted = FALSE`,
    [id]
  );
  if (found.length === 0) {
    return { source: 'database', deleted: false, notFound: true, item: null };
  }
  const victim = mappers.toFavItem(found[0]);

  // 第 ② 步：软删。加 is_deleted = FALSE 双保险（避免并发下重复标记）。
  // 保留 note / created_at，将来做恢复时用得上。
  await pg.query(
    'UPDATE favorites SET is_deleted = TRUE WHERE id = $1 AND is_deleted = FALSE',
    [id]
  );

  return { source: 'database', deleted: true, notFound: false, item: victim };
}

/** ③ 快照降级通道。 */
async function deleteFavoriteFromSnapshot(id) {
  const s = snap.readSnapshot('favorites.json');
  if (!s) throw snap.dataMissing('favorites_data_unavailable');

  const items = s.items || [];
  const idx = items.findIndex(function (r) {
    return Number(r.id) === Number(id) && r.isDeleted !== true;
  });
  if (idx === -1) {
    return { source: 'snapshot', deleted: false, notFound: true, item: null };
  }

  const victim = mappers.toFavItem(mappers.snapshotRowToDbShape(items[idx]));

  // 软删：只打标记，**不**从数组里摘掉，note / createdAt 都留着
  items[idx].isDeleted = true;
  s.items = items;
  s.count = items.filter(function (r) { return r.isDeleted !== true; }).length;
  snap.writeSnapshot('favorites.json', s);

  return { source: 'snapshot', deleted: true, notFound: false, item: victim };
}

/* ============================================================
 * Day 21 新增：my-app 作品站的 5 类只读数据
 * ------------------------------------------------------------
 * 背景：my-app 原本读的是打包在仓库里的本地 JSON（my-app/data/*.json），
 *       数据是**只读**的，改一条要重新生成文件再上传。
 *       现在改成读这 5 个接口 —— 数据来自真库，改库即生效。
 *
 * 五个接口对应 my-app 的 5 个数据来源：
 *   GET /api/works?category=music   → my-app/data/{music,doujin,game,video,art}.json
 *   GET /api/circles                → my-app/data/circles.json
 *   GET /api/original-games         → my-app/data/original_games.json（categories + games）
 *   GET /api/characters             → my-app/data/characters.json
 *   GET /api/originals              → my-app/data/originals.json
 *
 * 每个函数都照 getHot/getFavorites 的既有模式走**三条通道**：
 *   rest（HTTP API 真库） → pg（直连真库） → snapshot（JSON 快照降级）
 * 这样本地开发不走真库也能跑，公网走真库才是持久的那条。
 * ============================================================ */

/** works 表里，属于「作品站五大板块」的分类白名单（防止 ?category=xxx 传任意值）。 */
const WORK_CATEGORIES = ['music', 'doujin', 'game', 'video', 'art'];

/** works 表要取的全部列（一次查全，避免不同板块再查第二次）。 */
const WORK_COLS = 'work_id,category,name,circle_name,creator,year,characters,tags,' +
                  'popularity,views,cover,source_url,netease_url,description,' +
                  'video_type,video_platform,video_url,original_title,bvid';

/**
 * 读某个板块的作品列表。
 *
 * @param {object} opt
 *   - category: 'music'|'doujin'|'game'|'video'|'art'，不传则返回全部 30 条
 *   - limit:    条数上限（默认 200，最大 500）
 * @returns {Promise<{source, category, count, items}>}
 */
async function getWorks(opt) {
  const raw = (opt && opt.category) || '';
  const category = raw ? String(raw).trim().toLowerCase() : '';
  if (category && WORK_CATEGORIES.indexOf(category) === -1) {
    const e = new Error('invalid_category');
    e.code = 'INVALID_CATEGORY';
    e.valid = WORK_CATEGORIES;
    throw e;
  }
  let limit = parseInt((opt && opt.limit) || '200', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 200;
  if (limit > 500) limit = 500;

  if (rest.hasRestApi()) return getWorksFromRest(category, limit);
  if (pg.hasDatabase()) return getWorksFromPg(category, limit);
  return getWorksFromSnapshot(category, limit);
}

/** ① HTTP API 通道。 */
async function getWorksFromRest(category, limit) {
  const q = { select: WORK_COLS, order: 'work_id.asc', limit: String(limit) };
  if (category) q.category = 'eq.' + category;

  const res = await rest.restRequest('GET', 'works', { query: q });
  if (res.status !== 200) throw rest.restFailed('rest_works_failed', res.data);

  const items = (res.data || []).map(mappers.toWorkItem);
  return { source: 'rest', category: category || 'all', count: items.length, items: items };
}

/** ② pg 直连通道。 */
async function getWorksFromPg(category, limit) {
  const cols = WORK_COLS.split(',').join(', ');
  const sql = category
    ? `SELECT ${cols} FROM works WHERE category = $1 ORDER BY work_id LIMIT $2`
    : `SELECT ${cols} FROM works ORDER BY work_id LIMIT $1`;
  const params = category ? [category, limit] : [limit];
  const rows = await pg.query(sql, params);
  const items = rows.map(mappers.toWorkItem);
  return { source: 'database', category: category || 'all', count: items.length, items: items };
}

/** ③ 快照降级通道：用 works.json（快照字段是驼峰）先还原成库列名，再统一映射。 */
async function getWorksFromSnapshot(category, limit) {
  const s = snap.readSnapshot('works.json');
  if (!s || !Array.isArray(s.items)) throw snap.dataMissing('works_data_unavailable');

  let list = s.items;
  if (category) list = list.filter(function (w) { return w.category === category; });

  const items = list.slice(0, limit).map(function (w) {
    // 快照字段是驼峰，先对齐成库列名，好复用同一个 toWorkItem
    return mappers.toWorkItem({
      work_id: w.workId,
      category: w.category,
      name: w.name,
      circle_name: w.circle,
      creator: w.creator,
      year: w.year,
      characters: w.characters,
      tags: w.tags,
      popularity: w.popularity,
      views: w.views,
      cover: w.cover,
      source_url: w.sourceUrl,
      netease_url: w.neteaseUrl,
      description: w.description,
      video_type: w.type,
      video_platform: w.platform,
      video_url: w.videoUrl || w.url,   // 快照里 video 用 url（库里叫 video_url）
      original_title: w.originalTitle,
      bvid: w.bvid
    });
  });
  return { source: 'snapshot', category: category || 'all', count: items.length, items: items };
}

/* ------------------------------------------------------------ */

/** GET /api/circles —— 社团列表。 */
async function getCircles(opt) {
  let limit = parseInt((opt && opt.limit) || '200', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 200;
  if (limit > 500) limit = 500;

  if (rest.hasRestApi()) {
    const res = await rest.restRequest('GET', 'circles', {
      query: {
        select: 'name,name_en,intro,source_url,avatar,top_platform,followers,platform_url',
        order: 'name.asc',
        limit: String(limit)
      }
    });
    if (res.status !== 200) throw rest.restFailed('rest_circles_failed', res.data);
    const items = (res.data || []).map(mappers.toCircleItem);
    return { source: 'rest', count: items.length, items: items };
  }
  if (pg.hasDatabase()) {
    const rows = await pg.query(
      `SELECT name, name_en, intro, source_url, avatar, top_platform, followers, platform_url
         FROM circles ORDER BY name LIMIT $1`, [limit]
    );
    const items = rows.map(mappers.toCircleItem);
    return { source: 'database', count: items.length, items: items };
  }
  const s = snap.readSnapshot('circles.json');
  if (!Array.isArray(s)) throw snap.dataMissing('circles_data_unavailable');
  const items = s.slice(0, limit).map(mappers.toCircleItem);
  return { source: 'snapshot', count: items.length, items: items };
}

/* ------------------------------------------------------------ */

/**
 * GET /api/original-games —— 原作作品 + 分类。
 *
 * 为什么返回两个数组：my-app 前端读的是 `og.games` 和 `og.categories`，
 * 两个都要，所以这里一次都带回去，前端只发一次请求。
 */
async function getOriginalGames(opt) {
  if (rest.hasRestApi()) {
    const [catRes, gameRes] = await Promise.all([
      rest.restRequest('GET', 'original_game_categories', {
        query: { select: 'id,label,sort_order', order: 'sort_order.asc' }
      }),
      rest.restRequest('GET', 'original_games', {
        query: { select: 'id,th,title,subtitle,category,year,cover,tag', order: 'id.asc' }
      })
    ]);
    if (catRes.status !== 200) throw rest.restFailed('rest_og_categories_failed', catRes.data);
    if (gameRes.status !== 200) throw rest.restFailed('rest_og_games_failed', gameRes.data);

    const categories = (catRes.data || []).map(function (c) {
      return { id: c.id, label: c.label };
    });
    const games = (gameRes.data || []).map(mappers.toOriginalGameItem);
    return { source: 'rest', categories: categories, games: games, count: games.length };
  }

  if (pg.hasDatabase()) {
    const cats = await pg.query(
      'SELECT id, label FROM original_game_categories ORDER BY sort_order');
    const rows = await pg.query(
      `SELECT id, th, title, subtitle, category, year, cover, tag
         FROM original_games ORDER BY id`);
    const categories = cats.map(function (c) { return { id: c.id, label: c.label }; });
    const games = rows.map(mappers.toOriginalGameItem);
    return { source: 'database', categories: categories, games: games, count: games.length };
  }

  const s = snap.readSnapshot('original_games.json');
  if (!s || !Array.isArray(s.games)) throw snap.dataMissing('original_games_data_unavailable');
  const categories = (s.categories || []).map(function (c) { return { id: c.id, label: c.label }; });
  const games = s.games.map(mappers.toOriginalGameItem);
  return { source: 'snapshot', categories: categories, games: games, count: games.length };
}

/* ------------------------------------------------------------ */

/** GET /api/characters —— 角色列表。 */
async function getCharacters(opt) {
  let limit = parseInt((opt && opt.limit) || '200', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 200;
  if (limit > 500) limit = 500;

  if (rest.hasRestApi()) {
    const res = await rest.restRequest('GET', 'characters', {
      query: {
        select: 'id,name,name_en,games,playable_in,twilight_art,moegirl,source_url',
        order: 'id.asc',
        limit: String(limit)
      }
    });
    if (res.status !== 200) throw rest.restFailed('rest_characters_failed', res.data);
    const characters = (res.data || []).map(mappers.toCharacterItem);
    return { source: 'rest', count: characters.length, characters: characters };
  }
  if (pg.hasDatabase()) {
    const rows = await pg.query(
      `SELECT id, name, name_en, games, playable_in, twilight_art, moegirl, source_url
         FROM characters ORDER BY id LIMIT $1`, [limit]);
    const characters = rows.map(mappers.toCharacterItem);
    return { source: 'database', count: characters.length, characters: characters };
  }
  const s = snap.readSnapshot('characters.json');
  if (!s || !Array.isArray(s.characters)) throw snap.dataMissing('characters_data_unavailable');
  const characters = s.characters.slice(0, limit).map(mappers.toCharacterItem);
  return { source: 'snapshot', count: characters.length, characters: characters };
}

/* ------------------------------------------------------------ */

/** GET /api/originals —— 原曲列表。 */
async function getOriginals(opt) {
  let limit = parseInt((opt && opt.limit) || '200', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 200;
  if (limit > 500) limit = 500;

  if (rest.hasRestApi()) {
    const res = await rest.restRequest('GET', 'originals', {
      query: { select: 'id,title,game,track_no,description', order: 'id.asc', limit: String(limit) }
    });
    if (res.status !== 200) throw rest.restFailed('rest_originals_failed', res.data);
    const items = (res.data || []).map(mappers.toOriginalItem);
    return { source: 'rest', count: items.length, items: items };
  }
  if (pg.hasDatabase()) {
    const rows = await pg.query(
      'SELECT id, title, game, track_no, description FROM originals ORDER BY id LIMIT $1', [limit]);
    const items = rows.map(mappers.toOriginalItem);
    return { source: 'database', count: items.length, items: items };
  }
  const s = snap.readSnapshot('originals.json');
  if (!Array.isArray(s)) throw snap.dataMissing('originals_data_unavailable');
  const items = s.slice(0, limit).map(mappers.toOriginalItem);
  return { source: 'snapshot', count: items.length, items: items };
}

/* ============================================================
 * 辅助查询
 * ============================================================ */

/** 判断作品是否存在（写收藏前的前置检查，用来给出更友好的中文提示）。 */
async function workExists(workId) {
  if (rest.hasRestApi()) {
    const res = await rest.restRequest('GET', 'works', {
      query: { select: 'work_id', work_id: 'eq.' + workId, limit: '1' }
    });
    if (res.status !== 200) return null;  // 查询异常 → 不阻断，放行交给外键兜底
    return Array.isArray(res.data) && res.data.length > 0;
  }
  if (pg.hasDatabase()) {
    const rows = await pg.query('SELECT 1 FROM works WHERE work_id = $1', [workId]);
    return rows.length > 0;
  }
  const works = snap.readSnapshot('works.json');
  if (!works || !Array.isArray(works.items)) return null; // 快照缺失 → 无法判断，放行
  return works.items.some(function (w) { return w.workId === workId; });
}

/* ============================================================
 * 统一出口
 * ============================================================ */

module.exports = {
  // 业务接口（server.js 只用这几个）
  getHot: getHot,
  getFavorites: getFavorites,
  addFavorite: addFavorite,
  updateFavorite: updateFavorite,          // Day 22：PATCH 改收藏
  deleteFavorite: deleteFavorite,          // Day 22：DELETE 取消收藏
  workExists: workExists,
  validateFavoriteInput: mappers.validateFavoriteInput,
  validateFavoriteId: mappers.validateFavoriteId,        // Day 22
  validateFavoriteUpdate: mappers.validateFavoriteUpdate, // Day 22
  // Day 21 新增：my-app 作品站 5 类只读数据
  getWorks: getWorks,
  getCircles: getCircles,
  getOriginalGames: getOriginalGames,
  getCharacters: getCharacters,
  getOriginals: getOriginals,
  WORK_CATEGORIES: WORK_CATEGORIES,
  // 状态探测（health 接口判断数据源用）
  hasDatabase: pg.hasDatabase,
  hasRestApi: config.hasRestApi
};
