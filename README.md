# 美顔器レビューサイト

美顔器のユーザー投稿型口コミサイト。Django製。

## 機能

- 商品カタログ（カテゴリ、画像、参考価格、特徴、公式URL/アフィリURL）
- 会員登録 / ログイン（メール認証つき）
- 口コミ投稿（星評価・使用期間・効果実感・肌質）
- **ゲート機能**: 他ユーザーの口コミ全文を見るには、自分も1件以上の口コミを投稿する必要あり（未投稿者には2件だけプレビュー表示）
- 管理画面（Django admin）で商品・口コミ・会員を管理
- WordPress XML (WXR) からの記事インポート
- 構造化データ (JSON-LD) 出力で商品ページのSEO対応

## 開発セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python manage.py migrate
python manage.py seed_demo           # デモデータ投入
python manage.py createsuperuser     # 管理者作成
python manage.py runserver 0.0.0.0:8000
```

- サイト: http://localhost:8000/
- 管理画面: http://localhost:8000/admin/
- デモログイン: `hanako@example.com` / `demopass1234`

## WordPress XMLインポート

```bash
# 記事として取り込む
python manage.py import_wordpress /path/to/wordpress.xml

# 記事 + 商品 としても取り込む
python manage.py import_wordpress /path/to/wordpress.xml --as-products

# ドライラン（DBへ書き込まず件数確認）
python manage.py import_wordpress /path/to/wordpress.xml --dry-run
```

## URL構成

| URL | 内容 |
|---|---|
| `/` | 商品一覧（TOP）|
| `/products/<slug>/` | 商品詳細・口コミ |
| `/articles/` | 記事一覧 |
| `/articles/<slug>/` | 記事詳細 |
| `/reviews/` | 全ユーザーの口コミ（ゲート対象）|
| `/reviews/new/<product-slug>/` | 口コミ投稿フォーム |
| `/accounts/signup/` | 会員登録 |
| `/accounts/login/` | ログイン |
| `/accounts/profile/` | マイページ |
| `/admin/` | 管理画面 |

## 本番デプロイ（ConoHa VPS）

`DEPLOY.md` を参照してください。
