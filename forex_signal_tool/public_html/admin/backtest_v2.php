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
        <label>通貨ペア</label>
        <select id="pair">
          <option value="USDJPY">ドル円 (USD/JPY)</option>
          <option value="GBPJPY">ポンド円 (GBP/JPY)</option>
          <option value="EURJPY">ユーロ円 (EUR/JPY)</option>
        </select>
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
  <div id="section-conditions"><!-- 10c --></div>

  <!-- 10d: SL / TP / トレーリング -->
  <div id="section-risk"><!-- 10d --></div>

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

</body>
</html>
