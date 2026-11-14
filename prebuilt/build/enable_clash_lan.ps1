# 一键让 Clash Verge 监听 0.0.0.0（供 WSL2 使用），免重启内核。
# 原理：Clash Verge 的 external-controller 走命名管道，其 REST API 支持
#       PATCH /configs {"allow-lan":true}，mihomo 会立刻把监听从 127.0.0.1
#       切到双栈 any，WSL 即可通过 Windows 主机 IP 访问。
# 用法：powershell -ExecutionPolicy Bypass -File enable_clash_lan.ps1

$pipeName = (Get-ChildItem -Path '\\.\pipe\' |
    Where-Object { $_.Name -match '^verge-mihomo-sidecar-release-' } |
    Select-Object -First 1).Name

if (-not $pipeName) { Write-Output "未找到 mihomo 命名管道，Clash Verge 可能没在运行"; exit 1 }

function Invoke-MihomoApi {
    param([string]$Method, [string]$Path, [string]$Body)
    $p = New-Object System.IO.Pipes.NamedPipeClientStream('.', $pipeName, [System.IO.Pipes.PipeDirection]::InOut)
    $p.Connect(3000)
    $hd = "$Method $Path HTTP/1.1`r`nHost: localhost`r`nAuthorization: Bearer set-your-secret`r`nConnection: close`r`n"
    if ($Body) { $hd += "Content-Type: application/json`r`nContent-Length: $([Text.Encoding]::UTF8.GetByteCount($Body))`r`n" }
    $bytes = [Text.Encoding]::UTF8.GetBytes($hd + "`r`n" + $Body)
    $p.Write($bytes, 0, $bytes.Length); $p.Flush()
    $ms = New-Object System.IO.MemoryStream
    $buf = New-Object byte[] 16384
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt 5000) {
        try { $n = $p.Read($buf, 0, $buf.Length); if ($n -le 0) { break }; $ms.Write($buf, 0, $n) } catch { break }
    }
    $p.Close()
    [Text.Encoding]::UTF8.GetString($ms.ToArray())
}

$resp = Invoke-MihomoApi -Method 'PATCH' -Path '/configs' -Body '{"allow-lan":true}'
$status = ($resp -split "`r`n")[0]
Write-Output "PATCH /configs -> $status"

Start-Sleep -Milliseconds 500
$listen = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq 7897 } |
    Select-Object -ExpandProperty LocalAddress -Unique
Write-Output ("7897 监听地址: " + ($listen -join ', '))

if ($listen -contains '::' -or $listen -contains '0.0.0.0') {
    # 取 WSL 侧网关（Windows 在 vEthernet (WSL) 上的地址）
    $wslIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -match 'WSL' } |
        Select-Object -First 1).IPAddress
    if (-not $wslIp) { $wslIp = '172.31.96.1' }
    Write-Output "WSL 侧代理地址: http://${wslIp}:7897"
} else {
    Write-Output "警告：仍只监听回环，WSL 无法使用"
}
