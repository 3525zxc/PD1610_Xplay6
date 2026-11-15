# -*- coding: utf-8 -*-
"""
Xplay6 firehose 直连工具（走 9008 的 COM 口，不依赖 QFIL 界面）

前提: 设备已在 9008，且 firehose programmer 已装载。
     若未装载: QSaharaServer.exe -p \\.\COMn -s 13:<prog_emmc_firehose_8996_ddr.elf>

用法:
  py fh_tool.py gpt                  # 探测扇区大小并打印分区表
  py fh_tool.py read <name> <out>     # 按分区名读出
  py fh_tool.py backup [--dir dumps]  # 备份 NV 关键分区
"""
import argparse
import os
import struct
import sys
import time

try:
    import serial
except ImportError:
    import sysconfig
    sys.path.append(sysconfig.get_paths()["purelib"])
    import serial

NV_SET = ["devinfo", "modemst1", "modemst2", "fsg", "fsc", "persist", "misc", "modem"]
GPT_SIG = b"EFI PART"


class Firehose:
    def __init__(self, port, baud=115200):
        self.port = port
        self.ser = serial.Serial(port, baud, timeout=1, write_timeout=10)
        self.sector_size = 512
        self.memory = "emmc"
        self.num_partitions = 6

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def _drain_blocks(self, timeout):
        """读到出现 <response> 且以 </data> 结尾为止（一次应答可能分多段 XML）"""
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            n = self.ser.in_waiting
            if n:
                buf += self.ser.read(n)
                if buf.rstrip().endswith(b"</data>") and b"<response" in buf:
                    return buf
            else:
                time.sleep(0.02)
        raise TimeoutError("等应答超时(%ss)，已收 %d 字节: %r" % (timeout, len(buf), buf[:200]))

    def cmd(self, inner, timeout=15.0):
        xml = ('<?xml version="1.0" encoding="UTF-8" ?><data>%s</data>' % inner).encode("utf-8")
        self.ser.reset_input_buffer()
        self.ser.write(xml)
        self.ser.flush()
        return self._drain_blocks(timeout).decode("utf-8", "replace")

    def ok(self, inner, timeout=15.0):
        text = self.cmd(inner, timeout)
        if 'value="NAK"' in text:
            raise RuntimeError("NAK: " + " ".join(text.split())[:300])
        return text

    def configure(self, memory):
        return self.ok('<configure MemoryName="%s" />' % memory)

    def read_sectors(self, start, count, lun=0, sector_size=None):
        ss = sector_size or self.sector_size
        inner = ('<read SECTOR_SIZE_IN_BYTES="%d" num_partitions="%d" '
                 'physical_partition_number="%d" start_sector="%d" NUM_SECTORS="%d" />'
                 % (ss, self.num_partitions, lun, start, count))
        text = self.cmd(inner, timeout=30)
        if 'value="NAK"' in text:
            raise RuntimeError("NAK: " + " ".join(text.split())[:300])
        if 'rawmode="true"' not in text:
            raise RuntimeError("未进入 rawmode: " + " ".join(text.split())[:300])

        want = count * ss
        data = b""
        t0 = time.time()
        while len(data) < want and time.time() - t0 < 180:
            n = self.ser.in_waiting
            if n:
                data += self.ser.read(min(n, want - len(data)))
            else:
                time.sleep(0.01)
        if len(data) != want:
            raise RuntimeError("数据不足: 期望 %d 实收 %d" % (want, len(data)))

        tail = b""
        t0 = time.time()
        while time.time() - t0 < 10:
            n = self.ser.in_waiting
            if n:
                tail += self.ser.read(n)
                if tail.rstrip().endswith(b"</data>") and b"<response" in tail:
                    break
            else:
                time.sleep(0.02)
        if b'value="ACK"' not in tail:
            raise RuntimeError("数据后未收到 ACK: %r" % tail[:200])
        return data

    def attach(self):
        """确定扇区大小。设备会用 NAK 直接告知正确值，这里以 512 起试。"""
        for ss, mem in ((512, "emmc"), (4096, "ufs")):
            self.configure(mem)
            try:
                self.read_sectors(0, 2, sector_size=ss)
            except RuntimeError as e:
                if "disk sector size" in str(e):
                    continue
                raise
            self.sector_size = ss
            self.memory = mem
            print("[*] 扇区 %d 字节, memory=%s" % (ss, mem))
            return
        raise RuntimeError("无法确定扇区大小")

    def read_gpt(self):
        buf = self.read_sectors(0, 34)
        if GPT_SIG not in buf:
            buf = self.read_sectors(0, 34, sector_size=4096)
            if GPT_SIG not in buf:
                raise RuntimeError("读到的数据里没有 GPT 签名")
            self.sector_size = 4096
        return parse_gpt(buf, self.sector_size)


