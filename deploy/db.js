'use strict';
/**
 * 数据访问层（Day 17）
 * ------------------------------------------------------------------
 * 解决的问题：接口要读「真库」，但 CloudBase PostgreSQL 不在同一个沙箱里，
 * 而且线上 mock 服务不方便装 npm 依赖。所以这里做**双数据源**：
 *
 *   ① 有数据库连接串（环境变量 PG_URL / DATABASE_URL）
 *      → 通过 pg 驱动直连 PostgreSQL（真库）。本地开发和未来云端同环境走这条。
 *   ② 没有连接串（公网 mock 服务）
 *      → 读 deploy/data/*.json 快照。数据是同步脚本产出的，与库里同源同批。
 *
 * 这样做的好处：
 *   - 接口代码只有一套，切换数据源不用改业务代码；
 *   - 「接口 → 真库」这条链路本地能完整验证（截图证明读的是库）；
 *   - 「接口 → 公网可访问」这条链路也能达成（读快照）。
 *
 * pg 驱动是**按需加载**的：没装 pg 时不会 crash，自动降级到快照。
 */

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');

/** 缓存 pg 模块，避免每次请求都去 require（也避免没装时反复抛错） */
let pgModule = null;
let pgTried = false;

/** 连接池：只有真正要用的时候才创建 */
let pool = null;

/**
 * 取数据库连接串。
 * 支持两种环境变量名（PG_URL 是本项目约定，DATABASE_URL 是业界通用叫法）。
 */
function getConnString() {
  return process.env.PG_URL || process.env.DATABASE_URL || '';
}

/** 尝试加载 pg 驱动。返回 null 表示不可用（没装）。 */
function loadPg() {
  if (pgTried) return pgModule;
  pgTried = true;
  try {
    pgModule = require('pg');
  } catch (e) {
    pgModule = null;
  }
  return pgModule;
}

/** 判断当前是否有可用的真库连接。 */
function hasDatabase() {
  return !!getConnString() && !!loadPg();
}

/** 拿到连接池（懒创建）。 */
function getPool() {
  if (pool) return pool;
  const pg = loadPg();
  if (!pg) throw new Error('pg_driver_missing');
  pool = new pg.Pool({
    connectionString: getConnString(),
    // CloudBase / 云数据库通常要求 SSL；本地直连时若无 SSL 会自动降级
    ssl: process.env.PG_NO_SSL === '1' ? false : { rejectUnauthorized: false },
    max: 5,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 8000
  });
  return pool;
}

/** 执行一条 SQL，返回 rows 数组。 */
async function query(sql, params) {
  const p = getPool();
  const res = await p.query(sql, params || []);
  return res.rows;
}

// ===========================================================================
// HTTP API（PostgREST）通道 —— Day 19 新增
// ---------------------------------------------------------------------------
// 为什么需要它：
//   CloudBase PostgreSQL 有两套访问方式：
//     ① pg 协议直连（上面那套）—— 需要装 pg 驱动，发布平台 pre-check 不放过；
//     ② HTTP API（PostgREST 规范）—— 只要环境 ID + API Key，**不需要任何依赖**。
//   公网版走 ②，就能真正写进真库，而不是写进打包的快照文件（一发布就重置）。
//
// 需要的环境变量：
//   CLOUDBASE_ENV_ID   —— 环境 ID（必须从控制台「复制」取得，别手打）
//   CLOUDBASE_API_KEY  —— 服务端 API Key（service_role，**严禁进前端/仓库**）
//
// 启用顺序：HTTP API > pg 直连 > 快照。
//   本地开发没配 API Key 时自动退回 pg/快照，互不影响。
// ===========================================================================

/** CloudBase 环境变量。 */
function getRestEnvId() {
  return process.env.CLOUDBASE_ENV_ID || '';
}

/** CloudBase 服务端 API Key（service_role，绕过 RLS）。 */
function getRestApiKey() {
  return process.env.CLOUDBASE_API_KEY || '';
}

/** 是否具备走 HTTP API 的条件（环境 ID + API Key 都在）。 */
function hasRestApi() {
  return !!(getRestEnvId() && getRestApiKey());
}

/**
 * 发一个 PostgREST 请求。
 *
 * @param {string} method   GET / POST / PATCH / DELETE
 * @param {string} table    表名（必须在 public schema）
 * @param {object} opt
 *   - query: {select, order, limit, ...} → 拼成 PostgREST 查询串
 *   - body:  写入的 JSON（POST/PATCH 用）
 *   - prefer: Prefer 头的值，如 'return=representation'
 * @returns {Promise<{status:number, headers:Headers, data:any}>}
 */
