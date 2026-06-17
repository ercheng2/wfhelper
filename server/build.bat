@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   微信好友助手 v2.0 打包脚本
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: Install PyInstaller
echo [1/3] 安装打包工具...
pip install pyinstaller -q
if errorlevel 1 (
    echo [错误] PyInstaller 安装失败
    pause
    exit /b 1
)

:: Install app dependencies first (needed for PyInstaller to detect imports)
echo [2/3] 安装依赖...
pip install pymupdf Pillow pdf2image -q 2>nul

:: Build single exe
echo [3/3] 打包中（生成单个exe文件）...
pyinstaller --noconfirm --onefile --name "微信好友助手" ^
  --add-data "static;static" ^
  --add-data "preset_customers.json;.\" ^
  --add-data "extra_customers.json;.\" ^
  --add-data "config.json;.\" ^
  app.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

:: Copy config.json to output directory (user may need to edit it)
echo.
echo 复制配置文件...
copy config.json dist\ >nul

echo.
echo ========================================
echo   打包完成！
echo   输出目录：dist\
echo   主程序：dist\微信好友助手.exe
echo   配置文件：dist\config.json
echo.
echo   使用方法：
echo   1. 将 dist\微信好友助手.exe 和 config.json
echo      放在同一目录
echo   2. 编辑 config.json 可修改监听地址和端口
echo   3. 双击 微信好友助手.exe 启动服务器
echo   4. 局域网其他设备访问 http://IP:8199
echo ========================================
pause
