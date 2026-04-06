# FXシグナルツール

為替相場（USD/JPY・GBP/JPY・EUR/JPY）のリアルタイムシグナルツール。  
Alpha Vantage 無料APIでデータ取得、Google Gemini AIで相場レポートを自動生成します。

## 機能概要

| 機能 | 説明 |
|------|------|
| 価格データ取得 | Alpha Vantage 無料API（5分/15分/30分/1時間/4時間/日足） |
| テクニカル指標 | 20種類以上（オシレーター・トレンド・ライン・パターン・ボラティリティ） |
| バックテスト | 直近12時間の勝率・損益・ドローダウンを自動計算 |
| シグナル生成 | 勝率55%以上の指標のみ表示（閾値は設定画面で変更可） |
| AIレポート | Google Gemini で日本語の相場分析レポートを自動生成 |
| メール配信 | 設定した時刻にレポートをメール送信 |
| Webダッシュボード | シグナル・バックテスト・レポートを一画面で確認 |

## ディレクトリ構成

```
forex_signal_tool/
├── app/
│   ├── config.py              # 設定
│   ├── models/                # DBモデル (PostgreSQL)
│   ├── services/
│   │   ├── data_fetcher.py    # Alpha Vantage API
│   │   ├── indicators/        # テクニカル指標計算
│   │   ├── backtester.py      # バックテストエンジン
│   │   ├── signal_engine.py   # シグナル生成
│   │   ├── report_generator.py # Gemini AIレポート
│   │   └── email_sender.py    # メール送信
│   ├── routes/                # Flaskルート
│   └── templates/             # HTMLテンプレート
├── static/                    # CSS/JS
├── tasks/                     # Cronジョブスクリプト
├── migrations/
│   └── 001_init.sql           # DB初期化SQL
├── wsgi.py                    # Xサーバー用WSGIエントリ
├── run.py                     # ローカル開発用
└── requirements.txt
```

## セットアップ手順

### 1. APIキーの取得

| サービス | 取得先 | 無料枠 |
|----------|--------|--------|
| Alpha Vantage | https://www.alphavantage.co/support/#api-key | 25リクエスト/日 |
| Google Gemini | https://aistudio.google.com/app/apikey | 1500リクエスト/日 |

### 2. 環境変数の設定

```bash
cp .env.example .env
# .envを編集してAPIキー等を設定
```

### 3. PostgreSQLデータベースの作成

```bash
# XサーバーのPhpMyAdmin等でDBを作成後:
psql -U your_user -d forex_signal_db -f migrations/001_init.sql
```

### 4. Pythonパッケージのインストール

```bash
pip3 install -r requirements.txt
```

### 5. DBマイグレーション（Flask-Migrate使用の場合）

```bash
flask db init
flask db migrate
flask db upgrade
```

### 6. 動作確認（ローカル）

```bash
python3 run.py
# → http://localhost:5000 でアクセス
```

## Xサーバー デプロイ手順

### WSGIの設定

`.htaccess` を公開ディレクトリに配置:

```apache
Options +ExecCGI
AddHandler wsgi-script .py
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ /wsgi.py/$1 [QSA,PT,L]
```

### Cronジョブ設定

Xサーバーの「Cron設定」から以下を登録:

```bash
# データ取得（1日2回 - 無料プランの制限に注意）
0 0,12 * * * cd /home/user/public_html && python3 tasks/fetch_data.py >> logs/fetch.log 2>&1

# バックテスト + シグナル更新（30分ごと）
*/30 * * * * cd /home/user/public_html && python3 tasks/run_analysis.py >> logs/analysis.log 2>&1

# レポート配信（UTC 6:00, 12:00, 18:00）
0 6,12,18 * * * cd /home/user/public_html && python3 tasks/send_report.py >> logs/report.log 2>&1
```

### ログディレクトリの作成

```bash
mkdir -p logs
```

## Alpha Vantage 無料プランの制限について

無料プランは **25リクエスト/日** の制限があります。  
3通貨ペア × 5タイムフレーム = 15リクエストが最低限必要なため、**1日2回**のデータ取得を推奨します。

より頻繁な更新が必要な場合は、Alpha Vantageの有料プランへのアップグレードを検討してください。

## テクニカル指標一覧

### オシレーター系
- RSI (14)
- MACD (12, 26, 9)
- Stochastic (14, 3, 3)
- CCI (20)
- Williams %R (14)

### トレンド系
- SMA (20, 50)
- SMA クロス (20/50)
- EMA クロス (9/21)
- EMA (21)
- ボリンジャーバンド (20, 2σ)
- BB スクイーズ

### ライン系
- ピボットポイント（クラシック）
- フィボナッチリトレースメント
- 動的サポート・レジスタンス

### パターン系
- ハンマー
- 逆ハンマー
- 十字線（Doji）
- 強気包み足
- 弱気包み足
- 三白兵
- 三羽烏
- ピンバー

### ボラティリティ系
- ATR (14)
- ボラティリティインデックス

## ライセンス

このソフトウェアは投資助言を提供するものではありません。  
実際の取引は自己責任で行ってください。
