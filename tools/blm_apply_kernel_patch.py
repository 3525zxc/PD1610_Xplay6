#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
INCLUDE = '#include <linux/bootloop_monitor.h>\n'


class PatchError(Exception):
    pass


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.blm_', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def copy_into(src, dst):
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(dst))


def add_include(text, preferred_anchor):
    if INCLUDE in text:
        return text, 'skipped'
    if preferred_anchor and preferred_anchor in text:
        return text.replace(preferred_anchor, preferred_anchor + INCLUDE, 1), 'inserted'
    m = re.search(r'^#include .*$', text, re.M)
    if not m:
        raise PatchError('no include anchor')
    pos = m.end() + 1
    return text[:pos] + INCLUDE + text[pos:], 'inserted'


def replace_once(text, anchor, replacement, marker):
    if marker in text:
        return text, 'skipped'
    if anchor not in text:
        raise PatchError('anchor not found: ' + repr(anchor))
    return text.replace(anchor, replacement, 1), 'inserted'


def patch_main(text):
    ops = []
    text, st = add_include(text, '#include <linux/start_kernel.h>\n')
    ops.append(('main_include', st))
    checks = [
        ('main_do_one_initcall',
         'int __init_or_module do_one_initcall(initcall_t fn)\n{\n\tint count = preempt_count();\n\tint ret;\n\tchar msgbuf[64];\n',
         'int __init_or_module do_one_initcall(initcall_t fn)\n{\n\tint count = preempt_count();\n\tint ret;\n\tchar msgbuf[64];\n\tblm_note_initcall((unsigned long)fn);\n\tblm_trace_note(0, "IC", (unsigned long)fn);\n',
         'blm_note_initcall((unsigned long)fn);'),
        ('main_pre_smp_initcalls',
         '\tdo_pre_smp_initcalls();\n',
         '\tblm_write_text("BLM pre_smp_initcalls enter\\n");\n\tdo_pre_smp_initcalls();\n',
         'BLM pre_smp_initcalls enter'),
        ('main_smp_init',
         '\tsmp_init();\n',
         '\tblm_write_text("BLM smp_init enter\\n");\n\tsmp_init();\n',
         'BLM smp_init enter'),
        ('main_sched_init_smp',
         '\tsched_init_smp();\n',
         '\tblm_write_text("BLM sched_init_smp enter\\n");\n\tsched_init_smp();\n',
         'BLM sched_init_smp enter'),
        ('main_rootfs_check',
         '\tif (!ramdisk_execute_command)\n\t\tramdisk_execute_command = "/init";\n',
         '\tblm_write_text("BLM ramdisk_execute_command check\\n");\n\tif (!ramdisk_execute_command)\n\t\tramdisk_execute_command = "/init";\n',
         'BLM ramdisk_execute_command check'),
        ('main_load_default_modules',
         '\tload_default_modules();\n',
         '\tload_default_modules();\n\tblm_write_text("BLM kernel_init_freeable done\\n");\n',
         'BLM kernel_init_freeable done'),
        ('main_start_kernel',
         'asmlinkage __visible void __init start_kernel(void)\n{\n\tchar *command_line;\n\tchar *after_dashes;\n',
         'asmlinkage __visible void __init start_kernel(void)\n{\n\tchar *command_line;\n\tchar *after_dashes;\n\tblm_early_init(__fdt_pointer);\n\tblm_mark(BLM_STAGE_START_KERNEL);\n',
         'blm_early_init(__fdt_pointer);'),
        ('main_before_setup_arch',
         '\tsetup_arch(&command_line);\n',
         '\tblm_mark(BLM_STAGE_BEFORE_SETUP_ARCH);\n\tsetup_arch(&command_line);\n\tblm_mark(BLM_STAGE_AFTER_SETUP_ARCH);\n',
         'blm_mark(BLM_STAGE_BEFORE_SETUP_ARCH);'),
        ('main_console_init',
         '\tconsole_init();\n',
         '\tconsole_init();\n\tblm_mark(BLM_STAGE_CONSOLE_INIT);\n',
         'blm_mark(BLM_STAGE_CONSOLE_INIT);'),
        ('main_rest_init',
         'static noinline void __init_refok rest_init(void)\n{\n\tint pid;\n',
         'static noinline void __init_refok rest_init(void)\n{\n\tint pid;\n\tblm_mark(BLM_STAGE_REST_INIT);\n\tblm_arm_watchdog();\n',
         'blm_arm_watchdog();'),
        ('main_kernel_init',
         'static int __ref kernel_init(void *unused)\n{\n\tint ret;\n',
         'static int __ref kernel_init(void *unused)\n{\n\tint ret;\n\tblm_mark(BLM_STAGE_KERNEL_INIT);\n',
         'blm_mark(BLM_STAGE_KERNEL_INIT);'),
        ('main_do_basic_setup',
         '\tdo_basic_setup();\n',
         '\tblm_write_text("BLM do_basic_setup enter\\n");\n\tdo_basic_setup();\n\tblm_mark(BLM_STAGE_INITCALLS_DONE);\n\tblm_write_text("BLM do_basic_setup done\\n");\n',
         'blm_mark(BLM_STAGE_INITCALLS_DONE);'),
        ('main_prepare_namespace',
         '\t\tprepare_namespace();\n',
         '\t\tblm_write_text("BLM prepare_namespace enter\\n");\n\t\tprepare_namespace();\n\t\tblm_mark(BLM_STAGE_ROOTFS_READY);\n\t\tblm_write_text("BLM prepare_namespace done\\n");\n',
         'blm_mark(BLM_STAGE_ROOTFS_READY);'),
        ('main_user_init',
         '\t\tret = run_init_process(ramdisk_execute_command);\n',
         '\t\tblm_mark(BLM_STAGE_USER_INIT_ATTEMPT);\n\t\tret = run_init_process(ramdisk_execute_command);\n',
         'blm_mark(BLM_STAGE_USER_INIT_ATTEMPT);'),
    ]
    for name, anchor, replacement, marker in checks:
        text, st = replace_once(text, anchor, replacement, marker)
        ops.append((name, st))
    return text, ops


