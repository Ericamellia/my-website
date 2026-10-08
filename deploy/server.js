'use strict';
/**
 * 东方同人搜索 · mock 服务（Day 15）
 * ------------------------------------------------------------------
 * 一个单端口 HTTP 服务，只做两件事：
 *   1) GET /api/health  → 返回 JSON 健康信息（第一个上公网的接口，用来验证链路通不通）
 *   2) 其它路径         → 托管 public/ 下的前端 mock 版静态页面
 *
 * 刻意不使用任何第三方依赖（不装 express），只用 Node 内置 http/fs/path，
 * 这样在任何沙箱里都不需要 install，启动最快、失败面最小。
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

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
    'Cache-Control': 'no-store',                 // 健康检查绝不缓存，否则看到的是旧结果
    'Access-Control-Allow-Origin': '*'           // Day 16 再做正式跨域白名单，这里先全开方便手机连
  });
  res.end(body);
}

/** ⑦ /api/health 的处理逻辑：只回答「我还活着吗」，不查库、不调外部服务，保证永远快。 */
function handleHealth(req, res) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    return sendJson(res, 405, { ok: false, error: 'method_not_allowed', allow: ['GET', 'HEAD'] });
  }
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
      static: fs.existsSync(path.join(ROOT, 'index.html')) ? 'ok' : 'missing'
    }
  });
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

/** ⑨ 服务器主循环：先分派 /api/health，其余一律走静态。 */
const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('#')[0];
  if (urlPath.replace(/\/$/, '') === '/api/health') return handleHealth(req, res);
  if (urlPath.startsWith('/api/')) {
    // 其余 /api/* 还没实现（Day 16–20 的业务接口），明确返回 501 而不是假装成功
    return sendJson(res, 501, { ok: false, error: 'not_implemented', path: urlPath });
  }
  serveStatic(req, res, urlPath);
});

/** ⑩ 启动：监听 PORT，绑定所有网卡（0.0.0.0）才能被外部访问。 */
server.listen(PORT, '0.0.0.0', () => {
  console.log('[mock] listening on 0.0.0.0:' + PORT + '  env=' + ENV);
  console.log('[mock] health:  /api/health');
  console.log('[mock] static:  ' + ROOT);
});
