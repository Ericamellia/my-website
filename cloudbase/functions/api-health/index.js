'use strict';
/**
 * CloudBase 云函数：api-health（Day 15）
 * ------------------------------------------------------------------
 * 与 deploy/server.js 的 /api/health 返回完全一致（同一份契约，见 docs/api-contract.md），
 * 只是换成了云函数签名：CloudBase 会把 HTTP 请求转成 event 传进来，我们回一个
 * { statusCode, headers, body } 的「云函数 HTTP 响应」结构。
 *
 * 部署方式见同目录 README.md：
 *   tcb fn deploy api-health --force      （CLI 方式）
 */

/** 冷启动后第一次执行的时间，用来算 uptime（云函数实例活了多久）。 */
const STARTED_AT = Date.now();

const SERVICE = 'touhou-search';
const VERSION = '1.0.0';

/** CloudBase 云函数入口。event 在 HTTP 触发时自带 httpContext / path / headers 等字段。 */
exports.main = async (event = {}, context = {}) => {
  // ① 取环境 ID：云函数运行时通常能从上下文拿到，拿不到就退回环境变量
  const env =
    (context && (context.envId || (context.namespace && context.namespace.envId))) ||
    process.env.TCB_ENV ||
    process.env.SCF_NAMESPACE ||
    'cloudbase';

  // ② 取请求方法与路径（HTTP 触发才有；本地/定时触发时给默认值，方便直接调试）
  const http = event.httpContext || {};
  const method = (http.httpMethod || event.method || 'GET').toUpperCase();
  const path = http.path || event.path || '/api/health';

  // ③ 只接受 GET / HEAD，其它方法明确回 405，而不是照常返回 200
  if (method !== 'GET' && method !== 'HEAD') {
    return {
      statusCode: 405,
      headers: jsonHeaders(),
      body: JSON.stringify({ ok: false, error: 'method_not_allowed', allow: ['GET', 'HEAD'] }, null, 2)
    };
  }

  // ④ 组装健康信息：不查库、不调外部服务，保证毫秒级返回
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
};

/** 统一响应头：JSON + 不缓存。跨域白名单 Day 16 再收紧。 */
function jsonHeaders() {
  return {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*'
  };
}