def patch_setup(text):
    ops = []
    text, st = add_include(text, '#include <linux/bootmem.h>\n')
    ops.append(('setup_include', st))
    checks = [
        ('setup_arch_entry',
         'void __init setup_arch(char **cmdline_p)\n{\n',
         'void __init setup_arch(char **cmdline_p)\n{\n\tblm_mark(BLM_STAGE_SETUP_ARCH_ENTER);\n',
         'blm_mark(BLM_STAGE_SETUP_ARCH_ENTER);'),
        ('setup_fdt_scan',
         '\tsetup_machine_fdt(__fdt_pointer);\n',
         '\tsetup_machine_fdt(__fdt_pointer);\n\tblm_mark(BLM_STAGE_FDT_SCAN_DONE);\n\tblm_reserve_logmem();\n',
         'blm_reserve_logmem();'),
        ('setup_early_ioremap',
         '\tearly_ioremap_init();\n',
         '\tearly_ioremap_init();\n\tblm_mark(BLM_STAGE_EARLY_IOREMAP);\n',
         'blm_mark(BLM_STAGE_EARLY_IOREMAP);'),
        ('setup_paging_init',
         '\tpaging_init();\n',
         '\tpaging_init();\n\tblm_mark(BLM_STAGE_PAGING_INIT);\n',
         'blm_mark(BLM_STAGE_PAGING_INIT);'),
        ('setup_unflatten_dt',
         '\tunflatten_device_tree();\n',
         '\tunflatten_device_tree();\n\tblm_mark(BLM_STAGE_UNFLATTEN_DT);\n',
         'blm_mark(BLM_STAGE_UNFLATTEN_DT);'),
    ]
    for name, anchor, replacement, marker in checks:
        text, st = replace_once(text, anchor, replacement, marker)
        ops.append((name, st))
    return text, ops


