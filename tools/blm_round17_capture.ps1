param(
    [int]$ComPort = 5,
    [string]$Serial = '5fccbfeb'
)

# Round 17 offline-prepared runbook. NOT executed in this session.
# Flash -> observe -> dual peek -> fixed-slot diagnosis -> power reset -> rollback.
# The device must be on the stock system with adb online before running.

$ErrorActionPreference = 'Continue'
$root = 'D:\xplay6\evidence\kernel_re\out\stage2\bootloop_monitor'
$fb = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\fastboot.exe'
$adb = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\adb.exe'
$cand = Join-Path $root 'images\boot_los16_blm_vib_20261114160500.img'
$roll = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\images\boot.img'
$py = 'C:\Users\Tse\.workbuddy\binaries\python\versions\3.14.3\python.exe'
$peek = Join-Path $root 'tools\blm_firehose_peek.py'
$power = Join-Path $root 'tools\blm_firehose_power.py'
$traceReport = Join-Path $root 'tools\blm_trace_report.py'
$wd = Join-Path $root 'edl_probe'
$tl = Join-Path $root 'flash_log\20261114_blm_round17_timeline.txt'
$dump = Join-Path $root 'flash_log\blm_ram_round17.bin'
$fdt = Join-Path $root 'flash_log\fdt_round17.bin'
$smap = Join-Path $root 'build\vib-20261114160500\System.map'
$traceJson = Join-Path $root 'flash_log\blm_ram_round17.trace.json'

function W([string]$s) {
    $line = ('{0} | {1}' -f (Get-Date -Format 'HH:mm:ss.fff'), $s)
    Add-Content -Path $tl -Encoding UTF8 -Value $line
    Write-Output $line
}
function Flat([string]$s) { return ($s -replace "\r?\n", ' / ').Trim() }
function FbUp { return ((& $fb devices 2>&1 | Out-String) -match 'fastboot') }
function AdbUp { return ((& $adb devices 2>&1 | Out-String) -match '(?m)^\S+\s+device\s*$') }
function Com9008 {
    $devs = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'QDLoader|9008' }
    foreach ($d in $devs) { if ($d.FriendlyName -match 'COM(\d+)') { return [int]$Matches[1] } }
    return 0
}

W '=== ROUND17 QPNP_VIBRATOR PROBE TRACE ==='
$pf = Get-Content (Join-Path $root 'images\boot_los16_blm_vib_20261114160500.preflight.json') -Raw | ConvertFrom-Json
W ('preflight_verdict=' + $pf.verdict + ' pass=' + $pf.pass + '/' + $pf.total)
if ($pf.verdict -ne 'SAFE_TO_FLASH') { W 'ABORT_PREFLIGHT_NOT_SAFE'; exit 2 }
W ('candidate_sha256=' + (Get-FileHash $cand -Algorithm SHA256).Hash.ToLower())
W ('pre_kernel=' + (Flat ((& $adb -s $Serial shell uname -r 2>&1 | Out-String))))

W 'STEP1 adb reboot bootloader'
$null = (& $adb -s $Serial reboot bootloader 2>&1 | Out-String)
$ready = $false
for ($i = 0; $i -lt 35; $i++) { if (FbUp) { $ready = $true; break }; Start-Sleep -Seconds 1 }
if (-not $ready) {
    $g = (& $fb -s $Serial getvar product 2>&1 | Out-String)
    W ('getvar_probe=' + (Flat $g))
    if ($g -notmatch 'FAILED' -and $g -match 'product') { $ready = $true }
}
if (-not $ready) { W 'ABORT_NO_FASTBOOT'; exit 2 }
W ('fastboot_devices=' + (Flat ((& $fb devices 2>&1 | Out-String))))

