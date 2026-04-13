<?php
/**
 * 管理パネル トップ - ログイン / ダッシュボード
 */
require_once __DIR__ . '/_config.php';
session_start();

// ---- POST ログイン処理 ----
$loginError = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $pw = $_POST['password'] ?? '';
    if ($pw === ADMIN_PASSWORD) {
        $_SESSION['admin_logged_in'] = true;
        header('Location: /admin/');
        exit;
    }
    $loginError = 'パスワードが違います';
}

$isLoggedIn = !empty($_SESSION['admin_logged_in']);

// ---- ログアウト ----
if (isset($_GET['logout'])) {
    $_SESSION = [];
    session_destroy();
    header('Location: /admin/');
    exit;
}

// ---- ダッシュボードデータ (ログイン済みのみ) ----
$stats      = ['price_rows' => 0, 'signal_count' => 0, 'bt_count' => 0];
$lastFetch  = '未実行';
$lastBt     = '未実行';
$lastSignal = '未実行';
if ($isLoggedIn) {
    try {
        $pdo = get_pdo();
        $stats['price_rows']   = (int)$pdo->query('SELECT COUNT(*) FROM price_data')->fetchColumn();
        $stats['signal_count'] = (int)$pdo->query('SELECT COUNT(*) FROM trading_signals WHERE is_active=1')->fetchColumn();
        $stats['bt_count']     = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
    } catch (Exception $e) {}
    $lastFetch  = setting_get('last_data_fetch_at',    '未実行');
    $lastBt     = setting_get('last_backtest_at',      '未実行');
    $lastSignal = setting_get('last_signal_update_at', '未実行');
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= $isLoggedIn ? '管理ダッシュボード' : '管理パネル ログイン' ?> | FX Trend</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
/* ---- 共通ヘッダー ---- */
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav{display:flex;gap:12px;align-items:center}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;transition:background .15s}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
/* ---- ログイン ---- */
.login-wrap{display:flex;align-items:center;justify-content:center;min-height:calc(100vh - 57px)}
.login-card{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:36px 32px;width:340px}
.login-card h2{font-size:18px;font-weight:700;color:#f1f5f9;margin-bottom:24px;text-align:center}
.login-card label{display:block;font-size:12px;color:#94a3b8;margin-bottom:6px}
.login-card input[type=password]{width:100%;background:#0f172a;border:1px solid #475569;border-radius:8px;color:#e2e8f0;padding:10px 12px;font-size:14px;outline:none}
.login-card input[type=password]:focus{border-color:#3b82f6}
.login-card button{margin-top:18px;width:100%;background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:11px;font-size:14px;font-weight:600;cursor:pointer}
.login-card button:hover{background:#2563eb}
.login-err{margin-top:12px;color:#f87171;font-size:13px;text-align:center}
/* ---- ダッシュボード ---- */
main{max-width:900px;margin:0 auto;padding:28px 20px}
.section{margin-bottom:32px}
.section-title{font-size:13px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.7px;margin-bottom:14px}
.stats-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.stat-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 18px}
.stat-card .label{font-size:12px;color:#64748b;margin-bottom:6px}
.stat-card .value{font-size:26px;font-weight:700;color:#f1f5f9}
.run-times{background:#1e293b;border:1px solid #334155;border-radius:10px;overflow:hidden}
.run-row{display:flex;align-items:center;justify-content:space-between;padding:13px 18px;border-bottom:1px solid #0f172a}
.run-row:last-child{border-bottom:none}
.run-label{font-size:13px;color:#94a3b8}
.run-time{font-size:13px;color:#60a5fa;font-family:'Courier New',monospace}
.ops-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.op-card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px}
.op-card h3{font-size:14px;font-weight:600;color:#f1f5f9;margin-bottom:6px}
.op-card p{font-size:12px;color:#64748b;margin-bottom:14px;line-height:1.5}
.run-btn{width:100%;padding:9px;border:none;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;transition:background .2s}
.run-btn.fetch{background:#0e7490;color:#fff}.run-btn.fetch:hover{background:#0c6276}
.run-btn.bt{background:#7c3aed;color:#fff}.run-btn.bt:hover{background:#6d28d9}
.run-btn.sig{background:#15803d;color:#fff}.run-btn.sig:hover{background:#166534}
.run-btn:disabled{opacity:.5;cursor:not-allowed}
.result-msg{margin-top:8px;font-size:12px;min-height:18px;text-align:center}
.result-msg.ok{color:#4ade80}.result-msg.err{color:#f87171}.result-msg.info{color:#60a5fa}
.tool-card{background:#1e293b;border:1px solid #3b82f6;border-radius:10px;padding:20px 18px;display:flex;align-items:center;justify-content:space-between}
.tool-card .info h3{font-size:15px;font-weight:600;color:#f1f5f9;margin-bottom:4px}
.tool-card .info p{font-size:12px;color:#64748b}
.tool-card a{background:#3b82f6;color:#fff;text-decoration:none;padding:9px 20px;border-radius:8px;font-size:13px;font-weight:600;white-space:nowrap}
.tool-card a:hover{background:#2563eb}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{display:inline-block;width:13px;height:13px;border:2px solid #ffffff44;border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:5px}
</style>
</head>
<body>
<header>
  <h1>FX Trend 管理パネル</h1>
  <?php if ($isLoggedIn): ?>
  <nav class="nav">
    <a href="/admin/" class="active">ダッシュボード</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/export.php">CSVエクスポート</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/settings.php">設定 &amp; 診断</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
  <?php endif; ?>
</header>

<?php if (!$isLoggedIn): ?>
<!-- ===== ログインフォーム ===== -->
<div class="login-wrap">
  <div class="login-card">
    <h2>管理パネル ログイン</h2>
    <form method="post">
      <label for="pw">パスワード</label>
      <input type="password" id="pw" name="password" autofocus required>
      <button type="submit">ログイン</button>
      <?php if ($loginError): ?>
        <div class="login-err"><?= htmlspecialchars($loginError) ?></div>
      <?php endif; ?>
    </form>
  </div>
</div>

<?php else: ?>
<!-- ===== ダッシュボード ===== -->
<main>
  <div class="section">
    <div class="section-title">データ概要</div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="label">価格データ行数</div>
        <div class="value"><?= number_format($stats['price_rows']) ?></div>
      </div>
      <div class="stat-card">
        <div class="label">アクティブシグナル</div>
        <div class="value"><?= number_format($stats['signal_count']) ?></div>
      </div>
      <div class="stat-card">
        <div class="label">バックテスト件数</div>
        <div class="value"><?= number_format($stats['bt_count']) ?></div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">最終実行日時</div>
    <div class="run-times">
      <div class="run-row">
        <span class="run-label">データ取得</span>
        <span class="run-time" id="rt-fetch"><?= htmlspecialchars($lastFetch) ?></span>
      </div>
      <div class="run-row">
        <span class="run-label">バックテスト</span>
        <span class="run-time" id="rt-bt"><?= htmlspecialchars($lastBt) ?></span>
      </div>
      <div class="run-row">
        <span class="run-label">シグナル更新</span>
        <span class="run-time" id="rt-signal"><?= htmlspecialchars($lastSignal) ?></span>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">データ操作</div>
    <div class="ops-grid">
      <div class="op-card">
        <h3>データ取得</h3>
        <p>Yahoo Finance から全ペア・全TFの価格データを取得してDBに保存します。</p>
        <button class="run-btn fetch" onclick="runOp('fetch')">データ取得を実行</button>
        <div class="result-msg" id="msg-fetch"></div>
      </div>
      <div class="op-card">
        <h3>バックテスト</h3>
        <p>全ペア・全TF・全指標のバックテストを実行してDBに保存します（数分かかります）。</p>
        <button class="run-btn bt" onclick="runOp('backtest')">バックテストを実行</button>
        <div class="result-msg" id="msg-backtest"></div>
      </div>
      <div class="op-card">
        <h3>シグナル更新</h3>
        <p>現在の価格データと指標からアクティブシグナルを再生成します。</p>
        <button class="run-btn sig" onclick="runOp('signals')">シグナル更新を実行</button>
        <div class="result-msg" id="msg-signals"></div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">ユーザー向けツール</div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="tool-card">
        <div class="info">
          <h3>カスタムバックテスト v1</h3>
          <p>通貨ペア・期間・資金・RR比・指標を自由に設定してバックテストを実行できます</p>
        </div>
        <a href="/admin/backtest.php">ツールを開く →</a>
      </div>
      <div class="tool-card" style="border-color:#7c3aed">
        <div class="info">
          <h3>マルチ条件バックテスト v2</h3>
          <p>複数テクニカル条件・フィルター・複数ペア同時検証・パラメータ最適化に対応</p>
        </div>
        <a href="/admin/backtest_v2.php" style="background:#7c3aed">ツールを開く →</a>
      </div>
    </div>
  </div>
</main>

<script>
var _pollTimers = {};

function runOp(op) {
  var cfgs = {
    fetch:    { action: 'run_fetch',    btnSel: '.run-btn.fetch', msgId: 'msg-fetch',   rtId: 'rt-fetch',  opKey: 'fetch_status',   rtKey: 'last_fetch' },
    backtest: { action: 'run_backtest', btnSel: '.run-btn.bt',    msgId: 'msg-backtest',rtId: 'rt-bt',     opKey: 'backtest_status',rtKey: 'last_bt' },
    signals:  { action: 'run_signals',  btnSel: '.run-btn.sig',   msgId: 'msg-signals', rtId: 'rt-signal', opKey: 'signal_status',  rtKey: 'last_signal' },
  };
  var cfg = cfgs[op];
  var btn = document.querySelector(cfg.btnSel);
  var msg = document.getElementById(cfg.msgId);
  var origText = btn.textContent;

  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>開始中...';
  msg.className = 'result-msg info';
  msg.textContent = '';

  fetch('/admin/api.php?action=' + cfg.action, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
    body: JSON.stringify({}),
  })
  .then(function(r){ return r.text(); })
  .then(function(text){
    var d;
    try { d = JSON.parse(text); } catch(e) { d = {status:'error',message:text.substring(0,200)}; }
    if (d.status === 'started') {
      msg.textContent = d.message;
      btn.innerHTML = '<span class="spin"></span>実行中...';
      pollOpStatus(op, cfg, btn, msg, origText);
    } else {
      msg.textContent = d.message || 'エラー';
      msg.className = 'result-msg err';
      btn.disabled = false;
      btn.textContent = origText;
    }
  })
  .catch(function(e){
    msg.textContent = '通信エラー: ' + e.message;
    msg.className = 'result-msg err';
    btn.disabled = false;
    btn.textContent = origText;
  });
}

function pollOpStatus(op, cfg, btn, msg, origText) {
  if (_pollTimers[op]) clearInterval(_pollTimers[op]);
  var maxTries = 120; // 最大6分 (3s×120)
  var tries = 0;
  _pollTimers[op] = setInterval(function(){
    tries++;
    if (tries > maxTries) {
      clearInterval(_pollTimers[op]);
      msg.textContent = 'タイムアウト。ページをリロードして最終実行時刻を確認してください。';
      msg.className = 'result-msg info';
      btn.disabled = false;
      btn.textContent = origText;
      return;
    }
    fetch('/admin/api.php?action=op_status&op=' + op)
    .then(function(r){ return r.text(); })
    .then(function(text){
      var d;
      try { d = JSON.parse(text); } catch(e) { return; }
      var opSt = d.op_status || '';
      if (opSt === 'done') {
        clearInterval(_pollTimers[op]);
        msg.textContent = '完了！';
        msg.className = 'result-msg ok';
        btn.disabled = false;
        btn.textContent = origText;
        // 最終実行時刻を更新
        if (cfg.rtId === 'rt-fetch'  && d.last_fetch)  document.getElementById('rt-fetch').textContent  = d.last_fetch;
        if (cfg.rtId === 'rt-bt'     && d.last_bt)     document.getElementById('rt-bt').textContent     = d.last_bt;
        if (cfg.rtId === 'rt-signal' && d.last_signal) document.getElementById('rt-signal').textContent = d.last_signal;
      } else if (opSt === 'error') {
        clearInterval(_pollTimers[op]);
        msg.textContent = 'エラーが発生しました。ログを確認してください。';
        msg.className = 'result-msg err';
        btn.disabled = false;
        btn.textContent = origText;
      }
    })
    .catch(function(){});
  }, 3000);
}
</script>
<?php endif; ?>
</body>
</html>