def patch_usb_bam(text):
    ops = []
    text, st = add_include(text, None)
    ops.append(('usb_bam_include', st))
    checks = [
        ('bam_enter',
         '\tdev_dbg(&pdev->dev, "usb_bam_probe\\n");\n',
         '\tdev_dbg(&pdev->dev, "usb_bam_probe\\n");\n'
         '\tblm_trace_note(1, "BAM_ENTER", 0);\n',
         'BAM_ENTER'),
        ('bam_dt_before',
         '\tpdata = usb_bam_dt_to_pdata(pdev, io_res->start);\n',
         '\tblm_trace_note(2, "BAM_DT_BEFORE", (unsigned long)io_res->start);\n'
         '\tpdata = usb_bam_dt_to_pdata(pdev, io_res->start);\n',
         'BAM_DT_BEFORE'),
        ('bam_dt_after',
         '\tpdev->dev.platform_data = pdata;\n',
         '\tpdev->dev.platform_data = pdata;\n'
         '\tblm_trace_note(3, "BAM_DT_AFTER", (unsigned long)pdata);\n',
         'BAM_DT_AFTER'),
        ('bam_wq',
         '\tinit_completion(&info[bam_type].prod_avail);\n',
         '\tblm_trace_note(4, "BAM_WQ_OK", (unsigned long)ctx->usb_bam_wq);\n'
         '\tinit_completion(&info[bam_type].prod_avail);\n',
         'BAM_WQ_OK'),
        ('bam_enable_before',
         '\tret = enable_usb_bam(pdev);\n',
         '\tblm_trace_note(5, "BAM_ENABLE_BEFORE", 0);\n'
         '\tret = enable_usb_bam(pdev);\n',
         'BAM_ENABLE_BEFORE'),
        ('bam_enable_after',
         '\tpm_runtime_no_callbacks(&pdev->dev);\n',
         '\tblm_trace_note(6, "BAM_ENABLE_AFTER", (unsigned long)ret);\n'
         '\tpm_runtime_no_callbacks(&pdev->dev);\n',
         'BAM_ENABLE_AFTER'),
        ('bam_ipa_before',
         '\tspin_lock_init(&usb_bam_ipa_handshake_info_lock);\n',
         '\tblm_trace_note(7, "BAM_IPA_BEFORE", 0);\n'
         '\tspin_lock_init(&usb_bam_ipa_handshake_info_lock);\n',
         'BAM_IPA_BEFORE'),
        ('bam_ipa_after',
         '\t\tusb_bam_ipa_create_resources(bam_type);\n',
         '\t\tusb_bam_ipa_create_resources(bam_type);\n'
         '\tblm_trace_note(8, "BAM_IPA_AFTER", 0);\n',
         'BAM_IPA_AFTER'),
        ('bam_panic_hdlr',
         '\tusb_bam_register_panic_hdlr();\n',
         '\tblm_trace_note(9, "BAM_PANIC_HDLR", 0);\n'
         '\tusb_bam_register_panic_hdlr();\n',
         'BAM_PANIC_HDLR'),
        ('ebam_init_before',
         '\tret = usb_bam_init(pdev);\n',
         '\tblm_trace_note(10, "EBAM_INIT_BEFORE", 0);\n'
         '\tret = usb_bam_init(pdev);\n',
         'EBAM_INIT_BEFORE'),
        ('ebam_init_after',
         '\tctx->usb_bam_sps.sps_pipes = devm_kzalloc(&pdev->dev,\n',
         '\tblm_trace_note(11, "EBAM_INIT_AFTER", (unsigned long)ret);\n'
         '\tctx->usb_bam_sps.sps_pipes = devm_kzalloc(&pdev->dev,\n',
         'EBAM_INIT_AFTER'),
    ]
    for name, anchor, replacement, marker in checks:
        text, st = replace_once(text, anchor, replacement, marker)
        ops.append((name, st))
    return text, ops


