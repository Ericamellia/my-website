'use strict';
/**
 * 东方同人搜索 · Node 服务（Day 15 起，Day 17 扩展读接口，Day 18 加写接口，Day 19 加 HTTP API 数据源）
 * ------------------------------------------------------------------
 * 一个单端口 HTTP 服务，做四件事：
 *   1) GET  /api/health     → JSON 健康信息（验证链路通不通）
 *   2) GET  /api/hot        → 热搜榜（当日新发布 / 历史热门）  ← Day 17
 *   3) GET  /api/favorites  → 收藏列表                        ← Day 17
 *   4) POST /api/favorites  → 新增一条收藏（防重复 + 防错输）  ← Day 18
 *   5) PATCH /api/favorites/:id → 改收藏备注                    ← Day 22
 *   6) DELETE /api/favorites/:id → 取消收藏                     ← Day 22
 *   7) 其它路径             → 托管 public/ 下的静态页面
 *
 * 刻意不使用任何第三方依赖（不装 express），只用 Node 内置 http/fs/path。
 * 数据源优先级（详见 deploy/db.js）：
 *   ① HTTP API（CLOUDBASE_ENV_ID + CLOUDBASE_API_KEY）→ 真库，写入持久 ← Day 19
 *   ② pg 直连（PG_URL / DATABASE_URL + 装了 pg）      → 真库
 *   ③ 快照（deploy/data/*.json）                      → 兜底，写入不持久
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// 零依赖 .env 加载器（Day 19）
// ---------------------------------------------------------------------------
// 为什么自己写：项目刻意不装第三方依赖（发布平台 pre-check 会挑刺），
// dotenv 虽然轻但也是依赖。.env 格式很简单，二十行足够。
// 规则：KEY=VALUE，忽略空行与 # 开头的注释；**已存在的环境变量优先**（云端注入的不被覆盖）。
(function loadDotEnv() {
  const candidates = [
    path.join(__dirname, '.env'),           // deploy/.env
    path.join(__dirname, '..', '.env')      // 项目根 .env
  ];
  for (const file of candidates) {
    if (!fs.existsSync(file)) continue;
    let text;
    try { text = fs.readFileSync(file, 'utf8'); } catch (e) { continue; }
    text.split(/\r?\n/).forEach(function (line) {
      const s = line.trim();
      if (!s || s.charAt(0) === '#') return;
      const eq = s.indexOf('=');
      if (eq <= 0) return;
      const key = s.slice(0, eq).trim();
      let val = s.slice(eq + 1).trim();
      // 去掉可能的包裹引号
      if ((val.charAt(0) === '"' && val.slice(-1) === '"') ||
          (val.charAt(0) === "'" && val.slice(-1) === "'")) {
        val = val.slice(1, -1);
      }
      if (process.env[key] === undefined) process.env[key] = val;
    });
  }
})();

const db = require('./db');

/** ① 端口：云平台会注入 PORT 环境变量，本地没给就用 3000。必须绑定 0.0.0.0。 */
const PORT = process.env.PORT || 3000;

/** ② 静态资源根目录：所有前端 mock 页面都放在 public/ 下。 */
const ROOT = path.join(__dirname, 'public');

/** ③ 服务启动时记录的时间，用来算 uptime（服务活了多久）。 */
const STARTED_AT = Date.now();

/** ④ 一些固定元信息，直接出现在 health 的返回里，方便一眼看出连的是哪个环境。 */
const SERVICE = 'touhou-search';
const VERSION = '1.0.0';
const ENV = process.env.APP_ENV || 'mock'; // 部署平台/CI 可覆盖；默认 mock

/** ⑤ 常见文件后缀 → Content-Type，浏览器靠它决定是渲染还是下载。 */
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

/** ⑥ 统一写 JSON 响应：设状态码 + Content-Type + CORS 头，然后一次性输出。 */
function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload, null, 2); // 缩进 2 空格，浏览器里直接可读
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',                 // 数据接口绝不缓存，否则看到的是旧结果
    'Access-Control-Allow-Origin': '*'           // Day 16 再做正式跨域白名单，这里先全开方便手机连
  });
  res.end(body);
}

/** ⑥·补 解析 URL 查询参数（Node 内置 URLSearchParams，不引依赖）。 */
function parseQuery(urlPath) {
  const qIndex = urlPath.indexOf('?');
  if (qIndex === -1) return {};
  const out = {};
  const sp = new URLSearchParams(urlPath.slice(qIndex + 1));
  for (const [k, v] of sp.entries()) out[k] = v;
  return out;
}

