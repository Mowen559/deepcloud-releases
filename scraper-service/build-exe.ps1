# 把 scraper-service 打包成单文件 exe
#
# 用法：
#   .\build-exe.ps1            # 打包
#   .\build-exe.ps1 -Clean     # 先清掉 build/dist 再打包
#
# 【重要限制：exe 不包含浏览器】
# Chromium 是几百 MB 的外部二进制，不可能塞进 exe。目标机器需：
#   1. 执行一次 `scrapling install` 落地浏览器；
#   2. 设置 PLAYWRIGHT_BROWSERS_PATH 指向它。
# 第 2 步容易被遗漏但是必需的：打包后 patchright 会到 PyInstaller 的临时解包目录
# （_MEIxxxx\patchright\driver\...）去找浏览器，那里永远不会有——已实测确认
# 设了该变量后 stealthy 模式正常返回 200。

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Clean) {
    Write-Host "[build] 清理 build/ dist/ *.spec" -ForegroundColor Yellow
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
    Remove-Item -Force *.spec -ErrorAction SilentlyContinue
}

Write-Host "[build] 检查 pyinstaller" -ForegroundColor Cyan
$hasPyInstaller = $false
try {
    python -m PyInstaller --version | Out-Null
    $hasPyInstaller = ($LASTEXITCODE -eq 0)
} catch {
    $hasPyInstaller = $false
}
if (-not $hasPyInstaller) {
    Write-Host "[build] 未安装 pyinstaller，执行: pip install pyinstaller" -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "安装 pyinstaller 失败" }
}

# --collect-all 的依据都是实测得来的（只靠静态分析一定会漏）：
#   scrapling                    内部大量动态导入与数据文件（注入用 JS 等）
#   apify_fingerprint_datapoints 指纹数据 zip。漏了它 exe 能启动、/health 也正常，
#                                但一发请求就报 input-network-definition.zip 不存在
#   browserforge / curl_cffi     指纹生成与 TLS 模拟，带 C 扩展和证书文件
#   tld                          公共后缀列表数据（effective_tld_names.dat.txt）。漏了它
#                                每次请求会因找不到数据而重试数次并尝试联网下载，拖慢好几秒
# 不写 camoufox：当前版本并未安装它（已改用 patchright，即 patched playwright）。
# uvicorn 的 hidden-import：uvicorn 按字符串名加载协议/生命周期实现，
#   不显式声明则打包后启动即报 ModuleNotFoundError。
# 变量名不用 $args：那是 PowerShell 的自动变量（当前作用域的参数数组），覆盖它会让语义混乱。
$piArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--name", "deepcloud-engine",
    "--collect-all", "scrapling",
    "--collect-all", "apify_fingerprint_datapoints",
    "--collect-all", "browserforge",
    "--collect-all", "curl_cffi",
    "--collect-all", "tld",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.lifespan.on",
    "--hidden-import", "sqlite3",
    "--noconfirm",
    "run.py"
)

Write-Host "[build] 开始打包（首次约需数分钟）" -ForegroundColor Cyan
python @piArgs
if ($LASTEXITCODE -ne 0) { throw "打包失败" }

$exe = Join-Path $PSScriptRoot "dist\deepcloud-engine.exe"
if (-not (Test-Path $exe)) { throw "打包结束但未找到 $exe" }

$sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "[build] 完成: $exe ($sizeMB MB)" -ForegroundColor Green
Write-Host ""
Write-Host "运行方式:" -ForegroundColor Cyan
Write-Host "  set SCRAPER_PORT=18000"
Write-Host "  .\dist\deepcloud-engine.exe"
Write-Host ""
Write-Host "【浏览器模式必须额外做两件事】" -ForegroundColor Yellow
Write-Host "  1. 安装浏览器（exe 里不可能内含几百 MB 的 Chromium）:"
Write-Host "       pip install scrapling; scrapling install"
Write-Host "  2. 告诉 exe 浏览器在哪里（否则它只会在自己的临时解包目录里找，必然找不到）:"
Write-Host "       set PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\ms-playwright"
Write-Host ""
Write-Host "  不做这两步时 mode=static 仍可正常工作，dynamic/stealthy 会返回 502。" -ForegroundColor Yellow
