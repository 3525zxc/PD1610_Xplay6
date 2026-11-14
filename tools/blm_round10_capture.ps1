param([int]$ComPort = 5)

# Round 10: flash DDR_BASE-corrected BLM image, observe bootloop, capture
# BLM RAM log over EDL firehose peek, then roll back to stock boot.
# All device writes are limited to the boot partition. No 9008 partition write.

$root = 'D:\xplay6\evidence\kernel_re\out\stage2\bootloop_monitor'
$fb = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\fastboot.exe'
$adb = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\tools\adb.exe'
$py = 'C:\Users\Tse\.workbuddy\binaries\python\versions\3.14.3\python.exe'
$cand = Join-Path $root 'images\boot_los16_blm_ddr40000000.img'
$roll = 'D:\16\PD1610_81\release\PD1610_LOS16_20261112\images\boot.img'
$log = Join-Path $root 'flash_log\20261114_blm_round10_timeline.txt'
$dump = Join-Path $root 'flash_log\blm_ram.bin'
$wd = Join-Path $root 'edl_probe'
$peek = Join-Path $root 'tools\blm_firehose_peek.py'
$reader = Join-Path $root 'tools\blm_read.py'
$serial = '5fccbfeb'

function W([string]$s) {
    $line = ('{0} | {1}' -f (Get-Date -Format 'HH:mm:ss.fff'), $s)
    Add-Content -Path $log -Encoding UTF8 -Value $line
    Write-Output $line
}
function Flat([string]$s) { return ($s -replace "\r?\n", ' / ').Trim() }
function Com9008 {
    $devs = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'QDLoader|9008' }
    foreach ($d in $devs) { if ($d.FriendlyName -match 'COM(\d+)') { return [int]$Matches[1] } }
    return 0
}
function FbState { return (& $fb devices 2>&1 | Out-String).Trim() }
function AdbState { return (& $adb devices 2>&1 | Out-String).Trim() }
function FbUp { return ((FbState) -match 'fastboot') }
function AdbUp { return ((AdbState) -match '(?m)^\S+\s+device\s*$') }

W '=== ROUND10 BLM BOOT-ONLY + EDL CAPTURE ==='
foreach ($p in @($fb, $adb, $py, $cand, $roll, $peek, $reader)) {
    if (-not (Test-Path $p)) { W ('MISSING=' + $p); exit 2 }
}
W ('candidate_sha256=' + (Get-FileHash $cand -Algorithm SHA256).Hash.ToLower())
W ('candidate_bytes=' + (Get-Item $cand).Length)
W ('rollback_sha256=' + (Get-FileHash $roll -Algorithm SHA256).Hash.ToLower())
W ('pre_adb=' + (Flat (AdbState)))
if (-not (AdbUp)) { W 'ABORT: no adb device'; exit 2 }

W 'STEP1 adb reboot bootloader'
$null = (& $adb -s $serial reboot bootloader 2>&1 | Out-String)
for ($i = 0; $i -lt 25; $i++) { if (FbUp) { break }; Start-Sleep -Seconds 1 }
$fbReady = FbUp
if (-not $fbReady) {
    $g = (& $fb -s $serial getvar product 2>&1 | Out-String)
    W ('getvar_probe=' + (Flat $g))
    if ($g -notmatch 'FAILED' -and $g -match 'product') { $fbReady = $true }
}
if (-not $fbReady) { W ('ABORT: no fastboot, state=' + (Flat (FbState))); exit 2 }
W ('STEP1 fastboot_devices=' + (Flat (FbState)) + ' ready=' + $fbReady)

W 'STEP2 flash candidate'
$flash = (& $fb -s $serial flash boot $cand 2>&1 | Out-String)
W ('flash_output=' + (Flat $flash))
if ($flash -notmatch 'OKAY' -or $flash -match 'FAILED') { W 'FLASH_FAIL_STOP - no reboot, no rollback'; exit 3 }
W 'flash=OKAY'
$rb = (& $fb -s $serial reboot 2>&1 | Out-String)
W ('reboot_output=' + (Flat $rb))

