<?php
/**
 * カスタムバックテストツール (PHP版)
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();

// 日付範囲をDBから取得
$dateRanges = [];
try {
    $pdo = get_pdo();
    $pairs = ['USDJPY', 'GBPJPY', 'EURJPY'];
    $tfs   = ['15min', '1hr', '4hr', 'daily'];
    foreach ($pairs as $pair) {
        $dateRanges[$pair] = [];
        foreach ($tfs as $tf) {
            $stmt = $pdo->prepare(
                'SELECT MIN(DATE(timestamp)) AS mn, MAX(DATE(timestamp)) AS mx
                 FROM price_data WHERE currency_pair=? AND timeframe=?'
            );
            $stmt->execute([$pair, $tf]);
            $row = $stmt->fetch();
            $dateRanges[$pair][$tf] = ['min' => $row['mn'] ?? '', 'max' => $row['mx'] ?? ''];
        }
    }
} catch (Exception $e) {}

$dateRangesJson = json_encode($dateRanges, JSON_UNESCAPED_UNICODE);
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>カスタムバックテスト | AI×FX 管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
main{max-width:960px;margin:0 auto;padding:28px 20px}
h2{font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:6px}
.subtitle{font-size:13px;color:#64748b;margin-bottom:24px}
/* フォーム */
.form-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:24px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.form-row.three{grid-template-columns:1fr 1fr 1fr}
.form-group label{display:block;font-size:12px;color:#64748b;margin-bottom:6px}
.form-group select,.form-group input{width:100%;background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:9px 10px;font-size:13px;outline:none}
.form-group select:focus,.form-group input:focus{border-color:#3b82f6}
/* チェックボックスグループ */
.cb-section{margin-bottom:20px}
.cb-section-title{font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:10px;display:flex;align-items:center;gap:10px}
.cb-section-title .sel-btns{display:flex;gap:6px}
.sel-btn{background:none;border:1px solid #475569;color:#94a3b8;border-radius:5px;padding:3px 8px;font-size:11px;cursor:pointer}
.sel-btn:hover{background:#334155;color:#f1f5f9}
.cb-group{display:flex;flex-wrap:wrap;gap:8px}
.cb-item{display:flex;align-items:center;gap:6px;background:#0f172a;border:1px solid #334155;border-radius:7px;padding:7px 12px;cursor:pointer;transition:border-color .15s}
.cb-item:hover{border-color:#475569}
.cb-item input{accent-color:#3b82f6;width:14px;height:14px}
.cb-item span{font-size:12px;color:#cbd5e1}
.cb-item input:checked ~ span{color:#f1f5f9}
/* アクションボタン */
.actions{display:flex;gap:12px;align-items:center;margin-top:20px}
.btn-run{background:#3b82f6;color:#fff;border:none;border-radius:9px;padding:12px 28px;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s}
.btn-run:hover{background:#2563eb}
.btn-run:disabled{opacity:.5;cursor:not-allowed}
.btn-reset{background:none;border:1px solid #ef4444;color:#ef4444;border-radius:9px;padding:11px 20px;font-size:13px;cursor:pointer;display:none}
.btn-reset:hover{background:#7f1d1d}
.btn-st-reset{background:none;border:1px solid #f97316;color:#f97316;border-radius:9px;padding:11px 20px;font-size:13px;cursor:pointer}
.btn-st-reset:hover{background:rgba(249,115,22,.15)}
/* オーバーレイ */
.overlay{position:fixed;inset:0;background:rgba(15,23,42,.85);z-index:100;display:none;flex-direction:column;align-items:center;justify-content:center;gap:16px}
.overlay.active{display:flex}
.overlay-msg{color:#e2e8f0;font-size:16px;font-weight:600}
.overlay-sub{color:#64748b;font-size:13px}
@keyframes spin{to{transform:rotate(360deg)}}
.big-spin{width:48px;height:48px;border:4px solid #1e3a5f;border-top-color:#3b82f6;border-radius:50%;animation:spin .8s linear infinite}
/* エラー */
.err-banner{background:#7f1d1d;border:1px solid #ef4444;border-radius:9px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#fca5a5;display:none;white-space:pre-wrap}
/* 結果 */
.result-wrap{display:none}
.result-wrap.show{display:block}
.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.sum-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 14px;text-align:center}
.sum-card .s-label{font-size:11px;color:#64748b;margin-bottom:6px}
.sum-card .s-val{font-size:22px;font-weight:700;color:#f1f5f9}
.sum-card .s-val.green{color:#4ade80}
.sum-card .s-val.red{color:#f87171}
/* タブ */
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.tab-btn{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:7px;padding:7px 14px;font-size:12px;cursor:pointer}
.tab-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.tab-panel{display:none}
.tab-panel.active{display:block}
/* カードごとのサマリー */
.ind-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin-bottom:12px}
.ind-card h4{font-size:14px;font-weight:600;color:#f1f5f9;margin-bottom:12px}
.ind-stats{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:12px}
.ind-stat{text-align:center}
.ind-stat .iv{font-size:18px;font-weight:700;color:#f1f5f9}
.ind-stat .il{font-size:11px;color:#64748b;margin-top:2px}
/* トレード履歴 */
.trade-table{width:100%;border-collapse:collapse;font-size:12px}
.trade-table th{background:#0f172a;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}
.trade-table td{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1}
.trade-table tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.badge.buy{background:#1e3a5f;color:#60a5fa}
.badge.sell{background:#4c1d95;color:#c4b5fd}
.badge.win{background:#14532d;color:#4ade80}
.badge.loss{background:#7f1d1d;color:#f87171}
</style>
</head>
<body>
<div class="overlay" id="overlay">
  <div class="big-spin"></div>
  <div class="overlay-msg" id="overlay-msg">バックテスト実行中...</div>
  <div class="overlay-sub" id="overlay-sub">しばらくお待ちください（30秒〜数分）</div>
</div>

<header>
  <h1>AI×FX 管理パネル</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/articles.php">記事管理</a>
    <a href="/admin/backtest.php" class="active">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>

<main>
  <h2>カスタムバックテスト</h2>
  <p class="subtitle">通貨ペア・期間・資金・指標を選択してバックテストを実行します</p>

  <div class="err-banner" id="err-banner"></div>

  <div class="form-card">
    <!-- 通貨ペア・タイムフレーム -->
    <div class="form-row">
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
        <select id="timeframe" onchange="updateDateRange()">
          <option value="5min">5分足</option>
          <option value="15min">15分足</option>
          <option value="1hr">1時間足</option>
          <option value="4hr">4時間足</option>
          <option value="daily">日足</option>
        </select>
      </div>
    </div>

    <!-- 日付範囲 -->
    <div class="form-row">
      <div class="form-group">
        <label>開始日</label>
        <input type="date" id="start_date">
      </div>
      <div class="form-group">
        <label>終了日</label>
        <input type="date" id="end_date">
      </div>
    </div>

    <!-- 資金・SL・RR -->
    <div class="form-row three">
      <div class="form-group">
        <label>初期資金 (円)</label>
        <input type="number" id="capital" value="1000000" min="1000" step="1000">
      </div>
      <div class="form-group">
        <label>SL (pips) ※固定pipsモード時</label>
        <input type="number" id="sl_pips" value="20" min="1" max="200" step="1">
      </div>
      <div class="form-group">
        <label>RR比率</label>
        <select id="rr_ratio">
          <option value="1.2">1:1.2</option>
          <option value="1.5" selected>1:1.5</option>
          <option value="2.0">1:2.0</option>
          <option value="2.5">1:2.5</option>
          <option value="3.0">1:3.0</option>
        </select>
      </div>
    </div>

    <!-- 損切りロジック設定 -->
    <div class="form-row" style="margin-bottom:20px">
      <div class="form-group">
        <label>損切りロジック</label>
        <select id="sl_mode">
          <option value="pips">固定pips SL/TP（通常）</option>
          <option value="bb">BBバンドタッチ SL/TP（動的）</option>
        </select>
        <span style="font-size:11px;color:#475569;margin-top:4px;display:block">BBモード：SL = BB下限、TP = BB上限（エントリー時点の値を使用）</span>
      </div>
    </div>

    <!-- 指標選択 -->
    <div style="margin-top:4px">
      <div style="font-size:12px;color:#64748b;margin-bottom:14px">使用する指標を選択（複数可）</div>

      <?php
      $indicatorGroups = [
          'オシレーター' => [
              'RSI_14'          => 'RSI (14)',
              'MACD_12_26_9'    => 'MACD (12,26,9)',
              'Stochastic_14_3' => 'Stochastic (14,3,3)',
              'CCI_20'          => 'CCI (20)',
              'Williams_R_14'   => 'Williams %R (14)',
          ],
          'トレンド' => [
              'SMA_20'               => 'SMA (20)',
              'SMA_50'               => 'SMA (50)',
              'SMA_Cross_20_50'      => 'SMAクロス (20/50)',
              'EMA_Cross_9_21'       => 'EMAクロス (9/21)',
              'EMA_21'               => 'EMA (21)',
              'BollingerBands_20_2'  => 'ボリンジャーバンド (20,2)',
              'BB_Squeeze'           => 'BBスクイーズ',
          ],
          'ライン' => [
              'Pivot_Classic'          => 'ピボット (Classic)',
              'Fibonacci_Retracement' => 'フィボナッチ',
              'Support_Resistance'    => 'サポート/レジスタンス',
          ],
          'ボラティリティ' => [
              'ATR_14'          => 'ATR (14)',
              'Volatility_Index'=> 'ボラティリティ指数',
          ],
          'パターン' => [
              'Hammer'              => 'ハンマー',
              'Inverted_Hammer'     => '逆ハンマー',
              'Doji'                => '十字線',
              'Bullish_Engulfing'   => '陽の包み足',
              'Bearish_Engulfing'   => '陰の包み足',
              'Three_White_Soldiers'=> '三白兵',
              'Three_Black_Crows'   => '三羽烏',
              'Pin_Bar'             => 'ピンバー',
          ],
          '複合条件' => [
              'RSI_MACD_Combo'    => 'RSI + MACD 両方一致',
              'RSI_Stoch_Combo'   => 'RSI + Stochastic 両方一致',
              'MACD_Stoch_Combo'  => 'MACD + Stochastic 両方一致',
              'Triple_OSC_Combo'  => 'トリプルOSC（RSI+MACD+Stoch 全一致）',
              'All_AND_Consensus' => '全指標AND一致エントリー',
          ],
      ];
      $gIdx = 0;
      foreach ($indicatorGroups as $groupName => $indicators):
          $gIdx++;
          $groupId = 'grp' . $gIdx;
      ?>
      <div class="cb-section">
        <div class="cb-section-title">
          <?= htmlspecialchars($groupName) ?>
          <div class="sel-btns">
            <button class="sel-btn" onclick="selectGroup('<?= $groupId ?>', true)">全選択</button>
            <button class="sel-btn" onclick="selectGroup('<?= $groupId ?>', false)">全解除</button>
          </div>
        </div>
        <div class="cb-group" id="<?= $groupId ?>">
          <?php foreach ($indicators as $val => $label): ?>
          <label class="cb-item">
            <input type="checkbox" class="ind-cb" value="<?= htmlspecialchars($val) ?>">
            <span><?= htmlspecialchars($label) ?></span>
          </label>
          <?php endforeach; ?>
        </div>
      </div>
      <?php endforeach; ?>
    </div>

    <div class="actions">
      <button class="btn-run" id="btn-run" onclick="runBacktest()">バックテスト実行</button>
      <button class="btn-reset" id="btn-reset" onclick="resetBt()">実行フラグをリセット</button>
      <button class="btn-st-reset" onclick="resetSimulationTrades()">シミュレーション履歴をリセット</button>
    </div>
  </div>

  <!-- 結果表示エリア -->
  <div class="result-wrap" id="result-wrap">
    <div class="summary-grid" id="summary-grid"></div>
    <div class="tabs" id="tabs"></div>
    <div id="tab-content"></div>
  </div>
</main>

<script>
var DATE_RANGES = <?= $dateRangesJson ?>;
var _pollTimer = null;

// ---- 日付範囲自動セット ----
function updateDateRange() {
  var pair = document.getElementById('pair').value;
  var tf   = document.getElementById('timeframe').value;
  var r    = (DATE_RANGES[pair] || {})[tf] || {};
  if (r.min) document.getElementById('start_date').value = r.min;
  if (r.max) document.getElementById('end_date').value   = r.max;
}

document.getElementById('pair').addEventListener('change', updateDateRange);
document.getElementById('timeframe').addEventListener('change', updateDateRange);
updateDateRange();

// ---- グループ全選択/解除 ----
function selectGroup(groupId, checked) {
  document.querySelectorAll('#' + groupId + ' .ind-cb').forEach(function(cb){ cb.checked = checked; });
}

// ---- バックテスト実行 ----
function runBacktest() {
  var indicators = [];
  document.querySelectorAll('.ind-cb:checked').forEach(function(cb){ indicators.push(cb.value); });
  if (!indicators.length) { showErr('指標を1つ以上選択してください'); return; }

  hideErr();
  document.getElementById('result-wrap').classList.remove('show');
  showOverlay('バックテスト実行中...', 'しばらくお待ちください（30秒〜数分）');
  document.getElementById('btn-run').disabled = true;

  var params = {
    pair:            document.getElementById('pair').value,
    timeframe:       document.getElementById('timeframe').value,
    start_date:      document.getElementById('start_date').value,
    end_date:        document.getElementById('end_date').value,
    initial_capital: parseInt(document.getElementById('capital').value, 10),
    sl_pips:         parseFloat(document.getElementById('sl_pips').value),
    rr_ratio:        parseFloat(document.getElementById('rr_ratio').value),
    sl_mode:         document.getElementById('sl_mode').value,
    indicators:      indicators,
  };

  fetch('/admin/api.php?action=bt_run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(params),
  })
  .then(function(r){ return r.text(); })
  .then(function(text){
    var d;
    try { d = JSON.parse(text); } catch(e) { d = {status:'error',message:text.substring(0,300)}; }
    if (d.status === 'started') {
      pollStatus();
    } else if (d.status === 'busy') {
      hideOverlay();
      document.getElementById('btn-run').disabled = false;
      document.getElementById('btn-reset').style.display = 'inline-block';
      showErr(d.message);
    } else {
      hideOverlay();
      document.getElementById('btn-run').disabled = false;
      showErr(d.message || 'エラーが発生しました');
    }
  })
  .catch(function(e){
    hideOverlay();
    document.getElementById('btn-run').disabled = false;
    showErr('通信エラー: ' + e.message);
  });
}

// ---- ポーリング ----
function pollStatus() {
  if (_pollTimer) clearInterval(_pollTimer);
  var maxTries = 120; // 最大4分 (2s×120)
  var tries = 0;
  _pollTimer = setInterval(function(){
    tries++;
    if (tries > maxTries) {
      clearInterval(_pollTimer);
      hideOverlay();
      document.getElementById('btn-run').disabled = false;
      showErr('タイムアウト: バックテストが完了しませんでした。ページをリロードして再試行してください。');
      return;
    }
    fetch('/admin/api.php?action=bt_status')
    .then(function(r){ return r.text(); })
    .then(function(text){
      var d;
      try { d = JSON.parse(text); } catch(e) { return; }
      if (d.status === 'running') {
        document.getElementById('overlay-sub').textContent = '実行中... (' + tries + '秒経過)';
      } else if (d.status === 'done') {
        clearInterval(_pollTimer);
        hideOverlay();
        document.getElementById('btn-run').disabled = false;
        showResults(d.results || []);
      } else if (d.status === 'error') {
        clearInterval(_pollTimer);
        hideOverlay();
        document.getElementById('btn-run').disabled = false;
        showErr(d.error || d.message || 'バックテストエラー');
      }
    })
    .catch(function(){});
  }, 2000);
}

// ---- リセット ----
function resetBt() {
  fetch('/admin/api.php?action=bt_reset', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
  .then(function(r){ return r.text(); })
  .then(function(text){
    var d; try { d = JSON.parse(text); } catch(e) { d = {}; }
    document.getElementById('btn-reset').style.display = 'none';
    hideErr();
    alert(d.message || 'リセットしました');
  });
}

// ---- シミュレーション履歴リセット ----
function resetSimulationTrades() {
  if (!confirm('シミュレーション履歴とバックテスト結果をすべて削除します。\nこの操作は元に戻せません。よろしいですか？')) return;
  fetch('/admin/api.php?action=simulation_trades_reset', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
  .then(function(r){ return r.json(); })
  .then(function(d){
    alert(d.status === 'ok' ? d.message : 'エラー: ' + (d.message || '不明'));
  })
  .catch(function(){ alert('通信エラーが発生しました'); });
}

// ---- 結果表示 ----
function showResults(results) {
  if (!results || !results.length) {
    showErr('結果がありません。選択した条件では取引シグナルが発生しませんでした。');
    return;
  }
  // 集計
  var totalTrades = 0, totalWin = 0, totalProfit = 0, capital0 = results[0].initial_capital || 0;
  results.forEach(function(r){
    totalTrades += r.total_trades || 0;
    totalWin    += r.winning_trades || 0;
    totalProfit += r.total_profit || 0;
  });
  var winRate = totalTrades > 0 ? (totalWin / totalTrades * 100).toFixed(1) : '0.0';
  var yieldPct = capital0 > 0 ? (totalProfit / capital0 * 100).toFixed(2) : '0.00';

  var sg = document.getElementById('summary-grid');
  sg.innerHTML = [
    sumCard('総取引数',  totalTrades + '回', ''),
    sumCard('勝率', winRate + '%', parseFloat(winRate) >= 50 ? 'green' : 'red'),
    sumCard('損益合計', fmtJpy(totalProfit), totalProfit >= 0 ? 'green' : 'red'),
    sumCard('利回り', yieldPct + '%', parseFloat(yieldPct) >= 0 ? 'green' : 'red'),
  ].join('');

  // タブ
  var tabs = document.getElementById('tabs');
  var content = document.getElementById('tab-content');
  tabs.innerHTML = '';
  content.innerHTML = '';

  results.forEach(function(r, i){
    var id = 'tab_' + i;
    var btn = document.createElement('button');
    btn.className = 'tab-btn' + (i === 0 ? ' active' : '');
    btn.textContent = r.indicator_name || ('指標' + (i+1));
    btn.onclick = function(){ switchTab(id, btn); };
    tabs.appendChild(btn);

    var panel = document.createElement('div');
    panel.id = id;
    panel.className = 'tab-panel' + (i === 0 ? ' active' : '');
    panel.innerHTML = buildIndicatorCard(r);
    content.appendChild(panel);
  });

  document.getElementById('result-wrap').classList.add('show');
}

function switchTab(id, btn) {
  document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
  document.querySelectorAll('.tab-panel').forEach(function(p){ p.classList.remove('active'); });
  btn.classList.add('active');
  document.getElementById(id).classList.add('active');
}

function buildIndicatorCard(r) {
  var trades = r.trades || [];
  var wr = r.win_rate || 0;
  var pf = r.profit_factor || 0;

  var rows = trades.map(function(t){
    var signalBadge = '<span class="badge ' + (t.signal === 'BUY' ? 'buy' : 'sell') + '">' + (t.signal === 'BUY' ? '買い' : '売り') + '</span>';
    var outcomeBadge = '<span class="badge ' + (t.outcome === 'WIN' ? 'win' : 'loss') + '">' + (t.outcome === 'WIN' ? '勝' : '負') + '</span>';
    return '<tr><td>' + (t.entry_ts||'') + '</td><td>' + (t.exit_ts||'') + '</td><td>' + signalBadge + '</td>'
         + '<td>' + fmtPrice(t.entry_price) + '</td><td>' + fmtPrice(t.exit_price) + '</td>'
         + '<td>' + outcomeBadge + '</td><td>' + fmtJpy(t.capital_after) + '</td></tr>';
  }).join('');

  return '<div class="ind-card">'
    + '<h4>' + (r.indicator_name || '') + '</h4>'
    + '<div class="ind-stats">'
    + indStat(r.total_trades + '回', '取引数')
    + indStat(wr.toFixed(1) + '%', '勝率', wr >= 50 ? 'green' : 'red')
    + indStat(fmtJpy(r.total_profit), '損益', r.total_profit >= 0 ? 'green' : 'red')
    + indStat(pf.toFixed(2), 'PF', pf >= 1 ? 'green' : 'red')
    + indStat(r.sl_mode === 'bb' ? 'BB動的' : (r.sl_pips + '/' + r.tp_pips + 'p'), 'SL/TP', r.sl_mode === 'bb' ? 'green' : '')
    + '</div>'
    + (trades.length ? '<div style="overflow-x:auto"><table class="trade-table"><thead><tr>'
      + '<th>エントリー</th><th>エグジット</th><th>方向</th><th>EP</th><th>XP</th><th>結果</th><th>残高</th>'
      + '</tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div style="font-size:12px;color:#64748b;padding:8px 0">取引履歴なし</div>')
    + '</div>';
}

function sumCard(label, val, cls) {
  return '<div class="sum-card"><div class="s-label">' + label + '</div><div class="s-val ' + cls + '">' + val + '</div></div>';
}
function indStat(val, label, cls) {
  return '<div class="ind-stat"><div class="iv ' + (cls||'') + '">' + val + '</div><div class="il">' + label + '</div></div>';
}
function fmtJpy(v) {
  var n = parseInt(v, 10);
  return (n >= 0 ? '+' : '') + n.toLocaleString('ja-JP') + '円';
}
function fmtPrice(v) { return parseFloat(v).toFixed(3); }

function showOverlay(msg, sub) {
  document.getElementById('overlay-msg').textContent = msg || '';
  document.getElementById('overlay-sub').textContent = sub || '';
  document.getElementById('overlay').classList.add('active');
}
function hideOverlay() { document.getElementById('overlay').classList.remove('active'); }
function showErr(msg) {
  var b = document.getElementById('err-banner');
  b.textContent = msg;
  b.style.display = 'block';
  b.scrollIntoView({behavior:'smooth',block:'nearest'});
}
function hideErr() { document.getElementById('err-banner').style.display = 'none'; }
</script>
</body>
</html>
