<?php
require_once __DIR__ . '/_user_config.php';
require_once __DIR__ . '/admin/_config.php';

$user = require_user_login('/login.php');

// 本日の使用状況
$today_count = 0;
$has_result  = false;
try {
    $pdo = get_pdo();
    $pdo->exec("CREATE TABLE IF NOT EXISTS member_bt_log (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, user_id BIGINT UNSIGNED NOT NULL,
        run_date DATE NOT NULL, run_count INT NOT NULL DEFAULT 0,
        last_result_json MEDIUMTEXT NULL, last_run_at DATETIME NULL,
        PRIMARY KEY (id), UNIQUE KEY uk_user_date (user_id, run_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $s = $pdo->prepare('SELECT run_count, last_result_json FROM member_bt_log WHERE user_id=? AND run_date=?');
    $s->execute([$user['id'], date('Y-m-d')]);
    $row = $s->fetch();
    if ($row) { $today_count = (int)$row['run_count']; $has_result = !empty($row['last_result_json']); }
} catch (Exception $e) {}

$remaining  = max(0, 2 - $today_count);
$limit_reached = $remaining === 0;
?>
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>バックテスト | AI×FX</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, 'Noto Sans JP', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
    /* header */
    .app-header { background: #1a1a2e; height: 56px; display: flex; align-items: center; padding: 0 20px; justify-content: space-between; position: sticky; top: 0; z-index: 50; }
    .header-logo { color: #fff; font-size: 1.05rem; font-weight: 700; text-decoration: none; display: flex; align-items: center; gap: 8px; }
    .header-logo i { color: #c9ff3b; }
    .header-right { display: flex; align-items: center; gap: 12px; }
    .header-link { font-size: 0.8rem; color: #94a3b8; text-decoration: none; }
    .header-link:hover { color: #fff; }
    /* main */
    main { max-width: 960px; margin: 0 auto; padding: 28px 16px 60px; }
    h1 { font-size: 1.3rem; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }
    .subtitle { font-size: 13px; color: #64748b; margin-bottom: 24px; }
    /* usage bar */
    .usage-bar { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 14px 18px; display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
    .usage-label { font-size: 12px; color: #64748b; }
    .usage-dots { display: flex; gap: 6px; }
    .usage-dot { width: 14px; height: 14px; border-radius: 50%; background: #334155; }
    .usage-dot.used { background: #3b82f6; }
    .usage-text { font-size: 13px; color: #94a3b8; margin-left: auto; }
    .limit-notice { background: #450a0a; border: 1px solid #7f1d1d; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #fca5a5; margin-bottom: 20px; }
    /* cards */
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
    .card-title { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #334155; }
    /* form elements */
    .form-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; }
    .form-group { display: flex; flex-direction: column; gap: 5px; min-width: 120px; }
    .form-group label { font-size: 11px; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: .04em; }
    select, input[type=number], input[type=date] {
      background: #0f172a; border: 1px solid #475569; border-radius: 7px;
      color: #e2e8f0; padding: 8px 10px; font-size: 13px; outline: none; transition: border-color .15s;
    }
    select:focus, input:focus { border-color: #3b82f6; }
    /* checkboxes */
    .check-group { display: flex; flex-wrap: wrap; gap: 8px; }
    .check-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #cbd5e1; cursor: pointer; background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; transition: all .15s; }
    .check-label input { accent-color: #3b82f6; }
    .check-label:has(input:checked) { border-color: #3b82f6; color: #93c5fd; background: #172554; }
    /* condition builder */
    .cond-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
    .cond-row { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; }
    .cond-row .fg { display: flex; flex-direction: column; gap: 4px; }
    .cond-row label { font-size: 10px; color: #475569; }
    .cond-row select, .cond-row input[type=number] { padding: 6px 8px; font-size: 12px; }
    .cond-row input[type=number] { width: 72px; }
    .btn-del { background: none; border: 1px solid #475569; color: #64748b; border-radius: 5px; padding: 5px 8px; font-size: 11px; cursor: pointer; align-self: flex-end; transition: all .15s; }
    .btn-del:hover { border-color: #ef4444; color: #ef4444; }
    .btn-add-cond { width: 100%; background: none; border: 1px dashed #334155; color: #475569; border-radius: 7px; padding: 8px; font-size: 12px; cursor: pointer; transition: all .15s; }
    .btn-add-cond:hover { border-color: #3b82f6; color: #60a5fa; }
    .logic-row { display: flex; gap: 6px; margin-bottom: 10px; }
    .logic-btn { background: #0f172a; border: 1px solid #475569; color: #64748b; border-radius: 6px; padding: 4px 14px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all .15s; }
    .logic-btn.active { background: #172554; border-color: #3b82f6; color: #60a5fa; }
    /* run button */
    .btn-run { background: #3b82f6; color: #fff; border: none; border-radius: 8px; padding: 12px 32px; font-size: 0.95rem; font-weight: 700; cursor: pointer; transition: opacity .15s; width: 100%; margin-top: 8px; }
    .btn-run:hover:not(:disabled) { opacity: .85; }
    .btn-run:disabled { background: #1e3a5f; color: #475569; cursor: not-allowed; }
    /* results */
    .result-section { display: none; }
    .result-section.show { display: block; }
    .result-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
    .result-title { font-size: 1rem; font-weight: 700; color: #f1f5f9; }
    .btn-csv { display: inline-flex; align-items: center; gap: 6px; background: #0f766e; color: #fff; border: none; border-radius: 7px; padding: 8px 18px; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; transition: opacity .15s; }
    .btn-csv:hover { opacity: .85; }
    .metrics-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .metrics-table th { background: #162032; color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }
    .metrics-table td { padding: 10px 12px; border-bottom: 1px solid #0f172a; }
    .metrics-table tr:last-child td { border-bottom: none; }
    .metrics-table tr:hover td { background: #1a2844; }
    .badge-up   { background: #14532d; color: #86efac; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge-down { background: #450a0a; color: #fca5a5; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    /* spinner */
    .spinner { display: none; text-align: center; padding: 20px; color: #64748b; font-size: 13px; }
    .spinner.show { display: block; }
    .spin { display: inline-block; width: 18px; height: 18px; border: 2px solid #334155; border-top-color: #3b82f6; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: middle; margin-right: 8px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .error-box { background: #450a0a; border: 1px solid #7f1d1d; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #fca5a5; display: none; }
    .error-box.show { display: block; }
  </style>
</head>
<body>
<header class="app-header">
  <a href="/" class="header-logo">
    <i class="bi bi-graph-up-arrow"></i>
    <span>AI×FX</span>
  </a>
  <div class="header-right">
    <a href="/mypage.php" class="header-link">マイページ</a>
    <a href="/logout.php" class="header-link">ログアウト</a>
  </div>
</header>

<main>
  <h1><i class="bi bi-bar-chart-steps"></i> バックテスト</h1>
  <p class="subtitle">過去データを使ってテクニカル戦略を検証します</p>

  <!-- 使用状況 -->
  <div class="usage-bar">
    <span class="usage-label">本日の残り回数</span>
    <div class="usage-dots">
      <div class="usage-dot <?= $today_count >= 1 ? 'used' : '' ?>"></div>
      <div class="usage-dot <?= $today_count >= 2 ? 'used' : '' ?>"></div>
    </div>
    <span class="usage-text"><?= $remaining ?> / 2 回 残り</span>
  </div>

  <?php if ($limit_reached): ?>
  <div class="limit-notice"><i class="bi bi-exclamation-triangle"></i> 本日の実行回数（2回）に達しました。明日またお試しください。</div>
  <?php endif; ?>

  <!-- 設定フォーム -->
  <form id="bt-form">
    <!-- 通貨ペア -->
    <div class="card">
      <div class="card-title">通貨ペア・時間軸</div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group">
          <label>通貨ペア</label>
          <div class="check-group">
            <label class="check-label"><input type="radio" name="pair" value="USDJPY" checked> USD/JPY</label>
            <label class="check-label"><input type="radio" name="pair" value="GBPJPY"> GBP/JPY</label>
            <label class="check-label"><input type="radio" name="pair" value="EURJPY"> EUR/JPY</label>
          </div>
        </div>
      </div>
      <div class="form-row" style="margin-bottom:16px">
        <div class="form-group">
          <label>時間軸</label>
          <div class="check-group">
            <label class="check-label"><input type="radio" name="timeframe" value="15min" onchange="onTfChange('15min')"> 15分足 <span style="font-size:10px;color:#475569">最大40h</span></label>
            <label class="check-label"><input type="radio" name="timeframe" value="1hr"   onchange="onTfChange('1hr')"   checked> 1時間足 <span style="font-size:10px;color:#475569">最大72h</span></label>
            <label class="check-label"><input type="radio" name="timeframe" value="4hr"   onchange="onTfChange('4hr')"> 4時間足</label>
            <label class="check-label"><input type="radio" name="timeframe" value="daily" onchange="onTfChange('daily')"> 日足 <span style="font-size:10px;color:#475569">最大2ヶ月</span></label>
          </div>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>方向</label>
          <select id="direction">
            <option value="BOTH">BOTH（両方）</option>
            <option value="BUY">BUY（買いのみ）</option>
            <option value="SELL">SELL（売りのみ）</option>
          </select>
        </div>
        <div class="form-group" id="date-range-group">
          <label>集計期間</label>
          <span id="period-label" style="font-size:13px;color:#94a3b8;padding:8px 0">自動設定</span>
        </div>
      </div>
    </div>

    <!-- エントリー条件 -->
    <div class="card">
      <div class="card-title">エントリー条件</div>
      <div class="logic-row">
        <button type="button" class="logic-btn active" id="logic-and" onclick="setLogic('AND')">AND（すべて）</button>
        <button type="button" class="logic-btn"        id="logic-or"  onclick="setLogic('OR')">OR（いずれか）</button>
      </div>
      <div class="cond-list" id="cond-list"></div>
      <button type="button" class="btn-add-cond" onclick="addCond()" id="add-cond-btn">＋ 条件を追加</button>
    </div>

    <!-- SL / TP -->
    <div class="card">
      <div class="card-title">損切り（SL）・利確（TP）</div>
      <div class="form-row">
        <div class="form-group">
          <label>SL (pips)</label>
          <input type="number" id="sl_pips" value="20" min="1" step="1" style="width:100px">
        </div>
        <div class="form-group">
          <label>TP (pips)</label>
          <input type="number" id="tp_pips" value="40" min="1" step="1" style="width:100px">
        </div>
        <div class="form-group">
          <label>初期資金（円）</label>
          <input type="number" id="initial_capital" value="1000000" min="10000" step="10000" style="width:140px">
        </div>
      </div>
    </div>

    <div class="error-box" id="error-box"></div>
    <div class="spinner" id="spinner"><span class="spin"></span>バックテスト実行中... 最大30秒ほどかかります</div>
    <button type="button" class="btn-run" id="run-btn" <?= $limit_reached ? 'disabled' : '' ?> onclick="runBacktest()">
      <i class="bi bi-play-fill"></i> バックテストを実行
    </button>
  </form>

  <!-- 結果 -->
  <div class="result-section <?= $has_result ? 'show' : '' ?>" id="result-section">
    <div class="card" style="margin-top:20px">
      <div class="result-header">
        <span class="result-title"><i class="bi bi-bar-chart"></i> バックテスト結果</span>
        <a href="/member-api.php?action=csv" class="btn-csv" id="csv-btn">
          <i class="bi bi-download"></i> CSVダウンロード
        </a>
      </div>
      <div id="result-content">
        <?php if ($has_result): ?>
        <p style="font-size:13px;color:#64748b">前回の結果を表示しています。新しく実行すると更新されます。</p>
        <?php endif; ?>
      </div>
    </div>
  </div>
</main>

<script>
const IND = {
  RSI:         { label:'RSI',          params:[{n:'period',d:14}] },
  EMA:         { label:'EMA',          params:[{n:'period',d:21}] },
  EMA_SLOPE:   { label:'EMA 向き',     params:[{n:'period',d:21}] },
  SMA:         { label:'SMA',          params:[{n:'period',d:20}] },
  MACD_HIST:   { label:'MACD ヒスト',  params:[{n:'fast',d:12},{n:'slow',d:26},{n:'signal',d:9}] },
  MACD_LINE:   { label:'MACD ライン',  params:[{n:'fast',d:12},{n:'slow',d:26},{n:'signal',d:9}] },
  STOCH_K:     { label:'Stoch %K',     params:[{n:'k_period',d:14},{n:'d_period',d:3},{n:'smooth_k',d:3}] },
  STOCH_D:     { label:'Stoch %D',     params:[{n:'k_period',d:14},{n:'d_period',d:3},{n:'smooth_k',d:3}] },
  CCI:         { label:'CCI',          params:[{n:'period',d:20}] },
  BB_UPPER:    { label:'BB 上バンド',  params:[{n:'period',d:20},{n:'std',d:2.0}] },
  BB_LOWER:    { label:'BB 下バンド',  params:[{n:'period',d:20},{n:'std',d:2.0}] },
  CLOSE:       { label:'終値',         params:[] },
  BULLISH_ENGULFING: { label:'強気の包み足', params:[] },
  BEARISH_ENGULFING: { label:'弱気の包み足', params:[] },
  HAMMER:            { label:'ハンマー',     params:[] },
  DOJI:              { label:'十字線',       params:[] },
};
const COMPS = [
  {v:'less_than',l:'< 未満'},
  {v:'greater_than',l:'> 超え'},
  {v:'less_than_or_equal',l:'≤ 以下'},
  {v:'greater_than_or_equal',l:'≥ 以上'},
  {v:'crosses_above',l:'↑ クロスアップ'},
  {v:'crosses_below',l:'↓ クロスダウン'},
];

let _logic = 'AND', _seq = 0;

function setLogic(v) {
  _logic = v;
  document.getElementById('logic-and').classList.toggle('active', v === 'AND');
  document.getElementById('logic-or').classList.toggle('active',  v === 'OR');
}

function buildIndOpts() {
  return Object.entries(IND).map(([k,v]) => `<option value="${k}">${v.label}</option>`).join('');
}
function buildCompOpts() {
  return COMPS.map(c => `<option value="${c.v}">${c.l}</option>`).join('');
}
function buildParamFields(indKey, id) {
  const params = IND[indKey]?.params || [];
  if (!params.length) return '<span style="font-size:11px;color:#475569">パラメータなし</span>';
  return params.map(p =>
    `<div class="fg"><label>${p.n}</label><input type="number" step="0.1" value="${p.d}" id="${id}-${p.n}" style="width:66px"></div>`
  ).join('');
}

function addCond() {
  const list = document.getElementById('cond-list');
  if (list.children.length >= 3) { alert('条件は最大3つまでです'); return; }
  const id   = 'c' + (++_seq);
  const div  = document.createElement('div');
  div.className = 'cond-row';
  div.id = id;
  div.innerHTML = `
    <div class="fg"><label>指標</label>
      <select onchange="updateParams('${id}',this.value)">${buildIndOpts()}</select>
    </div>
    <div class="fg"><label>比較</label><select>${buildCompOpts()}</select></div>
    <div class="fg"><label>値</label><input type="number" step="0.1" value="30" style="width:80px"></div>
    <div class="params-wrap" id="${id}-params">${buildParamFields('RSI', id)}</div>
    <button type="button" class="btn-del" onclick="document.getElementById('${id}').remove()">✕</button>`;
  list.appendChild(div);
}

function updateParams(id, indKey) {
  document.getElementById(id + '-params').innerHTML = buildParamFields(indKey, id);
}

function buildConditions() {
  const rows = document.querySelectorAll('#cond-list .cond-row');
  const conds = [];
  rows.forEach(row => {
    const sels = row.querySelectorAll('select');
    const nums = row.querySelectorAll('input[type=number]');
    const indKey = sels[0].value;
    const comp   = sels[1].value;
    const val    = parseFloat(nums[nums.length - 1]?.value || 0);
    const params = IND[indKey]?.params || [];
    const pobj   = {};
    params.forEach(p => {
      const el = row.querySelector('#' + row.id + '-' + p.n);
      if (el) pobj[p.n] = parseFloat(el.value);
    });
    conds.push({ indicator_type: indKey, comparison: comp, value: val, params: pobj });
  });
  return conds;
}

const TF_LIMITS = { '15min': 160, '1hr': 72, '4hr': 500, 'daily': 60 };

function onTfChange(tf) {
  const labels = {
    '15min': '最大 40時間分（160本）',
    '1hr':   '最大 72時間分（72本）',
    '4hr':   '自動設定',
    'daily': '最大 2ヶ月分（60本）',
  };
  document.getElementById('period-label').textContent = labels[tf] || '自動設定';
}

async function runBacktest() {
  const btn = document.getElementById('run-btn');
  const spinner = document.getElementById('spinner');
  const errBox  = document.getElementById('error-box');
  errBox.classList.remove('show');

  const pairEl = document.querySelector('input[name=pair]:checked');
  const tfEl   = document.querySelector('input[name=timeframe]:checked');
  if (!pairEl) { showError('通貨ペアを選択してください'); return; }
  if (!tfEl)   { showError('時間軸を選択してください'); return; }
  const pair = pairEl.value;
  const tf   = tfEl.value;

  const conds = buildConditions();
  if (!conds.length) { showError('条件を1つ以上追加してください'); return; }

  btn.disabled = true;
  spinner.classList.add('show');

  const body = {
    action: 'run',
    pairs: [pair],
    timeframes: [tf],
    limit: TF_LIMITS[tf] || 500,
    direction: document.getElementById('direction').value,
    sim_params: {
      initial_capital: parseFloat(document.getElementById('initial_capital').value),
      sl: { type: 'fixed', pips: parseFloat(document.getElementById('sl_pips').value) },
      tp: { type: 'fixed', pips: parseFloat(document.getElementById('tp_pips').value) },
    },
    strategy_config: {
      strategy_version: '1.0',
      direction: document.getElementById('direction').value,
      entry_conditions: { logic: _logic, conditions: conds },
    },
  };

  try {
    const res = await fetch('/member-api.php?action=run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => r.json());

    spinner.classList.remove('show');

    if (!res.ok) {
      showError(res.error || '実行に失敗しました');
      btn.disabled = res.limit_reached ?? false;
      return;
    }

    // 残り回数更新
    const remaining = res.remaining ?? 0;
    const dots = document.querySelectorAll('.usage-dot');
    dots.forEach((d, i) => d.classList.toggle('used', i < (2 - remaining)));
    document.querySelector('.usage-text').textContent = remaining + ' / 2 回 残り';
    if (remaining === 0) { btn.disabled = true; }

    renderResults(res.results);

  } catch (e) {
    spinner.classList.remove('show');
    showError('通信エラー: ' + e.message);
    btn.disabled = false;
  }
}

function showError(msg) {
  const b = document.getElementById('error-box');
  b.textContent = '⚠ ' + msg;
  b.classList.add('show');
}

function renderResults(results) {
  const sec  = document.getElementById('result-section');
  const cont = document.getElementById('result-content');
  sec.classList.add('show');

  let html = '<div style="overflow-x:auto"><table class="metrics-table"><thead><tr>' +
    '<th>通貨ペア</th><th>TF</th><th>トレード数</th><th>勝率</th><th>PF</th>' +
    '<th>純損益(pips)</th><th>最大DD(pips)</th><th>期待値(pips)</th>' +
    '</tr></thead><tbody>';

  Object.entries(results).forEach(([key, r]) => {
    const m = r.metrics || {};
    const [pair, tf] = key.split('_');
    const wr  = m.win_rate != null ? (m.win_rate * 100).toFixed(1) + '%' : '-';
    const pf  = m.profit_factor != null ? parseFloat(m.profit_factor).toFixed(2) : '-';
    const pips = m.net_profit_pips != null ? parseFloat(m.net_profit_pips).toFixed(1) : '-';
    const dd   = m.max_drawdown_pips != null ? parseFloat(m.max_drawdown_pips).toFixed(1) : '-';
    const ev   = m.expectancy_pips != null ? parseFloat(m.expectancy_pips).toFixed(2) : '-';
    const pipsClass = parseFloat(pips) >= 0 ? 'badge-up' : 'badge-down';
    html += `<tr>
      <td><strong>${pair}</strong></td><td>${tf}</td>
      <td>${m.total_trades ?? '-'}</td>
      <td>${wr}</td>
      <td>${pf}</td>
      <td><span class="${pipsClass}">${pips}</span></td>
      <td>${dd}</td>
      <td>${ev}</td>
    </tr>`;
  });

  html += '</tbody></table></div>';
  cont.innerHTML = html;
}

// 初期条件を1つ追加
addCond();
</script>
</body>
</html>
