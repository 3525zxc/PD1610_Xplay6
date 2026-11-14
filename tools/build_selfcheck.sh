#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd $(dirname $0)/.. && pwd)

python3 -m py_compile $ROOT/tools/blm_layout.py $ROOT/tools/blm_tools.py $ROOT/tools/blm_apply_kernel_patch.py $ROOT/tools/blm_patch_dtb.py $ROOT/tools/blm_read.py
echo PY_COMPILE_OK

python3 $ROOT/tools/blm_tools.py validate-layout --header $ROOT/kernel/blm_layout.h
python3 $ROOT/tools/blm_tools.py selftest

gcc -std=c99 -Wall -Wextra -Werror -DBLM_HOST_TEST -I$ROOT/tools -I$ROOT/kernel $ROOT/tools/host_selftest.c -o $ROOT/tests/host_selftest
$ROOT/tests/host_selftest $ROOT/tests/blm_host_selftest.bin
python3 $ROOT/tools/blm_tools.py analyze --file $ROOT/tests/blm_host_selftest.bin

python3 $ROOT/tools/blm_patch_dtb.py selftest --out-dir $ROOT/tests
python3 $ROOT/tools/blm_patch_dtb.py patch --in $ROOT/fixtures/pd1610_81916_vivo.dtb --out $ROOT/tests/pd1610_81916_vivo.blm.dtb --ddr-base 0x40000000
python3 $ROOT/tools/blm_patch_dtb.py inspect --in $ROOT/tests/pd1610_81916_vivo.blm.dtb

python3 $ROOT/tools/blm_apply_kernel_patch.py --out-dir $ROOT/tests/patched_tree

python3 $ROOT/tools/blm_read.py --selftest
python3 $ROOT/tools/blm_read.py --input $ROOT/tests/blm_host_selftest.bin --already-region
python3 $ROOT/tools/blm_read.py --emit-command --ddr-base 0x40000000 --dump-base 0x40000000

echo SELFCHECK_OK
