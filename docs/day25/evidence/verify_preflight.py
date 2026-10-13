# -*- coding: utf-8 -*-
"""
Day 25 · 板块③ 实跑验证 —— 证明 preflight-check 不会「虚报通过」

做法（三步，缺一不可）：
  第 1 步 正常态跑      → 期望全绿（证明不误报）
  第 2 步 故意注入假密钥 → 期望检查项① 转红，并打印出注入的那一行（证明不虚报通过）
  第 3 步 移除后重跑    → 期望恢复全绿（证明检查是确定性的）

每一步的真实输出都存进 docs/day25/evidence/。

用法：python docs/day25/evidence/verify_preflight.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, 'docs', 'day25', 'evidence')
# 注入点：一个「被 git 跟踪」的文件（改完会还原，不留痕）
INJECT_FILE = os.path.join(ROOT, 'my-app', 'index.html')
# 假密钥：连续字符、无 `...` / `[A-Za-z` 这类「自证特征」，保证会被真正命中
FAKE_LINE = '<meta name="x-preflight-probe" content="CLOUDBASE_API_KEY=eyJhbGciOiJIUzI1NiIsFakeButLooksReal000000000000">'


def run(cmd, timeout=180):
    """跑一条命令，返回 (stdout+stderr, exitcode)。"""
    p = subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, timeout=timeout,
                       text=True, encoding='utf-8', errors='replace')
    return (p.stdout or '') + (p.stderr or ''), p.returncode


def save(name, text):
    os.makedirs(EVID, exist_ok=True)
    path = os.path.join(EVID, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return path


def main():
    # ---------- 读原始文件（用于还原）----------
    # ⚠️ 必须用**二进制**读写：文本模式下 Python 会把 LF 转成 CRLF（Windows），
    #    注入再还原会改动换行符 → 工作区出现「不明修改」（本次踩过，文件多了 135 字节）。
    with open(INJECT_FILE, 'rb') as f:
        original = f.read()

    if b'x-preflight-probe' in original:
        print('[FATAL] 文件里已经有探针残留，先清理：', INJECT_FILE)
        return 2

    report = []
    ok = True

    try:
        # ==================== 第 1 步：正常态 ====================
        print('=' * 66)
        print('第 1 步｜正常态跑（期望：全绿，不误报）')
        print('=' * 66)
        out1, code1 = run('bash skills/preflight-check/check.sh')
        print(out1)
        save('step1-normal.txt', out1)
        green1 = (code1 == 0) and ('通过 7 项，失败 0 项' in out1) and ('✅ 全部通过' in out1)
        print('→ 退出码 =', code1, '｜判定：', '全绿 ✅' if green1 else '异常 ❌')
        report.append(('第1步 正常态全绿', green1))
        ok = ok and green1

        # ==================== 第 2 步：注入假密钥 ====================
        print('')
        print('=' * 66)
        print('第 2 步｜故意注入一行假密钥（期望：检查项① 转红，并打印出这一行）')
        print('=' * 66)
        # 二进制追加（Windows 下仍用 \n 保持与仓库一致）
        injected = original.rstrip(b'\r\n') + b'\n' + FAKE_LINE.encode('utf-8') + b'\n'
        with open(INJECT_FILE, 'wb') as f:
            f.write(injected)
        print('已注入到：', os.path.relpath(INJECT_FILE, ROOT))
        print('注入内容：', FAKE_LINE)
        print('')

        out2, code2 = run('bash skills/preflight-check/check.sh')
        print(out2)
        save('step2-injected.txt', out2)

        red2 = (code2 == 1) and ('[FAIL] ① 密钥泄漏' in out2) and ('命中 1 行' in out2) and ('x-preflight-probe' in out2)
        print('→ 退出码 =', code2, '｜判定：', '查出来了 ✅' if red2 else '没查出来 ❌（虚报通过！）')
        report.append(('第2步 注入后 ① 转红且打印该行', red2))
        ok = ok and red2

        # ==================== 第 3 步：移除后重跑 ====================
        print('')
        print('=' * 66)
        print('第 3 步｜移除注入后重跑（期望：恢复全绿，证明是确定性的）')
        print('=' * 66)
        with open(INJECT_FILE, 'wb') as f:
            f.write(original)     # 二进制精确还原（连换行符一起还原）
        print('已还原：', os.path.relpath(INJECT_FILE, ROOT))
        print('')

        out3, code3 = run('bash skills/preflight-check/check.sh')
        print(out3)
        save('step3-restored.txt', out3)
        green3 = (code3 == 0) and ('通过 7 项，失败 0 项' in out3)
        print('→ 退出码 =', code3, '｜判定：', '恢复全绿 ✅' if green3 else '未恢复 ❌')
        report.append(('第3步 移除后恢复全绿', green3))
        ok = ok and green3

    finally:
        # 兜底还原：无论中途怎么失败，都不留探针
        try:
            with open(INJECT_FILE, 'rb') as f:
                cur = f.read()
            if b'x-preflight-probe' in cur:
                with open(INJECT_FILE, 'wb') as f:
                    f.write(original)
                print('[清理] 检测到探针残留，已还原')
        except Exception as e:
            print('[清理失败]', e)

    # ==================== 汇总 ====================
    print('')
    print('=' * 66)
    print('验证汇总')
    print('=' * 66)
    for tag, good in report:
        print('  [%s] %s' % ('PASS' if good else 'FAIL', tag))
    print('')
    print('结论：', '✅ preflight-check 不虚报通过（故障能被查出来）'
          if ok else '❌ 验证未通过')

    summary = '\n'.join('  [%s] %s' % ('PASS' if g else 'FAIL', t) for t, g in report)
    save('verify-summary.txt', 'Day 25 实跑验证汇总\n\n' + summary + '\n\n结论：' +
         ('preflight-check 不虚报通过' if ok else '验证未通过') + '\n')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
