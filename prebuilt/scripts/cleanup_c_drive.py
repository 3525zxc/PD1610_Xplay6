"""C-drive cleanup P0 + P1 + P3, 2026-11-11.

Safety:
  P0 already has a fully sha256-verified copy at D:\\16\\PD1610_81\\migrated_from_C\\qfilx.
  P1/P3 are backed up (file count + byte count verified) BEFORE the C source is removed.
  Per-directory batches: any failure leaves that directory's source intact.
  Never touches the C:\\qfilx junction, P2, .workbuddy, Documents/Pictures/Downloads.
"""
import os, sys, json, shutil, datetime, stat

BACKUP = r'D:\C盘清理备份_20261111'
LOG = r'D:\16\PD1610_81\work\cleanup_c_drive.json'

P0 = r'C:\qfilx_pending_delete'
P1 = [
    r'C:\Users\Tse\AppData\Local\Temp',
    r'C:\Users\Tse\AppData\Local\npm-cache',
    r'C:\Users\Tse\AppData\Local\uv',
    r'C:\temp',
    r'C:\tmp',
]
P3 = [
    r'C:\Users\Tse\AppData\Local\Quark',
    r'C:\Users\Tse\AppData\Local\Packages',
    r'C:\Users\Tse\AppData\Local\AMD',
]


def inventory(root):
    n = 0
    total = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, total


def copy_tree(src, dst, skipped):
    os.makedirs(dst, exist_ok=True)
    for dp, dn, fs in os.walk(src):
        rel = os.path.relpath(dp, src)
        target = dst if rel == '.' else os.path.join(dst, rel)
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as e:
            skipped.append((dp, 'mkdir: %s' % e))
            continue
        for f in fs:
            s, d = os.path.join(dp, f), os.path.join(target, f)
            try:
                if os.path.exists(d) and os.path.getsize(d) == os.path.getsize(s):
                    continue
                shutil.copy2(s, d)
            except OSError as e:
                skipped.append((s, str(e)[:100]))


def remove_contents(root, skipped, keep_root):
    """Bottom-up delete; files still in use are skipped and reported."""
    if not os.path.isdir(root):
        return False
    for dp, dn, fs in os.walk(root, topdown=False):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                os.chmod(p, stat.S_IWRITE)
                os.remove(p)
            except OSError as e:
                skipped.append((p, 'del: %s' % str(e)[:80]))
        if not (keep_root and dp == root):
            try:
                os.rmdir(dp)
            except OSError:
                pass
    return True


def process(root, tag, report, do_backup=True):
    if not os.path.exists(root):
        report['batches'].append({'path': root, 'tag': tag, 'status': '不存在，跳过'})
        print('  [跳过-不存在] %s' % root, flush=True)
        return
    n, size = inventory(root)
    entry = {'path': root, 'tag': tag, 'files': n, 'bytes': size,
             'gb': round(size / 1073741824, 3)}
    skipped = []
    if do_backup:
        name = os.path.basename(root.rstrip('\\/')) or 'root'
        dst = os.path.join(BACKUP, tag, name)
        copy_tree(root, dst, skipped)
        bn, bsize = inventory(dst)
        entry['backup'] = dst
        entry['backup_files'] = bn
        entry['backup_bytes'] = bsize
        if bsize < size or bn < n:
            entry['status'] = '备份不完整，保留源'
            entry['skipped'] = skipped[:20]
            report['batches'].append(entry)
            print('  [保留源-备份不完整] %s  %d/%d 文件 %.2f/%.2f GB' %
                  (root, bn, n, bsize / 1073741824, size / 1073741824), flush=True)
            return
        print('  备份校验 OK  %s -> %s  (%d 文件 / %.2f GB)' %
              (root, dst, bn, bsize / 1073741824), flush=True)
    remove_contents(root, skipped, keep_root=(root.endswith('Temp')))
    left = inventory(root)[1] if os.path.exists(root) else 0
    freed = size - left
    entry['freed_bytes'] = freed
    entry['skipped'] = skipped[:20]
    entry['skipped_count'] = len(skipped)
    entry['status'] = '已清理' if freed > 0 else '未释放'
    report['batches'].append(entry)
    print('  %s  %s  释放 %.2f GB  跳过 %d 项' %
          (entry['status'], root, freed / 1073741824, len(skipped)), flush=True)


def main():
    report = {'time': datetime.datetime.now().isoformat(timespec='seconds'),
              'batches': [], 'errors': []}

    # P0: D copy is the verified backup, delete directly
    print('=== P0 ===', flush=True)
    dcopy = r'D:\16\PD1610_81\migrated_from_C\qfilx'
    dn, dsz = inventory(dcopy)
    cn, csz = inventory(P0)
    if dn < cn or dsz < csz:
        print('  [中止] D 盘副本不完整 (%d/%d 文件)' % (dn, cn), flush=True)
        report['errors'].append('P0 D副本不完整')
    else:
        print('  D 副本 %d 文件 / %.2f GB >= C 暂存 %d 文件 / %.2f GB' %
              (dn, dsz / 1073741824, cn, csz / 1073741824), flush=True)
        sk = []
        remove_contents(P0, sk, keep_root=False)
        try:
            os.rmdir(P0)
        except OSError:
            pass
        left = inventory(P0)[1] if os.path.exists(P0) else 0
        report['batches'].append({'path': P0, 'tag': 'P0', 'files': cn,
                                  'bytes': csz, 'backup': dcopy,
                                  'freed_bytes': csz - left,
                                  'skipped': sk[:20], 'skipped_count': len(sk),
                                  'status': '已清理' if left == 0 else '部分残留'})
        print('  P0 释放 %.2f GB  跳过 %d 项' %
              ((csz - left) / 1073741824, len(sk)), flush=True)

    print('=== P1 ===', flush=True)
    for p in P1:
        process(p, 'P1_cache', report)

    print('=== P3 ===', flush=True)
    for p in P3:
        process(p, 'P3_appcache', report)

    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    total = sum(b.get('freed_bytes', 0) for b in report['batches'])
    print()
    print('合计释放: %.2f GB' % (total / 1073741824))
    print('备份位置: %s' % BACKUP)
    print('清单: %s' % LOG)


if __name__ == '__main__':
    main()