/** ⑥·补·日志（Day 18 余力加练）：写请求打一行结构化日志，方便以后排查。 */
function logWrite(req, action, extra) {
  const parts = [
    '[write]',
    new Date().toISOString(),
    req.method,
    req.url || '/',
    'action=' + action
  ];
  if (extra && extra.workId) parts.push('workId=' + extra.workId);
  if (extra && extra.userId) parts.push('userId=' + extra.userId);
  if (extra && extra.status) parts.push('status=' + extra.status);
  if (extra && extra.reason) parts.push('reason=' + extra.reason);
  if (extra && extra.source) parts.push('source=' + extra.source);
  console.log(parts.join(' '));
}

/* ============================================================
 * Day 23：把「裸报错」翻译成人话
 * ------------------------------------------------------------
 * 改前的问题：十几个 catch 块都写 `message: String(err.message || err)`，
 * 直接把内部错误的原文抛给调用方。实测会吐出三种东西：
 *
 *   · `rest_query_failed`                       ← 内部英文代号，用户看不懂
 *   · `connect ECONNREFUSED 127.0.0.1:5432`     ← 泄漏内网地址/端口（不只是难看了）
 *   · `[object Object]`                         ← 彻底没意义
 *
 * 改后的做法：**错误详情只进服务端日志，响应体只给人话**。
 *   · toUserError() 把内部错误归类 → 决定 状态码 / error 码 / 中文 message
 *   · 原文仍通过 logError() 打到控制台，排查不受影响
 * ============================================================ */

/** 内部错误码 → 人话。表驱动，加新码只改这里。 */
const ERROR_DIALOGUE = {
  DATA_MISSING: {
    status: 503,
    error: 'data_unavailable',
    message: '数据暂时取不到，可能是后台正在维护。请稍后再试一次。'
  },
  REST_FAILED: {
    status: 502,
    error: 'upstream_failed',
    message: '后端数据服务没有正常响应，请稍后再试。'
  },
  PG_FAILED: {
    status: 502,
    error: 'database_failed',
    message: '数据库连接不上，请稍后再试。'
  },
  WRITE_FAILED: {
    status: 500,
    error: 'write_failed',
    message: '写入没有成功，请稍后再试一次。'
  }
};

/** 从内部错误里取「分类用的码」（各级错误对象字段名不统一，这里逐个试）。 */
function errCodeOf(err) {
  if (!err || typeof err !== 'object') return '';
  return String(err.code || err.error || '');
}

/** 给服务端日志用：把内部错误的**全部细节**拼成一行（只在控制台，不进响应）。 */
function errDetailOf(err) {
  if (!err) return '(no error object)';
  if (typeof err !== 'object') return String(err);
  const bits = [];
  if (err.code) bits.push('code=' + err.code);
  if (err.message) bits.push('message=' + err.message);
  // detail 里常带上游返回的原始结构（如 PostgREST 的 DATABASE_xxxxx），排查全靠它
  if (err.detail) bits.push('detail=' + safeStringify(err.detail));
  if (err.stack) bits.push('at=' + String(err.stack).split('\n')[1]);
  return bits.length ? bits.join(' | ') : safeStringify(err);
}

function safeStringify(v) {
  try {
    return typeof v === 'string' ? v : JSON.stringify(v);
  } catch (e) {
    return '(无法序列化)';
  }
}

/**
 * 把内部错误翻译成**给用户看的**三件套。
 *
 * @returns {{status:number, error:string, message:string}}
 */
function toUserError(err) {
  const code = errCodeOf(err);
  const hit = ERROR_DIALOGUE[code];
  if (hit) return Object.assign({}, hit);
  // 表里没有的码：一律按「服务端出问题了」处理，
  // **绝不**把 err.message 拼进去 —— 那正是「裸报错」的来源。
  return {
    status: 500,
    error: 'internal_error',
    message: '服务出了点问题，请稍后再试。我们已经记下这次异常。'
  };
}

/**
 * 统一的「出错出口」：打日志（含全部细节）+ 回人话（只回三件套）。
 * 所有 catch 块都该用它，避免再出现裸报错。
 *
 * @param {object} req    用于日志
 * @param {object} res    用于响应
 * @param {string} where  出错位置标识，如 'GET /api/hot'
 * @param {Error}  err    内部错误对象
 * @param {object} [opts] { extra: {...} 附加日志字段, status/error/message 可覆盖 }
 */