W 'STEP2 flash (retry up to 3 times, never reboot on failure)'
$ok = $false
for ($i = 1; $i -le 3; $i++) {
    $f = (& $fb -s $Serial flash boot $cand 2>&1 | Out-String)
    W ('flash_' + $i + '=' + (Flat $f))
    if ($f -match 'Writing.*OKAY' -and $f -notmatch 'FAILED') { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ok) {
    W 'FLASH_RETRY_EXHAUSTED - restoring stock boot'
    $rf = (& $fb -s $Serial flash boot $roll 2>&1 | Out-String)
    W ('rollback_flash_output=' + (Flat $rf))
    $null = (& $fb -s $Serial reboot 2>&1 | Out-String)
    exit 3
}
$r = (& $fb -s $Serial reboot 2>&1 | Out-String)
W ('reboot_output=' + (Flat $r))

W 'STEP3 observe (wait for 9008)'
$com = 0
for ($t = 0; $t -le 180; $t += 5) {
    $c = Com9008
    W ('t=' + $t + 's com9008=' + $c + ' adb=[' + (Flat ((& $adb devices 2>&1 | Out-String))) + ']')
    if ($c -gt 0) { $com = $c; break }
    if (AdbUp) { W ('ADB_UP kernel=' + (Flat ((& $adb -s $Serial shell uname -r 2>&1 | Out-String)))); break }
    Start-Sleep -Seconds 5
}
W ('OBSERVE_RESULT com9008=' + $com)
if ($com -eq 0) { W 'NO_9008 - stop, device state unknown'; exit 4 }
if ($com -ne $ComPort) { W ('COM_PORT_OVERRIDE expected=' + $ComPort + ' actual=' + $com); $ComPort = $com }

W 'STEP4 dual peek (NO RESET)'
if (Test-Path $dump) { Remove-Item $dump -Force }
if (Test-Path $fdt) { Remove-Item $fdt -Force }
$p1 = (& $py $peek --com $ComPort --address 0x42000000 --size 0x10000 --chunk 0x10000 --out $fdt --workdir $wd 2>&1 | Out-String)
W ('fdt_peek=' + (Flat $p1))
$p2 = (& $py $peek --com $ComPort --address 0x42100000 --size 0x40000 --chunk 0x10000 --no-upload --out $dump --workdir $wd 2>&1 | Out-String)
W ('blm_peek=' + (Flat $p2))
if (Test-Path $dump) { W ('dump_bytes=' + (Get-Item $dump).Length + ' sha256=' + (Get-FileHash $dump -Algorithm SHA256).Hash.ToLower()) } else { W 'dump=MISSING'; exit 5 }

W 'STEP5 fixed-slot diagnosis'
$tr = (& $py $traceReport --input $dump --system-map $smap --report $traceJson 2>&1 | Out-String)
foreach ($line in ($tr -split "`n")) {
    if ($line -match 'LAST_INITCALL|LAST_VIB_MILESTONE|VIB_SUSPECTED_WINDOW|MISSING_SLOTS|TRACE_SLOT_COUNT|LAST_BAM_MILESTONE|SUSPECTED') {
        W ('diag=' + $line.Trim())
    }
}
W ('trace_json=' + $traceJson)

W 'STEP6 power reset -> wait fastboot -> rollback'
$p = (& $py $power --com $ComPort --mode reset --workdir $wd 2>&1 | Out-String)
W ('power_reset=' + (Flat $p))
$ready = $false
for ($t = 0; $t -le 120; $t += 5) { if (FbUp) { $ready = $true; W ('fastboot_ready t=' + $t + 's'); break }; Start-Sleep -Seconds 5 }
if (-not $ready) { W 'ROLLBACK_NOT_EXECUTED: manual fastboot needed, then rerun rollback block'; exit 6 }
W ('rollback_sha256=' + (Get-FileHash $roll -Algorithm SHA256).Hash.ToLower())
$rf = (& $fb -s $Serial flash boot $roll 2>&1 | Out-String)
W ('rollback_flash_output=' + (Flat $rf))
if ($rf -notmatch 'OKAY' -or $rf -match 'FAILED') { W 'ROLLBACK_FLASH_FAILED'; exit 7 }
$rr = (& $fb -s $Serial reboot 2>&1 | Out-String)
W ('rollback_reboot_output=' + (Flat $rr))
Start-Sleep -Seconds 50
for ($t = 0; $t -le 60; $t += 10) { if (AdbUp) { W ('rollback_adb_up t=' + $t + 's'); break }; Start-Sleep -Seconds 10 }
if (AdbUp) {
    W ('rollback_kernel_release=' + (Flat ((& $adb -s $Serial shell uname -r 2>&1 | Out-String))))
    W ('rollback_fingerprint=' + (Flat ((& $adb -s $Serial shell getprop ro.build.fingerprint 2>&1 | Out-String))))
    W 'ROLLBACK_VERIFIED'
} else { W 'ROLLBACK_ADB_NOT_ONLINE' }
W '=== ROUND17 END ==='
