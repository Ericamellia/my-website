'use strict';
/**
 * CloudBase 云函数：api-health
 * ------------------------------------------------------------------
 * 与 deploy/server.js 的 /api/health 返回**完全一致**（同一份契约，见 docs/api-contract.md）。
 *
 * ⚠️ Day 21 修正：控制台里这个函数被登记为「HTTP 云函数」，
 *    而 Day 15 写的只有 exports.main（那是「自定义函数」的写法）——
 *    类型与代码不匹配，导致经网关调用时上游返回 443（端口不通，见文档 §真因）。
 *    本地址：http://{envId}.api.tcloudbasegateway.com/v1/functions/api-health?webfn=true
 *    报 x-cloudbase-upstream-status-code: 443。
 *
 * 因此本文件现在**同时**支持两种调用形态：
 *   ① HTTP 云函数  —— 启动一个原生 http 服务监听 9000 端口（零依赖，不用 express）
 *   ② 自定义函数   —— 保留 exports.main，兼容事件调用 / 本地调试
 * 两条通道共用同一份 buildHealthPayload()，保证返回结构永远一致。
 *
 * 部署方式见同目录 README.md：
 *   tcb fn deploy api-health --force      （CLI 方式）
 */

const http = require('http');

/** 冷启动后第一次执行的时间，用来算 uptime（云函数实例活了多久）。 */
const STARTED_AT = Date.now();

const SERVICE = 'touhou-search';
const VERSION = '1.0.0';
const PORT = 9000; // CloudBase HTTP 云函数固定监听 9000

/**
 * 纯函数：根据「方法 + 路径 + 环境」组装响应。
 * HTTP 通道与事件通道都调它，避免两份逻辑漂移。
 * @returns {{statusCode:number, headers:object, body:string}}
 */
function buildHealthPayload(method, path, env) {
  const m = String(method || 'GET').toUpperCase();

  // 只接受 GET / HEAD，其它方法明确回 405
  if (m !== 'GET' && m !== 'HEAD') {
    return {
      statusCode: 405,
      headers: jsonHeaders(),
      body: JSON.stringify(
        { ok: false, error: 'method_not_allowed', allow: ['GET', 'HEAD'] },
        null,
        2
      )
    };
  }

  const payload = {
    ok: true,
    service: SERVICE,
    env: env,
    version: VERSION,
    time: new Date().toISOString(),
    uptimeSec: Math.round((Date.now() - STARTED_AT) / 1000),
    node: process.version,
    path: path,
    checks: {
      http: 'ok',
      static: 'n/a' // 云函数不托管静态资源，静态站单独走静态托管
    }
  };

  return {
    statusCode: 200,
    headers: jsonHeaders(),
    body: JSON.stringify(payload, null, 2)
  };
}

/** 取当前运行环境 ID：优先运行时上下文，其次环境变量，最后兜底。 */
function resolveEnv(context) {
  return (
    (context && (context.envId || (context.namespace && context.namespace.envId))) ||
    process.env.TCB_ENV ||
    process.env.SCF_NAMESPACE ||
    process.env.TENCENTCLOUD_RUNENV ||
    'cloudbase'
  );
}

/* ==================================================================
 * ① HTTP 云函数通道：监听 9000，处理原生 Node HTTP 请求
 * ================================================================== */
const server = http.createServer((req, res) => {
  const result = buildHealthPayload(req.method, req.url || '/api/health', resolveEnv(null));

  // HEAD 请求不要 body
  const isHead = String(req.method).toUpperCase() === 'HEAD';
  res.writeHead(result.statusCode, result.headers);
  res.end(isHead ? undefined : result.body);
});

// 启动监听。CloudBase 要求 HTTP 云函数必须监听 9000。
server.listen(PORT, () => {
  console.log('[api-health] HTTP 云函数已启动，监听端口 ' + PORT);
});

/* ==================================================================
 * ② 自定义函数通道：兼容事件调用 / 本地直接 require 调试
 * ================================================================== */
exports.main = async (event = {}, context = {}) => {
  const httpCtx = event.httpContext || {};
  const method = httpCtx.httpMethod || event.method || 'GET';
  const path = httpCtx.path || event.path || '/api/health';
  return buildHealthPayload(method, path, resolveEnv(context));
};

/** 统一响应头：JSON + 不缓存。 */
function jsonHeaders() {
  return {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*'
  };
}