function sendUserError(req, res, where, err, opts) {
  const t = toUserError(err);
  const status = (opts && opts.status) || t.status;
  const errorCode = (opts && opts.error) || t.error;
  const message = (opts && opts.message) || t.message;

  // ① 服务端日志：全量原文，排查够用
  console.error(
    '[error] ' + new Date().toISOString() + ' ' + where + ' -> ' + status + ' ' + errorCode +
    ' | ' + errDetailOf(err) +
    (opts && opts.extra ? ' | extra=' + safeStringify(opts.extra) : '')
  );

  // ② 给调用方：只有人话，不含任何内部细节
  sendJson(res, status, { ok: false, error: errorCode, message: message });
}

/**
 * ⑥·补 读取请求体并解析 JSON。
 * 带**大小上限**：防止有人塞一个 1GB 的 body 把服务打挂（写接口必须防这个）。
 */
const MAX_BODY_BYTES = 64 * 1024; // 64KB，收藏备注这种小数据足够
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let done = false;

    req.on('data', (c) => {
      if (done) return;
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        done = true;
        const e = new Error('body_too_large');
        e.code = 'BODY_TOO_LARGE';
        req.destroy();
        reject(e);
        return;
      }
      chunks.push(c);
    });

    req.on('end', () => {
      if (done) return;
      done = true;
      const raw = Buffer.concat(chunks).toString('utf8').trim();
      if (raw === '') return resolve({});   // 空 body 当空对象，交给校验层报「缺必填字段」
      try {
        resolve(JSON.parse(raw));
      } catch (e) {
        const err = new Error('invalid_json');
        err.code = 'INVALID_JSON';
        reject(err);
      }
    });

    req.on('error', (e) => {
      if (done) return;
      done = true;
      reject(e);
    });
  });
}

/** ⑥·补 只允许 GET / HEAD，否则回 405（两个读接口共用）。
 *  allow 可传，用来生成准确的「这个路径到底支持哪些方法」提示。 */
function guardMethod(req, res, allow) {
  const allowed = allow || ['GET', 'HEAD'];
  if (allowed.indexOf(req.method) === -1) {
    sendJson(res, 405, { ok: false, error: 'method_not_allowed', allow: allowed });
    return false;
  }
  return true;
}

/**
 * 当前生效的数据源名字。
 *
 * 三种可能（按优先级）：
 *   rest     —— HTTP API（PostgREST）＋ API Key。公网版走这条，**写入真库、持久**。
 *   database —— pg 协议直连真库（本地开发用，发布平台不带 pg）。
 *   snapshot —— 读 deploy/data/*.json 快照（兜底，写不持久）。
 */
function dataSourceName() {
  if (db.hasRestApi()) return 'rest';
  if (db.hasDatabase()) return 'database';
  return 'snapshot';
}

/** ⑦ /api/health 的处理逻辑：只回答「我还活着吗」，不查库、不调外部服务，保证永远快。 */
function handleHealth(req, res) {
  if (!guardMethod(req, res)) return;
  sendJson(res, 200, {
    ok: true,
    service: SERVICE,
    env: ENV,
    version: VERSION,
    time: new Date().toISOString(),
    uptimeSec: Math.round((Date.now() - STARTED_AT) / 1000),
    node: process.version,
    checks: {
      http: 'ok',
      static: fs.existsSync(path.join(ROOT, 'index.html')) ? 'ok' : 'missing',
      // Day 17 起：数据源探针。Day 19 扩展为三态：
      //   rest = HTTP API 真库（可写可持久）、database = pg 直连真库、snapshot = JSON 快照。
      // 注意这里**不真的去连库**（健康检查不能因为数据库慢而变慢），
      // 只是如实报告「配置上有没有凭证」。
      dataSource: dataSourceName()
    }
  });
}

