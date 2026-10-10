'use strict';
/**
 * 数据访问层 · JSON 快照通道（降级用）
 * ------------------------------------------------------------------
 * 当既没有 HTTP API 凭证、也没有 pg 连接串时（例如公网 mock 服务），
 * 读 deploy/data/*.json 快照。数据由同步脚本产出，与库里同源同批。
 *
 * 注意：快照是**只读降级**，写入会落在文件里（一发布就重置），
 * 所以生产持久化必须走 ① HTTP API 或 ② pg 直连。
 */

const fs = require('fs');
const path = require('path');
const config = require('./config');

/** 读 JSON 快照文件。文件不存在/解析失败返回 null。 */
function readSnapshot(name) {
  const p = path.join(config.DATA_DIR, name);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    return null;
  }
}

/** 写 JSON 快照文件（快照通道的写入降级）。失败抛 WRITE_FAILED。 */
function writeSnapshot(name, obj) {
  try {
    fs.writeFileSync(
      path.join(config.DATA_DIR, name),
      JSON.stringify(obj, null, 2) + '\n',
      'utf8'
    );
  } catch (e) {
    const err = new Error('snapshot_write_failed');
    err.code = 'WRITE_FAILED';
    throw err;
  }
}

/** 构造一个「数据缺失」错误。 */
function dataMissing(code) {
  const e = new Error(code);
  e.code = 'DATA_MISSING';
  return e;
}

module.exports = {
  readSnapshot: readSnapshot,
  writeSnapshot: writeSnapshot,
  dataMissing: dataMissing
};