def patch_qpnp_vibrator(text):
    ops = []
    text, st = add_include(text, None)
    ops.append(('vibrator_include', st))
    checks = [
        ('vib_enter',
         '\tvib = devm_kzalloc(&spmi->dev, sizeof(*vib), GFP_KERNEL);\n',
         '\tvib = devm_kzalloc(&spmi->dev, sizeof(*vib), GFP_KERNEL);\n'
         '\tblm_trace_note(16, "VIB_ENTER", 0);\n',
         'VIB_ENTER'),
        ('vib_spmi_set',
         '\tvib->spmi = spmi;\n',
         '\tvib->spmi = spmi;\n'
         '\tblm_trace_note(17, "VIB_SPMI_SET", 0);\n',
         'VIB_SPMI_SET'),
        ('vib_res_before',
         '\tvib_resource = spmi_get_resource(spmi, 0, IORESOURCE_MEM, 0);\n',
         '\tblm_trace_note(18, "VIB_RES_BEFORE", 0);\n'
         '\tvib_resource = spmi_get_resource(spmi, 0, IORESOURCE_MEM, 0);\n',
         'VIB_RES_BEFORE'),
        ('vib_res_after',
         '\tvib->base = vib_resource->start;\n',
         '\tvib->base = vib_resource->start;\n'
         '\tblm_trace_note(19, "VIB_RES_AFTER", (unsigned long)vib_resource->start);\n',
         'VIB_RES_AFTER'),
        ('vib_dt_before',
         '\trc = qpnp_vib_parse_dt(vib);\n',
         '\tblm_trace_note(20, "VIB_DT_BEFORE", 0);\n'
         '\trc = qpnp_vib_parse_dt(vib);\n',
         'VIB_DT_BEFORE'),
        ('vib_config_before',
         '\trc = qpnp_vibrator_config(vib);\n',
         '\tblm_trace_note(21, "VIB_CONFIG_BEFORE", 0);\n'
         '\trc = qpnp_vibrator_config(vib);\n',
         'VIB_CONFIG_BEFORE'),
        ('vib_read1',
         '\trc = qpnp_vib_read_u8(vib, &reg, QPNP_VIB_VTG_CTL(vib->base));\n',
         '\tblm_trace_note(22, "VIB_READ1", 0);\n'
         '\trc = qpnp_vib_read_u8(vib, &reg, QPNP_VIB_VTG_CTL(vib->base));\n',
         'VIB_READ1'),
        ('vib_read2',
         '\trc = qpnp_vib_read_u8(vib, &reg, QPNP_VIB_EN_CTL(vib->base));\n',
         '\tblm_trace_note(23, "VIB_READ2", 0);\n'
         '\trc = qpnp_vib_read_u8(vib, &reg, QPNP_VIB_EN_CTL(vib->base));\n',
         'VIB_READ2'),
        ('vib_pwm',
         '\t\tvib->pwm_info.pwm_dev = pwm_request(vib->pwm_info.pwm_channel,\n',
         '\t\tblm_trace_note(24, "VIB_PWM", 0);\n'
         '\t\tvib->pwm_info.pwm_dev = pwm_request(vib->pwm_info.pwm_channel,\n',
         'VIB_PWM'),
        ('vib_config_done',
         '\tmutex_init(&vib->lock);\n',
         '\tblm_trace_note(25, "VIB_CONFIG_DONE", (unsigned long)rc);\n'
         '\tmutex_init(&vib->lock);\n',
         'VIB_CONFIG_DONE'),
        ('vib_timed',
         '\trc = timed_output_dev_register(&vib->timed_dev);\n',
         '\tblm_trace_note(26, "VIB_TIMED", 0);\n'
         '\trc = timed_output_dev_register(&vib->timed_dev);\n',
         'VIB_TIMED'),
    ]
    for name, anchor, replacement, marker in checks:
        text, st = replace_once(text, anchor, replacement, marker)
        ops.append((name, st))
    return text, ops


SPMI_STUB_MARKER = 'BLM_SPMI_STUB_ACTIVE'