/** ⑦·补 GET /api/hot —— 热搜榜。支持 ?board=fresh|hot|all 与 ?limit=N（余力加练项）。 */
async function handleHot(req, res, urlPath) {
  if (!guardMethod(req, res)) return;
  const q = parseQuery(urlPath);
  try {
    const data = await db.getHot({ board: q.board, limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/hot',
      source: data.source,          // database | snapshot，一眼看出数据从哪来
      board: data.board,
      limit: data.limit,
      syncedAt: data.syncedAt || null,
      syncedDate: data.syncedDate || null,
      counts: data.counts,
      data: data.items
    });
  } catch (err) {
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/** ⑦·补 GET /api/favorites —— 收藏列表。支持 ?userId= 与 ?limit=N。 */
async function handleFavoritesGet(req, res, urlPath) {
  // 这个路径同时支持 GET 和 POST，所以方法不对时要如实列出两种
  if (!guardMethod(req, res, ['GET', 'HEAD', 'POST'])) return;
  const q = parseQuery(urlPath);
  try {
    const data = await db.getFavorites({ userId: q.userId, limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/favorites',
      source: data.source,
      userId: data.userId,
      limit: data.limit,
      count: data.count,
      data: data.items
    });
  } catch (err) {
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/**
 * ⑦·补 POST /api/favorites —— 新增一条收藏（Day 18）。
 *
 * 处理顺序（每一步失败都在「更贵」的操作之前挡住）：
 *   1. 方法对不对（只收 POST）
 *   2. body 能不能解析成 JSON        → 400 invalid_json
 *   3. 字段齐不齐、格式对不对          → 400 missing_xxx / invalid_xxx（中文提示）
 *   4. 作品存不存在                    → 404 work_not_found
 *   5. 落库；撞唯一约束说明已收藏过    → 409 already_favorited
 *
 * 前三步都是「不碰数据库」的纯计算，所以脏请求根本不会打到库上。
 */
async function handleFavoritesPost(req, res) {
  if (req.method !== 'POST') {
    return sendJson(res, 405, { ok: false, error: 'method_not_allowed', allow: ['POST'] });
  }

  // 第 2 步：解析 body
  let body;
  try {
    body = await readBody(req);
  } catch (err) {
    if (err.code === 'BODY_TOO_LARGE') {
      logWrite(req, 'reject', { status: 413, reason: 'body_too_large' });
      return sendJson(res, 413, {
        ok: false,
        error: 'body_too_large',
        message: '请求体过大，不能超过 64KB'
      });
    }
    logWrite(req, 'reject', { status: 400, reason: 'invalid_json' });
    return sendJson(res, 400, {
      ok: false,
      error: 'invalid_json',
      message: '请求体不是合法的 JSON，请检查格式（引号、逗号、括号）'
    });
  }

  // 第 3 步：字段校验（中文提示，直接给用户看）
  const check = db.validateFavoriteInput(body);
  if (!check.ok) {
    logWrite(req, 'reject', { status: 400, reason: check.error });
    return sendJson(res, 400, {
      ok: false,
      error: check.error,
      message: check.message
    });
  }
  const { userId, workId, note } = check.value;

  try {
    // 第 4 步：作品必须存在（否则外键会报错，不如提前给一句人话）
    const exists = await db.workExists(workId);
    if (exists === false) {
      logWrite(req, 'reject', { status: 404, reason: 'work_not_found', workId: workId });
      return sendJson(res, 404, {
        ok: false,
        error: 'work_not_found',
        message: `作品 ${workId} 不存在，请先确认 workId 是否正确`
      });
    }

    // 第 5 步：写入
    const r = await db.addFavorite({ userId: userId, workId: workId, note: note });

    // 撞唯一约束 = 重复提交 → 409（不是 500，也不是假装成功）
    if (r.duplicate) {
      logWrite(req, 'duplicate', {
        status: 409, workId: workId, userId: userId, source: r.source
      });
      return sendJson(res, 409, {
        ok: false,
        error: 'already_favorited',
        message: `你已经收藏过 ${workId} 了，不用重复提交`,
        data: r.item
      });
    }

    logWrite(req, 'created', {
      status: 201, workId: workId, userId: userId, source: r.source
    });
    sendJson(res, 201, {
      ok: true,
      endpoint: '/api/favorites',
      action: 'created',
      source: r.source,
      message: '收藏成功',
      data: r.item
    });
  } catch (err) {
    logWrite(req, 'error', { status: 500, reason: errCodeOf(err) || 'unknown' });
    sendUserError(req, res, 'POST /api/favorites', err, {
      extra: { userId: userId, workId: workId }
    });
  }
}

/* ============================================================
 * Day 21 新增：my-app 作品站的 5 个只读数据接口
 * ------------------------------------------------------------
 * 这 5 个接口的作用：把 my-app 原本读「打包在仓库里的本地 JSON」
 * 换成读真库 —— 数据改了不用重新打包前端。
 *
 * 统一响应格式（和 /api/hot、/api/favorites 保持一致）：
 *   { ok, endpoint, source, ...业务字段, data }
 *   source 会如实告诉你数据来自哪条通道（rest / database / snapshot）。
 *
 * 5 个接口的「业务字段」各不相同，是因为 my-app 前端的读法不同：
 *   /api/works          → data[]          前端按板块取数组
 *   /api/circles        → data[]          前端当数组用
 *   /api/original-games → categories[], games[]   前端读 og.games / og.categories
 *   /api/characters     → characters[]    前端读 .characters
 *   /api/originals      → data[]          前端当数组用
 * ============================================================ */

/** ⑧·补 GET /api/works?category=music&limit=200 —— 按板块读作品。 */
async function handleWorks(req, res, urlPath) {
  if (!guardMethod(req, res)) return;
  const q = parseQuery(urlPath);
  try {
    const d = await db.getWorks({ category: q.category, limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/works',
      source: d.source,
      category: d.category,
      count: d.count,
      data: d.items
    });
  } catch (err) {
    // 分类传错 → 400，并如实告诉调用方有哪些合法值（不要把锅甩给「查询失败」）
    if (err.code === 'INVALID_CATEGORY') {
      return sendJson(res, 400, {
        ok: false,
        error: 'invalid_category',
        message: 'category 只能是：' + (db.WORK_CATEGORIES || []).join(' / '),
        valid: db.WORK_CATEGORIES || []
      });
    }
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/** ⑧·补 GET /api/circles —— 社团列表。 */
async function handleCircles(req, res, urlPath) {
  if (!guardMethod(req, res)) return;
  const q = parseQuery(urlPath);
  try {
    const d = await db.getCircles({ limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/circles',
      source: d.source,
      count: d.count,
      data: d.items
    });
  } catch (err) {
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/** ⑧·补 GET /api/original-games —— 原作作品 + 分类（两个数组一起给）。 */
async function handleOriginalGames(req, res) {
  if (!guardMethod(req, res)) return;
  try {
    const d = await db.getOriginalGames({});
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/original-games',
      source: d.source,
      count: d.count,
      categories: d.categories,     // 前端读 og.categories
      games: d.games                // 前端读 og.games
    });
  } catch (err) {
    // 这个 handler 不接 urlPath（路径固定，没有查询串要解析），
    // 所以 where 直接写死，别去 split 一个不存在的参数。
    sendUserError(req, res, 'GET /api/original-games', err);
  }
}

/** ⑧·补 GET /api/characters —— 角色列表。 */
async function handleCharacters(req, res, urlPath) {
  if (!guardMethod(req, res)) return;
  const q = parseQuery(urlPath);
  try {
    const d = await db.getCharacters({ limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/characters',
      source: d.source,
      count: d.count,
      characters: d.characters     // 前端读 .characters
    });
  } catch (err) {
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/** ⑧·补 GET /api/originals —— 原曲列表。 */
async function handleOriginals(req, res, urlPath) {
  if (!guardMethod(req, res)) return;
  const q = parseQuery(urlPath);
  try {
    const d = await db.getOriginals({ limit: q.limit });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/originals',
      source: d.source,
      count: d.count,
      data: d.items
    });
  } catch (err) {
    sendUserError(req, res, 'GET ' + urlPath.split('?')[0], err);
  }
}

/* ============================================================
 * Day 22 新增：PATCH / DELETE /api/favorites/:id
 * ------------------------------------------------------------
 * 路径带参数，所以要先把 /api/favorites/3 里的 "3" 抠出来。
 * 这一层只做「切路径」，不做校验 —— 校验交给数据层（三条通道共用一套），
 * 免得三条通道各写一遍、改一处漏两处。
 * ============================================================ */

/**
 * 从 /api/favorites/:id 里取出 id 段。
 * 返回 null 表示路径形状不对（不是 /api/favorites/<一段>）。
 */
function matchFavoritesId(route) {
  // 要求精确两段：favorites / <id>
  const m = /^\/api\/favorites\/([^/]+)$/.exec(route);
  return m ? m[1] : null;
}

/**
 * ⑪ PATCH /api/favorites/:id —— 改收藏备注。
 *
 * 处理顺序（和 POST 一样，把便宜检查放前面）：
 *   1. 方法对不对           → 405
 *   2. id 是不是正整数       → 400 invalid_id
 *   3. body 解析             → 400 invalid_json
 *   4. 字段校验（只能给 note，且至少给一个）→ 400
 *   5. 改库；改到 0 行说明该条不存在 → 404
 *
 * ★ 删除为什么没有「防重复」问题、而 PATCH 也没有：
 *   两者都是**幂等**的 —— PATCH 改两次同一备注，结果一样；
 *   DELETE 删两次，第二次回 404 而不是报错。真正需要防重复的是 POST（会多一行）。
 */
async function handleFavoritesPatch(req, res, rawId) {
  if (req.method !== 'PATCH') {
    return sendJson(res, 405, { ok: false, error: 'method_not_allowed', allow: ['PATCH'] });
  }

  // 第 2 步：id 校验
  const idCheck = db.validateFavoriteId(rawId);
  if (!idCheck.ok) {
    logWrite(req, 'reject', { status: 400, reason: idCheck.error });
    return sendJson(res, 400, { ok: false, error: idCheck.error, message: idCheck.message });
  }
  const id = idCheck.value;

  // 第 3 步：解析 body
  let body;
  try {
    body = await readBody(req);
  } catch (err) {
    if (err.code === 'BODY_TOO_LARGE') {
      logWrite(req, 'reject', { status: 413, reason: 'body_too_large' });
      return sendJson(res, 413, { ok: false, error: 'body_too_large', message: '请求体过大，不能超过 64KB' });
    }
    logWrite(req, 'reject', { status: 400, reason: 'invalid_json' });
    return sendJson(res, 400, {
      ok: false, error: 'invalid_json', message: '请求体不是合法的 JSON，请检查格式（引号、逗号、括号）'
    });
  }

  // 第 4 步：字段校验
  const check = db.validateFavoriteUpdate(body);
  if (!check.ok) {
    logWrite(req, 'reject', { status: 400, reason: check.error });
    return sendJson(res, 400, { ok: false, error: check.error, message: check.message });
  }

  try {
    // 第 5 步：改库
    const r = await db.updateFavorite(id, check.value);

    // 改到 0 行 = 这条收藏不存在 → 404（不是 200，也不是 500）
    if (r.notFound) {
      logWrite(req, 'reject', { status: 404, reason: 'favorite_not_found:id=' + id });
      return sendJson(res, 404, {
        ok: false,
        error: 'favorite_not_found',
        message: `没有找到 id=${id} 的收藏，可能已经被取消了`
      });
    }

    logWrite(req, 'updated', { status: 200, source: r.source });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/favorites/' + id,
      action: 'updated',
      source: r.source,
      message: '备注已更新',
      data: r.item
    });
  } catch (err) {
    logWrite(req, 'error', { status: 500, reason: errCodeOf(err) || 'unknown' });
    sendUserError(req, res, 'PATCH /api/favorites/' + id, err, {
      extra: { id: id }
    });
  }
}

/**
 * ⑫ DELETE /api/favorites/:id —— 取消收藏。
 *
 * 处理顺序：
 *   1. 方法对不对        → 405
 *   2. id 是不是正整数    → 400
 *   3. 删；该条不存在     → 404（不是假装成功）
 *
 * ★ 为什么「不存在」要回 404 而不是 200：
 *   删除最容易出的事故就是**误以为删掉了**。
 *   如果 id 写错（比如把 7 打成 77）也回 200，调用方会以为「已取消」，
 *   结果那条收藏还好好躺在库里 —— 这种「静默失败」比直接报错危险得多。
 *   回 404 是逼调用方面对「你删的东西根本不在」。
 *
 * ★ DELETE 没有 body，所以不需要 readBody；也不需要字段校验。
 *   唯一的输入就是 URL 里的那个 id。
 */
async function handleFavoritesDelete(req, res, rawId) {
  if (req.method !== 'DELETE') {
    return sendJson(res, 405, { ok: false, error: 'method_not_allowed', allow: ['DELETE'] });
  }

  // 第 2 步：id 校验（和 PATCH 共用同一套，非法 id 绝不能拼进 SQL）
  const idCheck = db.validateFavoriteId(rawId);
  if (!idCheck.ok) {
    logWrite(req, 'reject', { status: 400, reason: idCheck.error });
    return sendJson(res, 400, { ok: false, error: idCheck.error, message: idCheck.message });
  }
  const id = idCheck.value;

  try {
    // 第 3 步：删（数据层内部是「先查 → 再删」，被删的那条会原样带回）
    const r = await db.deleteFavorite(id);

    // 没找到 = 这 id 不存在（或已经被删过了）→ 404
    if (r.notFound) {
      logWrite(req, 'reject', { status: 404, reason: 'favorite_not_found:id=' + id });
      return sendJson(res, 404, {
        ok: false,
        error: 'favorite_not_found',
        message: `没有找到 id=${id} 的收藏，可能已经被取消了`
      });
    }

    logWrite(req, 'deleted', { status: 200, source: r.source });
    sendJson(res, 200, {
      ok: true,
      endpoint: '/api/favorites/' + id,
      action: 'deleted',
      source: r.source,
      message: '已取消收藏',
      // 把被删的那条原样回传：前端可以显示「已取消收藏《XXX》」，
      // 也是误删后唯一的凭证（真删不可逆，只能靠这个知道删了什么）。
      data: r.item
    });
  } catch (err) {
    logWrite(req, 'error', { status: 500, reason: errCodeOf(err) || 'unknown' });
    sendUserError(req, res, 'DELETE /api/favorites/' + id, err, {
      extra: { id: id }
    });
  }
}

/**
 * ⑫ 静态文件服务：把 URL 路径映射到 public/ 下的真实文件。
 *
 * Day 21 补：支持三种情况
 *   ① 路径是文件          → 直接返回
 *   ② 路径是目录（无尾斜杠）→ 301 跳到带斜杠的目录形式（浏览器才会正确处理相对路径）
 *   ③ 路径是目录（有尾斜杠）→ 返回该目录下的 index.html
 * 例：/            → public/index.html（作品站）
 *     /verify/     → public/verify/index.html（验证页）
 *     /verify      → 301 → /verify/
 *
 * 兜底逻辑也随之调整：只在**同一目录**下找 index.html，找不到才回全局 index.html。
 * 这样 /verify/xxx 这种不存在的子路径不会错误地渲染成作品站。
 */
function serveStatic(req, res, urlPath) {
  let rel = decodeURIComponent(urlPath.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';

  // 安全：拼接后必须仍在 ROOT 内，挡掉 ../ 目录穿越
  const filePath = path.join(ROOT, rel);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('403 Forbidden');
  }

  // 目录处理：无尾斜杠 → 301 补斜杠；有尾斜杠 → 指向 index.html
  let stat = null;
  try { stat = fs.statSync(filePath); } catch (e) { stat = null; }

  if (stat && stat.isDirectory()) {
    if (!urlPath.endsWith('/')) {
      res.writeHead(301, { Location: urlPath.split('?')[0] + '/' + (urlPath.indexOf('?') > -1 ? urlPath.slice(urlPath.indexOf('?')) : '') });
      return res.end();
    }
    return sendFile(res, path.join(filePath, 'index.html'), rel + 'index.html');
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      // 文件不存在：兜底回**同目录**的 index.html（找不到再回根 index.html）
      const dirOfRel = rel.replace(/[^/]*$/, '');      // 如 /verify/xxx → /verify/
      const local = path.join(ROOT, dirOfRel, 'index.html');
      const candidates = [];
      if (dirOfRel !== '/') candidates.push(local);
      candidates.push(path.join(ROOT, 'index.html'));

      let i = 0;
      const tryNext = () => {
        if (i >= candidates.length) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          return res.end('404 Not Found: ' + rel);
        }
        const cand = candidates[i++];
        fs.readFile(cand, (e2, fb) => {
          if (e2) return tryNext();
          res.writeHead(200, { 'Content-Type': MIME['.html'] });
          res.end(fb);
        });
      };
      tryNext();
      return;
    }
    const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-cache' });
    res.end(data);
  });
}

/** 读一个确定的文件并返回（目录索引用）。 */
function sendFile(res, absPath, relForLog) {
  fs.readFile(absPath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('404 Not Found: ' + relForLog);
    }
    const type = MIME[path.extname(absPath).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-cache' });
    res.end(data);
  });
}