async function restRequest(method, table, opt) {
  const opts = opt || {};
  const base = 'https://' + getRestEnvId() + '.api.tcloudbasegateway.com/v1/rdb/rest/' + table;

  // 查询参数：PostgREST 用 query string 表达 select/order/limit 等
  const params = [];
  if (opts.query) {
    Object.keys(opts.query).forEach(function (k) {
      const v = opts.query[k];
      if (v === undefined || v === null || v === '') return;
      params.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
  }
  const url = params.length ? base + '?' + params.join('&') : base;

  const headers = {
    Authorization: 'Bearer ' + getRestApiKey(),
    'Content-Type': 'application/json'
  };
  if (opts.prefer) headers.Prefer = opts.prefer;

  const init = { method: method, headers: headers };
  if (opts.body !== undefined) init.body = JSON.stringify(opts.body);

  const res = await fetch(url, init);

  // 204 无内容（DELETE 成功）没有 body
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = text;
    }
  }
  return { status: res.status, headers: res.headers, data: data };
}

/**
 * 判断一个 PostgREST 错误是不是「撞唯一约束」。
 *
 * CloudBase 的实现不认 resolution=ignore-duplicates，而是直接回 409 +
 * DATABASE_23505（PostgreSQL 的 unique_violation 错误码）。
 * 所以我们按这个错误码来认定「重复提交」，比看 content-range 可靠。
 */
function isUniqueViolation(status, data) {
  if (status === 409) return true;
  if (data && typeof data === 'object' && String(data.code || '').indexOf('23505') !== -1) return true;
  return false;
}

/** 读 JSON 快照文件。文件不存在返回 null。 */
function readSnapshot(name) {
  const p = path.join(DATA_DIR, name);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    return null;
  }
}


// ===========================================================================
// GET /api/hot —— 热搜榜
// ===========================================================================

/**
 * 读热搜榜。
 *
 * @param {object} opt
 *   - board: 'fresh'（当日新发布）| 'hot'（历史热门）| 'all'|''（两榜都要）
 *   - limit: 每榜返回条数上限（默认 20，最大 100）—— 这是「余力加练」的查询参数
 *
 * @returns {Promise<{source:string, board:string, limit:number, items:Array, counts:object}>}
 */
