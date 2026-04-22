#!/bin/bash
# サーバーへのデプロイセットアップスクリプト
# SSH接続後に一度だけ実行する
#
# 使い方:
#   bash /home/xs539690/forex_project/forex_signal_tool/tasks/deploy_setup.sh

set -e

PROJECT_DIR="/home/xs539690/forex_project"
TOOL_DIR="$PROJECT_DIR/forex_signal_tool"
PUBLIC_HTML="/home/xs539690/kawase-ai.com/public_html"
PYTHON="/home/xs539690/forex_env/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"

echo "=== デプロイセットアップ開始 ==="

# ログディレクトリ作成
mkdir -p "$LOG_DIR"
echo "ログディレクトリ: $LOG_DIR"

# public_html のセットアップ
echo "--- public_html セットアップ ---"

# action.php をコピー
cp "$TOOL_DIR/public_html/action.php" "$PUBLIC_HTML/action.php"
echo "action.php コピー完了"

# .htaccess をコピー（既存を上書き）
cp "$TOOL_DIR/public_html/.htaccess" "$PUBLIC_HTML/.htaccess"
echo ".htaccess コピー完了"

# static ディレクトリをシンボリックリンクで公開
if [ ! -e "$PUBLIC_HTML/static" ]; then
    ln -s "$TOOL_DIR/static" "$PUBLIC_HTML/static"
    echo "staticディレクトリ シンボリックリンク作成"
else
    echo "staticディレクトリ 既存のリンク/ディレクトリあり (スキップ)"
fi

# 旧 app.cgi を無効化（存在する場合）
if [ -f "$PUBLIC_HTML/app.cgi" ]; then
    mv "$PUBLIC_HTML/app.cgi" "$PUBLIC_HTML/app.cgi.disabled"
    echo "app.cgi を無効化 → app.cgi.disabled"
fi

# 権限設定
chmod 755 "$PUBLIC_HTML/action.php"
echo "action.php パーミッション設定完了"

# 初回の静的HTML生成
echo "--- 静的HTML生成 ---"
cd "$TOOL_DIR"
"$PYTHON" "$TOOL_DIR/tasks/generate_static.py" 2>&1 | tee -a "$LOG_DIR/generate.log"

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "Cronジョブを設定してください（crontab -e）:"
echo "*/30 * * * * cd /home/xs539690 && /home/xs539690/forex_env/bin/python3 /home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py all >> /home/xs539690/forex_project/logs/cron.log 2>&1"
echo ""
echo "または個別に:"
echo "0 * * * * /home/xs539690/forex_env/bin/python3 /home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py fetch_data >> /home/xs539690/forex_project/logs/cron.log 2>&1"
echo "*/30 * * * * /home/xs539690/forex_env/bin/python3 /home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py backtest >> /home/xs539690/forex_project/logs/cron.log 2>&1"
echo "*/30 * * * * /home/xs539690/forex_env/bin/python3 /home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py signals >> /home/xs539690/forex_project/logs/cron.log 2>&1"
echo "0 6,12,18 * * * /home/xs539690/forex_env/bin/python3 /home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py report >> /home/xs539690/forex_project/logs/cron.log 2>&1"
