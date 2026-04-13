<?php
/**
 * Phase 1 マルチ条件バックテスト (v2)
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>マルチ条件バックテスト v2 | FX Trend 管理</title>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
/* ===== reset / base ===== */
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}

/* ===== header / nav ===== */
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}

/* ===== layout ===== */
main{max-width:1040px;margin:0 auto;padding:28px 20px}
h2{font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:6px}
.subtitle{font-size:13px;color:#64748b;margin-bottom:24px}

/* ===== form card ===== */
.form-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:20px}
.form-card h3{font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #334155}
.form-row{display:grid;gap:14px;margin-bottom:14px}
.form-row.col2{grid-template-columns:1fr 1fr}
.form-row.col3{grid-template-columns:1fr 1fr 1fr}
.form-row.col4{grid-template-columns:1fr 1fr 1fr 1fr}
.form-group label{display:block;font-size:11px;color:#64748b;margin-bottom:5px;font-weight:500;text-transform:uppercase;letter-spacing:.4px}
.form-group select,
.form-group input[type=number],
.form-group input[type=text]{
  width:100%;background:#0f172a;border:1px solid #475569;border-radius:7px;
  color:#e2e8f0;padding:8px 10px;font-size:13px;outline:none;transition:border-color .15s
}
.form-group select:focus,
.form-group input:focus{border-color:#3b82f6}
.form-hint{font-size:11px;color:#475569;margin-top:4px}

/* ===== condition builder ===== */
.cond-list{display:flex;flex-direction:column;gap:10px;margin-bottom:12px}
.cond-row{background:#0f172a;border:1px solid #334155;border-radius:9px;padding:12px 14px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:10px;align-items:end}
.cond-row .cond-params{display:flex;gap:6px}
.cond-row .cond-params input{width:70px}
.btn-add-cond{background:none;border:1px dashed #475569;color:#64748b;border-radius:7px;padding:8px 16px;font-size:12px;cursor:pointer;width:100%;transition:all .15s}
.btn-add-cond:hover{border-color:#3b82f6;color:#60a5fa}
.btn-del-cond{background:none;border:1px solid #475569;color:#64748b;border-radius:6px;padding:6px 10px;font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap}
.btn-del-cond:hover{border-color:#ef4444;color:#ef4444}
.logic-toggle{display:flex;gap:6px;margin-bottom:12px}
.logic-btn{background:#0f172a;border:1px solid #475569;color:#94a3b8;border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s}
.logic-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}

/* ===== SL/TP type panels ===== */
.type-panels{margin-top:12px}
.type-panel{display:none}
.type-panel.active{display:grid}

/* ===== trailing toggle ===== */
.toggle-row{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.toggle-label{font-size:13px;color:#94a3b8}
.toggle-sw{position:relative;width:38px;height:22px;cursor:pointer}
.toggle-sw input{opacity:0;width:0;height:0;position:absolute}
.toggle-track{position:absolute;inset:0;background:#334155;border-radius:11px;transition:background .2s}
.toggle-sw input:checked + .toggle-track{background:#3b82f6}
.toggle-thumb{position:absolute;top:3px;left:3px;width:16px;height:16px;background:#fff;border-radius:50%;transition:transform .2s}
.toggle-sw input:checked ~ .toggle-thumb{transform:translateX(16px)}
.trailing-fields{display:none}
.trailing-fields.open{display:grid}

/* ===== filter blocks ===== */
.filter-block{margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #1e293b}
.filter-block:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.filter-block-title{font-size:12px;font-weight:600;color:#64748b;margin-bottom:10px;text-transform:uppercase;letter-spacing:.4px}
.weekday-btns{display:flex;gap:6px;flex-wrap:wrap}
.wd-btn{background:#0f172a;border:1px solid #334155;color:#64748b;border-radius:6px;padding:5px 11px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;user-select:none}
.wd-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}

/* ===== pair checkboxes ===== */
.pair-checks{display:flex;flex-direction:column;gap:5px}
.pair-ck{display:flex;align-items:center;gap:6px;font-size:12px;color:#94a3b8;cursor:pointer;padding:5px 8px;background:#0f172a;border:1px solid #334155;border-radius:6px;transition:all .15s;user-select:none}
.pair-ck:has(input:checked){background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.pair-ck input{accent-color:#3b82f6}

/* ===== multi-pair ===== */
.pair-tabs{display:flex;gap:6px;margin-bottom:14px}
.pair-tab{background:#0f172a;border:1px solid #334155;color:#64748b;border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s}
.pair-tab.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.compare-tbl-wrap{overflow-x:auto;margin-bottom:4px}
.compare-tbl{width:100%;border-collapse:collapse;font-size:12px}
.compare-tbl th{background:#0f172a;color:#64748b;padding:9px 14px;border-bottom:2px solid #334155;white-space:nowrap;text-align:center}
.compare-tbl th:first-child{text-align:left}
.compare-tbl td{padding:8px 14px;border-bottom:1px solid #1e293b;color:#cbd5e1;text-align:center}
.compare-tbl td:first-child{color:#64748b;font-size:11px;font-weight:600;text-align:left;text-transform:uppercase;letter-spacing:.3px}
.compare-tbl tr:hover td{background:rgba(255,255,255,.02)}

/* ===== action buttons ===== */
.actions{display:flex;gap:12px;align-items:center;margin-top:8px}
.btn-run{background:#3b82f6;color:#fff;border:none;border-radius:9px;padding:12px 32px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s}
.btn-run:hover{background:#2563eb}
.btn-run:disabled{opacity:.5;cursor:not-allowed}

/* ===== overlay ===== */
.overlay{position:fixed;inset:0;background:rgba(15,23,42,.88);z-index:200;display:none;flex-direction:column;align-items:center;justify-content:center;gap:16px}
.overlay.active{display:flex}
.overlay-msg{color:#e2e8f0;font-size:16px;font-weight:600}
.overlay-sub{color:#64748b;font-size:13px}
@keyframes spin{to{transform:rotate(360deg)}}
.big-spin{width:48px;height:48px;border:4px solid #1e3a5f;border-top-color:#3b82f6;border-radius:50%;animation:spin .8s linear infinite}

/* ===== error banner ===== */
.err-banner{background:#7f1d1d;border:1px solid #ef4444;border-radius:9px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#fca5a5;display:none;white-space:pre-wrap}

/* ===== results ===== */
.result-wrap{display:none}
.result-wrap.show{display:block}
.metrics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.metric-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 14px;text-align:center}
.metric-card .mc-label{font-size:11px;color:#64748b;margin-bottom:6px}
.metric-card .mc-val{font-size:22px;font-weight:700;color:#f1f5f9}
.metric-card .mc-val.green{color:#4ade80}
.metric-card .mc-val.red{color:#f87171}
.metric-card .mc-val.yellow{color:#fbbf24}
.metrics-grid2{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px}
.metric-sm{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 10px;text-align:center}
.metric-sm .ms-label{font-size:10px;color:#64748b;margin-bottom:4px}
.metric-sm .ms-val{font-size:16px;font-weight:700;color:#f1f5f9}

/* ===== chart ===== */
.chart-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px}
.chart-card h3{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px}
#tv-chart{width:100%;height:420px}

/* ===== trade table ===== */
.table-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px}
.table-card h3{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px}
.tbl-wrap{overflow-x:auto}
.trade-tbl{width:100%;border-collapse:collapse;font-size:12px;min-width:680px}
.trade-tbl th{background:#0f172a;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155;white-space:nowrap}
.trade-tbl td{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1;white-space:nowrap}
.trade-tbl tr:last-child td{border-bottom:none}
.trade-tbl tr:hover td{background:rgba(255,255,255,.03)}
.bdg{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}
.bdg-buy{background:#1e3a5f;color:#60a5fa}
.bdg-sell{background:#4c1d95;color:#c4b5fd}
.bdg-tp{background:#14532d;color:#4ade80}
.bdg-sl{background:#7f1d1d;color:#f87171}
.bdg-tsl{background:#78350f;color:#fcd34d}
.bdg-eod{background:#1e293b;color:#64748b;border:1px solid #334155}
</style>
</head>
<body>

<div class="overlay" id="overlay">
  <div class="big-spin"></div>
  <div class="overlay-msg" id="overlay-msg">バックテスト実行中...</div>
  <div class="overlay-sub" id="overlay-sub">しばらくお待ちください</div>
</div>

<header>
  <h1>FX Trend 管理パネル</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php" class="active">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>


<main>
  <h2>マルチ条件バックテスト</h2>
  <p class="subtitle">複数テクニカル条件・SL/TP設定を組み合わせてバックテストを実行します（Phase 1）</p>

  <div class="err-banner" id="err-banner"></div>

  <!-- 10b: シミュレーション設定フォーム -->
  <div class="form-card" id="section-sim">
    <h3>基本設定</h3>
    <div class="form-row col3">
      <div class="form-group">
        <label>通貨ペア（複数選択可）</label>
        <div class="pair-checks">
          <label class="pair-ck"><input type="checkbox" class="pair-cb" value="USDJPY" checked> USD/JPY（ドル円）</label>
          <label class="pair-ck"><input type="checkbox" class="pair-cb" value="GBPJPY"> GBP/JPY（ポンド円）</label>
          <label class="pair-ck"><input type="checkbox" class="pair-cb" value="EURJPY"> EUR/JPY（ユーロ円）</label>
        </div>
      </div>
      <div class="form-group">
        <label>タイムフレーム</label>
        <select id="timeframe">
          <option value="5min">5分足</option>
          <option value="15min">15分足</option>
          <option value="1hr" selected>1時間足</option>
          <option value="4hr">4時間足</option>
          <option value="daily">日足</option>
        </select>
      </div>
      <div class="form-group">
        <label>取得バー数</label>
        <input type="number" id="limit" value="500" min="100" max="5000" step="100">
        <div class="form-hint">多いほど精度↑・実行時間↑</div>
      </div>
    </div>
    <div class="form-row col4">
      <div class="form-group">
        <label>初期資金 (円)</label>
        <input type="number" id="initial_capital" value="1000000" min="10000" step="10000">
      </div>
      <div class="form-group">
        <label>pip 価値 (円/pip)</label>
        <input type="number" id="pip_value" value="100" min="1" step="10">
        <div class="form-hint">例: 1万通貨=100円/pip</div>
      </div>
      <div class="form-group">
        <label>エントリー方向</label>
        <select id="direction">
          <option value="BUY">BUY（買いのみ）</option>
          <option value="SELL">SELL（売りのみ）</option>
          <option value="BOTH">BOTH（両方）</option>
        </select>
      </div>
      <div class="form-group">
        <label>最大保有バー数</label>
        <input type="number" id="max_bars_to_exit" value="200" min="10" max="1000" step="10">
        <div class="form-hint">未決済時の強制クローズ</div>
      </div>
    </div>
  </div>

  <!-- 10c: エントリー条件ビルダー -->
  <div class="form-card" id="section-conditions">
    <h3>エントリー条件</h3>
    <div class="logic-toggle">
      <span style="font-size:12px;color:#64748b;margin-right:4px">条件の結合:</span>
      <button class="logic-btn active" id="logic-and" onclick="setLogic('AND')">AND（全条件一致）</button>
      <button class="logic-btn"        id="logic-or"  onclick="setLogic('OR')">OR（いずれか一致）</button>
    </div>
    <div class="cond-list" id="cond-list"></div>
    <button class="btn-add-cond" onclick="addCondition()">＋ 条件を追加</button>
  </div>

  <!-- フィルター設定 -->
  <div class="form-card" id="section-filters">
    <h3>フィルター設定（任意）</h3>

    <!-- 時間帯 -->
    <div class="filter-block">
      <div class="filter-block-title">時間帯（JST）</div>
      <div class="form-row col2" style="margin-bottom:10px">
        <div class="form-group">
          <label>セッション プリセット</label>
          <select id="f-session" onchange="onSessionPreset()">
            <option value="">-- フィルターなし --</option>
            <option value="tokyo">東京セッション (07:00〜16:00 JST)</option>
            <option value="london">ロンドンセッション (17:00〜02:00 JST)</option>
            <option value="ny">ニューヨークセッション (22:00〜07:00 JST)</option>
            <option value="custom">カスタム</option>
          </select>
        </div>
      </div>
      <div class="form-row col2" id="f-custom-time" style="display:none">
        <div class="form-group">
          <label>開始時刻 (JST・時)</label>
          <input type="number" id="f-start-hour" value="9" min="0" max="23" step="1">
        </div>
        <div class="form-group">
          <label>終了時刻 (JST・時)</label>
          <input type="number" id="f-end-hour" value="17" min="0" max="23" step="1">
          <div class="form-hint">終了 &lt; 開始 の場合は日をまたぐ（例: 22〜7）</div>
        </div>
      </div>
    </div>

    <!-- 曜日 -->
    <div class="filter-block">
      <div class="filter-block-title">曜日（全選択 = フィルターなし）</div>
      <div class="weekday-btns" id="weekday-btns">
        <button class="wd-btn active" data-wd="0" onclick="toggleWd(this)">月</button>
        <button class="wd-btn active" data-wd="1" onclick="toggleWd(this)">火</button>
        <button class="wd-btn active" data-wd="2" onclick="toggleWd(this)">水</button>
        <button class="wd-btn active" data-wd="3" onclick="toggleWd(this)">木</button>
        <button class="wd-btn active" data-wd="4" onclick="toggleWd(this)">金</button>
        <button class="wd-btn" data-wd="5" onclick="toggleWd(this)">土</button>
        <button class="wd-btn" data-wd="6" onclick="toggleWd(this)">日</button>
      </div>
      <div class="form-hint" style="margin-top:8px">クリックで ON/OFF 切り替え。全ON は曜日フィルターなし。</div>
    </div>

    <!-- ATR ボラティリティ -->
    <div class="filter-block">
      <div class="filter-block-title">ボラティリティ（ATR フィルター）</div>
      <div class="form-row col3">
        <div class="form-group">
          <label>ATR 期間</label>
          <input type="number" id="f-atr-period" value="14" min="1" step="1">
        </div>
        <div class="form-group">
          <label>最小 pips</label>
          <input type="number" id="f-atr-min" value="0" min="0" step="1">
          <div class="form-hint">0 = 無効</div>
        </div>
        <div class="form-group">
          <label>最大 pips</label>
          <input type="number" id="f-atr-max" value="0" min="0" step="1">
          <div class="form-hint">0 = 無制限</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 10d: SL / TP / トレーリング -->
  <div class="form-card" id="section-risk">
    <h3>リスク管理（SL / TP / トレーリング）</h3>

    <!-- SL 設定 -->
    <div style="margin-bottom:20px">
      <div style="font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:10px">◆ ストップロス (SL)</div>
      <div class="form-row col3" style="margin-bottom:10px">
        <div class="form-group">
          <label>SL タイプ</label>
          <select id="sl_type" onchange="onSlTypeChange()">
            <option value="fixed">固定 pips</option>
            <option value="recentHighLow">直近高値/安値</option>
            <option value="atr">ATR 倍数</option>
          </select>
        </div>
      </div>
      <!-- fixed -->
      <div class="form-row col2 type-panel active" id="sl-fixed">
        <div class="form-group">
          <label>SL pips</label>
          <input type="number" id="sl_pips" value="20" min="1" step="1">
        </div>
      </div>
      <!-- recentHighLow -->
      <div class="form-row col3 type-panel" id="sl-recentHighLow">
        <div class="form-group">
          <label>ルックバック本数</label>
          <input type="number" id="sl_lookback" value="10" min="1" step="1">
        </div>
        <div class="form-group">
          <label>バッファ pips</label>
          <input type="number" id="sl_buffer" value="3" min="0" step="0.5">
        </div>
      </div>
      <!-- atr -->
      <div class="form-row col2 type-panel" id="sl-atr">
        <div class="form-group">
          <label>ATR 期間</label>
          <input type="number" id="sl_atr_period" value="14" min="1" step="1">
        </div>
        <div class="form-group">
          <label>ATR 倍数</label>
          <input type="number" id="sl_atr_mult" value="1.5" min="0.1" step="0.1">
        </div>
      </div>
    </div>

    <!-- TP 設定 -->
    <div style="margin-bottom:20px">
      <div style="font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:10px">◆ テイクプロフィット (TP)</div>
      <div class="form-row col3" style="margin-bottom:10px">
        <div class="form-group">
          <label>TP タイプ</label>
          <select id="tp_type" onchange="onTpTypeChange()">
            <option value="rr">RR 比率（SL × 倍率）</option>
            <option value="fixed">固定 pips</option>
            <option value="atr">ATR 倍数</option>
          </select>
        </div>
      </div>
      <!-- rr -->
      <div class="form-row col2 type-panel active" id="tp-rr">
        <div class="form-group">
          <label>RR 比率</label>
          <select id="tp_rr_ratio">
            <option value="1.0">1 : 1.0</option>
            <option value="1.5" selected>1 : 1.5</option>
            <option value="2.0">1 : 2.0</option>
            <option value="2.5">1 : 2.5</option>
            <option value="3.0">1 : 3.0</option>
          </select>
        </div>
      </div>
      <!-- fixed -->
      <div class="form-row col2 type-panel" id="tp-fixed">
        <div class="form-group">
          <label>TP pips</label>
          <input type="number" id="tp_pips" value="40" min="1" step="1">
        </div>
      </div>
      <!-- atr -->
      <div class="form-row col2 type-panel" id="tp-atr">
        <div class="form-group">
          <label>ATR 期間</label>
          <input type="number" id="tp_atr_period" value="14" min="1" step="1">
        </div>
        <div class="form-group">
          <label>ATR 倍数</label>
          <input type="number" id="tp_atr_mult" value="3.0" min="0.1" step="0.1">
        </div>
      </div>
    </div>

    <!-- トレーリングストップ -->
    <div>
      <div class="toggle-row">
        <span class="toggle-label" style="font-size:12px;font-weight:600;color:#94a3b8">◆ トレーリングストップ</span>
        <label class="toggle-sw">
          <input type="checkbox" id="trailing_enabled" onchange="onTrailingChange()">
          <div class="toggle-track"></div>
          <div class="toggle-thumb"></div>
        </label>
        <span id="trailing-label" style="font-size:12px;color:#64748b">OFF</span>
      </div>
      <div class="form-row col2 trailing-fields" id="trailing-fields">
        <div class="form-group">
          <label>トレール幅 (pips)</label>
          <input type="number" id="trail_pips" value="10" min="1" step="1">
        </div>
      </div>
    </div>
  </div>

  <!-- 実行ボタン -->
  <div class="actions" id="section-actions" style="display:none">
    <button class="btn-run" id="btn-run" onclick="runBacktest()">バックテスト実行</button>
    <span id="run-status" style="font-size:13px;color:#64748b"></span>
  </div>

  <!-- 10f: 結果 / 10g: チャート -->
  <div class="result-wrap" id="result-wrap">
    <!-- 10f metrics -->
    <div id="section-metrics"></div>
    <!-- 10g chart -->
    <div id="section-chart"></div>
    <!-- 10f trade table -->
    <div id="section-trades"></div>
  </div>
</main>

<script>
/* =====================================================================
   SL / TP / トレーリング パネル切り替え
   ===================================================================== */
function onSlTypeChange() {
  const t = document.getElementById('sl_type').value;
  ['fixed','recentHighLow','atr'].forEach(k => {
    const el = document.getElementById('sl-' + k);
    if (el) el.classList.toggle('active', k === t);
  });
}
function onTpTypeChange() {
  const t = document.getElementById('tp_type').value;
  ['rr','fixed','atr'].forEach(k => {
    const el = document.getElementById('tp-' + k);
    if (el) el.classList.toggle('active', k === t);
  });
}
function onTrailingChange() {
  const on = document.getElementById('trailing_enabled').checked;
  document.getElementById('trailing-label').textContent = on ? 'ON' : 'OFF';
  document.getElementById('trailing-fields').classList.toggle('open', on);
}

/* ---------- SL 設定オブジェクト構築 ---------- */
function buildSlConfig() {
  const t = document.getElementById('sl_type').value;
  if (t === 'fixed')
    return { type:'fixed', pips: parseFloat(document.getElementById('sl_pips').value),
             lookback_bars:null, buffer_pips:null, atr_period:null, atr_multiplier:null };
  if (t === 'recentHighLow')
    return { type:'recentHighLow', pips:null,
             lookback_bars: parseInt(document.getElementById('sl_lookback').value),
             buffer_pips:   parseFloat(document.getElementById('sl_buffer').value),
             atr_period:null, atr_multiplier:null };
  // atr
  return { type:'atr', pips:null, lookback_bars:null, buffer_pips:null,
           atr_period:      parseInt(document.getElementById('sl_atr_period').value),
           atr_multiplier:  parseFloat(document.getElementById('sl_atr_mult').value) };
}

/* ---------- TP 設定オブジェクト構築 ---------- */
function buildTpConfig() {
  const t = document.getElementById('tp_type').value;
  if (t === 'rr')
    return { type:'rr', pips:null,
             rr_ratio:   parseFloat(document.getElementById('tp_rr_ratio').value),
             atr_period:null, atr_multiplier:null };
  if (t === 'fixed')
    return { type:'fixed', pips: parseFloat(document.getElementById('tp_pips').value),
             rr_ratio:null, atr_period:null, atr_multiplier:null };
  // atr
  return { type:'atr', pips:null, rr_ratio:null,
           atr_period:     parseInt(document.getElementById('tp_atr_period').value),
           atr_multiplier: parseFloat(document.getElementById('tp_atr_mult').value) };
}

/* ---------- トレーリング設定オブジェクト構築 ---------- */
function buildTrailingConfig() {
  const enabled = document.getElementById('trailing_enabled').checked;
  return {
    enabled,
    type:       enabled ? 'fixedTrailing' : null,
    trail_pips: enabled ? parseFloat(document.getElementById('trail_pips').value) : null,
  };
}

/* =====================================================================
   フィルター UI
   ===================================================================== */
const SESSION_PRESETS = {
  tokyo:  { start: 7,  end: 16 },
  london: { start: 17, end: 2  },
  ny:     { start: 22, end: 7  },
};

function onSessionPreset() {
  const val = document.getElementById('f-session').value;
  const customEl = document.getElementById('f-custom-time');
  customEl.style.display = val === 'custom' ? 'grid' : 'none';
  if (val && val !== 'custom') {
    const p = SESSION_PRESETS[val];
    document.getElementById('f-start-hour').value = p.start;
    document.getElementById('f-end-hour').value   = p.end;
  }
}

function toggleWd(btn) {
  btn.classList.toggle('active');
}

/* フィルター ConditionGroup 構築（有効フィルターがなければ null） */
function buildFilters() {
  const conds = [];

  // 時間帯フィルター
  const session = document.getElementById('f-session').value;
  if (session) {
    const start = parseInt(document.getElementById('f-start-hour').value, 10);
    const end   = parseInt(document.getElementById('f-end-hour').value, 10);
    conds.push({
      id: 'f-time', indicator: 'TIME_RANGE',
      params: { start_hour: start, end_hour: end },
      comparison: 'filter_pass', value: null,
      compare_to_indicator: null, compare_to_params: null,
    });
  }

  // 曜日フィルター（全ON = フィルターなし）
  const activeDays = [...document.querySelectorAll('#weekday-btns .wd-btn.active')]
                       .map(b => parseInt(b.dataset.wd, 10));
  if (activeDays.length < 7) {
    if (activeDays.length === 0) {
      // 全OFFは設定ミス → 全曜日許可に戻す（フィルターなし）
    } else {
      conds.push({
        id: 'f-weekday', indicator: 'WEEKDAY',
        params: { days: activeDays },
        comparison: 'filter_pass', value: null,
        compare_to_indicator: null, compare_to_params: null,
      });
    }
  }

  // ATR ボラティリティフィルター
  const atrMin = parseFloat(document.getElementById('f-atr-min').value) || 0;
  const atrMax = parseFloat(document.getElementById('f-atr-max').value) || 0;
  if (atrMin > 0 || atrMax > 0) {
    conds.push({
      id: 'f-atr', indicator: 'ATR_THRESHOLD',
      params: {
        period:   parseInt(document.getElementById('f-atr-period').value, 10),
        min_pips: atrMin,
        max_pips: atrMax > 0 ? atrMax : null,
      },
      comparison: 'filter_pass', value: null,
      compare_to_indicator: null, compare_to_params: null,
    });
  }

  return conds.length ? { logic: 'AND', conditions: conds } : null;
}

/* =====================================================================
   指標定義マップ
   ===================================================================== */
const IND = {
  RSI:         { label:'RSI',          params:[{n:'period',   l:'期間',     d:14}] },
  EMA:         { label:'EMA',          params:[{n:'period',   l:'期間',     d:21}] },
  SMA:         { label:'SMA',          params:[{n:'period',   l:'期間',     d:20}] },
  MACD_HIST:   { label:'MACD ヒスト',  params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_LINE:   { label:'MACD ライン',  params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_SIGNAL: { label:'MACD シグナル',params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  STOCH_K:     { label:'Stoch %K',     params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  STOCH_D:     { label:'Stoch %D',     params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  CCI:         { label:'CCI',          params:[{n:'period',   l:'期間',     d:20}] },
  WILLIAMS_R:  { label:'Williams %R',  params:[{n:'period',   l:'期間',     d:14}] },
  ATR:         { label:'ATR',          params:[{n:'period',   l:'期間',     d:14}] },
  BB_UPPER:    { label:'BB 上バンド',  params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_LOWER:    { label:'BB 下バンド',  params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_MID:      { label:'BB 中央',      params:[{n:'period',   l:'期間',     d:20}] },
  CLOSE:       { label:'終値 (CLOSE)', params:[] },
  HIGH:        { label:'高値 (HIGH)',  params:[] },
  LOW:         { label:'安値 (LOW)',   params:[] },
};

const COMPARISONS = [
  { v:'less_than',             l:'< (小さい)' },
  { v:'less_than_or_equal',    l:'≤ (以下)' },
  { v:'greater_than',          l:'> (大きい)' },
  { v:'greater_than_or_equal', l:'≥ (以上)' },
  { v:'equals',                l:'= (等しい)' },
  { v:'crosses_above',         l:'↑ クロスアップ' },
  { v:'crosses_below',         l:'↓ クロスダウン' },
];

let _condSeq = 0;
let _logic = 'AND';

/* ---------- AND/OR 切り替え ---------- */
function setLogic(v) {
  _logic = v;
  document.getElementById('logic-and').classList.toggle('active', v === 'AND');
  document.getElementById('logic-or' ).classList.toggle('active', v === 'OR');
}

/* ---------- 条件追加 ---------- */
function addCondition() {
  const id = 'cond-' + (++_condSeq);
  const row = document.createElement('div');
  row.className = 'cond-row';
  row.id = id;
  row.dataset.id = 'c' + _condSeq;

  row.innerHTML = `
    <div class="form-group">
      <label>指標</label>
      <select onchange="onIndChange(this, '${id}')">
        ${Object.entries(IND).map(([k,v]) => `<option value="${k}">${v.label}</option>`).join('')}
      </select>
    </div>
    <div class="form-group" id="${id}-params">
      ${buildParamInputs('RSI', id)}
    </div>
    <div class="form-group">
      <label>比較</label>
      <select id="${id}-cmp" onchange="onCmpChange('${id}')">
        ${COMPARISONS.map(c => `<option value="${c.v}">${c.l}</option>`).join('')}
      </select>
    </div>
    <div class="form-group" id="${id}-rhs">
      ${buildRhsScalar(id)}
    </div>
    <div>
      <label style="visibility:hidden">削除</label>
      <button class="btn-del-cond" onclick="removeCondition('${id}')">✕</button>
    </div>`;

  document.getElementById('cond-list').appendChild(row);
  updateActions();
}

/* ---------- 条件削除 ---------- */
function removeCondition(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
  updateActions();
}

/* ---------- 指標変更 → パラメータ再描画 ---------- */
function onIndChange(sel, rowId) {
  document.getElementById(rowId + '-params').innerHTML =
    buildParamInputs(sel.value, rowId);
}

/* ---------- パラメータ入力 HTML 生成 ---------- */
function buildParamInputs(indKey, rowId) {
  const ps = (IND[indKey] || {}).params || [];
  if (!ps.length) return '<label style="visibility:hidden">-</label><div style="color:#475569;font-size:12px;padding:9px 0">パラメータなし</div>';
  const inputs = ps.map(p =>
    `<div style="display:flex;flex-direction:column;gap:3px">
       <span style="font-size:10px;color:#64748b">${p.l}</span>
       <input type="number" id="${rowId}-p-${p.n}" value="${p.d}" step="${p.n==='std'?0.1:1}" style="width:62px">
     </div>`
  ).join('');
  return `<label>パラメータ</label><div style="display:flex;gap:6px;flex-wrap:wrap">${inputs}</div>`;
}

/* ---------- 比較変更 → RHS 再描画 ---------- */
function onCmpChange(rowId) {
  const cmp = document.getElementById(rowId + '-cmp').value;
  const isCross = cmp === 'crosses_above' || cmp === 'crosses_below';
  document.getElementById(rowId + '-rhs').innerHTML = isCross
    ? buildRhsCross(rowId)
    : buildRhsScalar(rowId);
}

/* ---------- RHS: スカラー値 ---------- */
function buildRhsScalar(rowId) {
  return `<label>比較値</label>
    <input type="number" id="${rowId}-val" value="30" step="0.1" style="width:100%">`;
}

/* ---------- RHS: クロス比較先指標 ---------- */
function buildRhsCross(rowId) {
  const opts = Object.entries(IND).map(([k,v]) =>
    `<option value="${k}">${v.label}</option>`).join('');
  return `<label>比較先指標</label>
    <select id="${rowId}-cmp-ind" onchange="onCmpIndChange('${rowId}')">
      <option value="">--- スカラー値 ---</option>
      ${opts}
    </select>
    <div id="${rowId}-cross-val" style="margin-top:6px">
      <input type="number" id="${rowId}-val" value="0" step="0.1" placeholder="閾値" style="width:100%">
    </div>`;
}

/* ---------- クロス比較先指標変更 → 閾値表示切り替え ---------- */
function onCmpIndChange(rowId) {
  const sel = document.getElementById(rowId + '-cmp-ind');
  const valDiv = document.getElementById(rowId + '-cross-val');
  if (valDiv) valDiv.style.display = sel.value ? 'none' : 'block';
}

/* ---------- 実行ボタン表示制御 ---------- */
function updateActions() {
  const hasCond = document.querySelectorAll('#cond-list .cond-row').length > 0;
  document.getElementById('section-actions').style.display = hasCond ? 'flex' : 'none';
}

/* ---------- 条件 → StrategyCondition オブジェクト ---------- */
function buildConditions() {
  const rows = document.querySelectorAll('#cond-list .cond-row');
  const conds = [];
  for (const row of rows) {
    const condId   = row.dataset.id;
    const indSel   = row.querySelector('select');
    const indKey   = indSel ? indSel.value : 'RSI';
    const rowId    = row.id;
    const cmpVal   = document.getElementById(rowId + '-cmp')?.value || 'less_than';
    const isCross  = cmpVal === 'crosses_above' || cmpVal === 'crosses_below';

    // params
    const ps = (IND[indKey] || {}).params || [];
    const params = {};
    ps.forEach(p => {
      const el = document.getElementById(rowId + '-p-' + p.n);
      if (el) params[p.n] = parseFloat(el.value);
    });

    // value / compare_to_indicator
    let value = null;
    let compare_to_indicator = null;
    let compare_to_params    = null;

    if (isCross) {
      const cmpIndSel = document.getElementById(rowId + '-cmp-ind');
      if (cmpIndSel && cmpIndSel.value) {
        compare_to_indicator = cmpIndSel.value;
        const cps = (IND[cmpIndSel.value] || {}).params || [];
        compare_to_params = {};
        cps.forEach(p => {
          const el = document.getElementById(rowId + '-p-' + p.n);
          compare_to_params[p.n] = el ? parseFloat(el.value) : p.d;
        });
      } else {
        const valEl = document.getElementById(rowId + '-val');
        value = valEl ? parseFloat(valEl.value) : null;
      }
    } else {
      const valEl = document.getElementById(rowId + '-val');
      value = valEl ? parseFloat(valEl.value) : null;
    }

    conds.push({
      id: condId,
      indicator: indKey,
      params,
      comparison: cmpVal,
      value,
      compare_to_indicator,
      compare_to_params,
    });
  }
  return conds;
}

/* =====================================================================
   10g: Lightweight Charts — ローソク足 + トレードマーカー
   ===================================================================== */
let _lwChart = null;
let _candleSeries = null;

function renderChart(ohlcv, chartData) {
  /* ---- チャートコンテナを描画 ---- */
  document.getElementById('section-chart').innerHTML =
    '<div class="chart-card"><h3>チャート（ローソク足 + トレードシグナル）</h3><div id="tv-chart"></div></div>';

  /* ---- 既存チャートを破棄 ---- */
  if (_lwChart) { try { _lwChart.remove(); } catch(e){} _lwChart = null; }

  const container = document.getElementById('tv-chart');
  if (!container || !ohlcv.length) return;

  /* ---- チャート生成 ---- */
  _lwChart = LightweightCharts.createChart(container, {
    width:  container.clientWidth || 900,
    height: 420,
    layout:     { background: { color: '#0f172a' }, textColor: '#94a3b8' },
    grid:       { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#334155' },
    timeScale:  { borderColor: '#334155', timeVisible: true, secondsVisible: false },
  });

  _candleSeries = _lwChart.addCandlestickSeries({
    upColor:   '#22c55e', downColor: '#ef4444',
    borderUpColor: '#22c55e', borderDownColor: '#ef4444',
    wickUpColor:   '#22c55e', wickDownColor:   '#ef4444',
  });

  /* ---- OHLCV データ変換 ---- */
  const candles = ohlcv
    .map(d => {
      const t = toChartTime(d.timestamp || d.time || d.date);
      if (!t) return null;
      return { time: t, open: +d.open, high: +d.high, low: +d.low, close: +d.close };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);

  if (candles.length) _candleSeries.setData(candles);

  /* ---- トレードマーカー ---- */
  const markers = (chartData.markers || [])
    .map(m => {
      const t = toChartTime(m.time);
      if (!t) return null;
      return { time: t, position: m.position, color: m.color, shape: m.shape, text: m.text };
    })
    .filter(Boolean)
    .sort((a, b) => a.time - b.time);

  if (markers.length) _candleSeries.setMarkers(markers);

  /* ---- レスポンシブリサイズ ---- */
  new ResizeObserver(() => {
    if (_lwChart && container) _lwChart.resize(container.clientWidth, 420);
  }).observe(container);
}

/* ---------- タイムスタンプ → Unix 秒 ---------- */
function toChartTime(ts) {
  if (!ts && ts !== 0) return null;
  if (typeof ts === 'number') {
    if (ts > 1e15) return Math.floor(ts / 1e6);  // nanoseconds
    if (ts > 1e12) return Math.floor(ts / 1000);  // milliseconds
    return ts;                                     // seconds
  }
  const s = String(ts).replace(' ', 'T');
  const d = new Date(s.includes('Z') || s.includes('+') ? s : s + 'Z');
  return isNaN(d) ? null : Math.floor(d.getTime() / 1000);
}

/* ---------- 初期条件を1つ追加 ---------- */
addCondition();

/* =====================================================================
   10e: 実行ロジック
   ===================================================================== */

/* ---------- StrategyConfig 組み立て ---------- */
function buildStrategyConfig() {
  const conds = buildConditions();
  if (!conds.length) throw new Error('条件を1つ以上追加してください');
  return {
    strategy_version: '1.0',
    direction:        document.getElementById('direction').value,
    entry_conditions: { logic: _logic, conditions: conds },
    filters:          buildFilters(),
    sl_config:        buildSlConfig(),
    tp_config:        buildTpConfig(),
    trailing_config:  buildTrailingConfig(),
  };
}

/* ---------- 選択通貨ペア取得 ---------- */
function getSelectedPairs() {
  return [...document.querySelectorAll('.pair-cb:checked')].map(el => el.value);
}

/* ---------- 1ペア分 API 呼び出し ---------- */
async function fetchOnePair(pair, timeframe, limit, strategy, simParams) {
  const res = await fetch('/admin/api.php', {
    method:  'POST',
    headers: {'Content-Type':'application/json'},
    body:    JSON.stringify({
      action: 'bt_v2', pair, timeframe, limit,
      strategy_config: strategy,
      sim_params: simParams,
    }),
  }).then(r => r.json());
  if (!res.ok) throw new Error(`[${pair}] ${res.error || 'APIエラー'}`);
  return res;
}

/* ---------- メインエントリーポイント（複数ペア対応） ---------- */
let _lastTrades   = [];
let _lastOhlcv    = [];
let _lastMetrics  = null;
let _multiResults = {};

async function runBacktest() {
  hideErr();

  const pairs = getSelectedPairs();
  if (!pairs.length) { showErr('通貨ペアを1つ以上選択してください'); return; }

  let strategy;
  try { strategy = buildStrategyConfig(); }
  catch(e) { showErr(e.message); return; }

  const timeframe = document.getElementById('timeframe').value;
  const limit     = parseInt(document.getElementById('limit').value, 10);
  const simParams = {
    initial_capital:  parseFloat(document.getElementById('initial_capital').value),
    pip_value:        parseFloat(document.getElementById('pip_value').value),
    max_bars_to_exit: parseInt(document.getElementById('max_bars_to_exit').value, 10),
  };

  document.getElementById('btn-run').disabled = true;
  document.getElementById('run-status').textContent = '';
  document.getElementById('result-wrap').classList.remove('show');

  /* ---- 各ペアを順次実行 ---- */
  const results = {};
  for (let i = 0; i < pairs.length; i++) {
    const pair = pairs[i];
    showOverlay('バックテスト実行中...', `${pair} (${i + 1} / ${pairs.length})`);
    try {
      results[pair] = await fetchOnePair(pair, timeframe, limit, strategy, simParams);
    } catch(e) {
      hideOverlay();
      document.getElementById('btn-run').disabled = false;
      showErr(e.message);
      return;
    }
  }

  hideOverlay();
  document.getElementById('btn-run').disabled = false;

  if (pairs.length === 1) {
    const r = results[pairs[0]];
    _lastTrades  = r.trades  || [];
    _lastMetrics = r.metrics || {};
    _lastOhlcv   = r.ohlcv   || [];
    renderMetrics(r.metrics, r.bars_used);
    renderChart(_lastOhlcv, r.chart_data || {});
    renderTrades(_lastTrades);
  } else {
    _multiResults = results;
    renderMultiPairResults(results, timeframe);
  }

  document.getElementById('result-wrap').classList.add('show');
  document.getElementById('result-wrap').scrollIntoView({behavior:'smooth', block:'start'});
}

/* ---------- 複数ペア比較レンダリング ---------- */
function renderMultiPairResults(results, timeframe) {
  const pairs = Object.keys(results);
  const m = pair => results[pair].metrics || {};

  const fmtF = (v, d=2)  => v == null ? '-' : (isFinite(v) ? v.toFixed(d) : '∞');
  const fmtS = (v, unit, d=1) => v == null ? '-' : (v >= 0 ? '+' : '') + v.toFixed(d) + unit;
  const clsPN = v => v != null && v >= 0 ? 'style="color:#4ade80"' : 'style="color:#f87171"';
  const clsPF = v => v == null || v < 1   ? 'style="color:#f87171"' : 'style="color:#4ade80"';
  const clsWR = v => v != null && v >= 0.5 ? 'style="color:#4ade80"' : 'style="color:#f87171"';

  const ROWS = [
    { l:'総取引数',   f: p => m(p).total_trades + '回',       c: null },
    { l:'勝率',       f: p => m(p).win_rate != null ? (m(p).win_rate*100).toFixed(1)+'%' : '-', c: p => clsWR(m(p).win_rate) },
    { l:'PF',        f: p => fmtF(m(p).profit_factor),       c: p => clsPF(m(p).profit_factor) },
    { l:'期待値',     f: p => fmtS(m(p).expectancy_pips,'p'), c: p => clsPN(m(p).expectancy_pips) },
    { l:'純損益',     f: p => fmtS(m(p).net_profit_pips,'p'),c: p => clsPN(m(p).net_profit_pips) },
    { l:'最大DD',     f: p => m(p).max_drawdown_pips != null ? m(p).max_drawdown_pips.toFixed(1)+'p' : '-', c: () => 'style="color:#fbbf24"' },
    { l:'平均RR',     f: p => fmtF(m(p).avg_rr),             c: null },
    { l:'最大連勝',   f: p => m(p).max_win_streak + '連',    c: null },
    { l:'最大連敗',   f: p => m(p).max_loss_streak + '連',   c: null },
    { l:'平均保有',   f: p => m(p).avg_holding_bars != null ? m(p).avg_holding_bars.toFixed(1)+'bar' : '-', c: null },
    { l:'L勝率',      f: p => m(p).long_win_rate  != null ? (m(p).long_win_rate*100).toFixed(1)+'%' : '-',  c: p => clsWR(m(p).long_win_rate) },
    { l:'S勝率',      f: p => m(p).short_win_rate != null ? (m(p).short_win_rate*100).toFixed(1)+'%' : '-', c: p => clsWR(m(p).short_win_rate) },
  ];

  const th = pairs.map(p => `<th>${p}</th>`).join('');
  const tbody = ROWS.map(row => {
    const cells = pairs.map(p => {
      const cls = row.c ? row.c(p) : '';
      return `<td ${cls}>${row.f(p)}</td>`;
    }).join('');
    return `<tr><td>${row.l}</td>${cells}</tr>`;
  }).join('');

  document.getElementById('section-metrics').innerHTML = `
    <div class="form-card">
      <h3>通貨ペア比較（${timeframe}）</h3>
      <div class="compare-tbl-wrap">
        <table class="compare-tbl">
          <thead><tr><th>指標</th>${th}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>
      </div>
    </div>`;

  /* ---- チャート（タブ切り替え） ---- */
  const chartTabs = pairs.map((p,i) =>
    `<button class="pair-tab ${i===0?'active':''}" onclick="switchChartPair('${p}',this)">${p}</button>`
  ).join('');
  document.getElementById('section-chart').innerHTML = `
    <div class="chart-card">
      <h3>チャート（ローソク足 + トレードシグナル）</h3>
      <div class="pair-tabs" id="chart-tabs">${chartTabs}</div>
      <div id="tv-chart"></div>
    </div>`;
  const r0 = results[pairs[0]];
  renderChart(r0.ohlcv || [], r0.chart_data || {});

  /* ---- トレードログ（タブ切り替え） ---- */
  const tradeTabs = pairs.map((p,i) =>
    `<button class="pair-tab ${i===0?'active':''}" onclick="switchTradePair('${p}',this)">${p}</button>`
  ).join('');
  document.getElementById('section-trades').innerHTML = `
    <div class="table-card">
      <h3>トレードログ</h3>
      <div class="pair-tabs" id="trade-tabs">${tradeTabs}</div>
      <div id="trade-tab-content"></div>
    </div>`;
  renderTradesTo(r0.trades || [], document.getElementById('trade-tab-content'));
}

/* ---------- チャートタブ切り替え ---------- */
function switchChartPair(pair, btn) {
  btn.closest('.pair-tabs').querySelectorAll('.pair-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const r = _multiResults[pair];
  if (r) renderChart(r.ohlcv || [], r.chart_data || {});
}

/* ---------- トレードタブ切り替え ---------- */
function switchTradePair(pair, btn) {
  btn.closest('.pair-tabs').querySelectorAll('.pair-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const r = _multiResults[pair];
  if (r) renderTradesTo(r.trades || [], document.getElementById('trade-tab-content'));
}

/* ---------- トレードテーブルを任意コンテナに描画 ---------- */
function renderTradesTo(trades, container) {
  if (!container) return;
  if (!trades.length) {
    container.innerHTML = '<div style="color:#64748b;font-size:13px;padding:8px 0">取引なし</div>';
    return;
  }
  const reasonBadge = r => {
    const map = { TP:'bdg-tp', SL:'bdg-sl', TRAILING_SL:'bdg-tsl', END_OF_DATA:'bdg-eod' };
    const lbl = { TP:'TP', SL:'SL', TRAILING_SL:'TSL', END_OF_DATA:'EOD' };
    return `<span class="bdg ${map[r]||''}">${lbl[r]||r}</span>`;
  };
  const fmt = v => parseFloat(v).toFixed(3);
  const fmtPips = v => (v >= 0 ? '+' : '') + parseFloat(v).toFixed(1);
  const rows = trades.map((t, i) => {
    const dirBdg = t.direction === 'BUY'
      ? '<span class="bdg bdg-buy">BUY</span>'
      : '<span class="bdg bdg-sell">SELL</span>';
    const pnlCls = t.pnl_pips >= 0 ? 'style="color:#4ade80"' : 'style="color:#f87171"';
    return `<tr>
      <td style="color:#64748b">${i+1}</td>
      <td>${dirBdg}</td>
      <td>${t.entry_time.replace('T',' ').slice(0,16)}</td>
      <td>${fmt(t.entry_price)}</td>
      <td>${fmt(t.sl_price)}</td>
      <td>${fmt(t.tp_price)}</td>
      <td>${t.exit_time.replace('T',' ').slice(0,16)}</td>
      <td>${fmt(t.exit_price)}</td>
      <td>${reasonBadge(t.exit_reason)}</td>
      <td ${pnlCls}>${fmtPips(t.pnl_pips)}p</td>
      <td ${pnlCls}>${(t.pnl_currency >= 0 ? '+' : '')}${Math.round(t.pnl_currency).toLocaleString()}円</td>
      <td style="color:#64748b">${Math.round(t.running_capital).toLocaleString()}円</td>
    </tr>`;
  }).join('');
  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="trade-tbl">
        <thead><tr>
          <th>#</th><th>方向</th><th>エントリー時刻</th><th>EP</th>
          <th>SL</th><th>TP</th><th>クローズ時刻</th><th>XP</th>
          <th>決済理由</th><th>pips</th><th>損益</th><th>残高</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

/* ---------- オーバーレイ / エラー ---------- */
function showOverlay(msg, sub) {
  document.getElementById('overlay-msg').textContent = msg || '';
  document.getElementById('overlay-sub').textContent = sub || '';
  document.getElementById('overlay').classList.add('active');
}
function hideOverlay() { document.getElementById('overlay').classList.remove('active'); }
function showErr(msg) {
  const b = document.getElementById('err-banner');
  b.textContent = msg; b.style.display = 'block';
  b.scrollIntoView({behavior:'smooth', block:'nearest'});
}
function hideErr() { document.getElementById('err-banner').style.display = 'none'; }

/* =====================================================================
   10f: メトリクス & トレードログ表示
   ===================================================================== */

function renderMetrics(m, barsUsed) {
  const wr = m.win_rate != null ? (m.win_rate * 100).toFixed(1) : '-';
  const wrCls = m.win_rate >= 0.5 ? 'green' : 'red';
  const pf = m.profit_factor == null ? '-' : (isFinite(m.profit_factor) ? m.profit_factor.toFixed(2) : '∞');
  const pfCls = (m.profit_factor == null || m.profit_factor < 1) ? 'red' : 'green';
  const net = m.net_profit_pips != null ? (m.net_profit_pips >= 0 ? '+' : '') + m.net_profit_pips.toFixed(1) + ' pips' : '-';
  const netCls = m.net_profit_pips >= 0 ? 'green' : 'red';
  const dd = m.max_drawdown_pips != null ? m.max_drawdown_pips.toFixed(1) + ' pips' : '-';

  document.getElementById('section-metrics').innerHTML = `
    <div class="metrics-grid">
      ${mc('総取引数', m.total_trades + '回 / ' + barsUsed + 'bar', '')}
      ${mc('勝率',     wr + '%', wrCls)}
      ${mc('純損益',   net, netCls)}
      ${mc('最大DD',   dd, 'yellow')}
    </div>
    <div class="metrics-grid2">
      ${ms('PF',      pf, pfCls)}
      ${ms('期待値',  m.expectancy_pips != null ? m.expectancy_pips.toFixed(2)+'p' : '-', m.expectancy_pips >= 0 ? 'green' : 'red')}
      ${ms('平均RR',  m.avg_rr != null && isFinite(m.avg_rr) ? m.avg_rr.toFixed(2) : (m.avg_rr == null ? '-' : '∞'), '')}
      ${ms('勝 / 負', m.wins + ' / ' + m.losses, '')}
      ${ms('最大連勝/連敗', m.max_win_streak + ' / ' + m.max_loss_streak, '')}
      ${ms('平均保有', m.avg_holding_bars != null ? m.avg_holding_bars.toFixed(1)+'bar' : '-', '')}
      ${ms('L勝率', m.long_win_rate != null ? (m.long_win_rate*100).toFixed(1)+'%' : '-', '')}
      ${ms('S勝率', m.short_win_rate != null ? (m.short_win_rate*100).toFixed(1)+'%' : '-', '')}
      ${ms('総利益pips', m.gross_profit_pips != null ? '+'+m.gross_profit_pips.toFixed(1) : '-', 'green')}
      ${ms('総損失pips', m.gross_loss_pips   != null ? '-'+m.gross_loss_pips.toFixed(1)   : '-', 'red')}
    </div>`;
}

function mc(label, val, cls) {
  return `<div class="metric-card"><div class="mc-label">${label}</div><div class="mc-val ${cls}">${val}</div></div>`;
}
function ms(label, val, cls) {
  return `<div class="metric-sm"><div class="ms-label">${label}</div><div class="ms-val ${cls}">${val}</div></div>`;
}

function renderTrades(trades) {
  document.getElementById('section-trades').innerHTML = `
    <div class="table-card">
      <h3>トレードログ（${trades.length}件）</h3>
      <div id="trade-tab-content"></div>
    </div>`;
  renderTradesTo(trades, document.getElementById('trade-tab-content'));
}
</script>

</body>
</html>
