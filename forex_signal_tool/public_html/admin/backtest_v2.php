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

/* ===== trade log analysis ===== */
.reason-tag{display:inline-block;background:#1e3a5f;color:#93c5fd;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:600;margin:1px}
.trade-tbl tr.clickable{cursor:pointer}
.trade-tbl tr.clickable:hover td{background:rgba(59,130,246,.08)!important}
#equity-chart{width:100%;height:130px}

/* ===== optimization ===== */
.opt-row{background:#0f172a;border:1px solid #334155;border-radius:9px;padding:12px 14px;display:grid;grid-template-columns:1fr 1fr 80px 80px 80px auto;gap:10px;align-items:end}
.opt-result-tbl{width:100%;border-collapse:collapse;font-size:12px}
.opt-result-tbl th{background:#0f172a;color:#64748b;padding:9px 12px;border-bottom:2px solid #334155;white-space:nowrap;text-align:center}
.opt-result-tbl th:first-child,.opt-result-tbl td:first-child{text-align:left}
.opt-result-tbl td{padding:8px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1;text-align:center}
.opt-result-tbl tr:hover td{background:rgba(255,255,255,.03)}
.rank-1 td{background:rgba(250,204,21,.06)!important}
.rank-2 td{background:rgba(148,163,184,.04)!important}
.rank-3 td{background:rgba(180,120,60,.04)!important}
.opt-apply-btn{background:#1e3a5f;border:1px solid #3b82f6;color:#60a5fa;border-radius:5px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;transition:background .15s}
.opt-apply-btn:hover{background:#1e40af}

/* ===== preset bar ===== */
.preset-bar{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:13px 18px;margin-bottom:20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.preset-section{display:flex;align-items:center;gap:8px}
.preset-lbl{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}
.preset-sel{background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:6px 10px;font-size:12px;outline:none;min-width:210px}
.preset-sel:focus{border-color:#3b82f6}
.preset-sep{width:1px;height:24px;background:#334155}
.preset-btn{padding:6px 14px;border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid #3b82f6;background:#1e3a5f;color:#60a5fa;transition:background .15s;white-space:nowrap}
.preset-btn:hover{background:#1e40af}

/* ===== range mode toggle ===== */
.range-toggle{display:flex;gap:0;border:1px solid #475569;border-radius:7px;overflow:hidden;margin-bottom:8px}
.range-btn{flex:1;padding:5px 0;font-size:11px;font-weight:600;cursor:pointer;background:#0f172a;color:#64748b;border:none;transition:all .15s}
.range-btn.active{background:#1e3a5f;color:#60a5fa}
.date-pair{display:flex;gap:6px;align-items:center}
.date-pair input[type=date]{flex:1;background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:7px 8px;font-size:12px;outline:none;min-width:0}
.date-pair input[type=date]:focus{border-color:#3b82f6}
.date-pair span{color:#64748b;font-size:12px;white-space:nowrap}

/* ===== save modal ===== */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:400;display:flex;align-items:center;justify-content:center}
.modal-box{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:28px 24px;width:440px;max-width:90vw}
.modal-title{font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:18px}
.modal-input{width:100%;background:#0f172a;border:1px solid #475569;border-radius:8px;color:#e2e8f0;padding:10px 12px;font-size:14px;outline:none}
.modal-input:focus{border-color:#3b82f6}
.modal-err{font-size:12px;color:#f87171;margin-top:8px;min-height:18px}
.modal-actions{display:flex;gap:10px;margin-top:18px;justify-content:flex-end}
.modal-btn{padding:8px 20px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;border:none}
.modal-btn.cancel{background:#334155;color:#94a3b8}
.modal-btn.confirm{background:#3b82f6;color:#fff}

/* ===== signal registration panel ===== */
.signal-panel{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px}
.signal-panel h3{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px}
.signal-badge{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:9px;font-size:16px;font-weight:700;margin-bottom:16px}
.signal-badge.buy{background:rgba(74,222,128,.12);border:1px solid #4ade80;color:#4ade80}
.signal-badge.sell{background:rgba(248,113,113,.12);border:1px solid #f87171;color:#f87171}
.signal-badge.neutral{background:rgba(100,116,139,.12);border:1px solid #64748b;color:#64748b}
.signal-info-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.signal-info-item{background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:10px 12px;text-align:center}
.signal-info-item .si-label{font-size:10px;color:#64748b;margin-bottom:3px;text-transform:uppercase;letter-spacing:.4px}
.signal-info-item .si-val{font-size:14px;font-weight:700;color:#e2e8f0}
.btn-signal{background:#0e7490;color:#fff;border:none;border-radius:9px;padding:10px 24px;font-size:13px;font-weight:600;cursor:pointer;transition:background .2s}
.btn-signal:hover{background:#0891b2}
.btn-signal:disabled{opacity:.5;cursor:not-allowed}
.signal-status-txt{font-size:12px;color:#64748b;margin-left:12px}
.signal-hint{font-size:11px;color:#475569;margin-top:10px;line-height:1.5}

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

<!-- 保存モーダル -->
<div id="save-modal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeSaveModal()">
  <div class="modal-box">
    <div class="modal-title">戦略を保存</div>
    <label style="font-size:12px;color:#64748b;display:block;margin-bottom:6px">戦略名</label>
    <input type="text" id="save-name" class="modal-input" placeholder="例: USDJPY RSI 逆張り" maxlength="100">
    <label style="font-size:12px;color:#64748b;display:block;margin:12px 0 6px">改善対象指標（テクニカルページに比較掲載）</label>
    <select id="save-linked-ind" class="modal-input" style="cursor:pointer">
      <option value="">紐づけなし</option>
    </select>
    <div style="font-size:11px;color:#475569;margin-top:4px">
      選択するとバックテスト結果がその指標ページの比較コンテンツとして掲載されます
    </div>
    <div class="modal-err" id="save-err"></div>
    <div class="modal-actions">
      <button class="modal-btn cancel" onclick="closeSaveModal()">キャンセル</button>
      <button class="modal-btn confirm" onclick="confirmSave()">保存する</button>
    </div>
  </div>
</div>

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

  <!-- プリセット / 保存済み戦略バー -->
  <div class="preset-bar">
    <div class="preset-section">
      <span class="preset-lbl">プリセット</span>
      <select class="preset-sel" id="preset-select" onchange="loadPreset(this.value)">
        <option value="">-- 戦略を選択 --</option>
        <optgroup label="トレンドフォロー">
          <option value="macd_trend">MACD ゼロクロス</option>
          <option value="cci_momentum">CCI 100 突破</option>
        </optgroup>
        <optgroup label="逆張り">
          <option value="rsi_reversal">RSI 30 過売り（BUY）</option>
          <option value="stoch_reversal">Stoch 20 過売り（BUY）</option>
        </optgroup>
        <optgroup label="ブレイクアウト">
          <option value="bb_breakout">BB 上バンド突破（BUY）</option>
        </optgroup>
      </select>
    </div>
    <div class="preset-sep"></div>
    <div class="preset-section">
      <span class="preset-lbl">保存済み</span>
      <select class="preset-sel" id="saved-select" onchange="applySavedStrategy(this.value)">
        <option value="">-- 読み込む --</option>
      </select>
      <button class="preset-btn" onclick="showSaveModal()">この設定を保存</button>
    </div>
  </div>

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
        <label>検証期間</label>
        <div class="range-toggle">
          <button id="range-btn-limit" class="range-btn active" onclick="setRangeMode('limit')">本数指定</button>
          <button id="range-btn-date"  class="range-btn"        onclick="setRangeMode('date')">日時指定</button>
        </div>
        <div id="range-limit-wrap">
          <input type="number" id="limit" value="500" min="100" max="5000" step="100">
          <div class="form-hint">多いほど精度↑・実行時間↑</div>
        </div>
        <div id="range-date-wrap" style="display:none">
          <div class="date-pair">
            <input type="date" id="date-start">
            <span>〜</span>
            <input type="date" id="date-end">
          </div>
          <div class="form-hint">DB内の存在期間のみ有効</div>
        </div>
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
    <!-- 10g chart + equity curve -->
    <div id="section-chart"></div>
    <!-- 10f trade table -->
    <div id="section-trades"></div>
    <!-- 13: リアルタイムシグナル登録 -->
    <div id="section-signal" style="display:none"></div>
  </div>

  <!-- 最適化設定 -->
  <div class="form-card" id="section-optimize" style="display:none">
    <h3>最適化設定（グリッドサーチ）</h3>

    <div class="form-row col3" style="margin-bottom:14px">
      <div class="form-group">
        <label>最適化指標</label>
        <select id="opt-objective">
          <option value="profit_factor">プロフィットファクター（PF）</option>
          <option value="win_rate">勝率</option>
          <option value="expectancy_pips">期待値 (pips)</option>
          <option value="net_profit_pips">純損益 (pips)</option>
        </select>
      </div>
      <div class="form-group">
        <label>上位表示件数</label>
        <input type="number" id="opt-top-n" value="20" min="5" max="100" step="5">
      </div>
      <div class="form-group">
        <label>最大組み合わせ数</label>
        <input type="number" id="opt-max-combos" value="200" min="10" max="500" step="10">
        <div class="form-hint">上限超過時はエラーになります</div>
      </div>
    </div>

    <div style="font-size:12px;font-weight:600;color:#94a3b8;margin-bottom:10px">最適化対象パラメータ</div>
    <div class="cond-list" id="opt-target-list"></div>
    <button class="btn-add-cond" onclick="addOptTarget()">＋ 最適化対象を追加</button>

    <div class="actions" style="margin-top:16px">
      <button class="btn-run" id="btn-optimize" onclick="runOptimize()" style="background:#7c3aed">最適化実行</button>
      <span id="opt-status" style="font-size:13px;color:#64748b"></span>
    </div>
  </div>

  <!-- 最適化結果 -->
  <div class="result-wrap" id="opt-result-wrap">
    <div id="section-opt-result"></div>
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
   最適化 UI
   ===================================================================== */
let _optSeq = 0;

/* 現在の条件 ID リストを取得 */
function getConditionIds() {
  return [...document.querySelectorAll('#cond-list .cond-row')].map(r => r.dataset.id);
}

/* 最適化対象行を追加 */
function addOptTarget() {
  const ids = getConditionIds();
  if (!ids.length) { alert('先にエントリー条件を追加してください'); return; }
  const id = 'opt-' + (++_optSeq);
  const row = document.createElement('div');
  row.className = 'opt-row';
  row.id = id;
  const idOpts = ids.map(c => `<option value="${c}">${c}</option>`).join('');
  row.innerHTML = `
    <div class="form-group">
      <label>条件 ID</label>
      <select id="${id}-cid">${idOpts}</select>
    </div>
    <div class="form-group">
      <label>パラメータ名</label>
      <input type="text" id="${id}-param" value="period" placeholder="period / fast / slow ...">
    </div>
    <div class="form-group">
      <label>最小値</label>
      <input type="number" id="${id}-min" value="5" min="1" step="1">
    </div>
    <div class="form-group">
      <label>最大値</label>
      <input type="number" id="${id}-max" value="30" min="1" step="1">
    </div>
    <div class="form-group">
      <label>Step</label>
      <input type="number" id="${id}-step" value="5" min="1" step="1">
    </div>
    <div>
      <label style="visibility:hidden">削除</label>
      <button class="btn-del-cond" onclick="this.closest('.opt-row').remove()">✕</button>
    </div>`;
  document.getElementById('opt-target-list').appendChild(row);
}

/* 最適化設定オブジェクト構築 */
function buildOptimizeConfig() {
  const rows = document.querySelectorAll('#opt-target-list .opt-row');
  if (!rows.length) throw new Error('最適化対象パラメータを1つ以上追加してください');
  const targets = [...rows].map(row => {
    const id = row.id;
    return {
      condition_id: document.getElementById(id + '-cid').value,
      param:        document.getElementById(id + '-param').value.trim(),
      range:        [
        parseFloat(document.getElementById(id + '-min').value),
        parseFloat(document.getElementById(id + '-max').value),
      ],
      step: parseFloat(document.getElementById(id + '-step').value),
    };
  });
  return {
    target_conditions: targets,
    objective:  document.getElementById('opt-objective').value,
    top_n:      parseInt(document.getElementById('opt-top-n').value, 10),
    max_combos: parseInt(document.getElementById('opt-max-combos').value, 10),
  };
}

/* 最適化結果にパラメータを適用 */
function applyOptParams(paramsJson) {
  const params = JSON.parse(paramsJson);
  document.querySelectorAll('#cond-list .cond-row').forEach(row => {
    const condId = row.dataset.id;
    Object.entries(params).forEach(([key, val]) => {
      // key = "c1.period" 形式
      const [pid, pname] = key.split('.');
      if (pid !== condId) return;
      const el = row.querySelector(`[id$="-p-${pname}"]`);
      if (el) { el.value = val; }
    });
  });
}

/* 最適化実行 */
async function runOptimize() {
  hideErr();
  let optCfg, strategy;
  try {
    optCfg   = buildOptimizeConfig();
    strategy = buildStrategyConfig();
  } catch(e) { showErr(e.message); return; }

  const pairs = getSelectedPairs();
  const pair  = pairs[0] || 'USDJPY';

  const payload = {
    action:           'bt_optimize',
    pair,
    timeframe:        document.getElementById('timeframe').value,
    limit:            parseInt(document.getElementById('limit').value, 10),
    strategy_config:  strategy,
    sim_params: {
      initial_capital:  parseFloat(document.getElementById('initial_capital').value),
      pip_value:        parseFloat(document.getElementById('pip_value').value),
      max_bars_to_exit: parseInt(document.getElementById('max_bars_to_exit').value, 10),
    },
    optimize_config: optCfg,
  };

  document.getElementById('btn-optimize').disabled = true;
  document.getElementById('opt-status').textContent = '最適化中...';
  document.getElementById('opt-result-wrap').classList.remove('show');
  showOverlay('最適化実行中...', `グリッドサーチ中（最大 ${optCfg.max_combos} 組み合わせ）`);

  try {
    const res = await fetch('/admin/api.php', {
      method:  'POST',
      headers: {'Content-Type':'application/json'},
      body:    JSON.stringify(payload),
    }).then(r => r.json());

    hideOverlay();
    document.getElementById('btn-optimize').disabled = false;

    if (!res.ok) {
      document.getElementById('opt-status').textContent = '❌ ' + (res.error || 'エラー');
      showErr(res.error || '最適化エラー');
      return;
    }

    document.getElementById('opt-status').textContent =
      `✅ 完了 (${res.total_combinations} 組み合わせ / ${(res.results || []).length} 件表示)`;

    renderOptResults(res);
    document.getElementById('opt-result-wrap').classList.add('show');
    document.getElementById('opt-result-wrap').scrollIntoView({behavior:'smooth', block:'start'});

  } catch(e) {
    hideOverlay();
    document.getElementById('btn-optimize').disabled = false;
    document.getElementById('opt-status').textContent = '❌ エラー';
    showErr(e.message);
  }
}

/* 最適化結果テーブル描画 */
function renderOptResults(res) {
  const results  = res.results || [];
  const objLabel = {
    profit_factor:   'PF',
    win_rate:        '勝率',
    expectancy_pips: '期待値',
    net_profit_pips: '純損益',
  }[res.objective] || res.objective;

  if (!results.length) {
    document.getElementById('section-opt-result').innerHTML =
      '<div class="form-card"><h3>最適化結果</h3><div style="color:#64748b;font-size:13px">有効な結果がありません</div></div>';
    return;
  }

  // パラメータのキー一覧
  const paramKeys = Object.keys(results[0].params || {});

  const fmtPF = v => v == null ? '-' : (isFinite(v) ? v.toFixed(2) : '∞');
  const fmtWR = v => v == null ? '-' : (v * 100).toFixed(1) + '%';
  const fmtP  = v => v == null ? '-' : (v >= 0 ? '+' : '') + v.toFixed(1) + 'p';

  const clsPF = v => v != null && v >= 1    ? 'style="color:#4ade80"' : 'style="color:#f87171"';
  const clsWR = v => v != null && v >= 0.5  ? 'style="color:#4ade80"' : 'style="color:#f87171"';
  const clsPN = v => v != null && v >= 0    ? 'style="color:#4ade80"' : 'style="color:#f87171"';

  const paramThs = paramKeys.map(k => `<th>${k}</th>`).join('');
  const rows = results.map((r, i) => {
    const rankCls = i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : '';
    const paramCells = paramKeys.map(k => `<td><strong>${r.params[k] ?? '-'}</strong></td>`).join('');
    const paramsJson = JSON.stringify(r.params).replace(/"/g, '&quot;');
    return `<tr class="${rankCls}">
      <td style="color:#64748b">${i+1}</td>
      ${paramCells}
      <td>${r.total_trades}</td>
      <td ${clsWR(r.win_rate)}>${fmtWR(r.win_rate)}</td>
      <td ${clsPF(r.profit_factor)}>${fmtPF(r.profit_factor)}</td>
      <td ${clsPN(r.expectancy_pips)}>${fmtP(r.expectancy_pips)}</td>
      <td ${clsPN(r.net_profit_pips)}>${fmtP(r.net_profit_pips)}</td>
      <td ${clsPN(r.max_drawdown_pips ? -r.max_drawdown_pips : null)}>${r.max_drawdown_pips != null ? r.max_drawdown_pips.toFixed(1) + 'p' : '-'}</td>
      <td><button class="opt-apply-btn" onclick="applyOptParams('${paramsJson}')">適用</button></td>
    </tr>`;
  }).join('');

  document.getElementById('section-opt-result').innerHTML = `
    <div class="form-card">
      <h3>最適化結果（${res.pair} ${res.timeframe} / ${res.total_combinations} 組み合わせ / 最適化指標: ${objLabel}）</h3>
      <div class="tbl-wrap">
        <table class="opt-result-tbl">
          <thead><tr>
            <th>#</th>${paramThs}
            <th>取引数</th><th>勝率</th><th>PF</th><th>期待値</th><th>純損益</th><th>最大DD</th><th>適用</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
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
  // ローソク足パターン（戻り値: 検出=1, 未検出=0）→ 比較は「≥ 1」を推奨
  BULLISH_ENGULFING:    { label:'強気の包み足',     params:[], is_pattern:true },
  BEARISH_ENGULFING:    { label:'弱気の包み足',     params:[], is_pattern:true },
  HAMMER:               { label:'ハンマー',         params:[], is_pattern:true },
  INVERTED_HAMMER:      { label:'逆ハンマー',       params:[], is_pattern:true },
  DOJI:                 { label:'十字線（ドジ）',   params:[], is_pattern:true },
  THREE_WHITE_SOLDIERS: { label:'三白兵',           params:[], is_pattern:true },
  THREE_BLACK_CROWS:    { label:'三羽烏',           params:[], is_pattern:true },
  BULLISH_PIN_BAR:      { label:'ピンバー（陽線）', params:[], is_pattern:true },
  BEARISH_PIN_BAR:      { label:'ピンバー（陰線）', params:[], is_pattern:true },
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

/* ---------- 指標セレクト用 optgroup HTML ---------- */
function buildIndOptions(excludePatterns) {
  const techKeys = ['RSI','EMA','SMA','MACD_HIST','MACD_LINE','MACD_SIGNAL',
                    'STOCH_K','STOCH_D','CCI','WILLIAMS_R','ATR',
                    'BB_UPPER','BB_LOWER','BB_MID','CLOSE','HIGH','LOW'];
  const patKeys  = ['BULLISH_ENGULFING','BEARISH_ENGULFING','HAMMER','INVERTED_HAMMER',
                    'DOJI','THREE_WHITE_SOLDIERS','THREE_BLACK_CROWS',
                    'BULLISH_PIN_BAR','BEARISH_PIN_BAR'];
  const techOpts = techKeys.filter(k => IND[k])
    .map(k => `<option value="${k}">${IND[k].label}</option>`).join('');
  if (excludePatterns) return `<optgroup label="テクニカル指標">${techOpts}</optgroup>`;
  const patOpts = patKeys.filter(k => IND[k])
    .map(k => `<option value="${k}">${IND[k].label}</option>`).join('');
  return `<optgroup label="テクニカル指標">${techOpts}</optgroup>
          <optgroup label="ローソク足パターン (検出=1)">${patOpts}</optgroup>`;
}

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
        ${buildIndOptions(false)}
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
      ${buildRhsCross(id)}
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
  const indKey = sel.value;
  document.getElementById(rowId + '-params').innerHTML = buildParamInputs(indKey, rowId);
  // パターン指標: 比較を「≥ 1」に自動設定（0/1 値のため）
  if ((IND[indKey] || {}).is_pattern) {
    const cmpSel = document.getElementById(rowId + '-cmp');
    if (cmpSel) { cmpSel.value = 'greater_than_or_equal'; onCmpChange(rowId); }
    const valEl = document.getElementById(rowId + '-val');
    if (valEl) valEl.value = '1';
  }
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

/* ---------- 比較変更 → RHS 再描画（全比較タイプで統一） ---------- */
function onCmpChange(rowId) {
  document.getElementById(rowId + '-rhs').innerHTML = buildRhsCross(rowId);
}

/* ---------- RHS: 固定値 または 別指標（全比較タイプ共通） ---------- */
function buildRhsCross(rowId) {
  return `<label>比較値</label>
    <select id="${rowId}-cmp-ind" onchange="onCmpIndChange('${rowId}')">
      <option value="">--- 固定値 ---</option>
      ${buildIndOptions(true)}
    </select>
    <div id="${rowId}-cross-val" style="margin-top:4px">
      <input type="number" id="${rowId}-val" value="0" step="0.1" style="width:100%">
    </div>
    <div id="${rowId}-cmp-ind-params" style="margin-top:4px"></div>`;
}

/* ---------- 比較先指標変更 → 固定値入力の表示切り替え + パラメータ描画 ---------- */
function onCmpIndChange(rowId) {
  const sel = document.getElementById(rowId + '-cmp-ind');
  const valDiv = document.getElementById(rowId + '-cross-val');
  const paramsDiv = document.getElementById(rowId + '-cmp-ind-params');
  if (valDiv) valDiv.style.display = sel.value ? 'none' : 'block';
  if (paramsDiv) {
    if (sel.value) {
      const ps = (IND[sel.value] || {}).params || [];
      paramsDiv.innerHTML = ps.length ? ps.map(p =>
        `<div style="display:flex;align-items:center;gap:6px;margin-top:2px">
           <span style="font-size:10px;color:#64748b;min-width:32px">${p.l}</span>
           <input type="number" id="${rowId}-cind-p-${p.n}" value="${p.d}"
                  step="${p.n==='std'?0.1:1}" style="width:60px">
         </div>`).join('') : '';
    } else { paramsDiv.innerHTML = ''; }
  }
}

/* ---------- 実行ボタン表示制御 ---------- */
function updateActions() {
  const hasCond = document.querySelectorAll('#cond-list .cond-row').length > 0;
  document.getElementById('section-actions').style.display = hasCond ? 'flex' : 'none';
  document.getElementById('section-optimize').style.display = hasCond ? 'block' : 'none';
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

    // params
    const ps = (IND[indKey] || {}).params || [];
    const params = {};
    ps.forEach(p => {
      const el = document.getElementById(rowId + '-p-' + p.n);
      if (el) params[p.n] = parseFloat(el.value);
    });

    // value / compare_to_indicator（全比較タイプで共通処理）
    let value = null;
    let compare_to_indicator = null;
    let compare_to_params    = null;

    const cmpIndSel = document.getElementById(rowId + '-cmp-ind');
    if (cmpIndSel && cmpIndSel.value) {
      compare_to_indicator = cmpIndSel.value;
      const cps = (IND[cmpIndSel.value] || {}).params || [];
      compare_to_params = {};
      cps.forEach(p => {
        const el = document.getElementById(rowId + '-cind-p-' + p.n);
        compare_to_params[p.n] = el ? parseFloat(el.value) : p.d;
      });
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
let _equityChart  = null;
let _lastInitialCapital = 1000000;
let _currentOhlcv = [];

function renderChart(ohlcv, chartData) {
  _currentOhlcv = ohlcv;
  /* ---- チャートコンテナを描画 ---- */
  document.getElementById('section-chart').innerHTML =
    `<div class="chart-card">
       <h3>チャート（ローソク足 + トレードシグナル）</h3>
       <div id="tv-chart"></div>
       <div style="margin-top:14px;border-top:1px solid #1e293b;padding-top:12px">
         <div style="font-size:11px;color:#64748b;margin-bottom:6px">エクイティカーブ（残高推移）</div>
         <div id="equity-chart"></div>
       </div>
     </div>`;

  /* ---- 既存チャートを破棄 ---- */
  if (_lwChart)    { try { _lwChart.remove();    } catch(e){} _lwChart    = null; }
  if (_equityChart){ try { _equityChart.remove(); } catch(e){} _equityChart = null; }

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

/* ---------- エクイティカーブ描画 ---------- */
function renderEquityCurve(trades, initialCapital) {
  const container = document.getElementById('equity-chart');
  if (!container) return;
  if (_equityChart) { try { _equityChart.remove(); } catch(e){} _equityChart = null; }
  if (!trades || !trades.length) return;

  const data = [];
  // 開始点（初期資金）
  const firstT = toChartTime(trades[0].entry_time);
  if (firstT) data.push({ time: firstT - 1, value: initialCapital });
  // 各トレード決済時点
  trades.forEach(t => {
    const tm = toChartTime(t.exit_time);
    if (tm) data.push({ time: tm, value: t.running_capital });
  });
  data.sort((a, b) => a.time - b.time);
  if (data.length < 2) return;

  _equityChart = LightweightCharts.createChart(container, {
    width:  container.clientWidth || 900,
    height: 130,
    layout:     { background: { color: '#0f172a' }, textColor: '#94a3b8' },
    grid:       { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
    rightPriceScale: { borderColor: '#334155' },
    timeScale:  { borderColor: '#334155', timeVisible: true, secondsVisible: false },
    handleScroll: false,
    handleScale:  false,
    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
  });

  const profitColor = data[data.length-1].value >= initialCapital ? '#4ade80' : '#f87171';
  const topBg       = data[data.length-1].value >= initialCapital
    ? 'rgba(74,222,128,0.2)' : 'rgba(248,113,113,0.2)';

  const eq = _equityChart.addAreaSeries({
    lineColor:   profitColor,
    topColor:    topBg,
    bottomColor: 'rgba(15,23,42,0.0)',
    lineWidth: 2,
  });
  eq.setData(data);

  new ResizeObserver(() => {
    if (_equityChart && container) _equityChart.resize(container.clientWidth, 130);
  }).observe(container);
}

/* ---------- トレード行クリック → チャートジャンプ ---------- */
function jumpToBar(entryTime) {
  if (!_lwChart) return;
  const targetT = toChartTime(entryTime);
  if (!targetT) return;
  // _currentOhlcv から最近傍バーのインデックスを探す
  let bestIdx = 0, bestDiff = Infinity;
  _currentOhlcv.forEach((d, i) => {
    const t = toChartTime(d.timestamp || d.time || d.date);
    if (t != null) {
      const diff = Math.abs(t - targetT);
      if (diff < bestDiff) { bestDiff = diff; bestIdx = i; }
    }
  });
  _lwChart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, bestIdx - 50),
    to:   Math.min(_currentOhlcv.length - 1, bestIdx + 50),
  });
}

/* ---------- 初期条件を1つ追加 ---------- */
addCondition();

/* =====================================================================
   12: プリセット戦略
   ===================================================================== */

const PRESETS = {
  macd_trend: {
    direction: 'BOTH', logic: 'AND',
    conditions: [
      { indicator:'MACD_LINE', params:{fast:12,slow:26,signal:9}, comparison:'crosses_above', value:0, compare_to_indicator:null },
    ],
    sl: { type:'atr',   atr_period:14, atr_multiplier:2.0 },
    tp: { type:'rr',    rr_ratio:2.0 },
    trail: { enabled:false },
    desc: 'MACDラインがゼロ線を上抜け（下抜け）でエントリー。ATR×2 SL / RR2.0倍 TP。',
  },
  cci_momentum: {
    direction: 'BOTH', logic: 'AND',
    conditions: [
      { indicator:'CCI', params:{period:20}, comparison:'crosses_above', value:100, compare_to_indicator:null },
    ],
    sl: { type:'atr',   atr_period:14, atr_multiplier:1.5 },
    tp: { type:'atr',   atr_period:14, atr_multiplier:3.5 },
    trail: { enabled:true, trail_pips:15 },
    desc: 'CCI(20)が100を上抜けで強トレンド参加。ATRトレーリングで利益確保。',
  },
  rsi_reversal: {
    direction: 'BUY', logic: 'AND',
    conditions: [
      { indicator:'RSI', params:{period:14}, comparison:'less_than', value:30, compare_to_indicator:null },
    ],
    sl: { type:'fixed', pips:25 },
    tp: { type:'rr',    rr_ratio:1.5 },
    trail: { enabled:false },
    desc: 'RSI(14)が30未満で過売り判断。固定25pips SL / RR1.5倍 TP。',
  },
  stoch_reversal: {
    direction: 'BUY', logic: 'AND',
    conditions: [
      { indicator:'STOCH_K', params:{k_period:14,d_period:3,smooth_k:3}, comparison:'less_than', value:20, compare_to_indicator:null },
    ],
    sl: { type:'fixed', pips:20 },
    tp: { type:'rr',    rr_ratio:2.0 },
    trail: { enabled:true, trail_pips:10 },
    desc: 'Stoch %K(14)が20未満で過売り判断。トレーリング10pipsで利益確保。',
  },
  bb_breakout: {
    direction: 'BUY', logic: 'AND',
    conditions: [
      // CLOSE の params が空のため BB_UPPER の params はデフォルト値(period:20,std:2.0)が使われる
      { indicator:'CLOSE', params:{}, comparison:'crosses_above', compare_to_indicator:'BB_UPPER', compare_to_params:{period:20,std:2.0}, value:null },
    ],
    sl: { type:'atr',   atr_period:14, atr_multiplier:2.0 },
    tp: { type:'rr',    rr_ratio:2.5 },
    trail: { enabled:false },
    desc: '終値がBB(20, 2σ)上バンドを上抜けでブレイクアウトエントリー。ATR×2 SL。',
  },
};

/* ---------- プリセット読み込み ---------- */
function loadPreset(key) {
  if (!key) return;
  const p = PRESETS[key];
  if (!p) return;

  // 条件リセット
  document.getElementById('cond-list').innerHTML = '';
  _condSeq = 0;

  // 方向・ロジック
  document.getElementById('direction').value = p.direction;
  setLogic(p.logic || 'AND');

  // 条件追加
  (p.conditions || []).forEach(addConditionFromPreset);

  // SL
  restoreSlConfig(p.sl);

  // TP
  restoreTpConfig(p.tp);

  // トレーリング
  const tc = p.trail || {};
  document.getElementById('trailing_enabled').checked = !!tc.enabled;
  onTrailingChange();
  if (tc.enabled && tc.trail_pips) document.getElementById('trail_pips').value = tc.trail_pips;

  document.getElementById('preset-select').value = '';
  updateActions();
}

/* ---------- 条件データからフォーム行を生成 ---------- */
function addConditionFromPreset(cond) {
  addCondition();
  const rowId = 'cond-' + _condSeq;
  const row   = document.getElementById(rowId);

  // 指標
  const indSel = row.querySelector('select');
  if (indSel && cond.indicator) { indSel.value = cond.indicator; onIndChange(indSel, rowId); }

  // パラメータ
  Object.entries(cond.params || {}).forEach(([k, v]) => {
    const el = document.getElementById(rowId + '-p-' + k);
    if (el) el.value = v;
  });

  // 比較演算子
  const cmpSel = document.getElementById(rowId + '-cmp');
  if (cmpSel && cond.comparison) { cmpSel.value = cond.comparison; onCmpChange(rowId); }

  // RHS（全比較タイプで共通）
  if (cond.compare_to_indicator) {
    const cmpIndSel = document.getElementById(rowId + '-cmp-ind');
    if (cmpIndSel) { cmpIndSel.value = cond.compare_to_indicator; onCmpIndChange(rowId); }
    // 比較先指標のパラメータを復元
    Object.entries(cond.compare_to_params || {}).forEach(([k, v]) => {
      const el = document.getElementById(rowId + '-cind-p-' + k);
      if (el) el.value = v;
    });
  } else {
    const valEl = document.getElementById(rowId + '-val');
    if (valEl && cond.value !== null && cond.value !== undefined) valEl.value = cond.value;
  }
}

/* =====================================================================
   11: 戦略保存 / 読込
   ===================================================================== */

let _savedList = [];

/* --- 期間モード切替 --- */
function setRangeMode(mode) {
  const isDate = mode === 'date';
  document.getElementById('range-btn-limit').classList.toggle('active', !isDate);
  document.getElementById('range-btn-date' ).classList.toggle('active',  isDate);
  document.getElementById('range-limit-wrap').style.display = isDate ? 'none'  : '';
  document.getElementById('range-date-wrap' ).style.display = isDate ? ''      : 'none';
}

function getRangeParams() {
  const isDate = document.getElementById('range-btn-date').classList.contains('active');
  if (isDate) {
    const s = document.getElementById('date-start').value;
    const e = document.getElementById('date-end').value;
    if (!s || !e) throw new Error('開始日・終了日を両方入力してください');
    if (s > e)    throw new Error('開始日は終了日より前にしてください');
    return { start_date: s, end_date: e, limit: null };
  }
  return { limit: parseInt(document.getElementById('limit').value, 10), start_date: null, end_date: null };
}

/* --- 保存済みリストを取得してドロップダウンを更新 --- */
async function loadSavedStrategies() {
  try {
    const res = await fetch('/admin/api.php', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'get_strategies'}),
    }).then(r => r.json());
    if (!res.ok) return;
    _savedList = res.strategies || [];
    const sel = document.getElementById('saved-select');
    sel.innerHTML = '<option value="">-- 読み込む --</option>' +
      _savedList.map(s =>
        `<option value="${s.id}">[${s.created_at.slice(0,10)}] ${s.name}</option>`
      ).join('');
  } catch(e) {}
}

/* --- 保存済み戦略を適用 --- */
async function applySavedStrategy(id) {
  if (!id) return;
  document.getElementById('saved-select').value = '';
  try {
    const res = await fetch('/admin/api.php', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'load_strategy', id: parseInt(id, 10)}),
    }).then(r => r.json());
    if (!res.ok) { showErr(res.error || '読み込みエラー'); return; }
    restoreFromConfig(res.config);
  } catch(e) { showErr('読み込みエラー: ' + e.message); }
}

/* --- 保存モーダル --- */
async function showSaveModal() {
  document.getElementById('save-name').value = '';
  document.getElementById('save-err').textContent = '';
  // 指標リストを取得してセレクタを更新
  const sel = document.getElementById('save-linked-ind');
  if (sel.options.length <= 1) {
    try {
      const res = await fetch('/admin/api.php', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'get_indicators'}),
      }).then(r => r.json());
      if (res.ok && res.indicators) {
        res.indicators.forEach(ind => {
          const opt = document.createElement('option');
          opt.value = ind.name;
          opt.textContent = ind.display || ind.name;
          sel.appendChild(opt);
        });
      }
    } catch(_) {}
  }
  document.getElementById('save-modal').style.display = 'flex';
  setTimeout(() => document.getElementById('save-name').focus(), 80);
}
function closeSaveModal() { document.getElementById('save-modal').style.display = 'none'; }

async function confirmSave() {
  const name      = document.getElementById('save-name').value.trim();
  const linkedInd = document.getElementById('save-linked-ind').value;
  const errEl     = document.getElementById('save-err');
  if (!name) { errEl.textContent = '戦略名を入力してください'; return; }

  let config;
  try {
    const rp = getRangeParams();
    config = {
      pairs:      getSelectedPairs(),
      timeframe:  document.getElementById('timeframe').value,
      range_mode: rp.start_date ? 'date' : 'limit',
      limit:      rp.limit ?? parseInt(document.getElementById('limit').value, 10),
      start_date: rp.start_date || null,
      end_date:   rp.end_date   || null,
      sim_params: {
        initial_capital:  parseFloat(document.getElementById('initial_capital').value),
        pip_value:        parseFloat(document.getElementById('pip_value').value),
        max_bars_to_exit: parseInt(document.getElementById('max_bars_to_exit').value, 10),
      },
      strategy:  buildStrategyConfig(),
      filter_ui: captureFilterUI(),
    };
  } catch(e) { errEl.textContent = e.message; return; }

  try {
    const body = {action: 'save_strategy', name, config};
    if (linkedInd) body.linked_indicator = linkedInd;
    if (_lastBtSummary) body.bt_result = _lastBtSummary;

    const res = await fetch('/admin/api.php', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    }).then(r => r.json());
    if (!res.ok) { errEl.textContent = res.error || '保存エラー'; return; }
    closeSaveModal();
    await loadSavedStrategies();
  } catch(e) { errEl.textContent = '通信エラー: ' + e.message; }
}

/* --- フィルターUI状態の取得/復元 --- */
function captureFilterUI() {
  return {
    session:    document.getElementById('f-session').value,
    start_hour: parseInt(document.getElementById('f-start-hour').value, 10),
    end_hour:   parseInt(document.getElementById('f-end-hour').value, 10),
    weekdays:   [...document.querySelectorAll('#weekday-btns .wd-btn.active')].map(b => parseInt(b.dataset.wd, 10)),
    atr_period: parseInt(document.getElementById('f-atr-period').value, 10),
    atr_min:    parseFloat(document.getElementById('f-atr-min').value) || 0,
    atr_max:    parseFloat(document.getElementById('f-atr-max').value) || 0,
  };
}
function restoreFilterUI(f) {
  if (!f) return;
  document.getElementById('f-session').value = f.session || '';
  onSessionPreset();
  if (f.session === 'custom') {
    document.getElementById('f-start-hour').value = f.start_hour || 9;
    document.getElementById('f-end-hour').value   = f.end_hour   || 17;
  }
  const wds = f.weekdays ?? [0,1,2,3,4,5,6];
  document.querySelectorAll('#weekday-btns .wd-btn').forEach(b => {
    b.classList.toggle('active', wds.includes(parseInt(b.dataset.wd, 10)));
  });
  document.getElementById('f-atr-period').value = f.atr_period || 14;
  document.getElementById('f-atr-min').value    = f.atr_min    || 0;
  document.getElementById('f-atr-max').value    = f.atr_max    || 0;
}

/* --- SL/TP/トレーリング復元 --- */
function restoreSlConfig(sl) {
  if (!sl) return;
  document.getElementById('sl_type').value = sl.type;
  onSlTypeChange();
  if (sl.type === 'fixed')          document.getElementById('sl_pips').value       = sl.pips ?? 20;
  if (sl.type === 'recentHighLow') {
    document.getElementById('sl_lookback').value = sl.lookback_bars ?? 10;
    document.getElementById('sl_buffer').value   = sl.buffer_pips   ?? 3;
  }
  if (sl.type === 'atr') {
    document.getElementById('sl_atr_period').value = sl.atr_period     ?? 14;
    document.getElementById('sl_atr_mult').value   = sl.atr_multiplier ?? 1.5;
  }
}
function restoreTpConfig(tp) {
  if (!tp) return;
  document.getElementById('tp_type').value = tp.type;
  onTpTypeChange();
  if (tp.type === 'rr') {
    const v = parseFloat(tp.rr_ratio).toFixed(1);
    const opt = [...document.getElementById('tp_rr_ratio').options].find(o => o.value === v);
    if (opt) document.getElementById('tp_rr_ratio').value = v;
  }
  if (tp.type === 'fixed') document.getElementById('tp_pips').value = tp.pips ?? 40;
  if (tp.type === 'atr') {
    document.getElementById('tp_atr_period').value = tp.atr_period     ?? 14;
    document.getElementById('tp_atr_mult').value   = tp.atr_multiplier ?? 3.0;
  }
}

/* --- 保存済みからフォームを完全復元 --- */
function restoreFromConfig(cfg) {
  if (!cfg) return;
  const s = cfg.strategy || {};

  // ペア
  document.querySelectorAll('.pair-cb').forEach(cb => {
    cb.checked = (cfg.pairs || ['USDJPY']).includes(cb.value);
  });
  // 基本設定
  if (cfg.timeframe) document.getElementById('timeframe').value = cfg.timeframe;
  // 期間モード復元
  if (cfg.range_mode === 'date' && cfg.start_date) {
    setRangeMode('date');
    document.getElementById('date-start').value = cfg.start_date || '';
    document.getElementById('date-end'  ).value = cfg.end_date   || '';
  } else {
    setRangeMode('limit');
    if (cfg.limit) document.getElementById('limit').value = cfg.limit;
  }
  if (cfg.sim_params) {
    document.getElementById('initial_capital').value  = cfg.sim_params.initial_capital  || 1000000;
    document.getElementById('pip_value').value        = cfg.sim_params.pip_value        || 100;
    document.getElementById('max_bars_to_exit').value = cfg.sim_params.max_bars_to_exit || 200;
  }
  // 方向・ロジック・条件
  if (s.direction) document.getElementById('direction').value = s.direction;
  setLogic((s.entry_conditions || {}).logic || 'AND');
  document.getElementById('cond-list').innerHTML = '';
  _condSeq = 0;
  ((s.entry_conditions || {}).conditions || []).forEach(addConditionFromPreset);

  // SL / TP / トレーリング
  restoreSlConfig(s.sl_config);
  restoreTpConfig(s.tp_config);
  const t = s.trailing_config || {};
  document.getElementById('trailing_enabled').checked = !!t.enabled;
  onTrailingChange();
  if (t.enabled && t.trail_pips) document.getElementById('trail_pips').value = t.trail_pips;

  // フィルター
  restoreFilterUI(cfg.filter_ui);

  updateActions();
}

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
async function fetchOnePair(pair, timeframe, rangeParams, strategy, simParams) {
  const payload = {
    action: 'bt_v2', pair, timeframe,
    strategy_config: strategy,
    sim_params: simParams,
  };
  if (rangeParams.start_date) {
    payload.start_date = rangeParams.start_date;
    payload.end_date   = rangeParams.end_date;
  } else {
    payload.limit = rangeParams.limit;
  }
  const res = await fetch('/admin/api.php', {
    method:  'POST',
    headers: {'Content-Type':'application/json'},
    body:    JSON.stringify(payload),
  }).then(r => r.json());
  if (!res.ok) throw new Error(`[${pair}] ${res.error || 'APIエラー'}`);
  return res;
}

/* ---------- メインエントリーポイント（複数ペア対応） ---------- */
let _lastTrades   = [];
let _lastOhlcv    = [];
let _lastMetrics  = null;
let _lastBtSummary = null;  // 保存用サマリー（指標ページ比較コンテンツ用）
let _multiResults = {};

async function runBacktest() {
  hideErr();

  const pairs = getSelectedPairs();
  if (!pairs.length) { showErr('通貨ペアを1つ以上選択してください'); return; }

  let strategy;
  try { strategy = buildStrategyConfig(); }
  catch(e) { showErr(e.message); return; }

  const timeframe = document.getElementById('timeframe').value;
  let rangeParams;
  try { rangeParams = getRangeParams(); }
  catch(e) { showErr(e.message); return; }

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
      results[pair] = await fetchOnePair(pair, timeframe, rangeParams, strategy, simParams);
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
    _lastInitialCapital = simParams.initial_capital;
    renderMetrics(r.metrics, r.bars_used, r.data_from, r.data_to);
    renderChart(_lastOhlcv, r.chart_data || {});
    renderEquityCurve(_lastTrades, _lastInitialCapital);
    renderTrades(_lastTrades);
    renderSignalPanel(pairs[0], timeframe, strategy, r.metrics || {});
  } else {
    _multiResults = results;
    renderMultiPairResults(results, timeframe);
    document.getElementById('section-signal').style.display = 'none';
  }

  // 保存用サマリーを更新
  const _pairMetrics = {};
  for (const p of pairs) {
    const m = (results[p] || {}).metrics || {};
    _pairMetrics[p] = {
      win_rate:      m.win_rate      ?? null,
      profit_factor: m.profit_factor ?? null,
      total_trades:  m.total_trades  ?? 0,
      total_profit:  m.total_profit  ?? null,
      max_drawdown:  m.max_drawdown  ?? null,
    };
  }
  const _allTrades = pairs.reduce((s, p) => s + ((_pairMetrics[p] || {}).total_trades || 0), 0);
  const _allWins   = pairs.reduce((s, p) => {
    const m = (results[p] || {}).metrics || {};
    return s + (m.win_trades || Math.round((m.win_rate || 0) * (m.total_trades || 0)));
  }, 0);
  _lastBtSummary = {
    pairs:    pairs,
    timeframe: timeframe,
    per_pair: _pairMetrics,
    aggregate: {
      win_rate:      _allTrades > 0 ? _allWins / _allTrades : null,
      total_trades:  _allTrades,
    },
  };

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
  renderEquityCurve(r0.trades || [], _lastInitialCapital);

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
  if (r) {
    renderChart(r.ohlcv || [], r.chart_data || {});
    renderEquityCurve(r.trades || [], _lastInitialCapital);
  }
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
  const reasonTags = reasons => (reasons || [])
    .map(r => `<span class="reason-tag">${r}</span>`).join('') || '<span style="color:#475569">-</span>';

  const rows = trades.map((t, i) => {
    const dirBdg = t.direction === 'BUY'
      ? '<span class="bdg bdg-buy">BUY</span>'
      : '<span class="bdg bdg-sell">SELL</span>';
    const pnlCls = t.pnl_pips >= 0 ? 'style="color:#4ade80"' : 'style="color:#f87171"';
    const entryEsc = (t.entry_time || '').replace(/'/g, "\\'");
    return `<tr class="clickable" onclick="jumpToBar('${entryEsc}')">
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
      <td>${reasonTags(t.entry_reasons)}</td>
    </tr>`;
  }).join('');
  container.innerHTML = `
    <div class="tbl-wrap">
      <table class="trade-tbl">
        <thead><tr>
          <th>#</th><th>方向</th><th>エントリー時刻</th><th>EP</th>
          <th>SL</th><th>TP</th><th>クローズ時刻</th><th>XP</th>
          <th>決済理由</th><th>pips</th><th>損益</th><th>残高</th><th>条件ID</th>
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

function renderMetrics(m, barsUsed, dataFrom, dataTo) {
  const wr = m.win_rate != null ? (m.win_rate * 100).toFixed(1) : '-';
  const wrCls = m.win_rate >= 0.5 ? 'green' : 'red';
  const pf = m.profit_factor == null ? '-' : (isFinite(m.profit_factor) ? m.profit_factor.toFixed(2) : '∞');
  const pfCls = (m.profit_factor == null || m.profit_factor < 1) ? 'red' : 'green';
  const net = m.net_profit_pips != null ? (m.net_profit_pips >= 0 ? '+' : '') + m.net_profit_pips.toFixed(1) + ' pips' : '-';
  const netCls = m.net_profit_pips >= 0 ? 'green' : 'red';
  const dd = m.max_drawdown_pips != null ? m.max_drawdown_pips.toFixed(1) + ' pips' : '-';
  const rangeTxt = (dataFrom && dataTo) ? `${dataFrom} 〜 ${dataTo}` : `${barsUsed} bar`;

  document.getElementById('section-metrics').innerHTML = `
    <div style="font-size:11px;color:#64748b;margin-bottom:8px;padding:6px 10px;background:#1e293b;border-radius:6px;display:inline-block">
      📅 検証期間: <strong style="color:#94a3b8">${rangeTxt}</strong>（${barsUsed} bar）
    </div>
    <div class="metrics-grid">
      ${mc('総取引数', m.total_trades + '回', '')}
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

/* =====================================================================
   13: リアルタイムシグナル連携
   ===================================================================== */

let _signalStrategyConfig = null;
let _signalPair           = 'USDJPY';
let _signalTimeframe      = '1hr';
let _signalMetrics        = {};

/* シグナルパネルを描画（バックテスト完了後に呼ばれる） */
function renderSignalPanel(pair, timeframe, strategy, metrics) {
  _signalPair           = pair;
  _signalTimeframe      = timeframe;
  _signalStrategyConfig = strategy;
  _signalMetrics        = metrics;

  const wr    = metrics.win_rate != null ? (metrics.win_rate * 100).toFixed(1) + '%' : '-';
  const pf    = metrics.profit_factor != null
    ? (isFinite(metrics.profit_factor) ? metrics.profit_factor.toFixed(2) : '∞') : '-';
  const total = metrics.total_trades ?? '-';

  const el = document.getElementById('section-signal');
  el.style.display = 'block';
  el.innerHTML = `
    <div class="signal-panel">
      <h3>リアルタイムシグナル連携</h3>
      <p style="font-size:12px;color:#64748b;margin-bottom:14px">
        現在の戦略設定を使って最新ローソク足でシグナルを評価します。<br>
        条件成立時は <code style="background:#0f172a;padding:1px 5px;border-radius:3px;font-size:11px">trading_signals</code> テーブルに登録され、公開サイトのシグナル一覧に反映されます。
      </p>
      <div class="signal-info-grid">
        <div class="signal-info-item"><div class="si-label">通貨ペア</div><div class="si-val">${pair}</div></div>
        <div class="signal-info-item"><div class="si-label">タイムフレーム</div><div class="si-val">${timeframe}</div></div>
        <div class="signal-info-item"><div class="si-label">BT 勝率 / PF</div><div class="si-val">${wr} / ${pf}</div></div>
        <div class="signal-info-item"><div class="si-label">BT 取引数</div><div class="si-val">${total}回</div></div>
        <div class="signal-info-item"><div class="si-label">方向</div><div class="si-val">${strategy.direction || 'BOTH'}</div></div>
        <div class="signal-info-item"><div class="si-label">条件数</div><div class="si-val">${(strategy.entry_conditions?.conditions || []).length}件</div></div>
      </div>
      <div id="signal-result-area"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-top:4px">
        <button class="btn-signal" id="btn-check-signal" onclick="checkAndRegisterSignal()">
          現在のシグナルを確認・登録
        </button>
        <span id="signal-status-txt" class="signal-status-txt"></span>
      </div>
      <div class="signal-hint">
        ※ 保存した戦略を定期的にシグナル生成するには、<code style="background:#0f172a;padding:1px 4px;border-radius:3px">run_v2_signal.py</code> を cron で実行してください。<br>
        ※ シグナルの有効期限: 5min=1h / 1hr=6h / 4hr=24h / daily=72h
      </div>
    </div>`;
}

/* シグナルを評価してDBに登録 */
async function checkAndRegisterSignal() {
  if (!_signalStrategyConfig) return;

  const btn    = document.getElementById('btn-check-signal');
  const status = document.getElementById('signal-status-txt');
  btn.disabled = true;
  status.textContent = '評価中...';
  document.getElementById('signal-result-area').innerHTML = '';

  // 戦略名を取得（保存済み選択があればそれを使用、なければ無名）
  const savedSel = document.getElementById('saved-select');
  const savedOpt = savedSel.selectedIndex > 0 ? savedSel.options[savedSel.selectedIndex].text : null;
  const strategyName = savedOpt || `v2_${_signalPair}_${_signalTimeframe}`;

  const payload = {
    action:          'bt_v2_signal',
    pair:            _signalPair,
    timeframe:       _signalTimeframe,
    limit:           parseInt(document.getElementById('limit').value, 10),
    strategy_config: _signalStrategyConfig,
    strategy_name:   strategyName,
    win_rate:        _signalMetrics.win_rate  ?? null,
    total_trades:    _signalMetrics.total_trades ?? 0,
  };

  try {
    const res = await fetch('/admin/api.php', {
      method:  'POST',
      headers: {'Content-Type':'application/json'},
      body:    JSON.stringify(payload),
    }).then(r => r.json());

    btn.disabled = false;

    if (!res.ok) {
      status.textContent = '❌ ' + (res.error || 'エラー');
      document.getElementById('signal-result-area').innerHTML =
        `<div style="background:#7f1d1d;border:1px solid #ef4444;border-radius:8px;padding:10px 14px;font-size:12px;color:#fca5a5;margin-bottom:12px;white-space:pre-wrap">${res.error || 'エラー'}${res.detail ? '\n\n' + res.detail : ''}</div>`;
      return;
    }

    status.textContent = '✅ 完了';
    renderSignalResult(res);

  } catch(e) {
    btn.disabled = false;
    status.textContent = '❌ ' + e.message;
  }
}

/* シグナル評価結果を描画 */
function renderSignalResult(res) {
  const area  = document.getElementById('signal-result-area');
  const fired = res.signal_fired;
  const stype = res.signal_type;   // "BUY" / "SELL" / null

  const badgeCls  = stype === 'BUY' ? 'buy' : stype === 'SELL' ? 'sell' : 'neutral';
  const badgeTxt  = stype ? `▲ ${stype}` : '— シグナルなし（NEUTRAL）';
  const priceStr  = res.current_price != null ? res.current_price.toFixed(3) : '-';
  const slStr     = res.sl_price != null ? res.sl_price.toFixed(3) + (res.sl_pips ? ` (${res.sl_pips.toFixed(1)}p)` : '') : '-';
  const tpStr     = res.tp_price != null ? res.tp_price.toFixed(3) + (res.tp_pips ? ` (${res.tp_pips.toFixed(1)}p)` : '') : '-';
  const confStr   = res.confidence != null ? res.confidence.toFixed(1) : '-';
  const matchStr  = (res.conditions_matched || []).join(', ') || '-';
  const idStr     = res.signal_id ? `#${res.signal_id}` : '-';
  const newStr    = res.signal_id ? (res.is_new ? '新規登録' : '更新済み') : '登録なし';

  let regInfo = '';
  if (fired && res.signal_id) {
    regInfo = `<div style="background:rgba(74,222,128,.07);border:1px solid rgba(74,222,128,.3);border-radius:8px;padding:10px 14px;font-size:12px;color:#86efac;margin-bottom:12px">
      ✅ シグナル ID ${idStr} を trading_signals に${res.is_new ? '登録' : '更新'}しました（戦略名: ${escHtml(res.strategy_name)}）
    </div>`;
  } else if (!fired) {
    regInfo = `<div style="background:rgba(100,116,139,.1);border:1px solid #334155;border-radius:8px;padding:10px 14px;font-size:12px;color:#94a3b8;margin-bottom:12px">
      条件不成立のため新規シグナルは登録されませんでした。既存シグナルがあれば無効化されます。
    </div>`;
  }

  area.innerHTML = `
    ${regInfo}
    <div class="signal-badge ${badgeCls}" style="margin-bottom:12px">${badgeTxt}</div>
    <div class="signal-info-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:12px">
      <div class="signal-info-item"><div class="si-label">現在価格</div><div class="si-val">${priceStr}</div></div>
      <div class="signal-info-item"><div class="si-label">SL</div><div class="si-val" style="font-size:12px">${slStr}</div></div>
      <div class="signal-info-item"><div class="si-label">TP</div><div class="si-val" style="font-size:12px">${tpStr}</div></div>
      <div class="signal-info-item"><div class="si-label">信頼度スコア</div><div class="si-val">${confStr}</div></div>
      <div class="signal-info-item"><div class="si-label">成立条件 ID</div><div class="si-val" style="font-size:11px">${escHtml(matchStr)}</div></div>
      <div class="signal-info-item"><div class="si-label">DB 状態</div><div class="si-val" style="font-size:12px">${idStr} / ${newStr}</div></div>
    </div>`;
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ---------- 起動時初期化 ---------- */
(function initDateDefaults() {
  const today = new Date();
  const yyyy  = today.getFullYear();
  const mm    = String(today.getMonth() + 1).padStart(2, '0');
  const dd    = String(today.getDate()).padStart(2, '0');
  const todayStr = `${yyyy}-${mm}-${dd}`;
  const oneYearAgo = `${yyyy - 1}-${mm}-${dd}`;
  document.getElementById('date-end').value   = todayStr;
  document.getElementById('date-start').value = oneYearAgo;
})();
loadSavedStrategies();
</script>

</body>
</html>
