# Forex Signal Tool — 開発ガイド

## 絶対に守るルール

### タイムスタンプは必ず JST（日本時間）で表示する

**DBには UTC naive で保存。表示・出力はすべて JST（+9h）に変換すること。**

ユーザーに見えるすべての日時（トレード履歴のエントリー・エグジット、チャート軸、CSV 等）を
UTC のまま表示することは重大なバグ。9時間ずれた時刻が表示される。

#### 各レイヤーの変換ルール

| レイヤー | 正しい方法 | ファイル |
|---------|-----------|---------|
| Python バックテスター | `_bar_time()` が UTC naive + 9h → JST 文字列 | `app/services/backtest_engine.py` |
| Python v1 バックテスター (backtester.py) | `entry_ts` / `exit_ts` は UTC naive → 出力時に `+timedelta(hours=9)` | `tasks/run_custom_bt.py` |
| Python バックテスト v2 | `_JST_DELTA = timedelta(hours=9)` で変換 | `tasks/run_backtest_v2.py` |
| Python 静的ページ生成 | `utc_str_to_jst(t.entry_at)` | `tasks/generate_static.py` |
| PHP SQL | `CONVERT_TZ(ts, '+00:00', '+09:00')` | `public_html/admin/api.php` |
| Jinja2 テンプレート | `{{ value \| utc_to_jst }}` フィルター | `app/templates/*.html` |

#### 新しいトレード履歴表示を追加するとき必ず確認すること

1. タイムスタンプのソースはどこか（DB の `entry_at` / `exit_at` か、Python が返す文字列か）
2. そのソースはすでに JST 変換済みか、UTC のままか
3. UTC のままなら `+9h` 変換を追加してから表示する

#### よくあるミス

- `pandas.Timestamp` を `.strftime()` だけで出力 → UTC のまま（`+timedelta(hours=9)` を先に加算）
- `datetime.strftime()` を JST 変換なしで出力 → 同上
- `new Date(ts + 'Z')` で ISO 文字列をパース → 'Z' を付けると UTC 扱いになるため JST 文字列には使わない
- Jinja2 で `{{ entry_at }}` を直接表示 → `{{ entry_at | utc_to_jst }}` フィルターを使う

---

## アーキテクチャ概要

- Xserver 共有ホスティング（Apache + PHP + Python）
- DB: MySQL — タイムスタンプは UTC naive で保存
- バックテスト: PHP が `nohup python tasks/run_*.py` を起動、`/tmp/*.json` で状態共有
- 公開ページ: `tasks/generate_static.py` が Jinja2 テンプレートから静的 HTML を生成
- カスタム複合指標: `custom_v2_indicators` テーブル、`strategy_config` JSON カラム（v2.0 形式）

## カスタム複合指標 strategy_config v2.0 形式

```json
{
  "version": "2.0",
  "buy":  { "strategy_version": "1.0", "direction": "BUY",  "entry_conditions": {...} },
  "sell": { "strategy_version": "1.0", "direction": "SELL", "entry_conditions": {...} }
}
```

BUY と SELL の条件は独立して評価・保存・表示する（合算しない）。