def patch_vibrator_spmi_stub(text):
    """Replace the two SPMI helpers with bus-free stubs (Round 19 fix).

    On this 3.18.120 build spmi_ext_register_readl() for the vibrator VTG/EN
    registers never returns.  Skipping the bus access lets probe() finish and
    register the timed_output device that the vendor vibrator HAL requires.
    Vibration is intentionally non-functional; the goal is a booting system.
    """
    if SPMI_STUB_MARKER in text:
        return text, [('vibrator_spmi_stub', 'skipped')]
    read_stub = (
        'static int qpnp_vib_read_u8(struct qpnp_vib *vib, u8 *data, u16 reg)\n'
        '{\n'
        '\t/* BLM_SPMI_STUB_ACTIVE: bus read never returns on 3.18.120; '
        'return a neutral value so probe can register timed_output. */\n'
        '\t(void)vib;\n'
        '\tblm_trace_note(27, "VIB_STUB_READ", (unsigned long)reg);\n'
        '\t*data = 0;\n'
        '\treturn 0;\n'
        '}\n'
    )
    write_stub = (
        'static int qpnp_vib_write_u8(struct qpnp_vib *vib, u8 *data, u16 reg)\n'
        '{\n'
        '\t/* BLM_SPMI_STUB_ACTIVE: companion of qpnp_vib_read_u8 stub. */\n'
        '\t(void)vib;\n'
        '\t(void)data;\n'
        '\tblm_trace_note(28, "VIB_STUB_WRITE", (unsigned long)reg);\n'
        '\treturn 0;\n'
        '}\n'
    )
    text, n1 = re.subn(r'static int qpnp_vib_read_u8\([^)]*\)\n\{.*?\n\}\n',
                       lambda m: read_stub, text, count=1, flags=re.S)
    text, n2 = re.subn(r'static int qpnp_vib_write_u8\([^)]*\)\n\{.*?\n\}\n',
                       lambda m: write_stub, text, count=1, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise PatchError('spmi stub anchors not found read=%d write=%d' % (n1, n2))
    return text, [('vibrator_spmi_stub', 'inserted'),
                  ('vibrator_spmi_read_stub', 'inserted'),
                  ('vibrator_spmi_write_stub', 'inserted')]


def patch_panic(text):
    ops = []
    text, st = add_include(text, None)
    ops.append(('panic_include', st))
    checks = [
        ('panic_entry',
         'void panic(const char *fmt, ...)\n{\n\tstatic DEFINE_SPINLOCK(panic_lock);\n\tstatic char buf[1024];\n\tva_list args;\n\tlong i, i_next = 0;\n\tint state = 0;\n',
         'void panic(const char *fmt, ...)\n{\n\tstatic DEFINE_SPINLOCK(panic_lock);\n\tstatic char buf[1024];\n\tva_list args;\n\tlong i, i_next = 0;\n\tint state = 0;\n\tblm_mark(BLM_STAGE_PANIC_ENTER);\n',
         'blm_mark(BLM_STAGE_PANIC_ENTER);'),
        ('panic_message',
         '\tvsnprintf(buf, sizeof(buf), fmt, args);\n',
         '\tvsnprintf(buf, sizeof(buf), fmt, args);\n\tblm_write_text(buf);\n',
         'blm_write_text(buf);'),
    ]
    for name, anchor, replacement, marker in checks:
        text, st = replace_once(text, anchor, replacement, marker)
        ops.append((name, st))
    return text, ops


def patch_makefile(text):
    marker = 'obj-y += bootloop_monitor.o'
    if marker in text:
        return text, [('kernel_makefile', 'skipped')]
    if not text.endswith('\n'):
        text += '\n'
    return text + '\n' + marker + '\n', [('kernel_makefile', 'inserted')]


def main():
    ap = argparse.ArgumentParser(description='emit a patched 3.18 kernel tree without touching the source tree')
    ap.add_argument('--main-c', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'main.c.orig'))
    ap.add_argument('--setup-c', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'setup.c.orig'))
    ap.add_argument('--panic-c', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'panic.c.orig'))
    ap.add_argument('--kernel-makefile', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'kernel_Makefile.orig'))
    ap.add_argument('--usb-bam-c', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'usb_bam.c.orig'))
    ap.add_argument('--vibrator-c', default=str(Path(__file__).resolve().parents[1] / 'fixtures' / 'qpnp-vibrator.c.orig'))
    ap.add_argument('--monitor-c', default=str(PROJECT / 'kernel' / 'bootloop_monitor.c'))
    ap.add_argument('--monitor-h', default=str(PROJECT / 'kernel' / 'bootloop_monitor.h'))
    ap.add_argument('--layout-h', default=str(PROJECT / 'kernel' / 'blm_layout.h'))
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--spmi-stub', action='store_true',
                    help='replace qpnp_vib_read_u8/write_u8 with bus-free stubs (Round 19 fix)')
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {'source_tree_modified': False, 'operations': [], 'outputs': []}
    try:
        main_text = Path(args.main_c).read_text(encoding='utf-8', errors='replace')
        setup_text = Path(args.setup_c).read_text(encoding='utf-8', errors='replace')
        panic_text = Path(args.panic_c).read_text(encoding='utf-8', errors='replace')
        mk_text = Path(args.kernel_makefile).read_text(encoding='utf-8', errors='replace')
        usb_text = Path(args.usb_bam_c).read_text(encoding='utf-8', errors='replace')
        vib_text = Path(args.vibrator_c).read_text(encoding='utf-8', errors='replace')

        main_text, ops = patch_main(main_text)
        report['operations'].extend(ops)
        setup_text, ops = patch_setup(setup_text)
        report['operations'].extend(ops)
        panic_text, ops = patch_panic(panic_text)
        report['operations'].extend(ops)
        mk_text, ops = patch_makefile(mk_text)
        report['operations'].extend(ops)
        usb_text, ops = patch_usb_bam(usb_text)
        report['operations'].extend(ops)
        vib_text, ops = patch_qpnp_vibrator(vib_text)
        report['operations'].extend(ops)
        if args.spmi_stub:
            vib_text, ops = patch_vibrator_spmi_stub(vib_text)
            report['operations'].extend(ops)
        report['spmi_stub'] = bool(args.spmi_stub)

        outputs = {
            out / 'init' / 'main.c': main_text,
            out / 'arch' / 'arm64' / 'kernel' / 'setup.c': setup_text,
            out / 'kernel' / 'panic.c': panic_text,
            out / 'kernel' / 'Makefile': mk_text,
            out / 'drivers' / 'platform' / 'msm' / 'usb_bam.c': usb_text,
            out / 'drivers' / 'platform' / 'msm' / 'qpnp-vibrator.c': vib_text,
        }
        for path, data in outputs.items():
            atomic_write(path, data)
            report['outputs'].append(str(path))
        copy_into(args.monitor_c, out / 'kernel' / 'bootloop_monitor.c')
        copy_into(args.monitor_h, out / 'include' / 'linux' / 'bootloop_monitor.h')
        copy_into(args.layout_h, out / 'include' / 'linux' / 'blm_layout.h')
        report['outputs'].extend([
            str(out / 'kernel' / 'bootloop_monitor.c'),
            str(out / 'include' / 'linux' / 'bootloop_monitor.h'),
            str(out / 'include' / 'linux' / 'blm_layout.h'),
        ])
        markers = [
            'blm_early_init(__fdt_pointer);',
            'blm_reserve_logmem();',
            'blm_mark(BLM_STAGE_PANIC_ENTER);',
            'blm_write_text(buf);',
            'blm_note_initcall((unsigned long)fn);',
            'blm_trace_note(0, "IC"',
            'BLM do_basic_setup enter',
            'BLM prepare_namespace enter',
            'BLM kernel_init_freeable done',
            'BAM_ENTER',
            'BAM_IPA_AFTER',
            'EBAM_INIT_AFTER',
            'VIB_ENTER',
            'VIB_TIMED',
            'obj-y += bootloop_monitor.o',
        ]
        if args.spmi_stub:
            markers += [SPMI_STUB_MARKER, 'VIB_STUB_READ', 'VIB_STUB_WRITE']
        joined = main_text + setup_text + panic_text + mk_text + usb_text + vib_text
        report['marker_check'] = {m: (m in joined) for m in markers}
        report['status'] = 'OK' if all(report['marker_check'].values()) else 'MARKER_MISS'
        atomic_write(out / 'blm_patch_report.json', json.dumps(report, ensure_ascii=False, indent=2))
        print('KERNEL_PATCH_OK status=' + report['status'] + ' outputs=' + str(len(report['outputs'])))
        return 0 if report['status'] == 'OK' else 1
    except PatchError as e:
        print('KERNEL_PATCH_FAIL ' + str(e))
        return 1


if __name__ == '__main__':
    sys.exit(main())
