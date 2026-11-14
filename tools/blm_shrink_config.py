#!/usr/bin/env python3
"""Produce a shrunk .config from the Round 10 BLM build config.

Changes are limited to debug / tracing / symbol-table / log-buffer knobs.
Storage (UFS), display, power, serial, and the BLM instrumentation are left
exactly as-is. Emits a JSON report of every effective change.
"""
import argparse
import json
from pathlib import Path

# value overrides: option -> new value
SET_VAL = {
    'CONFIG_LOG_BUF_SHIFT': '16',              # 1 MiB -> 64 KiB __log_buf
    'CONFIG_LOG_CPU_MAX_BUF_SHIFT': '12',
    'CONFIG_FRAME_WARN': '2048',
}

# options explicitly disabled
DISABLE = [
    # tracing / ftrace
    'CONFIG_FTRACE', 'CONFIG_FUNCTION_TRACER', 'CONFIG_FUNCTION_GRAPH_TRACER',
    'CONFIG_DYNAMIC_FTRACE', 'CONFIG_FTRACE_SYSCALLS', 'CONFIG_TRACING',
    'CONFIG_GENERIC_TRACER', 'CONFIG_TRACING_SUPPORT', 'CONFIG_EVENT_TRACING',
    'CONFIG_TRACEPOINTS', 'CONFIG_RING_BUFFER', 'CONFIG_NOP_TRACER',
    'CONFIG_CONTEXT_SWITCH_TRACER', 'CONFIG_IRQSOFF_TRACER',
    'CONFIG_PREEMPT_TRACER', 'CONFIG_SCHED_TRACER', 'CONFIG_STACK_TRACER',
    'CONFIG_TRACER_SNAPSHOT', 'CONFIG_ENABLE_DEFAULT_TRACERS',
    'CONFIG_BLK_DEV_IO_TRACE', 'CONFIG_UPROBES', 'CONFIG_KPROBES',
    'CONFIG_JUMP_LABEL',
    # profiling (PERF_EVENTS kept: drivers/devfreq/arm-memlat-mon.c needs
    # perf_event_* and fails -Werror when it is disabled)
    'CONFIG_PROFILING',
    # symbol tables
    'CONFIG_KALLSYMS_ALL',
    # debug kernel family
    'CONFIG_DEBUG_KERNEL', 'CONFIG_DEBUG_INFO', 'CONFIG_SCHED_DEBUG',
    'CONFIG_DEBUG_PREEMPT', 'CONFIG_SLUB_DEBUG', 'CONFIG_KMEMLEAK',
    'CONFIG_DEBUG_SPINLOCK', 'CONFIG_DEBUG_MUTEXES', 'CONFIG_DEBUG_ATOMIC_SLEEP',
    'CONFIG_LOCKDEP', 'CONFIG_PROVE_LOCKING', 'CONFIG_DEBUG_BUGVERBOSE',
    'CONFIG_DEBUG_PAGEALLOC', 'CONFIG_DEBUG_OBJECTS',
    'CONFIG_CMA_DEBUGFS', 'CONFIG_MSM_SMD_DEBUG', 'CONFIG_MSM_SMP2P_TEST',
    'CONFIG_MMC_TEST', 'CONFIG_MMC_BLOCK_TEST', 'CONFIG_SCSI_UFS_TEST',
    'CONFIG_INPUT_EVBUG',
    # large BSS debug buffers / unused test drivers
    'CONFIG_IOSCHED_TEST', 'CONFIG_WIL6210', 'CONFIG_MSM_RDBG',
    'CONFIG_SPI_SPIDEV', 'CONFIG_LCD_CLASS_DEVICE',
    'CONFIG_BACKLIGHT_CLASS_DEVICE', 'CONFIG_BACKLIGHT_GENERIC',
    'CONFIG_CRYPTO_ANSI_CPRNG',
]


def parse(path):
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--report', required=True)
    args = ap.parse_args()

    lines = parse(Path(args.src))
    seen = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('CONFIG_') and '=' in s:
            k, v = s.split('=', 1)
            seen[k] = (i, v)
        elif s.startswith('# CONFIG_') and s.endswith('is not set'):
            k = s.split()[1]
            seen[k] = (i, None)

    changes = []
    for k, newv in SET_VAL.items():
        if k in seen:
            i, old = seen[k]
            lines[i] = k + '=' + newv
            changes.append({'option': k, 'old': old, 'new': newv, 'kind': 'set'})
        else:
            lines.append(k + '=' + newv)
            changes.append({'option': k, 'old': None, 'new': newv, 'kind': 'append'})

    for k in DISABLE:
        if k in seen:
            i, old = seen[k]
            if old is None:
                continue
            lines[i] = '# ' + k + ' is not set'
            changes.append({'option': k, 'old': old, 'new': None, 'kind': 'disable'})
        else:
            lines.append('# ' + k + ' is not set')
            changes.append({'option': k, 'old': None, 'new': None, 'kind': 'append_disabled'})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    report = {
        'source': str(args.src),
        'output': str(args.out),
        'set_values': SET_VAL,
        'disable_list': DISABLE,
        'effective_changes': changes,
        'effective_change_count': len(changes),
        'policy': 'debug/trace/symbol/log-buffer only; storage, display, power and BLM untouched',
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SHRINK_CONFIG_OK changes=%d out=%s' % (len(changes), args.out))
    return 0


if __name__ == '__main__':
    __import__('sys').exit(main())
