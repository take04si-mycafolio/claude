# アプリ実装指示書：利用規約・プライバシー・コミュニティガイドラインの表示

対象: iOSアプリ（`~/Projects/sc-tsusho-app`）チーム
前提: サーバー側API（`/api/legal/`）は実装・本番稼働済み。本書はアプリ側で「規約をアプリ画面に表示する」ためのクライアント実装手順です。
関連: API仕様の詳細は `docs/legal_documents_api.md` を参照。

---

## 0. ゴール
3つの法的文書（利用規約 / プライバシーポリシー / コミュニティガイドライン）を、WEBと**完全に同一の内容**でアプリ内に表示する。内容はサーバーDBの単一ソース（`LegalDocument`）から取得するため、アプリ側は文言をハードコードしない。

---

## 1. 使用するAPI

ベースURL: `https://sc-tsusho.jp`
**認証不要（AllowAny）** — JWTトークンは付けても付けなくてもよい（未ログイン状態の会員登録画面からも表示可能）。

| 用途 | メソッド / パス |
| --- | --- |
| 一覧（起動時の一括取得・キャッシュ向け） | `GET /api/legal/` |
| 個別取得 | `GET /api/legal/{type}/`（type = `terms` / `privacy` / `community`） |

`{type}` が未公開・不明な場合は `404`。

### レスポンス（legal object）
```json
{
  "type": "terms",
  "type_label": "利用規約",
  "eyebrow": "Terms",
  "title": "利用規約",
  "body_html": "<p>...</p><h2>第1条 適用</h2><ol><li>...</li></ol>...",
  "body_text": "タグを除去したプレーンテキスト全文",
  "enacted_on": null,
  "revised_on": "2026-06-28",
  "updated_at": "2026-06-28T06:30:00+09:00"
}
```
- 表示には **`body_html` を推奨**（WEBと同じ構造。`<h2><h3><p><ul><li><ol><li><a>` のみ、class属性なし）。
- 簡易表示なら `body_text`（書式なし）。
- `revised_on`＝最終改定日の表示に使用。`updated_at`＝更新検知（キャッシュ無効化）に使用。
- `enacted_on` / `revised_on` は `null` のことがある（任意項目）。

---

## 2. データモデル（Swift / Codable）

```swift
struct LegalDocument: Codable, Identifiable {
    let type: String          // "terms" | "privacy" | "community"
    let typeLabel: String
    let eyebrow: String
    let title: String
    let bodyHtml: String
    let bodyText: String
    let enactedOn: String?    // "YYYY-MM-DD" or nil
    let revisedOn: String?
    let updatedAt: String     // ISO8601

    var id: String { type }

    enum CodingKeys: String, CodingKey {
        case type, eyebrow, title
        case typeLabel  = "type_label"
        case bodyHtml   = "body_html"
        case bodyText   = "body_text"
        case enactedOn  = "enacted_on"
        case revisedOn  = "revised_on"
        case updatedAt  = "updated_at"
    }
}

enum LegalType: String, CaseIterable {
    case terms, privacy, community
    var path: String { "/api/legal/\(rawValue)/" }
}
```

---

## 3. 取得処理（API クライアント）

```swift
enum LegalAPIError: Error { case notFound, server(Int), decoding }

struct LegalAPI {
    static let baseURL = URL(string: "https://sc-tsusho.jp")!

    /// 個別取得
    static func fetch(_ type: LegalType) async throws -> LegalDocument {
        let url = baseURL.appendingPathComponent(type.path)
        let (data, resp) = try await URLSession.shared.data(from: url)
        guard let http = resp as? HTTPURLResponse else { throw LegalAPIError.server(-1) }
        switch http.statusCode {
        case 200:
            do { return try JSONDecoder().decode(LegalDocument.self, from: data) }
            catch { throw LegalAPIError.decoding }
        case 404: throw LegalAPIError.notFound
        default:  throw LegalAPIError.server(http.statusCode)
        }
    }

    /// 一覧（起動時プリフェッチ用）
    static func fetchAll() async throws -> [LegalDocument] {
        let url = baseURL.appendingPathComponent("/api/legal/")
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode([LegalDocument].self, from: data)
    }
}
```

---

## 4. 表示画面（SwiftUI + WKWebView）

`body_html` はHTMLなので WebView 表示が最も簡単かつWEBと見た目を揃えやすい。アプリ用に最低限のCSSを内側で当てる（フォント・余白・行間）。

