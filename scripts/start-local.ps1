<#
.SYNOPSIS
    本地一键启动/停止「医疗岗位情报与真实简历定制工具」。
    后端：uv + uvicorn (127.0.0.1:8000)；前端：pnpm + Vite (127.0.0.1:5173)。

.DESCRIPTION
    默认动作：检查工具链与端口 → 前端依赖安装（非交互）→ 后台启动前后端
    （日志写入 logs/）→ 等待健康检查 → 输出接口自检摘要 → 打开浏览器。

    注意：
    - 后端必须在 backend/ 目录下启动（app 包在该目录），数据库对应
      backend/data/app.db（仓库根目录的 data/app.db 是另一份数据）。
    - pnpm 与 node_modules 布局版本不一致时会弹出交互确认，脚本已将其
      禁用并把 stdin 指向 NUL，避免启动命令永远卡在等待输入。

    加 -Stop 则停止由本脚本启动的服务（按 PID 文件 + 进程树停止），
    不会误杀其他程序。

.EXAMPLE
    pwsh -NoProfile -File scripts/start-local.ps1
    pwsh -NoProfile -File scripts/start-local.ps1 -NoBrowser -SkipInstall
    pwsh -NoProfile -File scripts/start-local.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Stop,          # 停止本脚本启动的前后端服务
    [switch]$NoBrowser,     # 启动后不自动打开浏览器
    [switch]$SkipInstall    # 跳过前端依赖检查/安装
)

$ErrorActionPreference = 'Stop'

$Root        = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir  = Join-Path $Root 'backend'
$LogDir      = Join-Path $Root 'logs'
$FrontendDir = Join-Path $Root 'frontend'
$BackendPort  = 8000
$FrontendPort = 5173

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}
function Write-ErrorLine {
    param([string]$Message)
    Write-Host "[X] $Message" -ForegroundColor Red
}
function Assert-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        Write-ErrorLine "找不到命令 '$Name'。请先安装：backend 依赖用 uv (https://docs.astral.sh/uv/)，前端用 pnpm (npm i -g pnpm)。"
        exit 1
    }
    return $cmd
}
function Test-PortBindable {
    param([int]$Port)
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        $listener.Stop()
    }
}
function Remove-PidFile {
    param([string]$Path)
    if (Test-Path $Path) { Remove-Item $Path -Force }
}
function Stop-ServiceByPidFile {
    param([string]$PidFile, [string]$Label)
    if (Test-Path $PidFile) {
        $pidText = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($pidText -match '^\d+$') {
            Write-Host "  停止 $Label (PID $pidText 及其子进程) ..."
            & taskkill.exe /PID ([int]$pidText) /T /F 2>$null | Out-Null
        }
        Remove-PidFile $PidFile
    }
}

# ---------------------------------------------------------------------------
# 停止模式
# ---------------------------------------------------------------------------
if ($Stop) {
    Write-Step '停止本地服务'
    Stop-ServiceByPidFile (Join-Path $LogDir 'backend.pid')  '后端'
    Stop-ServiceByPidFile (Join-Path $LogDir 'frontend.pid') '前端'
    Start-Sleep -Milliseconds 800

    $backendFree  = Test-PortBindable $BackendPort
    $frontendFree = Test-PortBindable $FrontendPort
    $allFree = $backendFree -and $frontendFree
    if ($allFree) {
        Write-Host '  服务已全部停止，端口已释放。' -ForegroundColor Green
    } else {
        Write-ErrorLine "仍有进程占用端口（PID 文件可能失效或进程非本脚本启动）："
        Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -in $BackendPort, $FrontendPort } |
            ForEach-Object { Write-Host "    端口 $($_.LocalPort) <- PID $($_.OwningProcess) ($((Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName))" }
        Write-Host '  如需强制停止，请自行确认后 taskkill /PID <pid> /T /F。'
    }
    exit 0
}

# ---------------------------------------------------------------------------
# 启动模式
# ---------------------------------------------------------------------------
Write-Step '检查工具链 (uv / pnpm)'
$uv     = Assert-Command 'uv'
$pnpm   = Assert-Command 'pnpm'
$cmdExe = (Get-Command cmd.exe).Source

Write-Step "检查端口 (后端 $BackendPort / 前端 $FrontendPort)"
foreach ($p in @($BackendPort, $FrontendPort)) {
    if (-not (Test-PortBindable $p)) {
        Write-ErrorLine "端口 $p 已被占用（可能已有实例在运行）。先执行 scripts/start-local.ps1 -Stop，或自行排查："
        Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -eq $p } |
            ForEach-Object { Write-Host "    端口 $p <- PID $($_.OwningProcess) ($((Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName))" }
        exit 1
    }
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# 全程 CI=true（仅对本脚本进程及其子进程生效）：
#  - pnpm 不再弹出交互确认（ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY 的官方建议）
#  - pnpm 不会自动切换 packageManager 声明的版本，install 与 dev 始终用同一个 pnpm，
#    避免 node_modules 布局在两次运行间不一致导致反复要求重装
#  - vite 在 CI 模式下正常服务，仅关闭清屏/自动开浏览器等小特性
$env:CI = 'true'
$env:npm_config_confirm_modules_purge = 'false'

