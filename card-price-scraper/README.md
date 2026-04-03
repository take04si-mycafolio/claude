# カード相場スクレイパー

ポケモンカード・MTG・ワンピースカードの相場を自動取得してCSVエクスポートするWindows向けツールです。

## 使い方

### 1. 起動（Windows）

```
run.bat をダブルクリック
```

初回起動時に依存ライブラリ（`requests`, `beautifulsoup4`, `lxml`）が自動インストールされます。

### 2. 検索

1. ゲーム種別を選択（Pokemon / MTG / OnePiece / 全て）
2. カード名を入力（日本語・英語どちらでも可）
3. 「検索」ボタンをクリック または Enter キー

### 3. CSVエクスポート

- 「CSVエクスポート」ボタン → 保存先を選択
- 「既存ファイルに追記」チェックで複数回の検索結果を1ファイルにまとめられます

## データソース

| ゲーム | データソース | 方式 | 費用 |
|--------|------------|------|------|
| ポケモン | [Pokemon TCG API](https://pokemontcg.io/) | 公式API | 無料 |
| MTG | [Scryfall API](https://scryfall.com/docs/api) | 公式API | 無料 |
| ワンピース | TCGPlayer / Cardmarket | スクレイピング | 無料 |

## ポケモン APIキー（任意）

無料での利用が可能ですが、[api.pokemontcg.io](https://dev.pokemontcg.io/) でAPIキーを取得すると
レート制限が緩和されます（1000リクエスト/日 → 無制限）。

## CSVの列

| 列名 | 説明 |
|------|------|
| fetched_at | 取得日時 |
| game | ゲーム名 |
| name | カード名 |
| set | セット名 |
| number | カード番号 |
| rarity | レアリティ |
| price_market_usd | 相場価格（USD） |
| price_low_usd | 最安値（USD） |
| price_eur | 相場価格（EUR） |
| currency | 通貨 |
| source_url | 参照元URL |

## 動作要件

- Windows 10/11
- Python 3.10 以上
- インターネット接続
