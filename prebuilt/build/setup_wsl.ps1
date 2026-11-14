# =============================================================================
# setup_wsl.ps1  --  Create a WSL2 Ubuntu 20.04 build box for LineageOS 16.0
#
#   Purpose : replace the blocked wsl.exe workflow with a clean, D:-hosted
#             distribution that is ready to build AOSP/LineageOS.
#   Run     : powershell -ExecutionPolicy Bypass -File setup_wsl.ps1
#             (no admin required for --import into D:)
#
#   Layout after success:
#     D:\WSL\PD1610\ext4.vhdx      <- distro disk (grows on demand)
#     user "builder" (passwordless sudo), default WSL user
#     /mnt/d mounted with metadata (case-sensitive inside ext4, not host NTFS)
# =============================================================================

$ErrorActionPreference = 'Continue'

$Distro      = 'PD1610'
$InstallPath = 'D:\WSL\PD1610'
$Rootfs      = 'D:\16\PD1610_81\build\ubuntu-base-20.04.5-base-amd64.tar.gz'
$Provision   = 'D:\16\PD1610_81\build\wsl_provision.sh'
$WslConfig   = Join-Path $env:USERPROFILE '.wslconfig'

function Step($n, $msg) { Write-Host ""; Write-Host "[$n] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "    OK   $msg" -ForegroundColor Green }
function Fail($msg)     { Write-Host "    FAIL $msg" -ForegroundColor Red }

# ------------------------------------------------------------------ 1. probe
Step '1/6' 'Checking wsl.exe availability'
$wslOk = $false
try {
    $null = & wsl.exe --status 2>&1
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1) { $wslOk = $true }
} catch {
    $wslOk = $false
}
if (-not $wslOk) {
    Fail 'wsl.exe is still blocked. Remove it from Security Center -> Command Security -> Program Blacklist, then rerun.'
    exit 1
}
Ok 'wsl.exe callable'
$ver = (& wsl.exe --version 2>&1 | Out-String)
Write-Host ("    " + ($ver -split "`n" | Select-Object -First 1))

# ------------------------------------------------------------------ 2. wslconfig
Step '2/6' 'Tuning global .wslconfig'
if (Test-Path $WslConfig) {
    Ok "$WslConfig already exists, left untouched"
    Get-Content $WslConfig | ForEach-Object { Write-Host "      $_" }
} else {
    $cfg = @"
[wsl2]
# Host has 28 GB RAM / 16 threads. Leave headroom for Windows itself.
memory=18GB
processors=14
swap=8GB
localhostForwarding=true

[experimental]
sparseVhd=true
"@
    Set-Content -Path $WslConfig -Value $cfg -Encoding ascii
    Ok "written $WslConfig"
}

# ------------------------------------------------------------------ 3. import
Step '3/6' 'Importing Ubuntu 20.04 into D:\WSL\PD1610'
$existing = (& wsl.exe -l -q 2>&1 | Out-String)
if ($existing -match [regex]::Escape($Distro)) {
    Ok "distribution '$Distro' already registered, skipping import"
} else {
    if (-not (Test-Path $Rootfs)) { Fail "rootfs not found: $Rootfs"; exit 1 }
    New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
    & wsl.exe --import $Distro $InstallPath $Rootfs --version 2 2>&1 | ForEach-Object { Write-Host "      $_" }
    if ($LASTEXITCODE -ne 0) {
        Fail "import failed (exit $LASTEXITCODE)"
        exit 1
    }
    Ok 'imported'
}

# ------------------------------------------------------------------ 4. ensure v2
Step '4/6' 'Ensuring WSL version 2'
& wsl.exe --set-version $Distro 2 2>&1 | ForEach-Object { Write-Host "      $_" }
$vlist = (& wsl.exe -l -v 2>&1 | Out-String)
Write-Host $vlist
Ok 'version check done'

# ------------------------------------------------------------------ 5. provision
# NOTE: single-quoted strings only. PowerShell 5.1 treats \$ as a literal
# backslash plus $, which makes "$(...)" start a subexpression and choke on &&.
Step '5/6' 'Provisioning inside the distro (apt mirror + build deps)'
Write-Host '    this takes a few minutes on first run...'
& wsl.exe -d $Distro -u root -- bash -lc 'bash /mnt/d/16/PD1610_81/build/wsl_provision.sh' 2>&1 | ForEach-Object { Write-Host "      $_" }
if ($LASTEXITCODE -ne 0) {
    Fail "provision failed (exit $LASTEXITCODE)"
    exit 1
}
Ok 'provisioned'

# ------------------------------------------------------------------ 6. verify
Step '6/6' 'Verifying the build box'
& wsl.exe -d $Distro -- bash -lc 'cat /etc/os-release | head -2' 2>&1 | ForEach-Object { Write-Host "    $_" }
& wsl.exe -d $Distro -- bash -lc 'echo "user=$(whoami)  cwd=$(pwd)  fs=$(stat -f -c %T /home)"' 2>&1 | ForEach-Object { Write-Host "    $_" }
& wsl.exe -d $Distro -- bash -lc 'echo "nproc=$(nproc)  mem=$(free -g | awk "/^Mem:/{print \$2}")GB"' 2>&1 | ForEach-Object { Write-Host "    $_" }
& wsl.exe -d $Distro -- bash -lc 'python --version 2>&1; java -version 2>&1 | head -1; gcc --version | head -1' 2>&1 | ForEach-Object { Write-Host "    $_" }
& wsl.exe -d $Distro -- bash -lc 'sudo -n true' 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host '    sudo: passwordless OK' } else { Write-Host '    sudo: NOT passwordless' }

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host " WSL2 build box ready. Next steps:" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host ""
Write-Host " 1) enter the box:"
Write-Host "      wsl -d PD1610"
Write-Host ""
Write-Host " 2) sync LineageOS 16.0 source (~35 GB, 1-4 h depending on link):"
Write-Host "      cd ~ && mkdir -p los16 && cp /mnt/d/16/PD1610_81/build/repo ~/bin/repo"
Write-Host "      chmod +x ~/bin/repo && export PATH=~/bin:\$PATH"
Write-Host "      bash /mnt/d/16/PD1610_81/build/sync_los16.sh"
Write-Host ""
Write-Host " 3) build (after source is in and device tree copied):"
Write-Host "      DEVICE_TREE_SRC=/mnt/d/16/PD1610_81/device_tree/device/vivo/pd1610 \\"
Write-Host "      BLOBS_DIR=/mnt/d/16/PD1610_81/blobs \\"
Write-Host "      bash /mnt/d/16/PD1610_81/build/build_los16.sh"
Write-Host ""
