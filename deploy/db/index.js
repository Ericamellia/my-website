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
  const res = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      user_id: 'eq.' + userId,
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
  const sql = `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
                      w.category, w.name, w.circle_name, w.creator, w.year,
                      w.cover, w.tags, w.characters, w.description, w.source_url
                 FROM favorites f
                 LEFT JOIN works w ON w.work_id = f.work_id
                WHERE f.user_id = $1
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

  const items = (s.items || []).slice(0, limit).map(function (r) {
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
  // POST + Prefer: return=representation
  //   → 201 返回插入后的整行（含数据库生成的 id、created_at）
  //   → 409 + DATABASE_23505 撞 UNIQUE (user_id, work_id)，即「已收藏过」
  const res = await rest.restRequest('POST', 'favorites', {
    query: { select: 'id,user_id,work_id,note,created_at' },
    prefer: 'return=representation',
    body: { user_id: userId, work_id: workId, note: note }
  });

  if (rest.isUniqueViolation(res.status, res.data)) {
    // 撞唯一约束：把已有那条读回来，告诉调用方「已收藏过」而不是报错
    const exist = await rest.restRequest('GET', 'favorites', {
      query: {
        select: 'id,user_id,work_id,note,created_at',
        user_id: 'eq.' + userId,
        work_id: 'eq.' + workId,
        limit: '1'
      }
    });
    const row = (exist.data && exist.data[0]) || {};
    return { source: 'rest', created: false, duplicate: true, item: mappers.toFavItem(row) };
  }

  if (res.status !== 201) throw rest.restFailed('rest_insert_failed', res.data);

  // 插入成功：再查一次（带 JOIN）把作品详情补全，让返回体与 GET 条目同形状
  const inserted = (res.data && res.data[0]) || {};
  const full = await rest.restRequest('GET', 'favorites', {
    query: {
      select: 'id,user_id,work_id,note,created_at,' +
              'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
      id: 'eq.' + inserted.id,
      limit: '1'
    }
  });
  const r0 = (full.data && full.data[0]) || {};
  const w = r0.works || {};
  return {
    source: 'rest',
    created: true,
    duplicate: false,
    item: mappers.toFavItem({
      id: r0.id !== undefined ? r0.id : inserted.id,
      user_id: r0.user_id || inserted.user_id,
      work_id: r0.work_id || inserted.work_id,
      note: r0.note !== undefined ? r0.note : inserted.note,
      created_at: r0.created_at || inserted.created_at,
      category: w.category, name: w.name, circle_name: w.circle_name,
      creator: w.creator, year: w.year, cover: w.cover,
      tags: w.tags, characters: w.characters,
      description: w.description, source_url: w.source_url
    })
  };
}

/** ② pg 直连通道。 */
async function addFavoriteToPg(userId, workId, note) {
  // RETURNING 让 INSERT 一次性把插入后的整行带回，不用再查一次
  const sql = `INSERT INTO favorites (user_id, work_id, note)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, work_id) DO NOTHING
               RETURNING id, user_id, work_id, note, created_at`;
  const rows = await pg.query(sql, [userId, workId, note]);

  if (rows.length === 0) {
    // 撞唯一约束：没插进去，但不算错误 —— 去把已有那条读回来告诉调用方
    const exist = await pg.query(
      `SELECT id, user_id, work_id, note, created_at
         FROM favorites WHERE user_id = $1 AND work_id = $2`,
      [userId, workId]
    );
    return { source: 'database', created: false, duplicate: true, item: mappers.toFavItem(exist[0]) };
  }

  // 插入成功：把作品详情 JOIN 回来，让返回体和 GET 的条目形状一致
  const full = await pg.query(
    `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
            w.category, w.name, w.circle_name, w.creator, w.year,
            w.cover, w.tags, w.characters, w.description, w.source_url
       FROM favorites f
       LEFT JOIN works w ON w.work_id = f.work_id
      WHERE f.id = $1`,
    [rows[0].id]
  );
  return { source: 'database', created: true, duplicate: false, item: mappers.toFavItem(full[0]) };
}

/** ③ 快照降级通道：用文件里的数据模拟同一套语义（先查重，再追加）。 */
async function addFavoriteToSnapshot(userId, workId, note) {
  const s = snap.readSnapshot('favorites.json');
  if (!s) throw snap.dataMissing('favorites_data_unavailable');
  const items = s.items || [];

  const dup = items.find(function (r) {
    return r.userId === userId && r.workId === workId;
  });
  if (dup) {
    return {
      source: 'snapshot',
      created: false,
      duplicate: true,
      item: mappers.toFavItem(mappers.snapshotRowToDbShape(dup))
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
  // 业务接口（server.js 只用这四个）
  getHot: getHot,
  getFavorites: getFavorites,
  addFavorite: addFavorite,
  workExists: workExists,
  validateFavoriteInput: mappers.validateFavoriteInput,
  // 状态探测（health 接口判断数据源用）
  hasDatabase: pg.hasDatabase,
  hasRestApi: config.hasRestApi
};
