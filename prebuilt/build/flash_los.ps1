# PD1610 刷入 LineageOS 16.0
# 前置：设备已解锁（verifiedbootstate=orange），能进 fastboot 或 adb
# 注意：本脚本会擦除 userdata（从官方 8.1 的 FDE 切到 LOS，必须清）
# 用法：powershell -ExecutionPolicy Bypass -File flash_los.ps1 [-SkipWipe]

param([switch]$SkipWipe)

$PT  = 'D:\16\viqoo_extract\bin'
$OUT = 'D:\16\PD1610_81\out'
$fb  = Join-Path $PT 'fastboot.exe'
$adb = Join-Path $PT 'adb.exe'

function Step($n, $msg) { Write-Output ""; Write-Output "=== [$n] $msg ===" }

# ---------- 0. 环境检查 ----------
Step 0 '环境检查'
foreach ($f in @("$OUT\boot.img", "$OUT\system.img")) {
    if (-not (Test-Path $f)) { Write-Output "缺少 $f"; exit 1 }
    $sz = [math]::Round((Get-Item $f).Length / 1MB, 1)
    Write-Output ("  {0}  {1} MB" -f (Split-Path $f -Leaf), $sz)
}

# ---------- 1. 进入 fastboot ----------
Step 1 '等待 fastboot 设备'
& $fb devices 2>&1 | ForEach-Object { Write-Output "  $_" }
$devs = (& $fb devices 2>&1) -join "`n"
if ($devs -notmatch 'fastboot') {
    Write-Output '  未检测到 fastboot 设备，尝试通过 adb 重启到 bootloader...'
    $ad = (& $adb devices 2>&1) -join "`n"
    if ($ad -match 'device\s*$' -or $ad -match "device`r?`n") {
        & $adb reboot bootloader 2>&1 | Out-Null
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 2
            $devs = (& $fb devices 2>&1) -join "`n"
            if ($devs -match 'fastboot') { break }
        }
    }
}
if ($devs -notmatch 'fastboot') {
    Write-Output '  仍无 fastboot 设备：请插 USB 并手动进 bootloader（音量下+电源，或短接 EDL 后另行处理）'
    exit 2
}
Write-Output '  fastboot 就绪'

# ---------- 2. 刷 boot ----------
Step 2 '刷 boot.img'
& $fb flash boot "$OUT\boot.img" 2>&1 | ForEach-Object { Write-Output "  $_" }
if ($LASTEXITCODE -ne 0) { Write-Output '  boot 刷写失败'; exit 3 }

# ---------- 3. 刷 system ----------
Step 3 '刷 system.img（1.8 GB sparse，视 USB 速度需 3-10 分钟）'
& $fb flash system "$OUT\system.img" 2>&1 | ForEach-Object { Write-Output "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Output '  system 刷写失败 —— 改用 EDL：见 edl_flash_system.ps1'
    exit 4
}

# ---------- 4. 清 data ----------
if (-not $SkipWipe) {
    Step 4 '擦除 userdata / metadata（FDE → 新加密，必须）'
    & $fb erase userdata 2>&1 | ForEach-Object { Write-Output "  $_" }
    & $fb erase metadata 2>&1 | ForEach-Object { Write-Output "  $_" }
    & $fb erase cache 2>&1 | ForEach-Object { Write-Output "  $_" }
} else {
    Step 4 '跳过擦除（-SkipWipe）'
}

# ---------- 5. 重启 ----------
Step 5 '重启到系统'
& $fb reboot 2>&1 | ForEach-Object { Write-Output "  $_" }
Write-Output ''
Write-Output '刷写完成。首启约 3-8 分钟（dex2oat），期间黑屏/logo 循环属正常。'
Write-Output '若卡在 logo 超过 10 分钟：adb logcat 或 adb shell dmesg 收集日志。'