def parse_gpt(buf, ss):
    hdr = ss
    if buf[hdr:hdr + 8] != GPT_SIG:
        i = buf.find(GPT_SIG)
        if i < 0:
            raise RuntimeError("没找到 GPT 签名")
        hdr = i
    entry_lba, num_entries, entry_size = struct.unpack_from("<QII", buf, hdr + 72)
    off = entry_lba * ss
    parts = []
    for i in range(num_entries):
        o = off + i * entry_size
        if o + 128 > len(buf):
            break
        if buf[o:o + 16] == b"\x00" * 16:
            continue
        first, last = struct.unpack_from("<QQ", buf, o + 32)
        name = buf[o + 56:o + 128].decode("utf-16-le", "ignore").split("\x00")[0]
        if name:
            parts.append((name, first, last - first + 1))
    return parts


def cmd_gpt(args):
    fh = Firehose(args.port)
    try:
        fh.attach()
        parts = fh.read_gpt()
        print("\n[*] 分区表 (%d 个):" % len(parts))
        w = max(len(p[0]) for p in parts)
        for name, first, cnt in parts:
            print("  %-*s start=%-10d sectors=%-8d %8.2f MB" %
                  (w, name, first, cnt, cnt * fh.sector_size / 1048576.0))
    finally:
        fh.close()
    return 0


def cmd_read(args):
    fh = Firehose(args.port)
    try:
        fh.attach()
        parts = {p[0]: p for p in fh.read_gpt()}
        if args.name not in parts:
            print("[x] 无此分区。可用: %s" % ", ".join(sorted(parts)))
            return 1
        _n, first, cnt = parts[args.name]
        print("[*] %s: %d 扇区 %.2f MB" % (args.name, cnt, cnt * fh.sector_size / 1048576.0))
        data = fh.read_sectors(first, cnt)
        with open(args.out, "wb") as f:
            f.write(data)
        print("[+] %s (%d 字节)" % (args.out, len(data)))
    finally:
        fh.close()
    return 0


def cmd_backup(args):
    os.makedirs(args.dir, exist_ok=True)
    fh = Firehose(args.port)
    try:
        fh.attach()
        parts = {p[0]: p for p in fh.read_gpt()}
        print("\n[*] 备份 -> %s" % os.path.abspath(args.dir))
        missing = []
        for name in NV_SET:
            if name not in parts:
                missing.append(name)
                print("  [-] %-10s 不在分区表" % name)
                continue
            _n, first, cnt = parts[name]
            print("  [>] %-10s %7.2f MB ... " % (name, cnt * fh.sector_size / 1048576.0),
                  end="", flush=True)
            data = fh.read_sectors(first, cnt)
            with open(os.path.join(args.dir, name + ".bin"), "wb") as f:
                f.write(data)
            print("%d 字节" % len(data))
        if missing:
            print("\n[!] 缺失: %s" % ", ".join(missing))
    finally:
        fh.close()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="COM5")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gpt").set_defaults(func=cmd_gpt)
    sub.add_parser("detect").set_defaults(func=cmd_gpt)
    sp = sub.add_parser("read"); sp.add_argument("name"); sp.add_argument("out")
    sp.set_defaults(func=cmd_read)
    sp = sub.add_parser("backup"); sp.add_argument("--dir", default="dumps")
    sp.set_defaults(func=cmd_backup)
    a = p.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