/** ⑨ 服务器主循环：先分派 /api/*，其余一律走静态。 */
const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('#')[0];
  // 归一化：去掉结尾斜杠，让 /api/hot 和 /api/hot/ 等价
  const route = (urlPath.split('?')[0] || '/').replace(/\/+$/, '') || '/';

  // ---- Day 23 余力加练：一行请求日志（时间 / 路径 / 结果）----
  // 怎么拿到「结果」：handler 各自 sendJson，主循环看不到最终状态码，
  // 所以这里**包一层 res.writeHead** 把 status 记下来，等响应结束时统一打日志。
  // 挂在最前面，保证无论走 /api/* 还是静态、无论成功还是报错都会记上。
  const t0 = Date.now();
  const origWriteHead = res.writeHead;
  let logged = false;
  res.writeHead = function () {
    res.__status = arguments[0];
    return origWriteHead.apply(res, arguments);
  };
  res.on('finish', function () {
    if (logged) return;
    logged = true;
    const ms = Date.now() - t0;
    const status = res.__status || res.statusCode || 0;
    // 一条日志三段：时间 / 路径（含查询串） / 结果（状态码 + 耗时）
    console.log('[req] ' + new Date().toISOString() +
      ' ' + req.method + ' ' + (req.url || '/') +
      ' -> ' + status + ' ' + ms + 'ms');
  });

  if (route === '/api/health') return handleHealth(req, res);
  if (route === '/api/hot') return handleHot(req, res, urlPath);

  // /api/favorites 支持两种方法：GET 读列表，POST 新增（Day 18）
  if (route === '/api/favorites') {
    if (req.method === 'POST') return handleFavoritesPost(req, res);
    return handleFavoritesGet(req, res, urlPath);
  }

  // Day 22 新增：/api/favorites/:id —— PATCH 改备注 / DELETE 取消收藏
  const favId = matchFavoritesId(route);
  if (favId !== null) {
    if (req.method === 'PATCH') return handleFavoritesPatch(req, res, favId);
    if (req.method === 'DELETE') return handleFavoritesDelete(req, res, favId);
    // 这条路径支持 PATCH + DELETE，方法不对要如实列出（而不是掉进 501）
    return sendJson(res, 405, {
      ok: false, error: 'method_not_allowed', allow: ['PATCH', 'DELETE'], path: route
    });
  }

  // ---- Day 21 新增：my-app 作品站的 5 个只读数据接口 ----
  if (route === '/api/works') return handleWorks(req, res, urlPath);
  if (route === '/api/circles') return handleCircles(req, res, urlPath);
  if (route === '/api/original-games') return handleOriginalGames(req, res);
  if (route === '/api/characters') return handleCharacters(req, res, urlPath);
  if (route === '/api/originals') return handleOriginals(req, res, urlPath);

  if (urlPath.startsWith('/api/')) {
    // 其余 /api/* 还没实现，明确返回 501 而不是假装成功
    return sendJson(res, 501, { ok: false, error: 'not_implemented', path: route });
  }
  serveStatic(req, res, urlPath);
});

