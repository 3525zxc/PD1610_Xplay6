# -*- coding: utf-8 -*-
"""探活：判断 9008 端口当前处于 Sahara 还是 firehose。"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM5"
XML = '<?xml version="1.0" encoding="UTF-8" ?><data><configure MemoryName="ufs" /></data>'

s = serial.Serial(PORT, 115200, timeout=1, write_timeout=5)
s.reset_input_buffer()
s.write(XML.encode())
s.flush()
t0 = time.time()
buf = b""
while time.time() - t0 < 5:
    n = s.in_waiting
    if n:
        buf += s.read(n)
        if buf.rstrip().endswith(b"</data>"):
            break
    else:
        time.sleep(0.05)
s.close()

print("收到 %d 字节" % len(buf))
print("原文: %r" % buf[:400])
if not buf:
    print("结论: 无应答 —— 设备可能在 Sahara 等待 programmer，或已死")
elif b"<response" in buf:
    print("结论: firehose 在线，可直接下发命令")
else:
    print("结论: 有应答但不是 firehose XML，需进一步判断")
