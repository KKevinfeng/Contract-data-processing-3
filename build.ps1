# Build script: 使用 Nuitka 打包 PySide6 应用为 exe
# 要求: Python 3.10+ 且已安装依赖 (pip install -r requirements.txt)
#       PySide6 版本需在 venv 中运行：.\venv\Scripts\activate
# 输出: dist\v{version}\main.exe
#
# 说明：本脚本会先复制源码到一个干净的临时目录，排除运行时自动生成的缓存文件，
#      避免把用户本地数据（industry_dict.json、续保明细等）打包进 exe。

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# 强制控制台 UTF-8 编码，防止中文乱码
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 优先使用项目 venv 中的 Python（已安装 PySide6 + Nuitka）
$venvPython = "$projectDir\venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    Write-Host "使用 venv Python: $python" -ForegroundColor Green
} else {
    # 兜底：使用 workbuddy 或系统 Python
    $python = "$env:USERPROFILE\.workbuddy\binaries\python\versions\3.14.3\python.exe"
    if (-not (Test-Path $python)) { $python = "python" }
    Write-Host "使用系统 Python: $python" -ForegroundColor Yellow
}

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$buildDir = Join-Path $env:TEMP "contract-data-processing-build-$timestamp"

Write-Host "准备干净构建目录: $buildDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

# 复制源码文件到临时目录（排除运行时缓存/日志/版本控制/旧构建产物）
$sourceItems = @(
    "main.py",
    "data_processor.py",
    "utils.py",
    "requirements.txt",
    "CHANGELOG.txt",
    "README.md",
    "logo.ico",
    "ui"
)

foreach ($item in $sourceItems) {
    $src = Join-Path $projectDir $item
    $dst = Join-Path $buildDir $item
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Recurse -Force
    } else {
        Write-Warning "源文件不存在，已跳过: $src"
    }
}

Write-Host "开始打包..." -ForegroundColor Cyan

Push-Location $buildDir

try {
    & $python -m nuitka `
        --standalone `
        --windows-console-mode=disable `
        --enable-plugin=pyside6 `
        --include-data-files="CHANGELOG.txt=CHANGELOG.txt" `
        --include-data-files="README.md=README.md" `
        --include-data-files="logo.ico=logo.ico" `
        --windows-icon-from-ico=logo.ico `
        --remove-output `
        --output-dir=dist `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka 打包失败，退出码: $LASTEXITCODE"
    }

    # 提取版本号（从 main_window.py 中读取）
    $versionFile = Join-Path (Join-Path $buildDir "ui") "main_window.py"
    $versionMatch = Select-String -Path $versionFile -Pattern '版本信息：([\d.]+)' | Select-Object -First 1
    if ($versionMatch) {
        $version = $versionMatch.Matches.Groups[1].Value
        $versionDir = "v$version"
    } else {
        $versionDir = "main.dist"
        Write-Warning "无法提取版本号，使用默认目录名"
    }

    # 把生成的 dist 目录复制回项目根目录
    $srcDist = Join-Path $buildDir "dist"
    $dstDist = Join-Path $projectDir "dist"

    # 直接复制 main.dist 并重命名为版本号目录
    $srcMainDist = Join-Path $srcDist "main.dist"
    $newDir = Join-Path $dstDist $versionDir
    if (Test-Path $newDir) {
        Remove-Item -Recurse -Force $newDir
    }
    Copy-Item -Path $srcMainDist -Destination $newDir -Recurse -Force

    Write-Host "打包完成! 输出目录: $newDir\" -ForegroundColor Green
} finally {
    Pop-Location
    Write-Host "清理临时构建目录..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
}
