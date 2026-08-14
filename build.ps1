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

# 优先使用项目 venv311 中的 Python（Python 3.11.9，Nuitka 稳定支持，已装依赖）
$venvPython = "$projectDir\venv311\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    Write-Host "使用 venv311 Python: $python" -ForegroundColor Green
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
        --assume-yes-for-downloads `
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
    # 注意：PowerShell 5 默认按 ANSI/GBK 读取 UTF-8 文件，"版本信息"等中文会乱码；
    # 同时版本行格式为 ("版本信息：", "3.0.2.0")，"：" 与数字之间隔了引号逗号。
    # 因此这里用码点构造中文 pattern（避免本脚本被 GBK 读取时中文乱码），
    # 并显式按 UTF-8 读取文件内容后匹配，正则允许"："后跳过非数字再捕获版本号。
    $versionFile = Join-Path (Join-Path $buildDir "ui") "main_window.py"
    $pat = ([string][char]0x7248 + [string][char]0x672C + [string][char]0x4FE1 +
            [string][char]0x606F + [string][char]0xFF1A + '[^0-9]*([0-9.]+)')
    $fileContent = [System.IO.File]::ReadAllText($versionFile, [System.Text.Encoding]::UTF8)
    $m = [regex]::Match($fileContent, $pat)
    if ($m.Success) {
        $version = $m.Groups[1].Value
        $versionDir = "v$version"
    } else {
        $versionDir = "main.dist"
        Write-Warning "无法提取版本号，使用默认目录名"
    }

    # standalone 模式下，Nuitka 在 dist 下生成 main.dist 目录（含 exe + DLL + 依赖）
    $srcDist = Join-Path $buildDir "dist"
    $dstDist = Join-Path $projectDir "dist"

    # 复制 main.dist 并重命名为版本号目录
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
