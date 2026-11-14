#!/usr/bin/env python3
"""Assemble a PD1610 custom-ROM OTA-style zip (for TWRP / custom recovery).

The stock vivo recovery verifies zips against its own otacert and will REJECT
a testkey-signed package. For stock-ish flashing use flash_custom_rom.xml over
EDL instead. This script is for the recovery-based path.

Usage:
  python make_rom_zip.py --boot boot_81_noverify.img [--system system.img] \
      [--extra DIR] [--name "PD1610-CustomROM"] [--out out.zip] [--no-sign]
"""
import argparse
import os
import shutil
import subprocess
import zipfile

ROOT = r'D:\16\PD1610_81'
WORK = os.path.join(ROOT, 'work')
SCRIPTS = os.path.join(ROOT, 'scripts')
OFFICIAL_ZIP = r'C:\qfilx\firmware\full81916\PD1610_D_8.19.16-update-full_1108090720.zip'
UB = 'META-INF/com/google/android/update-binary'
US = 'META-INF/com/google/android/updater-script'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boot', required=True)
    ap.add_argument('--system', default=None)
    ap.add_argument('--extra', default=None, help='dir with xbl/tz/... and oem/ subdir')
    ap.add_argument('--name', default='PD1610 Custom ROM')
    ap.add_argument('--out', default=os.path.join(WORK, 'custom_rom_unsigned.zip'))
    ap.add_argument('--no-sign', action='store_true')
    a = ap.parse_args()

    stage = os.path.join(WORK, 'rom_stage')
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(os.path.join(stage, 'META-INF', 'com', 'google', 'android'))
    os.makedirs(os.path.join(stage, 'META-INF', 'com', 'android'))

    # update-binary: reuse the official 8.1 one (edify interpreter)
    with zipfile.ZipFile(OFFICIAL_ZIP) as z:
        open(os.path.join(stage, UB), 'wb').write(z.read(UB))

    tpl = open(os.path.join(SCRIPTS, 'updater-script.template'), encoding='utf-8').read()
    tpl = tpl.replace('{{ROM_NAME}}', a.name)
    # Keep the script self-consistent when optional payloads are not bundled.
    import re
    if not a.system:
        tpl = tpl.replace('package_extract_file("system.img", "/dev/block/bootdevice/by-name/system");',
                          'ui_print("No system.img bundled - skipping system");')
    if not a.extra:
        tpl = re.sub(r'assert\(package_extract_file\("([^"]+)",\s*"[^"]+"\)\);',
                     lambda m: 'ui_print("skip %s (not bundled)");' % m.group(1), tpl)
        tpl = re.sub(r'package_extract_file\("oem/[^"]+",\s*"[^"]+"\);',
                     'ui_print("skip oem (not bundled)");', tpl)
    open(os.path.join(stage, US), 'w', encoding='utf-8', newline='\n').write(tpl)

    open(os.path.join(stage, 'META-INF', 'com', 'android', 'metadata'), 'w').write(
        'ota-type=BLOCK\npre-device=PD1610\npre-branch=PD1610MD\n'
        'ota-required-cache=0\npost-build=%s\n' % a.name.replace(' ', '_'))

    shutil.copy2(a.boot, os.path.join(stage, 'boot.img'))
    if a.system:
        shutil.copy2(a.system, os.path.join(stage, 'system.img'))
    if a.extra:
        for root, dirs, files in os.walk(a.extra):
            rel = os.path.relpath(root, a.extra)
            dst = os.path.join(stage, rel) if rel != '.' else stage
            os.makedirs(dst, exist_ok=True)
            for fn in files:
                shutil.copy2(os.path.join(root, fn), os.path.join(dst, fn))

    out = a.out
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6,
                         allowZip64=True) as z:
        for root, dirs, files in os.walk(stage):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, stage).replace('\\', '/'))
    print('built %s (%d B)' % (out, os.path.getsize(out)))
    with zipfile.ZipFile(out) as z:
        for i in z.infolist():
            print('  %-56s %10d' % (i.filename, i.file_size))

    if not a.no_sign:
        ks = os.path.join(WORK, 'testkey.jks')
        if not os.path.exists(ks):
            subprocess.run(['keytool', '-genkeypair', '-alias', 'testkey',
                            '-keystore', ks, '-storepass', 'android',
                            '-keypass', 'android', '-keyalg', 'RSA',
                            '-keysize', '2048', '-validity', '10000',
                            '-dname', 'CN=PD1610 Custom, OU=Dev, O=Local, C=CN'],
                           check=True)
        subprocess.run(['jarsigner', '-keystore', ks, '-storepass', 'android',
                        '-keypass', 'android', '-digestalg', 'SHA1',
                        '-sigalg', 'SHA1withRSA', out, 'testkey'], check=True)
        print('signed with locally generated testkey (NOT trusted by stock recovery)')


if __name__ == '__main__':
    main()
