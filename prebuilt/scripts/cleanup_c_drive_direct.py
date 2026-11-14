"""Direct C-drive cleanup, no backup (user explicitly requested).

Only the 9 explicitly listed directories. Never touches the C:\\qfilx junction,
P2 (old reversing project), .workbuddy, Documents/Pictures/Downloads.
In-use files are skipped and reported, not force-killed.
"""
import os, json, stat, datetime

LOG = r'D:\16\PD1610_81\work\cleanup_c_drive_direct.json'

P0 = [(r'C:\qfilx_pending_delete', False)]          # remove dir itself
P1 = [
    (r'C:\Users\Tse\AppData\Local\Temp', True),     # keep empty root
    (r'C:\Users\Tse\AppData\Local\npm-cache', True),
    (r'C:\Users\Tse\AppData\Local\uv', True),
    (r'C:\temp', True),
    (r'C:\tmp', True),
]
P3 = [
    (r'C:\Users\Tse\AppData\Local\Quark', True),
    (r'C:\Users\Tse\AppData\Local\Packages', True),
    (r'C:\Users\Tse\AppData\Local\AMD', True),
]


def size_of(root):
    n = tot = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, tot


def purge(root, keep_root):
    skipped = []
    for dp, dn, fs in os.walk(root, topdown=False):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                os.chmod(p, stat.S_IWRITE)
                os.remove(p)
            except OSError as e:
                skipped.append((p, str(e)[:90]))
        if not (keep_root and os.path.abspath(dp) == os.path.abspath(root)):
            try:
                os.rmdir(dp)
            except OSError:
                pass
    if not keep_root:
        try:
            os.rmdir(root)
        except OSError:
            pass
    return skipped


def main():
    rep = {'time': datetime.datetime.now().isoformat(timespec='seconds'),
           'mode': 'direct-no-backup', 'batches': []}
    total = 0
    for tag, group in (('P0', P0), ('P1', P1), ('P3', P3)):
        print('=== %s ===' % tag, flush=True)
        for root, keep in group:
            if not os.path.exists(root):
                print('  [跳过-不存在] %s' % root, flush=True)
                rep['batches'].append({'tag': tag, 'path': root, 'status': '不存在'})
                continue
            n, sz = size_of(root)
            sk = purge(root, keep)
            left_n, left_sz = size_of(root) if os.path.exists(root) else (0, 0)
            freed = sz - left_sz
            total += freed
            rec = {'tag': tag, 'path': root, 'before_files': n, 'before_bytes': sz,
                   'freed_bytes': freed, 'remaining_bytes': left_sz,
                   'skipped_count': len(sk), 'skipped': sk[:10]}
            rep['batches'].append(rec)
            print('  释放 %6.2f GB  剩余 %5.2f GB  跳过 %4d 项  %s' %
                  (freed / 1073741824, left_sz / 1073741824, len(sk), root), flush=True)
    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print()
    print('合计释放: %.2f GB' % (total / 1073741824))
    print('清单: %s' % LOG)


if __name__ == '__main__':
    main()
