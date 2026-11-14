# PD1610 system 分区 EDL 刷写（9008 兜底方案）
# 适用：fastboot flash system 传 1.8 GB 时挂死 / 设备无法进 fastboot
# 前置：拆机短接进 9008（设备管理器出现 Qualcomm HS-USB QDLoader 9008，COM 口）
# 用法：powershell -ExecutionPolicy Bypass -File edl_flash_system.ps1 -Com 5

param([int]$Com = 5)

$QF  = 'D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5'
$OUT = 'D:\16\PD1610_81\out'
$XML = 'D:\16\PD1610_81\scripts\flash_system_edl.xml'
$ELF = Join-Path $QF 'prog_ufs_firehose_8996_ddr.elf'
$PORT = "\\.\COM$Com"

Write-Output "=== 0. 检查 ==="
foreach ($f in @("$OUT\system_raw.img", $XML, $ELF)) {
    if (-not (Test-Path $f)) { Write-Output "缺少 $f"; exit 1 }
    Write-Output ("  {0}  {1} MB" -f (Split-Path $f -Leaf), [math]::Round((Get-Item $f).Length/1MB,1))
}
$rawSize = (Get-Item "$OUT\system_raw.img").Length
if ($rawSize -ne 3221225472) {
    Write-Output "  警告：raw 大小 $rawSize != 3221225472（3 GB），与 num_partition_sectors 不符"
    Write-Output "  请重新执行 simg2img 展开"
    exit 2
}

Write-Output ""
Write-Output "=== 1. 确认 9008 端口 ==="
$ports = [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
Write-Output ("  当前串口: " + ($ports -join ', '))
$qd = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match 'QDLoader|9008' } | Select-Object -First 1
if ($qd) { Write-Output ("  检测到: " + $qd.Name) }
else { Write-Output "  未检测到 9008 设备 —— 请短接 EDL 点后重试"; exit 3 }

Write-Output ""
Write-Output "=== 2. Sahara 下发 firehose ==="
Push-Location $QF
& "$QF\QSaharaServer.exe" -u $PORT -s "13:$ELF" 2>&1 | ForEach-Object { Write-Output "  $_" }
Pop-Location
Start-Sleep -Seconds 3

Write-Output ""
Write-Output "=== 3. 写入 system（3 GB，约 3-6 分钟）==="
Push-Location $QF
& "$QF\fh_loader.exe" --port=$PORT --sendxml="$XML" --search_path="$OUT" `
    --noprompt --zlpawarehost=1 --memoryname=ufs 2>&1 | ForEach-Object { Write-Output "  $_" }
$rc = $LASTEXITCODE
Pop-Location

Write-Output ""
if ($rc -eq 0) {
    Write-Output 'system 写入完成。断开 9008（拔插电池排线），然后 adb/fastboot 重启。'
} else {
    Write-Output "fh_loader 返回 $rc，检查 port_trace.txt"
}
