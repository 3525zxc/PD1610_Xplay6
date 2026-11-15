# -*- coding: utf-8 -*-
"""窗口控制小工具：列窗口 / 取真实坐标 / 前置 / 移动。仅用 ctypes，无第三方依赖。"""
import argparse
import ctypes
import ctypes.wintypes as wt
import sys

u32 = ctypes.WinDLL("user32", use_last_error=True)

try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
except Exception:
    try:
        u32.SetProcessDPIAware()
    except Exception:
        pass

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x0001, 0x0002, 0x0004


def windows():
    out = []

    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        cn = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, cn, 256)
        r = wt.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        out.append({
            "hwnd": hwnd, "pid": pid.value, "title": buf.value, "cls": cn.value,
            "rect": (r.left, r.top, r.right, r.bottom),
            "size": (r.right - r.left, r.bottom - r.top),
        })
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def match(pid=None, title=None, cls=None):
    res = []
    for w in windows():
        if pid and w["pid"] != pid:
            continue
        if title and title.lower() not in w["title"].lower():
            continue
        if cls and cls.lower() not in w["cls"].lower():
            continue
        res.append(w)
    return res


def cmd_list(args):
    rows = windows()
    if args.filter:
        rows = [r for r in rows if args.filter.lower() in (r["title"] + r["cls"]).lower()]
    print("%-10s %-7s %-22s %-34s %s" % ("hwnd", "pid", "class", "title", "rect"))
    for w in sorted(rows, key=lambda x: x["pid"]):
        x, y, r, b = w["rect"]
        print("%-10d %-7d %-22s %-34s (%d,%d)-(%d,%d) %dx%d" % (
            w["hwnd"], w["pid"], w["cls"][:22], w["title"][:34], x, y, r, b,
            w["size"][0], w["size"][1]))
    return 0


def cmd_focus(args):
    ws = match(args.pid, args.title, args.cls)
    if not ws:
        print("[x] 没找到匹配窗口")
        return 1
    w = ws[0]
    u32.ShowWindow(w["hwnd"], SW_RESTORE)
    u32.SetForegroundWindow(w["hwnd"])
    u32.BringWindowToTop(w["hwnd"])
    print("[+] 已前置 hwnd=%d pid=%d title=%s" % (w["hwnd"], w["pid"], w["title"]))
    x, y, r, b = w["rect"]
    print("    rect=(%d,%d)-(%d,%d) size=%dx%d" % (x, y, r, b, r - x, b - y))
    return 0


def cmd_rect(args):
    ws = match(args.pid, args.title, args.cls)
    if not ws:
        print("[x] 没找到匹配窗口")
        return 1
    for w in ws:
        x, y, r, b = w["rect"]
        print("hwnd=%d pid=%d title=%r rect=(%d,%d)-(%d,%d) size=%dx%d" % (
            w["hwnd"], w["pid"], w["title"], x, y, r, b, r - x, b - y))
    return 0


def cmd_move(args):
    ws = match(args.pid, args.title, args.cls)
    if not ws:
        print("[x] 没找到匹配窗口")
        return 1
    w = ws[0]
    u32.SetWindowPos(w["hwnd"], 0, args.x, args.y, args.w, args.h, 0x0040)
    x, y, r, b = w["rect"]
    print("[+] 移到 (%d,%d) %dx%d -> 现在 rect=(%d,%d)-(%d,%d)" % (
        args.x, args.y, args.w, args.h, x, y, r, b))
    return 0


def cmd_top(args):
    ws = match(args.pid, args.title, args.cls)
    if not ws:
        print("[x] 没找到匹配窗口")
        return 1
    w = ws[0]
    after = HWND_TOPMOST if args.on else HWND_NOTOPMOST
    u32.SetWindowPos(w["hwnd"], after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    print("[+] hwnd=%d topmost=%s" % (w["hwnd"], args.on))
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list"); sp.add_argument("--filter"); sp.set_defaults(func=cmd_list)

    for name, fn, helptext in (("focus", cmd_focus, "前置窗口"),
                               ("rect", cmd_rect, "打印窗口坐标"),
                               ("move", cmd_move, "移动/调整窗口")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--pid", type=int); sp.add_argument("--title"); sp.add_argument("--cls")
        if name == "move":
            for a in ("x", "y", "w", "h"):
                sp.add_argument("--" + a, type=int, required=True)
        sp.set_defaults(func=fn)

    sp = sub.add_parser("top", help="置顶/取消置顶")
    sp.add_argument("--pid", type=int); sp.add_argument("--title"); sp.add_argument("--cls")
    sp.add_argument("--on", action="store_true")
    sp.set_defaults(func=cmd_top)

    a = p.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
