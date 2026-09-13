# 規約・ポリシー 一元管理（利用規約 / プライバシーポリシー / コミュニティガイドライン）

## 目的
WEBとアプリで内容がズレていた利用規約・プライバシーポリシー・コミュニティガイドラインを、
**管理画面の単一レコード（`pages.LegalDocument`）** を唯一のソースとして統一する。
管理画面で本文を更新すると、WEBページとアプリの両方に同じ内容が反映される。

## 管理画面
- 場所: `/admin/` → 「ページ（pages）」→ **規約・ポリシー**
- 3レコード: `terms`（利用規約）/ `privacy`（プライバシーポリシー）/ `community`（コミュニティガイドライン）
- 編集項目: タイトル / 英字ラベル(eyebrow) / 本文(HTML) / 制定日 / 最終改定日 / 公開フラグ
- 本文はセマンティックHTMLで記述（`<h2> <h3> <p> <ul><li> <ol><li> <a href>`）。
  **class属性は不要** — WEB側のCSS（`templates/pages/legal.html` 内 `.legal-prose`）で自動装飾。
- 「公開」をオフにするとWEB・アプリ双方で 404（非表示）になる。
- 保存後、WEBは即時反映。アプリは次回取得時に反映（キャッシュ方針はアプリ側依存）。

## WEB（既存URLは不変）
- `/terms/` `/privacy/` `/community-guidelines/`
- ビューは `apps/pages/views.py` の `_legal()` がDBから取得し `pages/legal.html` で描画。
- 旧静的テンプレート（terms.html 等）は廃止し削除済み。

## アプリ用 API（DRF・**未ログインでも取得可** AllowAny）

### 一覧（起動時に一括取得・キャッシュ向け）
```
GET /api/legal/
200 → [ {legal object}, {legal object}, {legal object} ]   # 公開中のみ
```

### 個別取得
```
GET /api/legal/{type}/      # type = terms | privacy | community
200 → {legal object}
404 → 未公開 または 不明なtype
```

### legal object スキーマ
```json
{
  "type": "terms",
  "type_label": "利用規約",
  "eyebrow": "Terms",
  "title": "利用規約",
  "body_html": "<p>...</p><h2>第1条 適用</h2><ol><li>...</li></ol>...",
  "body_text": "タグを除去したプレーンテキスト全文",
  "enacted_on": "2026-06-22",
  "revised_on": "2026-06-22",
  "updated_at": "2026-06-26T12:34:56+09:00"
}
```

### アプリ実装メモ
- 推奨: `body_html` を WebView / ネイティブHTMLレンダラで表示（WEBと同一の構造）。
  CSSはアプリ側で用意（h2=見出し、ol/ul=リスト等）。class属性は付かない。
- 簡易表示なら `body_text` を使う（書式なしプレーンテキスト）。
- 本文中のリンク（`/terms/` `/contact/` 等）はサイト相対パス。アプリ側で適宜ハンドリング。
- `revised_on` / `updated_at` で「最終改定日」表示や更新検知が可能。

## バックエンド実装ファイル
- モデル: `apps/pages/models.py` `LegalDocument`
- マイグレーション: `apps/pages/migrations/0002_legaldocument.py`（スキーマ）、
  `0003_seed_legal_documents.py`（既存WEB内容を初期投入）
- 管理画面: `apps/pages/admin.py` `LegalDocumentAdmin`
- WEB: `apps/pages/views.py` `_legal()` / `templates/pages/legal.html`
- API: `apps/pages/api_serializers.py` `LegalDocumentSerializer` /
  `apps/pages/api_views.py` `LegalDocumentListAPIView` `LegalDocumentDetailAPIView` /
  `config/api_urls.py`

## 反映手順（本番）
1. `git pull`（または本環境）でコード反映
2. `.venv/bin/python manage.py migrate pages`（初回のみ・スキーマ＋初期データ）
3. `sudo systemctl reload gunicorn-tushou`（HUP 無停止リロード／コード変更のみのため reload で可）
