<?php
require_once __DIR__ . '/_config.php';
session_start();
require_login();

$slug     = preg_replace('/[^a-z0-9_]/', '', $_GET['slug']     ?? '');
$ind_name = trim($_GET['ind_name'] ?? '');
$title    = trim($_GET['title']    ?? $ind_name);
if (!$slug) { header('Location: /admin/articles.php'); exit; }

$ci_name = 'CustomV2_' . $slug;
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>条件設定 | <?= htmlspecialchars($title) ?></title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.logout-btn{color:#ef4444}
main{max-width:900px;margin:0 auto;padding:24px 16px}
.breadcrumb{display:flex;align-items:center;gap:6px;margin-bottom:18px;font-size:12px;color:#64748b}
.breadcrumb a{color:#60a5fa;text-decoration:none}
.section{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:18px}
.section h3{font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #334155}
label{font-size:11px;font-weight:600;color:#94a3b8;display:block;margin-bottom:4px}
input[type=number],input[type=text],select,textarea{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:13px;outline:none;width:100%}
input[type=number],input[type=text]{width:auto}
select{cursor:pointer}
input:focus,select:focus,textarea:focus{border-color:#3b82f6}
.form-row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:12px}
.form-group{display:flex;flex-direction:column;gap:3px}
.logic-toggle{display:flex;align-items:center;gap:6px;margin-bottom:10px}
.logic-btn{background:#0f172a;color:#94a3b8;border:1px solid #334155;border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;cursor:pointer}
.logic-btn.active{background:#1e3a5f;color:#60a5fa;border-color:#3b82f6}
.cond-list{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.cond-row{background:#0b1525;border:1px solid #1e3a5f;border-radius:8px;padding:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}
.btn-add{background:#0f766e;color:#fff;border:none;border-radius:6px;padding:7px 16px;font-size:12px;font-weight:600;cursor:pointer}
.btn-add:hover{background:#0d9488}
.btn-del{background:#7f1d1d;color:#fca5a5;border:none;border-radius:6px;padding:7px 12px;font-size:12px;cursor:pointer}
.btn-run{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 28px;font-size:14px;font-weight:600;cursor:pointer}
.btn-run:hover{background:#2563eb}
.btn-run:disabled{background:#1e3a5f;color:#475569;cursor:not-allowed}
.btn-save{background:#7c3aed;color:#fff;border:none;border-radius:8px;padding:10px 28px;font-size:14px;font-weight:600;cursor:pointer}
.btn-save:hover{background:#6d28d9}
.btn-save:disabled{background:#334155;color:#475569;cursor:not-allowed}
.results-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
.result-cell{background:#0b1525;border:1px solid #1e3a5f;border-radius:7px;padding:10px}
.result-cell-hdr{font-size:11px;font-weight:600;color:#60a5fa;margin-bottom:6px}
.result-row{display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px}
.result-label{color:#64748b}
.result-val{font-weight:600}
.wr-good{color:#4ade80}
.wr-mid{color:#fbbf24}
.wr-bad{color:#f87171}
.status-msg{font-size:13px;padding:8px 0;color:#94a3b8}
.form-hint{font-size:11px;color:#475569;margin-top:2px}
textarea{width:100%;resize:vertical;font-family:inherit;line-height:1.5;min-height:60px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>⚙️ 条件設定</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/articles.php" class="active">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>
<main>
  <div class="breadcrumb">
    <a href="/admin/articles.php">記事管理</a> › <?= htmlspecialchars($title) ?> › 条件設定
  </div>

  <!-- 1: エントリー条件 -->
  <div class="section">
    <h3>📊 エントリー条件</h3>
    <div class="form-row">
      <div class="form-group">
        <label>エントリー方向</label>
        <select id="direction" style="width:160px">
          <option value="BUY">BUY（買い）</option>
          <option value="SELL">SELL（売り）</option>
          <option value="BOTH">BOTH（両方）</option>
        </select>
      </div>
    </div>
    <div class="logic-toggle">
      <span style="font-size:12px;color:#64748b">条件の結合:</span>
      <button class="logic-btn active" id="logic-and" onclick="setLogic('AND')">AND（全条件一致）</button>
      <button class="logic-btn"        id="logic-or"  onclick="setLogic('OR')">OR（いずれか一致）</button>
    </div>
    <div class="cond-list" id="cond-list"></div>
    <button class="btn-add" onclick="addCondition()">＋ 条件を追加</button>
  </div>

  <!-- 2: クイックバックテスト -->
  <div class="section">
    <h3>🔬 クイックバックテスト（3ペア × 3足）</h3>
    <div class="form-row" style="margin-bottom:14px">
      <div class="form-group">
        <label>SL (pips)</label>
        <input type="number" id="sl_pips" value="20" min="1" max="200" step="1" style="width:80px">
      </div>
      <div class="form-group">
        <label>TP (pips)</label>
        <input type="number" id="tp_pips" value="40" min="1" max="400" step="1" style="width:80px">
      </div>
      <div class="form-group">
        <label>取得バー数</label>
        <input type="number" id="bt_limit" value="500" min="100" max="2000" step="100" style="width:90px">
      </div>
      <div class="form-group" style="justify-content:flex-end">
        <button class="btn-run" id="btn-run" onclick="runQuickBt()">▶ バックテスト実行</button>
      </div>
    </div>
    <div id="bt-status" class="status-msg"></div>
    <div class="results-grid" id="results-grid" style="display:none"></div>
  </div>

  <!-- 3: 指標として登録 -->
  <div class="section">
    <h3>💾 指標として登録</h3>
    <div class="form-row" style="margin-bottom:12px">
      <div class="form-group" style="flex:1;min-width:200px">
        <label>内部キー名（自動生成・変更可）</label>
        <input type="text" id="ci-name" value="<?= htmlspecialchars($ci_name) ?>" style="width:100%">
        <div class="form-hint">半角英数字・アンダースコアのみ</div>
      </div>
      <div class="form-group" style="flex:1;min-width:200px">
        <label>表示名（日本語可）</label>
        <input type="text" id="ci-display" value="<?= htmlspecialchars($title) ?> 複合シグナル" style="width:100%">
      </div>
    </div>
    <div style="margin-bottom:12px">
      <label>説明（任意）</label>
      <textarea id="ci-desc" rows="2" placeholder="この指標の概要を入力（省略可）"></textarea>
    </div>
    <div class="grid2" style="margin-bottom:14px">
      <div>
        <label>得な相場（1行1項目）</label>
        <textarea id="ci-good" rows="3" placeholder="例)&#10;トレンド相場&#10;ボラティリティ高め"></textarea>
      </div>
      <div>
        <label>苦手な相場（1行1項目）</label>
        <textarea id="ci-bad" rows="3" placeholder="例)&#10;レンジ相場&#10;急騰・急落局面"></textarea>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <button class="btn-save" id="btn-save" onclick="saveIndicator()">📌 指標として登録してバックテスト開始</button>
      <span id="save-status" style="font-size:13px"></span>
    </div>
  </div>
</main>

<script>
/* ===== 指標定義 ===== */
const IND = {
  RSI:         { label:'RSI',           params:[{n:'period',  l:'期間',  d:14}] },
  EMA:         { label:'EMA',           params:[{n:'period',  l:'期間',  d:21}] },
  EMA_SLOPE:   { label:'EMA 向き',      params:[{n:'period',  l:'期間',  d:21}], hint:'上向き≥1 / 下向き≤-1' },
  SMA:         { label:'SMA',           params:[{n:'period',  l:'期間',  d:20}] },
  MACD_HIST:   { label:'MACD ヒスト',   params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_LINE:   { label:'MACD ライン',   params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_SIGNAL: { label:'MACD シグナル', params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  STOCH_K:     { label:'Stoch %K',      params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  STOCH_D:     { label:'Stoch %D',      params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  CCI:         { label:'CCI',           params:[{n:'period',  l:'期間',  d:20}] },
  WILLIAMS_R:  { label:'Williams %R',   params:[{n:'period',  l:'期間',  d:14}] },
  ATR:         { label:'ATR',           params:[{n:'period',  l:'期間',  d:14}] },
  BB_UPPER:    { label:'BB 上バンド',   params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_LOWER:    { label:'BB 下バンド',   params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_MID:      { label:'BB 中央',       params:[{n:'period',  l:'期間',  d:20}] },
  CLOSE:       { label:'終値(CLOSE)',   params:[] },
  HIGH:        { label:'高値(HIGH)',    params:[] },
  LOW:         { label:'安値(LOW)',     params:[] },
  BULLISH_ENGULFING:    { label:'強気の包み足',   params:[], is_pattern:true },
  BEARISH_ENGULFING:    { label:'弱気の包み足',   params:[], is_pattern:true },
  HAMMER:               { label:'ハンマー',       params:[], is_pattern:true },
  INVERTED_HAMMER:      { label:'逆ハンマー',     params:[], is_pattern:true },
  DOJI:                 { label:'十字線（ドジ）', params:[], is_pattern:true },
  THREE_WHITE_SOLDIERS: { label:'三白兵',         params:[], is_pattern:true },
  THREE_BLACK_CROWS:    { label:'三羽烏',         params:[], is_pattern:true },
  BULLISH_PIN_BAR:      { label:'ピンバー（陽線）',params:[], is_pattern:true },
  BEARISH_PIN_BAR:      { label:'ピンバー（陰線）',params:[], is_pattern:true },
};
const COMPARISONS = [
  { v:'less_than',             l:'< 小さい' },
  { v:'less_than_or_equal',    l:'≤ 以下' },
  { v:'greater_than',          l:'> 大きい' },
  { v:'greater_than_or_equal', l:'≥ 以上' },
  { v:'crosses_above',         l:'↑ クロスアップ' },
  { v:'crosses_below',         l:'↓ クロスダウン' },
  { v:'equal',                 l:'= 等しい' },
];
function buildIndOptions(forRhs) {
  return Object.entries(IND).map(([k, v]) => {
    if (forRhs && v.is_pattern) return '';
    return `<option value="${k}">${v.label}</option>`;
  }).join('');
}

/* ===== 条件ビルダー ===== */
let _condSeq = 0;
let _logic   = 'AND';

function setLogic(v) {
  _logic = v;
  document.getElementById('logic-and').classList.toggle('active', v === 'AND');
  document.getElementById('logic-or' ).classList.toggle('active', v === 'OR');
}

function addCondition() {
  const id  = 'cond-' + (++_condSeq);
  const row = document.createElement('div');
  row.className  = 'cond-row';
  row.id         = id;
  row.dataset.id = 'c' + _condSeq;
  row.innerHTML = `
    <div class="form-group">
      <label>指標</label>
      <select onchange="onIndChange(this,'${id}')" style="width:150px">${buildIndOptions(false)}</select>
    </div>
    <div class="form-group" id="${id}-params">${buildParamInputs('RSI',id)}</div>
    <div class="form-group">
      <label>比較</label>
      <select id="${id}-cmp" onchange="onCmpChange('${id}')" style="width:130px">
        ${COMPARISONS.map(c=>`<option value="${c.v}">${c.l}</option>`).join('')}
      </select>
    </div>
    <div class="form-group" id="${id}-rhs">${buildRhs(id)}</div>
    <div class="form-group" style="justify-content:flex-end">
      <label style="visibility:hidden">×</label>
      <button class="btn-del" onclick="document.getElementById('${id}').remove()">✕</button>
    </div>`;
  document.getElementById('cond-list').appendChild(row);
}

function onIndChange(sel, rowId) {
  const k = sel.value;
  document.getElementById(rowId + '-params').innerHTML = buildParamInputs(k, rowId);
  if ((IND[k]||{}).is_pattern) {
    const c = document.getElementById(rowId+'-cmp'); if(c){c.value='greater_than_or_equal';onCmpChange(rowId);}
    const v = document.getElementById(rowId+'-val'); if(v) v.value='1';
  }
}

function buildParamInputs(k, rowId) {
  const ps = (IND[k]||{}).params || [];
  if (!ps.length) return '<label style="visibility:hidden">-</label><div style="color:#475569;font-size:12px;padding:9px 0">なし</div>';
  const hint = (IND[k]||{}).hint || '';
  return `<label>パラメータ</label>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      ${ps.map(p=>`<div style="display:flex;flex-direction:column;gap:2px">
        <span style="font-size:10px;color:#64748b">${p.l}</span>
        <input type="number" id="${rowId}-p-${p.n}" value="${p.d}" step="${p.n==='std'?0.1:1}" style="width:58px">
      </div>`).join('')}
    </div>${hint?`<div class="form-hint">${hint}</div>`:''}`;
}

function onCmpChange(rowId) {
  document.getElementById(rowId+'-rhs').innerHTML = buildRhs(rowId);
}

function buildRhs(rowId) {
  return `<label>比較値</label>
    <select id="${rowId}-cmp-ind" onchange="onCmpIndChange('${rowId}')" style="width:140px">
      <option value="">--- 固定値 ---</option>${buildIndOptions(true)}
    </select>
    <div id="${rowId}-cross-val" style="margin-top:4px">
      <input type="number" id="${rowId}-val" value="0" step="0.1" style="width:90px">
    </div>
    <div id="${rowId}-cmp-ind-params" style="margin-top:4px"></div>`;
}

function onCmpIndChange(rowId) {
  const sel = document.getElementById(rowId+'-cmp-ind');
  const vd  = document.getElementById(rowId+'-cross-val');
  const pd  = document.getElementById(rowId+'-cmp-ind-params');
  if (vd) vd.style.display = sel.value ? 'none' : '';
  if (pd) {
    if (sel.value) {
      const ps = (IND[sel.value]||{}).params || [];
      pd.innerHTML = ps.map(p=>`<div style="display:flex;align-items:center;gap:4px;margin-top:2px">
        <span style="font-size:10px;color:#64748b;min-width:28px">${p.l}</span>
        <input type="number" id="${rowId}-cind-p-${p.n}" value="${p.d}" step="${p.n==='std'?0.1:1}" style="width:58px">
      </div>`).join('');
    } else { pd.innerHTML = ''; }
  }
}

function buildConditions() {
  const rows  = document.querySelectorAll('#cond-list .cond-row');
  const conds = [];
  for (const row of rows) {
    const condId = row.dataset.id;
    const indSel = row.querySelector('select');
    const indKey = indSel ? indSel.value : 'RSI';
    const rowId  = row.id;
    const cmpVal = document.getElementById(rowId+'-cmp')?.value || 'less_than';
    const ps = (IND[indKey]||{}).params || [];
    const params = {};
    ps.forEach(p => { const el=document.getElementById(rowId+'-p-'+p.n); if(el) params[p.n]=parseFloat(el.value); });
    let value = null, compare_to_indicator = null, compare_to_params = null;
    const cmpIndSel = document.getElementById(rowId+'-cmp-ind');
    if (cmpIndSel && cmpIndSel.value) {
      compare_to_indicator = cmpIndSel.value;
      const cps = (IND[cmpIndSel.value]||{}).params || [];
      compare_to_params = {};
      cps.forEach(p => { const el=document.getElementById(rowId+'-cind-p-'+p.n); compare_to_params[p.n]=el?parseFloat(el.value):p.d; });
    } else {
      const valEl = document.getElementById(rowId+'-val');
      value = valEl ? parseFloat(valEl.value) : null;
    }
    conds.push({ id:condId, indicator:indKey, params, comparison:cmpVal, value, compare_to_indicator, compare_to_params });
  }
  return conds;
}

function buildStrategyConfig() {
  const conds = buildConditions();
  if (!conds.length) throw new Error('条件を1つ以上追加してください');
  return {
    strategy_version: '1.0',
    direction:        document.getElementById('direction').value,
    entry_conditions: { logic: _logic, conditions: conds },
    filters: null,
    sl_config: { type:'pips', pips: parseFloat(document.getElementById('sl_pips').value)||20 },
    tp_config: { type:'pips', pips: parseFloat(document.getElementById('tp_pips').value)||40 },
    trailing_config: { enabled: false },
  };
}

function addConditionFromPreset(cond) {
  addCondition();
  const rowId = 'cond-' + _condSeq;
  const row   = document.getElementById(rowId);
  const indSel = row.querySelector('select');
  if (indSel && cond.indicator) { indSel.value = cond.indicator; onIndChange(indSel, rowId); }
  Object.entries(cond.params||{}).forEach(([k,v]) => { const el=document.getElementById(rowId+'-p-'+k); if(el) el.value=v; });
  const cmpSel = document.getElementById(rowId+'-cmp');
  if (cmpSel && cond.comparison) { cmpSel.value = cond.comparison; onCmpChange(rowId); }
  if (cond.compare_to_indicator) {
    const cmpIndSel = document.getElementById(rowId+'-cmp-ind');
    if (cmpIndSel) { cmpIndSel.value = cond.compare_to_indicator; onCmpIndChange(rowId); }
    Object.entries(cond.compare_to_params||{}).forEach(([k,v]) => { const el=document.getElementById(rowId+'-cind-p-'+k); if(el) el.value=v; });
  } else {
    const valEl = document.getElementById(rowId+'-val');
    if (valEl && cond.value !== null && cond.value !== undefined) valEl.value = cond.value;
  }
}

/* ===== クイックバックテスト ===== */
const QBT_PAIRS = ['USDJPY','GBPJPY','EURJPY'];
const QBT_TFS   = ['1hr','4hr','daily'];
const TF_LABELS = {'1hr':'1時間','4hr':'4時間','daily':'日足'};

async function runQuickBt() {
  let strategy;
  try { strategy = buildStrategyConfig(); } catch(e) { alert(e.message); return; }

  const limit   = parseInt(document.getElementById('bt_limit').value,10) || 500;
  const sl_pips = parseFloat(document.getElementById('sl_pips').value) || 20;
  const tp_pips = parseFloat(document.getElementById('tp_pips').value) || 40;
  const simParams = { initial_capital:1000000, pip_value:1000, max_bars_to_exit:200 };

  const btn  = document.getElementById('btn-run');
  const stat = document.getElementById('bt-status');
  const grid = document.getElementById('results-grid');
  btn.disabled = true;
  grid.style.display = 'none';
  stat.textContent = '実行中...';

  const results = {};
  let done = 0;
  const total = QBT_PAIRS.length * QBT_TFS.length;

  await Promise.all(QBT_PAIRS.flatMap(pair => QBT_TFS.map(async tf => {
    try {
      const res = await fetch('/admin/api.php', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ action:'bt_v2', pair, timeframe:tf, limit, strategy_config:strategy, sim_params:simParams }),
      }).then(r => r.json());
      results[pair + '_' + tf] = res;
    } catch(e) {
      results[pair + '_' + tf] = { ok: false, error: e.message };
    }
    done++;
    stat.textContent = `実行中... (${done}/${total})`;
  })));

  stat.textContent = '✓ 完了';
  renderResults(results);
  grid.style.display = 'grid';
  btn.disabled = false;
  // バックテスト結果をグローバルに保存（登録時に使う）
  window._lastBtResults = results;
}

function wrCls(wr) { return wr >= 55 ? 'wr-good' : wr >= 45 ? 'wr-mid' : 'wr-bad'; }

function renderResults(results) {
  const grid = document.getElementById('results-grid');
  const cells = QBT_PAIRS.flatMap(pair => QBT_TFS.map(tf => {
    const r   = results[pair + '_' + tf] || {};
    const ok  = r.ok;
    const wr  = ok && r.metrics ? (r.metrics.win_rate * 100).toFixed(1) : null;
    const pf  = ok && r.metrics ? (r.metrics.profit_factor || 0).toFixed(2) : null;
    const tr  = ok && r.metrics ? r.metrics.total_trades : null;
    const pairLabel = {USDJPY:'ドル円',GBPJPY:'ポンド円',EURJPY:'ユーロ円'}[pair] || pair;
    return `<div class="result-cell">
      <div class="result-cell-hdr">${pairLabel} ${TF_LABELS[tf]||tf}</div>
      ${ok && tr > 0 ? `
        <div class="result-row"><span class="result-label">勝率</span><span class="result-val ${wrCls(parseFloat(wr))}">${wr}%</span></div>
        <div class="result-row"><span class="result-label">PF</span><span class="result-val">${pf}</span></div>
        <div class="result-row"><span class="result-label">取引数</span><span class="result-val">${tr}</span></div>
      ` : `<div style="font-size:12px;color:#475569;padding:4px 0">${ok ? '取引なし' : (r.error||'エラー')}</div>`}
    </div>`;
  }));
  grid.innerHTML = cells.join('');
}

/* ===== 指標登録 ===== */
async function saveIndicator() {
  const name    = document.getElementById('ci-name').value.trim();
  const display = document.getElementById('ci-display').value.trim();
  const desc    = document.getElementById('ci-desc').value.trim();
  const toArr   = t => t.split('\n').map(s=>s.trim()).filter(Boolean);
  const good    = toArr(document.getElementById('ci-good').value);
  const bad     = toArr(document.getElementById('ci-bad').value);

  if (!name || !display) { alert('内部キー名と表示名は必須です'); return; }
  if (!/^[A-Za-z0-9_]{1,80}$/.test(name)) { alert('内部キー名は半角英数字・アンダースコアのみ'); return; }

  let strategy;
  try { strategy = buildStrategyConfig(); } catch(e) { alert(e.message); return; }

  const btn  = document.getElementById('btn-save');
  const stat = document.getElementById('save-status');
  btn.disabled = true;
  stat.style.color = '#94a3b8';
  stat.textContent = '保存中...';

  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ action:'save_custom_indicator', name, display_name:display, description:desc, good_markets:good, bad_markets:bad, strategy_config:strategy }),
    }).then(r => r.json());

    if (res.status === 'ok') {
      stat.style.color = '#22c55e';
      stat.textContent = '✓ 登録しました。バックテストをバックグラウンドで開始しました。';
    } else {
      stat.style.color = '#ef4444';
      stat.textContent = 'エラー: ' + (res.message||'');
    }
  } catch(e) {
    stat.style.color = '#ef4444';
    stat.textContent = 'ネットワークエラー: ' + e.message;
  }
  btn.disabled = false;
}

/* ===== 初期化: 既存設定を読み込む ===== */
(async function init() {
  const name = document.getElementById('ci-name').value;
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ action:'get_custom_indicator', name }),
    }).then(r => r.json());
    if (res.status === 'ok' && res.indicator) {
      const ci = res.indicator;
      document.getElementById('ci-display').value = ci.display_name || '';
      document.getElementById('ci-desc').value    = ci.description  || '';
      try { document.getElementById('ci-good').value = JSON.parse(ci.good_markets||'[]').join('\n'); } catch(_) {}
      try { document.getElementById('ci-bad').value  = JSON.parse(ci.bad_markets ||'[]').join('\n'); } catch(_) {}
      const cfg = ci.strategy_config;
      if (cfg) {
        if (cfg.direction) document.getElementById('direction').value = cfg.direction;
        if (cfg.sl_config?.pips) document.getElementById('sl_pips').value = cfg.sl_config.pips;
        if (cfg.tp_config?.pips) document.getElementById('tp_pips').value = cfg.tp_config.pips;
        setLogic((cfg.entry_conditions||{}).logic || 'AND');
        ((cfg.entry_conditions||{}).conditions || []).forEach(addConditionFromPreset);
      }
    }
  } catch(_) {}
})();
</script>
</body>
</html>
