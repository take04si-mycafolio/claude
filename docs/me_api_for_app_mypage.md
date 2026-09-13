# `GET /api/me/` アプリ向け仕様（マイページ プロフィールカード表示用）

最終更新: 2026-06-15 / 対象: 拡張後の `UserSerializer`（本番反映済み）

> このドキュメントは **アプリ実装者向けの参照資料** です。Django 側の API は本番反映済み。
> アプリ側コード（React Native / Expo, `src/types/api.ts` 等）はこのサーバーに無いため、
> ここでは型定義と「マイページのプロフィールカードで各フィールドをどう使うか」だけを定義します。

---

## 1. エンドポイント

- メソッド/パス: `GET /api/me/`
- 認証: 必須（JWT / `IsAuthenticated`）
- 用途: ログイン中ユーザー自身の表示用情報。**read-only**（更新APIは未実装。編集画面はまだ作らない）。

## 2. レスポンスのフィールドと型（キー順）

| フィールド | 型 | nullable | 説明 |
|---|---|---|---|
| `id` | number | no | ユーザーID |
| `username` | string | no | ログインID（登録時は email と同値） |
| `email` | string | no | メールアドレス |
| `display_name` | string | no | 表示名（`nickname` あれば nickname、無ければ email） |
| `nickname` | string | no | ニックネーム（未設定時は空文字 `""`） |
| `bio` | string | no | 自己紹介（未設定時は空文字 `""`） |
| `gender` | string | no | 性別コード `female`/`male`/`other`/`""` |
| `age_range` | string | no | 年代コード `10s`/`20s`/.../`60s+`/`""` |
| `skin_type` | string | no | 肌質コード `dry`/`oily`/`combination`/`sensitive`/`normal`/`""` |
| `review_level` | number | no | **会員ランク**（1〜10）。「レビューランク Lv.X」と表示 |
| `category_badge` | string \| null | yes | 「○○マスター」バッジ。該当なしは `null` |
| `review_count` | number | no | 承認済み口コミ数 |
| `helpful_count` | number | no | 獲得した「参考になった」数 |
| `avatar_url` | string \| null | yes | プロフィール画像の絶対URL。未設定は `null` |
| `email_verified` | boolean | no | メール認証済みか |
| `created_at` | string (ISO8601) | no | 登録日時 |

> ⚠️ `points` / `reward_points` / `membership_points` / `rank` / `membership_rank` は
> **存在しない**（このサイトにポイント残高・会員等級制度は無い）。会員ランクは `review_level` を使う。

## 3. TypeScript 型（`src/types/api.ts` の `Me` に反映する想定）

```ts
export interface Me {
  id: number;
  username: string;
  email: string;
  display_name: string;
  nickname: string;
  bio: string;
  gender: "" | "female" | "male" | "other";
  age_range: "" | "10s" | "20s" | "30s" | "40s" | "50s" | "60s+";
  skin_type: "" | "dry" | "oily" | "combination" | "sensitive" | "normal";
  review_level: number;          // 会員ランク（1..10）
  category_badge: string | null; // 例: "美顔器マスター"
  review_count: number;
  helpful_count: number;
  avatar_url: string | null;
  email_verified: boolean;
  created_at: string;            // ISO8601
}
```

不足分のみ追加（既存の `id` 等は維持・リネームしない）：
`display_name` / `username` / `created_at` / `bio` / `gender`

## 4. プロフィールカードの表示マッピング

| カード上の表示 | 使うフィールド（優先順） | 備考 |
|---|---|---|
| 名前 | `display_name` → `nickname` → `email` | サーバ側 `display_name` がすでに `nickname or email` |
| メール | `email` | そのまま |
| 会員ランク | `review_level` | 「レビューランク Lv.{review_level}」。バー幅 `review_level/10*100%`（PC版と同じ） |
| バッジ | `category_badge` | `null` のとき非表示 |
| 口コミ数 | `review_count` | 数値表示 |
| 参考になった | `helpful_count` | 数値表示 |
| 登録日 | `created_at` | 日付フォーマットして「登録日: YYYY/MM/DD」等 |
| 自己紹介 | `bio` | 空文字 `""` のとき非表示 |
| 性別 | `gender` | 空文字 `""` のとき非表示。コード→表示名変換（female=女性 等） |
| 画像 | `avatar_url` | `null` のとき従来のプレースホルダーのまま |

### 表示優先順位（要件どおり）
- 名前: `display_name` → `nickname` → `email`
- ランク: `review_level`
- バッジ: `category_badge`
- 登録日: `created_at`
- 自己紹介: `bio`

### 擬似コード（言語非依存）
```text
name      = me.display_name || me.nickname || me.email
rankLabel = "レビューランク Lv." + me.review_level
badge     = me.category_badge        // null なら非表示
joined    = formatDate(me.created_at) // "登録日: YYYY/MM/DD"
bioText   = me.bio                    // "" なら非表示
genderTxt = me.gender ? label(me.gender) : null  // "" なら非表示
avatar    = me.avatar_url ?? <従来のプレースホルダー>
```

## 5. 実装者向け注意（やってはいけないこと）

- `points` / `rank` / `membership_rank` を参照しない（存在しない）。会員ランクは `review_level`。
- プロフィール**編集画面は作らない**（更新API `PATCH /api/me/` は未実装。今回は表示のみ）。
- `email` / password / 画像アップロードの編集はしない。
- 空文字 `""` と `null` の両方を「未設定 → 非表示」として防御的に扱う
  （`nickname`/`bio`/`gender`/`age_range`/`skin_type` は未設定時 `""`、`avatar_url`/`category_badge` は `null`）。
- トークンや `email` 等を **ログ・解析・画面の意図しない場所に出さない**。
- 既存の「ミッション状況・自分の口コミ・ログアウト」表示には手を入れない（プロフィールカードのみ更新）。

## 6. 既存互換性

`id` / `email` / `nickname` / `age_range` / `skin_type` / `review_level` / `category_badge` /
`review_count` / `helpful_count` / `avatar_url` / `email_verified` は **従来どおり維持**。
今回の追加（`display_name` / `username` / `created_at` / `bio` / `gender`）は **追加のみ・後方互換**。
PC版Webはこのシリアライザを経由せず（テンプレート描画）影響を受けない。