/** ⑩ 启动：监听 PORT，绑定所有网卡（0.0.0.0）才能被外部访问。 */
server.listen(PORT, '0.0.0.0', () => {
  console.log('[server] listening on 0.0.0.0:' + PORT + '  env=' + ENV);
  console.log('[server] data source: ' + (function () {
    var s = dataSourceName();
    if (s === 'rest') return 'rest (CLOUDBASE_API_KEY 已配置 → HTTP API 真库，写入持久)';
    if (s === 'database') return 'database (PG_URL 已配置 → pg 直连真库)';
    return 'snapshot (deploy/data/*.json，写入不持久)';
  })());
  console.log('[server] health:    /api/health');
  console.log('[server] hot:       /api/hot?board=fresh|hot|all&limit=20');
  console.log('[server] favorites: /api/favorites?userId=local&limit=50   (GET)');
  console.log('[server] favorites: /api/favorites  {workId,note?}          (POST，Day 18)');
  console.log('[server] favorites: /api/favorites/3  {note}                (PATCH 改备注，Day 22)');
  console.log('[server] favorites: /api/favorites/3                      (DELETE 取消收藏，Day 22)');
  console.log('[server] works:     /api/works?category=music|doujin|game|video|art   (Day 21)');
  console.log('[server] circles:   /api/circles                                (Day 21)');
  console.log('[server] og:        /api/original-games                         (Day 21)');
  console.log('[server] characters:/api/characters                             (Day 21)');
  console.log('[server] originals: /api/originals                              (Day 21)');
  console.log('[server] 作品站:     /                （my-app 完整作品站，数据走真库）');
  console.log('[server] 验证页:     /verify/          （Day 17-20 的 health/写接口/收藏/热搜）');
  console.log('[server] static:    ' + ROOT);
});