```swift
import SwiftUI
import WebKit

struct LegalWebView: UIViewRepresentable {
    let html: String

    func makeUIView(context: Context) -> WKWebView { WKWebView() }

    func updateUIView(_ webView: WKWebView, context: Context) {
        webView.loadHTMLString(Self.wrap(html), baseURL: LegalAPI.baseURL)
    }

    // 相対リンク(/terms/ /contact/ 等)を baseURL で解決させるため baseURL を渡す。
    private static func wrap(_ body: String) -> String {
        """
        <!doctype html><html lang="ja"><head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body { font-family: -apple-system, sans-serif; line-height: 1.8;
                 color: #333; padding: 16px; margin: 0; }
          h2 { font-size: 1.15rem; margin: 1.6em 0 .6em; padding-bottom: .3em;
               border-bottom: 1px solid #eee; }
          h3 { font-size: 1.02rem; margin: 1.2em 0 .4em; }
          p, li { font-size: .95rem; }
          ul, ol { padding-left: 1.3em; }
          li { margin: .3em 0; }
          a { color: #c47; }
        </style></head><body>\(body)</body></html>
        """
    }
}

struct LegalScreen: View {
    let type: LegalType
    @State private var doc: LegalDocument?
    @State private var error: String?

    var body: some View {
        Group {
            if let doc {
                VStack(spacing: 0) {
                    LegalWebView(html: doc.bodyHtml)
                    if let r = doc.revisedOn {
                        Text("最終改定日：\(r)")
                            .font(.caption).foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                            .padding(8)
                    }
                }
                .navigationTitle(doc.title)
            } else if let error {
                Text(error).foregroundColor(.secondary)
            } else {
                ProgressView()
            }
        }
        .task { await load() }
    }

    private func load() async {
        do { doc = try await LegalAPI.fetch(type) }
        catch LegalAPIError.notFound { error = "この文書は現在公開されていません。" }
        catch { error = "読み込みに失敗しました。時間をおいて再度お試しください。" }
    }
}
```

呼び出し例（設定画面などの導線）:
```swift
NavigationLink("利用規約",            destination: LegalScreen(type: .terms))
NavigationLink("プライバシーポリシー", destination: LegalScreen(type: .privacy))
NavigationLink("コミュニティガイドライン", destination: LegalScreen(type: .community))
```

---

## 5. 本文中のリンクの扱い（重要）
`body_html` 内のリンクは **サイト相対パス**（`/terms/`, `/privacy/`, `/community-guidelines/`, `/contact/`）。
- WebView に `baseURL` を渡しているので、タップ時は `https://sc-tsusho.jp/...` に解決される。
- そのまま外部Safari/アプリ内ブラウザで開く実装で問題ない。
- もしアプリ内の対応画面（例: `/contact/`→お問い合わせ画面、`/terms/`→規約画面）へ遷移させたい場合は、`WKNavigationDelegate` の `decidePolicyFor` でパスを判定してネイティブ遷移に差し替える。必須ではない。

---

## 6. キャッシュ・更新検知（推奨）
法的文書は頻繁に変わらないので、毎回フルロードは不要。
1. 起動時または規約画面初回表示時に `GET /api/legal/` を1回叩き、3件まとめてローカル保存（UserDefaults / ファイル）。
2. 各文書の `updated_at` を保存。次回は `updated_at` が変わっていたら本文を更新、同じならキャッシュ表示。
3. オフライン時はキャッシュを表示。

> 注意: 文書が「非公開」に切り替わると一覧から消え、個別取得は404になる。キャッシュ運用時は「一覧に存在しない＝非表示扱い」とすること。

---

## 7. 必須対応チェックリスト（App Store審査・法令対応）
- [ ] 会員登録画面に「利用規約」「プライバシーポリシー」への導線（同意取得の文脈で表示）
- [ ] 設定画面に3文書すべてへの導線
- [ ] 口コミ・画像投稿フローからコミュニティガイドラインへの導線
- [ ] `revised_on` の表示（最終改定日）
- [ ] 404/通信エラー時のフォールバック表示

---

## 8. 動作確認
```bash
curl -s https://sc-tsusho.jp/api/legal/terms/ | python3 -m json.tool
curl -s https://sc-tsusho.jp/api/legal/ | python3 -c "import sys,json;print([d['type'] for d in json.load(sys.stdin)])"
# 期待: ['community', 'privacy', 'terms']
```
すべて 200・最新本文（`revised_on=2026-06-28`）が返ることをアプリ実装前に確認できる。

---

## 注意事項
- アプリ側は文言を一切ハードコードしない（内容ズレ防止が本機構の目的）。
- 文言の修正は管理画面（`/admin/` → 規約・ポリシー）で行えば、WEB・アプリ両方に反映される（アプリは次回取得時）。
- サーバー側の追加作業は不要。この指示書の範囲はすべてアプリ側リポジトリでの実装。