async function getHot(opt) {
  const board = (opt && opt.board) || 'all';
  let limit = parseInt((opt && opt.limit) || '20', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 20;
  if (limit > 100) limit = 100;                 // 上限兜底，防止被拉爆

  if (hasRestApi()) {
    // ---- HTTP API 路径（Day 19 新增）：公网版走这条，读的是真库 ----
    const q = {
      select: 'bvid,board,title,author,mid,play,danmaku,favorites,duration,typename,pubdate,cover,description,source,rank_no',
      order: board === 'all' ? 'board.asc,rank_no.asc' : 'rank_no.asc',
      limit: String(board === 'all' ? limit * 2 : limit)
    };
    if (board !== 'all') q.board = 'eq.' + board;

    const res = await restRequest('GET', 'hot_videos', { query: q });
    if (res.status !== 200) {
      const e = new Error('rest_hot_failed');
      e.code = 'REST_FAILED';
      e.detail = res.data;
      throw e;
    }
    const restItems = (res.data || []).map(toHotItem);
    return {
      source: 'rest',
      board,
      limit,
      counts: countByBoard(restItems, limit),
      items: restItems
    };
  }

  if (hasDatabase()) {
    // ---- 真库路径 ----
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
    const rows = await query(sql, params);
    const items = rows.map(toHotItem);
    return {
      source: 'database',
      board,
      limit,
      counts: countByBoard(items, limit),
      items
    };
  }

  // ---- 快照路径（公网降级）----
  const snap = readSnapshot('hot.json');
  if (!snap) {
    const e = new Error('hot_data_unavailable');
    e.code = 'DATA_MISSING';
    throw e;
  }
  let items = [];
  if (board === 'fresh' || board === 'all') {
    items = items.concat((snap.fresh || []).slice(0, limit));
  }
  if (board === 'hot' || board === 'all') {
    items = items.concat((snap.hot || []).slice(0, limit));
  }
  return {
    source: 'snapshot',
    board,
    limit,
    syncedAt: snap.syncedAt || null,
    syncedDate: snap.syncedDate || null,
    counts: countByBoard(items, limit),
    items
  };
}

/** 把数据库行 / 快照项统一成对外的字段结构。 */
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


// ===========================================================================
// GET /api/favorites —— 收藏列表
// ===========================================================================

/**
 * 读收藏列表。
 *
 * Day 17 只有「读」——写入接口（POST）排在 Day 18。
 *
 * @param {object} opt
 *   - userId: 用户标识，默认 'local'（Day 17 还没有登录体系）
 *   - limit:  返回条数上限（默认 50，最大 200）
 */
async function getFavorites(opt) {
  const userId = (opt && opt.userId) || 'local';
  let limit = parseInt((opt && opt.limit) || '50', 10);
  if (!Number.isFinite(limit) || limit <= 0) limit = 50;
  if (limit > 200) limit = 200;

  if (hasRestApi()) {
    // ---- HTTP API 路径（Day 19 新增）----
    // PostgREST 的 JOIN 靠「嵌套 select」表达：
    //   select=id,user_id,...,works(category,name,...)
    // 返回时 works 会是一个对象（外键是单条），要把它拍平回 GET 的形状。
    const res = await restRequest('GET', 'favorites', {
      query: {
        select: 'id,user_id,work_id,note,created_at,' +
                'works(category,name,circle_name,creator,year,cover,tags,characters,description,source_url)',
        user_id: 'eq.' + userId,
        order: 'created_at.desc,id.desc',
        limit: String(limit)
      }
    });
    if (res.status !== 200) {
      const e = new Error('rest_favorites_failed');
      e.code = 'REST_FAILED';
      e.detail = res.data;
      throw e;
    }
    const restItems = (res.data || []).map(function (r) {
      // 把嵌套的 works 拍平到顶层，保持与 pg 路径、快照路径同一形状
      const w = r.works || {};
      return toFavItem({
        id: r.id, user_id: r.user_id, work_id: r.work_id,
        note: r.note, created_at: r.created_at,
        category: w.category, name: w.name, circle_name: w.circle_name,
        creator: w.creator, year: w.year, cover: w.cover,
        tags: w.tags, characters: w.characters,
        description: w.description, source_url: w.source_url
      });
    });
    return { source: 'rest', userId: userId, limit: limit, count: restItems.length, items: restItems };
  }

  if (hasDatabase()) {
    // JOIN works 把作品名/社团/封面一起带出来，前端不用再发一次请求
    const sql = `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
                        w.category, w.name, w.circle_name, w.creator, w.year,
                        w.cover, w.tags, w.characters, w.description, w.source_url
                   FROM favorites f
                   LEFT JOIN works w ON w.work_id = f.work_id
                  WHERE f.user_id = $1
                  ORDER BY f.created_at DESC, f.id DESC
                  LIMIT $2`;
    const rows = await query(sql, [userId, limit]);
    const items = rows.map(toFavItem);
    return { source: 'database', userId: userId, limit: limit, count: items.length, items: items };
  }

  // ---- 快照路径 ----
  const snap = readSnapshot('favorites.json');
  if (!snap) {
    const e = new Error('favorites_data_unavailable');
    e.code = 'DATA_MISSING';
    throw e;
  }
  const items = (snap.items || []).slice(0, limit).map(function (r) {
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

// ===========================================================================
// POST /api/favorites —— 新增一条收藏（Day 18）
// ===========================================================================

/**
 * 校验并规范写入参数。**在入库之前**挡住错误输入，是防脏数据的第一道闸门。
 *
 * 为什么校验要放在 db 层而不是 server 层：
 *   数据库路径和快照路径都要过同一套校验，放这里两边自动共用，不会漏。
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

  // ---- userId：选填，默认 local（Day 18 还没有登录体系） ----
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

/**
 * 新增一条收藏（Day 18 的写接口）。
 *
 * 两道闸门：
 *   ① 入参校验 —— 见 validateFavoriteInput()，入库前挡住错误输入；
 *   ② 唯一约束 —— favorites 表的 UNIQUE (user_id, work_id)，
 *      配合 ON CONFLICT DO NOTHING，重复提交不会报错也不会多插一行，
 *      而是「插了 0 行」，我们据此返回 409 告诉调用方「已收藏过」。
 *
 * 为什么不能只靠前端禁用按钮防重复：
 *   网络自动重试、脚本直接调用、双开页面都能绕过前端。
 *   唯一可靠的位置是数据库约束 —— 它是最后一道，而且是原子的（并发下也不会漏）。
 *
 * @returns {Promise<{source, created:boolean, duplicate:boolean, item:object}>}
 *   created=true  → 真的插入了新行
 *   duplicate=true → 撞了唯一约束，此前已收藏过
 */
async function addFavorite(input) {
  const { userId, workId, note } = input;

  if (hasRestApi()) {
    // ---- HTTP API 路径（Day 19 新增）：真正写进真库，持久化 ----
    // POST /v1/rdb/rest/favorites + Prefer: return=representation
    //   → 201 返回插入后的整行（含数据库生成的 id、created_at）
    //   → 409 + DATABASE_23505 撞 UNIQUE (user_id, work_id)，即「已收藏过」
    const res = await restRequest('POST', 'favorites', {
      query: { select: 'id,user_id,work_id,note,created_at' },
      prefer: 'return=representation',
      body: { user_id: userId, work_id: workId, note: note }
    });

    if (isUniqueViolation(res.status, res.data)) {
      // 撞唯一约束：去把已有那条读回来，告诉调用方「已收藏过」而不是报错
      const exist = await restRequest('GET', 'favorites', {
        query: {
          select: 'id,user_id,work_id,note,created_at',
          user_id: 'eq.' + userId,
          work_id: 'eq.' + workId,
          limit: '1'
        }
      });
      const row = (exist.data && exist.data[0]) || {};
      return { source: 'rest', created: false, duplicate: true, item: toFavItem(row) };
    }

    if (res.status !== 201) {
      const e = new Error('rest_insert_failed');
      e.code = 'REST_FAILED';
      e.detail = res.data;
      throw e;
    }

    // 插入成功：再查一次（带 JOIN）把作品详情补全，让返回体与 GET 条目同形状
    const inserted = (res.data && res.data[0]) || {};
    const full = await restRequest('GET', 'favorites', {
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
      item: toFavItem({
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

  if (hasDatabase()) {
    // RETURNING 让 INSERT 一次性把插入后的整行带回，不用再查一次
    const sql = `INSERT INTO favorites (user_id, work_id, note)
                 VALUES ($1, $2, $3)
                 ON CONFLICT (user_id, work_id) DO NOTHING
                 RETURNING id, user_id, work_id, note, created_at`;
    const rows = await query(sql, [userId, workId, note]);

    if (rows.length === 0) {
      // 撞唯一约束：没插进去，但不算错误 —— 去把已有那条读回来告诉调用方
      const exist = await query(
        `SELECT id, user_id, work_id, note, created_at
           FROM favorites WHERE user_id = $1 AND work_id = $2`,
        [userId, workId]
      );
      return { source: 'database', created: false, duplicate: true, item: toFavItem(exist[0]) };
    }

    // 插入成功：把作品详情 JOIN 回来，让返回体和 GET 的条目形状一致
    const full = await query(
      `SELECT f.id, f.user_id, f.work_id, f.note, f.created_at,
              w.category, w.name, w.circle_name, w.creator, w.year,
              w.cover, w.tags, w.characters, w.description, w.source_url
         FROM favorites f
         LEFT JOIN works w ON w.work_id = f.work_id
        WHERE f.id = $1`,
      [rows[0].id]
    );
    return { source: 'database', created: true, duplicate: false, item: toFavItem(full[0]) };
  }

  // ---- 快照路径（公网无库时）----
  // 用文件里的数据模拟同一套语义：先查重，再追加，保证「重复提交被拒」行为一致。
  const snap = readSnapshot('favorites.json');
  if (!snap) {
    const e = new Error('favorites_data_unavailable');
    e.code = 'DATA_MISSING';
    throw e;
  }
  const items = snap.items || [];

  const dup = items.find(function (r) {
    return r.userId === userId && r.workId === workId;
  });
  if (dup) {
    return {
      source: 'snapshot',
      created: false,
      duplicate: true,
      item: toFavItem(snapshotRowToDbShape(dup))
    };
  }

  // 作品必须存在（对应真库路径的外键约束，快照路径手工补上同等的检查）
  const works = readSnapshot('works.json');
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
  snap.items = items;
  snap.count = items.length;

  try {
    fs.writeFileSync(
      path.join(DATA_DIR, 'favorites.json'),
      JSON.stringify(snap, null, 2) + '\n',
      'utf8'
    );
  } catch (e) {
    const err = new Error('snapshot_write_failed');
    err.code = 'WRITE_FAILED';
    throw err;
  }

  return {
    source: 'snapshot',
    created: true,
    duplicate: false,
    item: toFavItem(snapshotRowToDbShape(row))
  };
}

/** 判断作品是否存在（写收藏前的前置检查，用来给出更友好的中文提示）。 */
async function workExists(workId) {
  if (hasRestApi()) {
    const res = await restRequest('GET', 'works', {
      query: { select: 'work_id', work_id: 'eq.' + workId, limit: '1' }
    });
    if (res.status !== 200) return null;  // 查询异常 → 不阻断，放行交给外键兜底
    return Array.isArray(res.data) && res.data.length > 0;
  }
  if (hasDatabase()) {
    const rows = await query('SELECT 1 FROM works WHERE work_id = $1', [workId]);
    return rows.length > 0;
  }
  const works = readSnapshot('works.json');
  if (!works || !Array.isArray(works.items)) return null; // 快照缺失 → 无法判断，放行
  return works.items.some(function (w) { return w.workId === workId; });
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

/** 把数据库行统一成对外结构（works 的字段是 NULL 也要能兜住）。 */
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


module.exports = {
  getHot: getHot,
  getFavorites: getFavorites,
  addFavorite: addFavorite,
  validateFavoriteInput: validateFavoriteInput,
  workExists: workExists,
  hasDatabase: hasDatabase,
  hasRestApi: hasRestApi
};
