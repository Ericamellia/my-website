'use strict';
/**
 * 东方同人搜索 · Node 服务（Day 15 起，Day 17 扩展读接口，Day 18 加写接口）
 * ------------------------------------------------------------------
 * 一个单端口 HTTP 服务，做四件事：
 *   1) GET  /api/health     → JSON 健康信息（验证链路通不通）
 *   2) GET  /api/hot        → 热搜榜（当日新发布 / 历史热门）  ← Day 17
 *   3) GET  /api/favorites  → 收藏列表                        ← Day 17
 *   4) POST /api/favorites  → 新增一条收藏（防重复 + 防错输）  ← Day 18
 *   5) 其它路径             → 托管 public/ 下的静态页面
 *
 * 刻意不使用任何第三方依赖（不装 express），只用 Node 内置 http/fs/path。
 * 数据库驱动（pg）也是**按需加载**：装了就连真库，没装就降级读 JSON 快照，
 * 详见 deploy/db.js。
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
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
      // Day 17 起：数据源探针。database = 直连真库；snapshot = 读 JSON 快照。
      // 注意这里**不真的去连库**（健康检查不能因为数据库慢而变慢），
      // 只是如实报告「配置上有没有连接串、驱动在不在」。
      dataSource: db.hasDatabase() ? 'database' : 'snapshot'
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
    sendJson(res, 500, {
      ok: false,
      error: err.code === 'DATA_MISSING' ? 'data_unavailable' : 'query_failed',
      message: String(err.message || err)
    });
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
    sendJson(res, 500, {
      ok: false,
      error: err.code === 'DATA_MISSING' ? 'data_unavailable' : 'query_failed',
      message: String(err.message || err)
    });
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
    logWrite(req, 'error', { status: 500, reason: String(err.message || err) });
    sendJson(res, 500, {
      ok: false,
      error: err.code === 'WRITE_FAILED' ? 'write_failed' : 'insert_failed',
      message: '写入失败：' + String(err.message || err)
    });
  }
}

/** ⑧ 静态文件服务：把 URL 路径映射到 public/ 下的真实文件。 */
function serveStatic(req, res, urlPath) {
  // 去掉查询串，并把 / 结尾补成 /index.html
  let rel = decodeURIComponent(urlPath.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';

  // 安全：拼接后必须仍在 ROOT 内，挡掉 ../ 目录穿越
  const filePath = path.join(ROOT, rel);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('403 Forbidden');
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      // 文件不存在：SPA 兜底回 index.html（hash 路由刷新时不会白屏）
      const fallback = path.join(ROOT, 'index.html');
      fs.readFile(fallback, (e2, fb) => {
        if (e2) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          return res.end('404 Not Found: ' + rel);
        }
        res.writeHead(200, { 'Content-Type': MIME['.html'] });
        res.end(fb);
      });
      return;
    }
    const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-cache' });
    res.end(data);
  });
}

/** ⑨ 服务器主循环：先分派 /api/*，其余一律走静态。 */
const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('#')[0];
  // 归一化：去掉结尾斜杠，让 /api/hot 和 /api/hot/ 等价
  const route = (urlPath.split('?')[0] || '/').replace(/\/+$/, '') || '/';

  if (route === '/api/health') return handleHealth(req, res);
  if (route === '/api/hot') return handleHot(req, res, urlPath);

  // /api/favorites 支持两种方法：GET 读列表，POST 新增（Day 18）
  if (route === '/api/favorites') {
    if (req.method === 'POST') return handleFavoritesPost(req, res);
    return handleFavoritesGet(req, res, urlPath);
  }

  if (urlPath.startsWith('/api/')) {
    // 其余 /api/* 还没实现，明确返回 501 而不是假装成功
    return sendJson(res, 501, { ok: false, error: 'not_implemented', path: route });
  }
  serveStatic(req, res, urlPath);
});

/** ⑩ 启动：监听 PORT，绑定所有网卡（0.0.0.0）才能被外部访问。 */
server.listen(PORT, '0.0.0.0', () => {
  console.log('[server] listening on 0.0.0.0:' + PORT + '  env=' + ENV);
  console.log('[server] data source: ' + (db.hasDatabase() ? 'database (PG_URL 已配置)' : 'snapshot (deploy/data/*.json)'));
  console.log('[server] health:    /api/health');
  console.log('[server] hot:       /api/hot?board=fresh|hot|all&limit=20');
  console.log('[server] favorites: /api/favorites?userId=local&limit=50   (GET)');
  console.log('[server] favorites: /api/favorites  {workId,note?}          (POST，Day 18)');
  console.log('[server] static:    ' + ROOT);
});
