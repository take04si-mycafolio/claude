@echo off
chcp 65001 > nul
echo ========================================
echo   カード相場スクレイパー 起動中...
echo ========================================
echo.

REM Python がインストールされているか確認
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python が見つかりません。
    echo https://www.python.org/downloads/ からインストールしてください。
    pause
    exit /b 1
)

REM 依存ライブラリのインストール（初回のみ）
echo 依存ライブラリを確認中...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [WARNING] 一部のライブラリインストールに失敗しました。
)

echo.
echo アプリケーションを起動します...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 起動に失敗しました。
    pause
)
