"""Migrate C-drive project data to D:\\16\\PD1610_81\\migrated_from_C.

Stage 1 (always): copy every file, verify size + sha256 on both sides.
Stage 2 (only for the 4 rebuildable intermediates): delete the C source
AFTER its D copy is byte-identical.

Never touches .workbuddy (project memory) and never deletes anything else.
"""
import os, sys, json, hashlib, shutil, datetime

C_QFILX = r'C:\qfilx'
C_WORKSPACE = r'C:\Users\Tse\WorkBuddy\寒霜刷机'
DEST = r'D:\16\PD1610_81\migrated_from_C'
LOG = r'D:\16\PD1610_81\work\migrate_c_to_d.json'

# Rebuildable / duplicated intermediates previously listed to the user.
DELETE_OK = {
    r'C:\qfilx\flash81\system_81916_raw.img',
    r'C:\qfilx\firmware\full81916\system_81916_raw.img',
    r'C:\qfilx\firmware\full81916\system.new.dat',
    r'C:\qfilx\firmware\full81916\system.new.dat.br',
}

CH = 8 << 20


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(CH)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect(root, prefix):
    out = []
    for dp, dn, fn in os.walk(root):
        # project memory stays in place, always
        dn[:] = [d for d in dn if d != '.workbuddy']
        for f in fn:
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, root)
            dst = os.path.join(DEST, prefix, rel)
            out.append((src, dst))
    return out


def main():
    do_delete = '--delete-verified' in sys.argv
    items = collect(C_QFILX, 'qfilx') + collect(C_WORKSPACE, 'workspace')
    print('待迁移文件数: %d' % len(items), flush=True)
    total = sum(os.path.getsize(s) for s, _ in items)
    print('合计: %.2f GB' % (total / 1073741824), flush=True)

    report = {'time': datetime.datetime.now().isoformat(timespec='seconds'),
              'files': [], 'deleted': [], 'errors': []}
    done_bytes = 0

    for i, (src, dst) in enumerate(items, 1):
        try:
            sz = os.path.getsize(src)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst) and os.path.getsize(dst) == sz:
                status = '已存在(大小一致)'
            else:
                shutil.copy2(src, dst)
                status = '已复制'
            # byte-level verification on both sides
            h_src = sha256(src)
            h_dst = sha256(dst)
            ok = (h_src == h_dst and os.path.getsize(dst) == sz)
            if not ok:
                report['errors'].append({'src': src, 'dst': dst,
                                         'src_sha': h_src, 'dst_sha': h_dst})
                print('  [校验失败] %s' % src, flush=True)
                continue
            report['files'].append({'src': src, 'dst': dst, 'size': sz,
                                    'sha256': h_src, 'status': status})
            done_bytes += sz
            if i % 25 == 0 or i == len(items):
                print('  %d/%d  %.2f/%.2f GB' % (i, len(items),
                      done_bytes / 1073741824, total / 1073741824), flush=True)
        except Exception as e:
            report['errors'].append({'src': src, 'error': str(e)})
            print('  [错误] %s -> %s' % (src, e), flush=True)

    # Stage 2: only after a verified copy exists
    if do_delete:
        verified = {f['src'] for f in report['files']}
        for src in sorted(DELETE_OK):
            if src not in verified:
                report['errors'].append({'src': src, 'error': '未通过校验，拒绝删除'})
                continue
            sz = os.path.getsize(src)
            os.remove(src)
            report['deleted'].append({'src': src, 'size': sz})
            print('  已删除源: %s (%.2f GB)' % (src, sz / 1073741824), flush=True)

    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print()
    print('复制并校验: %d 个 / %.2f GB' % (len(report['files']), done_bytes / 1073741824))
    print('删除源: %d 个 / %.2f GB' % (len(report['deleted']),
          sum(x['size'] for x in report['deleted']) / 1073741824))
    print('错误: %d' % len(report['errors']))
    print('清单: %s' % LOG)


if __name__ == '__main__':
    main()