# --- 前端依赖：非交互安装（node_modules 布局与 pnpm 不一致时需要确认删除重建，
#     由 CI=true 禁掉确认，再由 cmd 把 Y 喂进 pnpm 的 stdin 兜底）---
if (-not $SkipInstall) {
    Write-Step '同步前端依赖 (pnpm install，非交互)'
    Push-Location $FrontendDir
    try {
        & $cmdExe /c "echo Y| pnpm install" | Select-Object -Last 5
        if ($LASTEXITCODE -ne 0) { throw "pnpm install 失败 (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

# --- 后端 ---
$backendOut = Join-Path $LogDir 'backend.log'
$backendErr = Join-Path $LogDir 'backend.err.log'
$backendPid = Join-Path $LogDir 'backend.pid'
Write-Step "启动后端 (uvicorn 127.0.0.1:$BackendPort)"
# 必须在 backend/ 下启动；用 python -m 保证 backend/ 在 sys.path
$backend = Start-Process -FilePath $uv.Source `
    -ArgumentList @('run', '--project', '.', 'python', '-m', 'uvicorn',
                    'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort") `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError  $backendErr `
    -WindowStyle Hidden -PassThru
$backend.Id | Set-Content $backendPid

# --- 前端 ---
$frontendOut = Join-Path $LogDir 'frontend.log'
$frontendErr = Join-Path $LogDir 'frontend.err.log'
$frontendPid = Join-Path $LogDir 'frontend.pid'
Write-Step "启动前端 (Vite 127.0.0.1:$FrontendPort)"
# stdin 指向 NUL：即使 pnpm 再出现交互提示也会立刻 EOF，不会永久挂起
$frontend = Start-Process -FilePath $cmdExe `
    -ArgumentList @('/c', 'pnpm dev <nul') `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError  $frontendErr `
    -WindowStyle Hidden -PassThru
$frontend.Id | Set-Content $frontendPid

# --- 等待健康检查 ---
Write-Step '等待后端健康检查 (/health)'
$backendReady = $false
$deadline = (Get-Date).AddSeconds(90)
while (-not $backendReady -and (Get-Date) -lt $deadline) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2
        $backendReady = $true
    } catch {
        Start-Sleep -Milliseconds 700
    }
}
if (-not $backendReady) {
    Write-ErrorLine "后端 90 秒内未就绪，最近错误日志 (logs/backend.err.log)："
    Get-Content $backendErr -Tail 20 -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "  后端就绪: http://127.0.0.1:$BackendPort" -ForegroundColor Green

Write-Step "等待前端就绪 (http://127.0.0.1:$FrontendPort)"
$frontendReady = $false
$deadline = (Get-Date).AddSeconds(60)
while (-not $frontendReady -and (Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2
        $frontendReady = $true
    } catch {
        Start-Sleep -Milliseconds 700
    }
}
if (-not $frontendReady) {
    Write-ErrorLine "前端 60 秒内未就绪，最近日志 (logs/frontend.log / logs/frontend.err.log)："
    Get-Content $frontendErr -Tail 20 -ErrorAction SilentlyContinue
    Get-Content $frontendOut  -Tail 20 -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "  前端就绪: http://127.0.0.1:$FrontendPort" -ForegroundColor Green

# --- 只读接口自检 ---
Write-Step '接口自检 (/api/jobs, /api/analytics/summary)'
try {
    $jobsResp = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/jobs" -TimeoutSec 15
    $jobItems = if ($null -ne $jobsResp.jobs)  { $jobsResp.jobs }
                elseif ($null -ne $jobsResp.items) { $jobsResp.items }
                else { $jobsResp }
    $jobCount = if ($null -ne $jobsResp.total) { $jobsResp.total } else { @($jobItems).Count }
    Write-Host "  /api/jobs            -> $jobCount 条岗位记录" -ForegroundColor Green

    $summary = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/analytics/summary" -TimeoutSec 15
    $summaryText = ($summary | ConvertTo-Json -Depth 3 -Compress)
    if ($summaryText.Length -gt 400) { $summaryText = $summaryText.Substring(0, 400) + '...' }
    Write-Host "  /api/analytics/summary -> $summaryText" -ForegroundColor Green
} catch {
    Write-Host "  (接口自检失败，但不影响服务运行: $($_.Exception.Message))" -ForegroundColor Yellow
}

# --- 打开浏览器 ---
if (-not $NoBrowser) {
    Write-Step '打开浏览器'
    Start-Process "http://127.0.0.1:$FrontendPort"
}

Write-Host ''
Write-Host '======================== 本地服务已启动 ========================' -ForegroundColor Cyan
Write-Host "  前端     http://127.0.0.1:$FrontendPort"
Write-Host "  后端     http://127.0.0.1:$BackendPort      健康检查 /health"
Write-Host "  数据库   $BackendDir\data\app.db"
Write-Host "  日志     logs\backend.log / logs\frontend.log (错误: *.err.log)"
Write-Host "  PID 文件 logs\backend.pid / logs\frontend.pid"
Write-Host ''
Write-Host '  服务在独立后台进程运行，关闭本终端不会停止它们。' -ForegroundColor Yellow
Write-Host "  停止:   pwsh -NoProfile -File $($MyInvocation.MyCommand.Path) -Stop"
Write-Host '================================================================' -ForegroundColor Cyan
exit 0