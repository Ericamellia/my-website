'use strict';
/**
 * 数据访问层 · 形状转换与入参校验
 * ------------------------------------------------------------------
 * 这一层是「数据形状的唯一真相」：
 *   三条通道（rest / pg / snapshot）返回的原始行结构各不相同
 *   （snake_case 列名、嵌套 JOIN、驼峰快照字段），
 *   全部在这里收敛成**同一个对外形状**，接口层就不用关心数据从哪来。
 *
 * 含四组函数：
 *   - toHotItem()   热搜榜行 → 对外形状
 *   - toFavItem()   收藏行   → 对外形状
 *   - snapshotRowToDbShape()  快照驼峰字段 → 数据库列名
 *   - validateFavoriteInput() 写接口入参校验
 */

/** 把热搜榜的行/快照项统一成对外的字段结构。 */
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

/** 把收藏行统一成对外结构（works 的字段是 NULL 也要能兜住）。 */
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

/**
 * 校验并规范写入参数。**在入库之前**挡住错误输入，是防脏数据的第一道闸门。
 *
 * 为什么校验要放在数据层而不是接口层：
 *   三条通道（rest / pg / snapshot）都要过同一套校验，放这里三方自动共用，不会漏。
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

  // ---- userId：选填，默认 local（还没有登录体系） ----
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

module.exports = {
  toHotItem: toHotItem,
  countByBoard: countByBoard,
  toFavItem: toFavItem,
  snapshotRowToDbShape: snapshotRowToDbShape,
  validateFavoriteInput: validateFavoriteInput
};