W 'STEP3 observe'
$com = 0
$adbSeen = $false
$oemTried = $false
for ($t = 0; $t -le 150; $t += 5) {
    $f = Flat (FbState)
    $a = Flat (AdbState)
    $c = Com9008
    W ('t=' + $t + 's fastboot=[' + $f + '] adb=[' + $a + '] com9008=' + $c)
    if ($c -gt 0) { $com = $c; break }
    if (AdbUp) { $adbSeen = $true; break }
    if ($t -ge 60 -and -not $oemTried -and (FbUp)) {
        $oem = (& $fb -s $serial oem reboot-edl 2>&1 | Out-String)
        W ('oem_reboot_edl=' + (Flat $oem))
        $oemTried = $true
    }
    Start-Sleep -Seconds 5
}

if ($adbSeen) {
    W ('ADB_UP kernel_release=' + (Flat (& $adb -s $serial shell uname -r 2>&1 | Out-String)))
    W ('ADB_UP uname=' + (Flat (& $adb -s $serial shell uname -a 2>&1 | Out-String)))
    W 'NOTE: device booted to adb; no failed-boot RAM capture in this run'
} elseif ($com -eq 0) {
    W 'WAIT_FOR_MANUAL_9008: power off, hold VolUp+VolDown, plug USB (up to 120s)'
    for ($t = 0; $t -le 120; $t += 5) {
        $c = Com9008
        if ($c -gt 0) { $com = $c; W ('manual_9008_detected t=' + $t + 's COM=' + $c); break }
        Start-Sleep -Seconds 5
    }
    if ($com -eq 0) { W 'NO_9008_WITHIN_TIMEOUT - capture not executed, rollback next'; }
}

if ($com -gt 0) {
    W ('STEP4 EDL CAPTURE COM=' + $com)
    if (Test-Path $dump) { Remove-Item $dump -Force }
    $pk = (& $py $peek --com $com --address '0x42100000' --size '0x40000' --chunk '0x10000' --reset --out $dump --workdir $wd 2>&1 | Out-String)
    $tail = (($pk -split "`n") | Select-Object -Last 10) -join ' / '
    W ('peek_tail=' + (Flat $tail))
    W ('peek_rc=' + $LASTEXITCODE)
    if (Test-Path $dump) {
        W ('dump_bytes=' + (Get-Item $dump).Length)
        W ('dump_sha256=' + (Get-FileHash $dump -Algorithm SHA256).Hash.ToLower())
        $rd = (& $py $reader --input $dump --already-region 2>&1 | Out-String)
        W ('blm_read=' + (Flat $rd))
    } else {
        W 'dump=MISSING'
    }
} else {
    W 'STEP4 SKIPPED: no 9008'
}

W 'STEP5 ROLLBACK'
$fbReady = $false
for ($t = 0; $t -le 120; $t += 5) {
    if (FbUp) { $fbReady = $true; W ('fastboot_ready t=' + $t + 's'); break }
    if (AdbUp) { W ('adb_online_before_rollback t=' + $t + 's'); }
    Start-Sleep -Seconds 5
}
if (-not $fbReady) {
    W 'ROLLBACK_NOT_EXECUTED: device never returned to fastboot; manual recovery needed'
    exit 4
}
$rf = (& $fb -s $serial flash boot $roll 2>&1 | Out-String)
W ('rollback_flash_output=' + (Flat $rf))
if ($rf -notmatch 'OKAY' -or $rf -match 'FAILED') { W 'ROLLBACK_FLASH_FAILED'; exit 5 }
$rr = (& $fb -s $serial reboot 2>&1 | Out-String)
W ('rollback_reboot_output=' + (Flat $rr))
Start-Sleep -Seconds 50
for ($t = 0; $t -le 60; $t += 10) {
    if (AdbUp) { W ('rollback_adb_up t=' + $t + 's'); break }
    Start-Sleep -Seconds 10
}
if (AdbUp) {
    W ('rollback_uname=' + (Flat (& $adb -s $serial shell uname -a 2>&1 | Out-String)))
    W ('rollback_kernel_release=' + (Flat (& $adb -s $serial shell uname -r 2>&1 | Out-String)))
    W 'ROLLBACK_VERIFIED'
} else {
    W 'ROLLBACK_ADB_NOT_ONLINE'
}
W '=== ROUND10 END ==='
