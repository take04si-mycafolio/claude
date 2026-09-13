# `GET /api/missions/` アプリ向け仕様（ミッションカード表示用）

最終更新: 2026-06-15 / 対象: 拡張後の `MissionSerializer`（本番反映済み）

> このドキュメントは **アプリ実装者向けの参照資料** です。Django 側の API は本番反映済み。
> アプリ側コード（React Native / Expo）はこのサーバーには無いため、ここでは
> レスポンス仕様と「ミッションカードでどのフィールドをどう使うか」だけを定義します。

---

## 1. エンドポイント

- メソッド/パス: `GET /api/missions/`
- 認証: 必須（JWT / `IsAuthenticated`）
- 内容: **公開中(`is_active=True`)の全ミッション一覧**を、ログインユーザー視点の進捗込みで返す。
  マイページのミッション状況も同じデータ（`mission_summary` は同じ overview の先頭数件）なので、
  **マイページと一覧画面で同じ表示ロジックを共有できる**。

## 2. レスポンス例（個人情報・コードは除外して掲載）

```json
[
  {
    "id": 4,
    "title": "リニューアルオープン記念！先着５００Pあげちゃうキャンペーン！",
    "description": "当サイトのリニューアルを記念したキャンペーンになります。",
    "reward_label": "amazonギフト券５００P",
    "status": "in_progress",
    "condition_text": "メールアドレスを承認しよう／プロフィールを完成させよう／あなたの体験を投稿しよう／写真付きで口コミを投稿しよう",
    "current": 2,
    "target": 5,
    "progress": 50,
    "is_completed": false,
    "not_started": false,
    "ended": false,
    "starts_at": null,
    "ends_at": null,
    "steps": [
      { "label": "メールアドレスを承認しよう", "current": 1, "target": 1, "is_done": true,  "percent": 100 },
      { "label": "プロフィールを完成させよう", "current": 1, "target": 1, "is_done": true,  "percent": 100 },
      { "label": "あなたの体験を投稿しよう",   "current": 0, "target": 2, "is_done": false, "percent": 0 },
      { "label": "写真付きで口コミを投稿しよう", "current": 0, "target": 1, "is_done": false, "percent": 0 }
    ]
  }
]
```

> 上記以外に `reward_status` / `reward_code` / `waiting_approval` / `code_pending` /
> `missed` / `limit` / `remaining` / `sold_out` / `is_eligible` 等も返るが、カード基本
> 表示では未使用でよい。
> `reward_code` は本人の獲得コードなので **ログ・画面の不用意な箇所に出さないこと**。
> 2026-07-30 から特典は運営承認制になり `reward_status` に `"waiting"`(承認待ち) が
> 追加された。表示対応は `docs/approval_flow_app_instructions.md` を参照。

## 3. ミッションカードのフィールド対応表

| カード上の表示 | 優先して使うフィールド | フォールバック | 備考 |
|---|---|---|---|
| 状態 | `status` | `is_completed` / `not_started` / `ended` から判定 | 値は下表参照 |
| 進捗（数値） | `current` / `target` | `progress` | `target===0` のときは数値非表示 |
| 進捗バー（％） | `current/target*100` | `progress` | 0除算ガード必須 |
| 達成条件 | `condition_text` | `steps[].label` を「／」結合 | 空文字なら非表示 |
| 報酬 | `reward_label` | （なし） | **`reward_points` は存在しない／使わない** |
| 期間・期限 | `ends_at`（期限） / `starts_at`（開始） | （なし） | `null` のとき「無期限/常設」 |
| タイトル/説明 | `title` / `description` | — | — |

### `status` の値と表示

| 値 | 意味 | 表示例 |
|---|---|---|
| `not_started` | 開始前 | 「開始前」 |
| `ended` | 期間終了 | 「終了」 |
| `completed` | 達成済み | 「達成済み」 |
| `in_progress` | 進行中 | 「挑戦中」 |

## 4. 表示優先順位（防御的フォールバック・擬似コード）

実装言語に依存しないロジックのみ示す（アプリ側で実装）。

```text
state =
  status ?? (
    not_started ? "not_started" :
    ended       ? "ended" :
    is_completed? "completed" :
                  "in_progress"
  )

cur = current ?? sum(steps[].current)   // steps も無ければ undefined
tgt = target  ?? sum(steps[].target)
percent =
  (tgt && tgt > 0) ? round(cur / tgt * 100)
                   : (progress ?? 0)     // 0除算を必ず回避

conditionText = condition_text || steps.map(s => s.label).join("／")
reward        = reward_label                 // reward_points は使わない
deadline      = ends_at ?? null              // null は「無期限」表示
```

## 5. やってはいけないこと（実装者向け注意）

- `reward_points` を参照しない（このサイトの報酬はクーポン/ギフトコード方式で、ポイント残高フィールドは存在しない）。
- `target` が 0 / 欠落のときに進捗率計算で 0 除算しない。
- `reward_code` 等の本人特典コードを **ログ・解析・画面の意図しない場所に出さない**。
- API 仕様（フィールド名・型）は変更しない。アプリ側は read のみ。

## 6. 既存フィールド互換性

`id` / `title` / `description` / `reward_label` / `progress` / `steps` /
`is_completed` / `starts_at` / `ends_at` は **従来どおり維持**。今回の追加
(`status` / `condition_text` / `current` / `target`) は **追加のみ・後方互換**。
PC版Webはこのシリアライザを経由せず（テンプレート描画）影響を受けない。
