#!/usr/bin/env python3
"""给 system/core/init/init.cpp 打 PD1610 启动诊断补丁（可重复执行，幂等）。

用途：设备卡厂标且无 adb 时，把 init 自身进度 + 内核日志原始写入 cache 分区，
watchdog 120 s 后自动 reboot 到 bootloader，之后用 recovery 读回 /dev/block/sda3。

写盘位置：/dev/block/sda3（cache, 8:3）偏移 64 MB 起 2 MB（主日志），
          偏移 66 MB 起 2 MB（watchdog 日志）。
"""
import sys, os, io

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    r"//wsl$/PD1610/home/builder/los16/system/core/init/init.cpp"

BEG = "// ===== PD1610 DIAG BEGIN ====="
END = "// ===== PD1610 DIAG END ====="

BLOCK = BEG + r"""
#include <stdarg.h>
#include <sys/reboot.h>
#include <sys/syscall.h>
#include <linux/reboot.h>
#include <time.h>

#define PD_DIAG_BASE     (64L * 1024 * 1024)
#define PD_DIAG_LIMIT    (2L * 1024 * 1024)
#define PD_DIAG_WD_BASE  (66L * 1024 * 1024)
#define PD_WD_SECONDS    100000   /* 诊断期不自动重启（原 120s，实测会打断分析） */

static int  g_pd_fd  = -1;
static long g_pd_off = PD_DIAG_BASE;

static void pd_open(void) {
    if (g_pd_fd >= 0) return;
    if (mknod("/pdblk", S_IFBLK | 0600, makedev(8, 3)) != 0) {
        if (errno != EEXIST) return;
    }
    g_pd_fd = open("/pdblk", O_WRONLY | O_CLOEXEC);
}

static void pd_raw(const char* s, size_t n) {
    if (g_pd_fd < 0) return;
    if (g_pd_off + (long)n > PD_DIAG_BASE + PD_DIAG_LIMIT) return;
    ssize_t w = pwrite(g_pd_fd, s, n, g_pd_off);
    if (w > 0) g_pd_off += (long)w;
}

static void pd_line(const char* fmt, ...) {
    char body[400];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(body, sizeof(body), fmt, ap);
    va_end(ap);
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    char buf[480];
    int m = snprintf(buf, sizeof(buf), "\n[PD %ld.%03ld] %s",
                     (long)ts.tv_sec, (long)(ts.tv_nsec / 1000000), body);
    if (m > 0) {
        pd_raw(buf, (size_t)m);
        int fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
        if (fd >= 0) {
            ssize_t w = write(fd, buf, (size_t)m);
            (void)w;
            close(fd);
        }
    }
}

static void pd_dump_kmsg(void) {
    int fd = open("/proc/kmsg", O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) { pd_line("dump_kmsg open fail errno=%d", errno); return; }
    static char kbuf[16384];
    long total = 0;
    for (int i = 0; i < 20000; i++) {
        ssize_t n = read(fd, kbuf, sizeof(kbuf));
        if (n <= 0) break;
        pd_raw(kbuf, (size_t)n);
        total += (long)n;
        if (total > 1500000L) break;
    }
    close(fd);
    pd_line("dump_kmsg total=%ld", total);
}

static void pd_watchdog(void) {
    pid_t p = fork();
    if (p != 0) return;
    g_pd_off = PD_DIAG_WD_BASE;
    pd_line("watchdog armed 120s");
    for (int i = 0; i < PD_WD_SECONDS; i++) {
        sleep(1);
        if (access("/dev/.pd_stop", F_OK) == 0) { pd_line("watchdog cancelled"); _exit(0); }
    }
    pd_line("WATCHDOG TIMEOUT -> dump kmsg, reboot bootloader");
    pd_dump_kmsg();
    sync();
    syscall(SYS_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
            LINUX_REBOOT_CMD_RESTART2, const_cast<char*>("bootloader"));
    _exit(0);
}
""" + END + "\n"


def sub_once(text, anchor, repl, insert_before=True, label=""):
    n = text.count(anchor)
    if n != 1:
        raise SystemExit("anchor %r matched %d times (expected 1)" % (label or anchor[:40], n))
    return text.replace(anchor, (repl + anchor) if insert_before else (anchor + repl))


def main():
    with io.open(PATH, "r", encoding="utf-8", errors="surrogateescape") as f:
        src = f.read()

    # 幂等：先剥掉旧的诊断片段
    while BEG in src and END in src:
        i = src.index(BEG)
        j = src.index(END) + len(END)
        src = src[:i] + src[j:]
        # 去掉残留空行
        src = src.replace("\n\n\n\n", "\n\n")

    src = sub_once(src, "int main(int argc, char** argv) {", BLOCK + "\n", True, "main")

    src = sub_once(src,
                   '    bool is_first_stage = (getenv("INIT_SECOND_STAGE") == nullptr);',
                   '\n    pd_open();\n    pd_line("PD01 main entry pid=%d", (int)getpid());\n'
                   '    pd_watchdog();\n',
                   False, "is_first_stage")

    src = sub_once(src,
                   '        LOG(INFO) << "init first stage started!";',
                   '\n        pd_line("PD02 dev/proc/sys mounted");\n        pd_dump_kmsg();\n',
                   False, "first-stage-started")

    src = sub_once(src, '        if (!DoFirstStageMount()) {',
                   '        pd_line("PD03 DoFirstStageMount begin");\n', True, "DoFirstStageMount")

    src = sub_once(src, '        SetInitAvbVersionInRecovery();',
                   '        pd_line("PD04 first-stage mount OK");\n        pd_dump_kmsg();\n',
                   True, "avb")

    src = sub_once(src, '        global_seccomp();',
                   '        pd_line("PD05 avb done, seccomp begin");\n', True, "seccomp")

    src = sub_once(src,
                   '        SelinuxSetupKernelLogging();\n        SelinuxInitialize();',
                   '        pd_line("PD06 seccomp done, selinux init begin");\n', True, "selinux-init")

    src = sub_once(src, '        if (selinux_android_restorecon("/init", 0) == -1) {',
                   '        pd_line("PD07 selinux done, restorecon begin");\n', True, "restorecon")

    src = sub_once(src, '        setenv("INIT_SECOND_STAGE", "true", 1);',
                   '        pd_line("PD08 restorecon ok");\n', True, "setenv-second")

    src = sub_once(src, '        execv(path, args);',
                   '        pd_line("PD09 execv %s", path);\n        pd_dump_kmsg();\n',
                   True, "execv")

    src = sub_once(src, '    LOG(INFO) << "init second stage started!";',
                   '\n    pd_line("PD10 second stage entry");\n    pd_dump_kmsg();\n',
                   False, "second-stage")

    src = sub_once(src, '    LoadBootScripts(am, sm);',
                   '\n    pd_line("PD11 boot scripts loaded");\n    pd_dump_kmsg();\n',
                   False, "LoadBootScripts")

    src = sub_once(src, '    am.QueueEventTrigger("early-init");',
                   '    pd_line("PD12 queue early-init");\n', True, "queue-early-init")

    src = sub_once(src, '    while (true) {\n        // By default, sleep until something happens.',
                   '    pd_line("PD13 main loop enter");\n    pd_dump_kmsg();\n',
                   True, "main-loop")

    with io.open(PATH, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(src)

    print("patched OK ->", PATH)
    for ln_no, line in enumerate(src.splitlines(), 1):
        if "pd_line(" in line and "PD0" in line or "PD1" in line and "pd_line(" in line:
            print("  %5d %s" % (ln_no, line.strip()))


if __name__ == "__main__":
    main()
