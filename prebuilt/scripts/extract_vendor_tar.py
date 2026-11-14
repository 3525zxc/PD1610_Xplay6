#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解包 Android vendor tar（Windows 上无法创建 Unix 符号链接，故按类型分别处理）

- 普通文件  -> 落盘到 blobs/vendor/...，模式记录到清单
- 符号链接  -> 不落盘，记入 blobs/vendor_links.json（Linux 侧重建）
- 硬链接    -> 同上
- 目录      -> 建目录

输出：
  blobs/vendor/                普通文件树
  blobs/vendor_inventory.json  全量条目（path/type/size/mode/uid/gid/mtime/linkname/sha256）
  blobs/vendor_links.json      仅链接条目
"""
import hashlib
import json
import os
import sys
import tarfile

BASE = r"D:\16\PD1610_81\blobs"
TAR = os.path.join(BASE, "_vendor.tar")
OUT = os.path.join(BASE, "vendor")


def main():
    inv = []
    links = []
    nfile = ndir = nlink = nhard = nother = 0
    os.makedirs(OUT, exist_ok=True)
    with tarfile.open(TAR, "r:") as tf:
        members = tf.getmembers()
        for m in members:
            name = m.name.replace("\\", "/")
            while name.startswith("./"):
                name = name[2:]
            if name in ("", ".", "vendor"):
                continue
            rel = name[len("vendor/"):] if name.startswith("vendor/") else name
            rec = {
                "path": "vendor/" + rel,
                "size": m.size,
                "mode": oct(m.mode),
                "uid": m.uid,
                "gid": m.gid,
                "mtime": int(m.mtime),
            }
            if m.isdir():
                ndir += 1
                os.makedirs(os.path.join(OUT, rel), exist_ok=True)
                rec["type"] = "dir"
            elif m.issym():
                nlink += 1
                rec["type"] = "symlink"
                rec["linkname"] = m.linkname
                links.append({"path": rec["path"], "linkname": m.linkname})
            elif m.islnk():
                nhard += 1
                rec["type"] = "hardlink"
                rec["linkname"] = m.linkname
                links.append({"path": rec["path"], "linkname": m.linkname,
                              "hardlink": True})
            elif m.isfile():
                nfile += 1
                rec["type"] = "file"
                dst = os.path.join(OUT, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                f = tf.extractfile(m)
                h = hashlib.sha256()
                got = 0
                with open(dst, "wb") as o:
                    while True:
                        b = f.read(1 << 20)
                        if not b:
                            break
                        o.write(b)
                        h.update(b)
                        got += len(b)
                rec["sha256"] = h.hexdigest()
                if got != m.size:
                    rec["size_mismatch"] = got
            else:
                nother += 1
                rec["type"] = "other"
            inv.append(rec)

    inv.sort(key=lambda x: x["path"])
    with open(os.path.join(BASE, "vendor_inventory.json"), "w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=0)
    with open(os.path.join(BASE, "vendor_links.json"), "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=0)

    tot = sum(x["size"] for x in inv if x["type"] == "file")
    print("entries=%d  file=%d dir=%d symlink=%d hardlink=%d other=%d" %
          (len(inv), nfile, ndir, nlink, nhard, nother))
    print("regular bytes=%d (%.1f MB)" % (tot, tot / 1e6))
    bad = [x for x in inv if x.get("size_mismatch")]
    print("size mismatch=%d" % len(bad))


if __name__ == "__main__":
    sys.exit(main())
