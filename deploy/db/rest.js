'use strict';
/**
 * 数据访问层 · HTTP API（PostgREST）通道
 * ------------------------------------------------------------------
 * CloudBase PostgreSQL 的第二套访问方式：HTTP API（PostgREST 规范）。
 *
 * 为什么需要它（而不是只用 pg 直连）：
 *   - pg 直连需要装 pg 驱动，发布平台的前置检查不放过；
 *   - HTTP API 只要「环境 ID + API Key」两个环境变量，**零依赖**；
 *   - 公网版走这条，写入的是真库，而不是打包进去的快照文件（一发布就重置）。
 *
 * 两个环境变量（见 config.js）：
 *   CLOUDBASE_ENV_ID   —— 环境 ID（必须从控制台「复制」取得）
 *   CLOUDBASE_API_KEY  —— 服务端 API Key（service_role，严禁进前端/仓库）
 *
 * 对外暴露：hasRestApi() / restRequest() / isUniqueViolation()
 */

const config = require('./config');

/**
 * 发一个 PostgREST 请求。
 *
 * @param {string} method   GET / POST / PATCH / DELETE
 * @param {string} table    表名（必须在 public schema）
 * @param {object} opt
 *   - query:  {select, order, limit, ...} → 拼成 PostgREST 查询串
 *   - body:   写入的 JSON（POST/PATCH 用）
 *   - prefer: Prefer 头的值，如 'return=representation'
 * @returns {Promise<{status:number, headers:Headers, data:any}>}
 */
async function restRequest(method, table, opt) {
  const opts = opt || {};
  const base = config.getRestBase(table);

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
    Authorization: 'Bearer ' + config.getRestApiKey(),
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
 *
 * ★ Day 24 余力修复：原来第一行是 `if (status === 409) return true;`，
 *   把**任何** 409 都当成唯一冲突。但 PostgREST 对外键违规（23503）也回 409：
 *       {"code":"DATABASE_23503",
 *        "message":"...violates foreign key constraint \"fk_favorites_work\""}
 *   后果：凡是「关联的作品不存在」这种错，都会被误判成「已收藏过」，
 *   用户拿到一句完全搭不上边的提示。
 *
 *   实测证据：docs/day24/evidence/repro_fk_409-output.txt
 *     - 唯一冲突   → 409 + DATABASE_23505
 *     - 外键违规   → 409 + DATABASE_23503   ← 都被老逻辑判成 true
 *
 *   正确判据：409 只是「客户端语义错误」这个大类，**必须再看错误码**。
 *   只有 23505 才算唯一冲突；其余（含 23503）一律不算，交给上层当真正的失败处理。
 */
function isUniqueViolation(status, data) {
  // 唯一冲突一定是 409（PostgREST 把 PG 的 unique_violation 映射成 409）
  if (status !== 409) return false;
  // 是 409 还不够 —— 必须确认错误码是 23505，否则 23503（外键）等会被误伤
  const code = (data && typeof data === 'object') ? String(data.code || '') : '';
  if (code) return code.indexOf('23505') !== -1;
  // 409 但没带错误码：宁可当「不是唯一冲突」，让上层如实报错，也不要误报「已收藏」
  return false;
}

/** 构造一个统一的 REST 失败错误（带 detail，方便日志排查）。 */
function restFailed(code, detail) {
  const e = new Error(code);
  e.code = 'REST_FAILED';
  e.detail = detail;
  return e;
}

module.exports = {
  hasRestApi: config.hasRestApi,
  restRequest: restRequest,
  isUniqueViolation: isUniqueViolation,
  restFailed: restFailed
};
