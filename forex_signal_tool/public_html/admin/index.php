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
$stats      = ['price_rows' => 0, 'signal_count' => 0, 'bt_count' => 0, 'sim_count' => 0];
$lastFetch       = '未実行';
$lastDailyFetch  = '未実行';
$lastBt          = '未実行';
$lastSignal      = '未実行';
$dbUsage         = [];
$simByPair       = [];
$simByTf         = [];
$simWinLoss      = ['WIN' => 0, 'LOSS' => 0];
$btTopByWinRate  = [];
$btByPair        = [];
$btByTf          = [];

if ($isLoggedIn) {
    try {
        $pdo = get_pdo();

        // ---- 基本統計 ----
        $stats['price_rows']   = (int)$pdo->query('SELECT COUNT(*) FROM price_data')->fetchColumn();
        $stats['signal_count'] = (int)$pdo->query('SELECT COUNT(*) FROM trading_signals WHERE is_active=1')->fetchColumn();
        $stats['bt_count']     = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
        $stats['sim_count']    = (int)$pdo->query('SELECT COUNT(*) FROM simulation_trades')->fetchColumn();

        // ---- DB 使用量内訳 (information_schema) ----
        $dbName = $pdo->query('SELECT DATABASE()')->fetchColumn();
        $dbRows = $pdo->query("
            SELECT table_name,
                   ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb,
                   table_rows AS est_rows
            FROM information_schema.tables
            WHERE table_schema = " . $pdo->quote($dbName) . "
            ORDER BY (data_length + index_length) DESC
        ")->fetchAll(PDO::FETCH_ASSOC);
        foreach ($dbRows as $r) {
            $dbUsage[] = [
                'table'    => $r['table_name'],
                'size_mb'  => (float)$r['size_mb'],
                'est_rows' => (int)$r['est_rows'],
            ];
        }

        // ---- シミュレーショントレード: 通貨ペア別 ----
        $rows = $pdo->query("
            SELECT currency_pair,
                   COUNT(*) AS cnt,
                   SUM(outcome='WIN')  AS wins,
                   SUM(outcome='LOSS') AS losses
            FROM simulation_trades
            GROUP BY currency_pair
            ORDER BY cnt DESC
        ")->fetchAll(PDO::FETCH_ASSOC);
        foreach ($rows as $r) {
            $simByPair[] = [
                'pair'   => $r['currency_pair'],
                'cnt'    => (int)$r['cnt'],
                'wins'   => (int)$r['wins'],
                'losses' => (int)$r['losses'],
                'rate'   => $r['cnt'] > 0 ? round($r['wins'] / $r['cnt'] * 100, 1) : 0,
            ];
        }

        // ---- シミュレーショントレード: 時間足別 ----
        $tfOrder = ['5min','15min','30min','1hr','4hr','daily'];
        $rows = $pdo->query("
            SELECT timeframe,
                   COUNT(*) AS cnt,
                   SUM(outcome='WIN')  AS wins,
                   SUM(outcome='LOSS') AS losses
            FROM simulation_trades
            GROUP BY timeframe
        ")->fetchAll(PDO::FETCH_ASSOC);
        $tfMap = [];
        foreach ($rows as $r) { $tfMap[$r['timeframe']] = $r; }
        foreach ($tfOrder as $tf) {
            if (!isset($tfMap[$tf])) continue;
            $r = $tfMap[$tf];
            $simByTf[] = [
                'tf'     => $tf,
                'cnt'    => (int)$r['cnt'],
                'wins'   => (int)$r['wins'],
                'losses' => (int)$r['losses'],
                'rate'   => $r['cnt'] > 0 ? round($r['wins'] / $r['cnt'] * 100, 1) : 0,
            ];
        }

        // ---- シミュレーショントレード: 勝敗合計 ----
        $simWinLoss['WIN']  = (int)$pdo->query("SELECT COUNT(*) FROM simulation_trades WHERE outcome='WIN'")->fetchColumn();
        $simWinLoss['LOSS'] = (int)$pdo->query("SELECT COUNT(*) FROM simulation_trades WHERE outcome='LOSS'")->fetchColumn();

        // ---- バックテスト: 勝率上位10件 ----
        $btTopByWinRate = $pdo->query("
            SELECT currency_pair, timeframe, indicator_name, win_rate, total_trades, calculated_at
            FROM backtest_results
            WHERE total_trades >= 10
            ORDER BY win_rate DESC
            LIMIT 10
        ")->fetchAll(PDO::FETCH_ASSOC);

        // ---- バックテスト: 通貨ペア別件数 ----
        $rows = $pdo->query("
            SELECT currency_pair, COUNT(*) AS cnt
            FROM backtest_results
            GROUP BY currency_pair
            ORDER BY cnt DESC
        ")->fetchAll(PDO::FETCH_ASSOC);
        foreach ($rows as $r) {
            $btByPair[] = ['pair' => $r['currency_pair'], 'cnt' => (int)$r['cnt']];
        }

        // ---- バックテスト: 時間足別件数 ----
        $rows = $pdo->query("
            SELECT timeframe, COUNT(*) AS cnt
            FROM backtest_results
            GROUP BY timeframe
        ")->fetchAll(PDO::FETCH_ASSOC);
        $tfMap2 = [];
        foreach ($rows as $r) { $tfMap2[$r['timeframe']] = (int)$r['cnt']; }
        foreach ($tfOrder as $tf) {
            if (!isset($tfMap2[$tf])) continue;
            $btByTf[] = ['tf' => $tf, 'cnt' => $tfMap2[$tf]];
        }

    } catch (Exception $e) {}

    $lastFetch      = setting_get('last_data_fetch_at',    '未実行');
    $lastDailyFetch = setting_get('last_daily_fetch_at',   '未実行');
    $lastBt         = setting_get('last_backtest_at',      '未実行');
    $lastSignal     = setting_get('last_signal_update_at', '未実行');
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
.run-btn.qf{background:#4f46e5;color:#fff}.run-btn.qf:hover{background:#4338ca}
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
/* ---- 拡張テーブル ---- */
.data-table{width:100%;border-collapse:collapse;font-size:13px}
.data-table th{background:#1e293b;color:#64748b;font-weight:600;padding:9px 12px;text-align:left;border-bottom:1px solid #334155}
.data-table td{padding:8px 12px;border-bottom:1px solid #1e293b;color:#e2e8f0}
.data-table tr:last-child td{border-bottom:none}
.data-table tr:hover td{background:#1e293b55}
.data-table .num{text-align:right;font-family:'Courier New',monospace}
.table-wrap{background:#0f172a;border:1px solid #334155;border-radius:10px;overflow:hidden}
.win-bar-wrap{background:#1e293b;border-radius:4px;height:8px;min-width:60px;display:inline-block;vertical-align:middle;margin-right:6px}
.win-bar{background:#22c55e;height:8px;border-radius:4px}
.badge-pair{display:inline-block;background:#1e3a5f;color:#60a5fa;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:600}
.badge-tf{display:inline-block;background:#1e1a3a;color:#a78bfa;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:600}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:640px){.two-col{grid-template-columns:1fr}.stats-grid{grid-template-columns:repeat(2,1fr)}.ops-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>FX Trend 管理パネル</h1>
  <?php if ($isLoggedIn): ?>
  <nav class="nav">
    <a href="/admin/" class="active">ダッシュボード</a>
    <a href="/admin/articles.php">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
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
    <div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">
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
      <div class="stat-card">
        <div class="label">シミュレーション取引数</div>
        <div class="value"><?= number_format($stats['sim_count']) ?></div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">最終実行日時</div>
    <div class="run-times">
      <div class="run-row">
        <span class="run-label">データ取得（短期足）</span>
        <span class="run-time" id="rt-fetch"><?= htmlspecialchars($lastFetch) ?></span>
      </div>
      <div class="run-row">
        <span class="run-label">データ取得（日足 / Alpha Vantage）</span>
        <span class="run-time" id="rt-daily-fetch"><?= htmlspecialchars($lastDailyFetch) ?></span>
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
      <div class="op-card" style="border-color:#4f46e5">
        <h3 style="color:#a5b4fc">QuantFlow スコア更新</h3>
        <p>直近30日分の1hrスコアを計算してDBに保存します（チャートデータの更新）。</p>
        <button class="run-btn qf" onclick="runOp('qfscores')">スコア更新を実行</button>
        <div class="result-msg" id="msg-qfscores"></div>
      </div>
      <div class="op-card" style="border-color:#3730a3">
        <h3 style="color:#a5b4fc">QuantFlow 月次BT</h3>
        <p>USDJPYの5分足スキャルピングシミュレーションを再実行してDBに保存します（数分かかります）。</p>
        <button class="run-btn qf-bt" style="background:#3730a3;color:#fff" onclick="runOp('quantflow')">QuantFlow BT を実行</button>
        <div class="result-msg" id="msg-quantflow"></div>
      </div>
      <div class="op-card" style="border-color:#1e40af">
        <h3 style="color:#93c5fd">コード更新 (git pull)</h3>
        <p>サーバー上のコードを最新に更新します。プッシュ後にここから反映できます。</p>
        <button class="run-btn" style="background:#1d4ed8" id="btn-gitpull" onclick="runGitPull()">git pull を実行</button>
        <div id="git-output" style="display:none;margin-top:10px;padding:10px;background:#0f172a;border:1px solid #334155;border-radius:6px;font-family:monospace;font-size:11px;color:#94a3b8;white-space:pre-wrap;word-break:break-all;max-height:160px;overflow-y:auto"></div>
      </div>
      <div class="op-card" style="border-color:#065f46">
        <h3 style="color:#6ee7b7">DB マイグレーション</h3>
        <p>新機能に必要なテーブルを作成します。初回のみ実行してください（既存テーブルは変更されません）。</p>
        <button class="run-btn" style="background:#065f46;color:#fff" onclick="runMigration()">マイグレーション実行</button>
        <div class="result-msg" id="msg-migrate"></div>
      </div>
    </div>
  </div>

  <!-- ===== QuantFlow スコア（1時間足）===== -->
  <div class="section">
    <div class="section-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>QuantFlow スコア（1時間足）</span>
      <div style="display:flex;gap:8px;align-items:center">
        <select id="qf1h-range" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 8px;border-radius:6px;cursor:pointer">
          <option value="168">直近7日</option>
          <option value="336">直近14日</option>
          <option value="720">直近30日</option>
        </select>
        <button onclick="loadQf1hChart()" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer">再読込</button>
      </div>
    </div>
    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin-top:10px">
      <div id="qf1h-loading" style="text-align:center;color:#64748b;font-size:13px;padding:40px 0">
        <span class="spin" style="border-color:#33415599;border-top-color:#60a5fa"></span> 読み込み中...
      </div>
      <div id="qf1h-error" style="display:none;text-align:center;color:#f87171;font-size:13px;padding:20px 0"></div>
      <div id="qf1h-empty" style="display:none;text-align:center;padding:40px 0">
        <div style="color:#64748b;font-size:13px;margin-bottom:12px">データがありません。「QuantFlow スコア更新」を実行してください。</div>
        <button class="run-btn qf" onclick="runOp('qfscores')" style="width:auto;padding:8px 20px">スコア更新を実行</button>
      </div>
      <div id="qf1h-wrap" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div style="font-size:12px;color:#64748b">
            最新スコア:
            <span id="qf1h-latest-score" style="font-weight:700;font-size:18px;margin:0 4px"></span>
            <span id="qf1h-latest-level" style="font-size:11px;padding:2px 7px;border-radius:4px;background:#1e293b;border:1px solid #334155"></span>
          </div>
          <div style="font-size:12px;color:#64748b">
            終値: <span id="qf1h-latest-close" style="color:#94a3b8"></span>
          </div>
        </div>
        <div style="position:relative;height:260px">
          <canvas id="qfChart1h"></canvas>
        </div>
        <div style="margin-top:10px;display:flex;gap:16px;font-size:11px;color:#64748b">
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#4ade80"></span> Score ≥+30 (BUY)</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#f87171"></span> Score ≤−30 (SELL)</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#60a5fa"></span> Neutral</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#33415588;border-top:1px dashed #33415588"></span> ±30 閾値</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== QuantFlow スコア（5分足）===== -->
  <div class="section">
    <div class="section-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>QuantFlow スコア（5分足）</span>
      <div style="display:flex;gap:8px;align-items:center">
        <select id="qf5m-range" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 8px;border-radius:6px;cursor:pointer">
          <option value="288">直近1日</option>
          <option value="864">直近3日</option>
          <option value="2016" selected>直近7日</option>
        </select>
        <button onclick="loadQf5mChart()" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer">再読込</button>
      </div>
    </div>
    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin-top:10px">
      <div id="qf5m-loading" style="text-align:center;color:#64748b;font-size:13px;padding:40px 0">
        <span class="spin" style="border-color:#33415599;border-top-color:#60a5fa"></span> 読み込み中...
      </div>
      <div id="qf5m-error" style="display:none;text-align:center;color:#f87171;font-size:13px;padding:20px 0"></div>
      <div id="qf5m-empty" style="display:none;text-align:center;padding:40px 0">
        <div style="color:#64748b;font-size:13px">データがありません。5分足スコアを更新してください。</div>
      </div>
      <div id="qf5m-wrap" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div style="font-size:12px;color:#64748b">
            最新スコア:
            <span id="qf5m-latest-score" style="font-weight:700;font-size:18px;margin:0 4px"></span>
            <span id="qf5m-latest-level" style="font-size:11px;padding:2px 7px;border-radius:4px;background:#1e293b;border:1px solid #334155"></span>
          </div>
          <div style="font-size:12px;color:#64748b">
            終値: <span id="qf5m-latest-close" style="color:#94a3b8"></span>
          </div>
        </div>
        <div id="qf5m-scroll" style="overflow-x:auto;overflow-y:hidden;border-radius:4px">
          <div id="qf5m-canvas-wrap" style="height:220px">
            <canvas id="qfChart5m"></canvas>
          </div>
        </div>
        <div style="margin-top:4px;font-size:10px;color:#475569;text-align:right">← スクロールで過去データを確認</div>
        <div style="margin-top:8px;display:flex;gap:16px;font-size:11px;color:#64748b">
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#4ade80"></span> Score ≥+30 (BUY)</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#f87171"></span> Score ≤−30 (SELL)</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="display:inline-block;width:20px;height:2px;background:#60a5fa"></span> Neutral</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== QuantFlow ライブポジション ===== -->
  <div class="section">
    <div class="section-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>QuantFlow ライブポジション</span>
      <button onclick="loadLivePosition()" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer">再読込</button>
    </div>
    <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;margin-top:10px">
      <div id="live-pos-loading" style="text-align:center;color:#64748b;font-size:13px;padding:20px 0">
        <span class="spin" style="border-color:#33415599;border-top-color:#60a5fa"></span> 読み込み中...
      </div>
      <div id="live-pos-content" style="display:none"></div>
    </div>
  </div>

  <!-- ===== QuantFlow トレード実績 ===== -->
  <div class="section">
    <div class="section-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>QuantFlow トレード実績</span>
      <div style="display:flex;gap:8px;align-items:center">
        <a href="/admin/api.php?action=qf_trades_csv&pair=USDJPY" style="padding:4px 10px;background:#1e293b;border:1px solid #4f46e5;color:#a5b4fc;border-radius:6px;font-size:12px;font-weight:600;text-decoration:none">↓ CSV</a>
        <button onclick="loadAllTrades()" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer">再読込</button>
      </div>
    </div>

    <!-- サマリー -->
    <div id="live-hist-loading" style="text-align:center;color:#64748b;font-size:13px;padding:20px 0">
      <span class="spin" style="border-color:#33415599;border-top-color:#60a5fa"></span>
    </div>
    <div id="live-hist-error" style="display:none;text-align:center;color:#f87171;font-size:13px;padding:10px 0"></div>
    <div id="live-hist-content" style="display:none">

      <!-- 統計カード -->
      <div id="live-hist-stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:16px"></div>

      <!-- 全トレード一覧 -->
      <div id="live-hist-table"></div>
    </div>

  </div>

  <!-- ===== DB 使用量内訳 ===== -->
  <div class="section">
    <div class="section-title">データベース使用量内訳</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>テーブル名</th>
          <th class="num">推定件数</th>
          <th class="num">サイズ (MB)</th>
        </tr></thead>
        <tbody>
        <?php
          $totalMb = 0;
          foreach ($dbUsage as $row):
            $totalMb += $row['size_mb'];
        ?>
          <tr>
            <td><code style="font-size:12px"><?= htmlspecialchars($row['table']) ?></code></td>
            <td class="num"><?= number_format($row['est_rows']) ?></td>
            <td class="num"><?= $row['size_mb'] ?> MB</td>
          </tr>
        <?php endforeach; ?>
        </tbody>
        <tfoot><tr style="border-top:1px solid #334155">
          <td colspan="2" style="padding:9px 12px;color:#64748b;font-weight:600">合計</td>
          <td class="num" style="padding:9px 12px;font-weight:700;color:#60a5fa"><?= round($totalMb, 2) ?> MB</td>
        </tr></tfoot>
      </table>
    </div>
  </div>

  <!-- ===== シミュレーショントレード ===== -->
  <div class="section">
    <div class="section-title">シミュレーショントレード詳細</div>
    <?php
      $totalSim = $simWinLoss['WIN'] + $simWinLoss['LOSS'];
      $overallRate = $totalSim > 0 ? round($simWinLoss['WIN'] / $totalSim * 100, 1) : 0;
    ?>
    <!-- 勝敗サマリー -->
    <div class="stats-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:12px">
      <div class="stat-card">
        <div class="label">勝ちトレード</div>
        <div class="value" style="color:#4ade80"><?= number_format($simWinLoss['WIN']) ?></div>
      </div>
      <div class="stat-card">
        <div class="label">負けトレード</div>
        <div class="value" style="color:#f87171"><?= number_format($simWinLoss['LOSS']) ?></div>
      </div>
      <div class="stat-card">
        <div class="label">全体勝率</div>
        <div class="value" style="color:<?= $overallRate >= 50 ? '#4ade80' : '#f87171' ?>"><?= $overallRate ?>%</div>
      </div>
    </div>
    <!-- 通貨ペア別 / 時間足別 -->
    <div class="two-col">
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>通貨ペア</th>
            <th class="num">件数</th>
            <th>勝率</th>
          </tr></thead>
          <tbody>
          <?php foreach ($simByPair as $r): ?>
            <tr>
              <td><span class="badge-pair"><?= htmlspecialchars($r['pair']) ?></span></td>
              <td class="num"><?= number_format($r['cnt']) ?></td>
              <td>
                <span class="win-bar-wrap"><span class="win-bar" style="width:<?= $r['rate'] ?>%"></span></span>
                <?= $r['rate'] ?>%
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (empty($simByPair)): ?>
            <tr><td colspan="3" style="color:#475569;text-align:center;padding:16px">データなし</td></tr>
          <?php endif; ?>
          </tbody>
        </table>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>時間足</th>
            <th class="num">件数</th>
            <th>勝率</th>
          </tr></thead>
          <tbody>
          <?php foreach ($simByTf as $r): ?>
            <tr>
              <td><span class="badge-tf"><?= htmlspecialchars($r['tf']) ?></span></td>
              <td class="num"><?= number_format($r['cnt']) ?></td>
              <td>
                <span class="win-bar-wrap"><span class="win-bar" style="width:<?= $r['rate'] ?>%"></span></span>
                <?= $r['rate'] ?>%
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (empty($simByTf)): ?>
            <tr><td colspan="3" style="color:#475569;text-align:center;padding:16px">データなし</td></tr>
          <?php endif; ?>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ===== バックテスト詳細 ===== -->
  <div class="section">
    <div class="section-title">バックテスト詳細</div>
    <!-- ペア別 / TF別 -->
    <div class="two-col" style="margin-bottom:12px">
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>通貨ペア</th>
            <th class="num">件数</th>
          </tr></thead>
          <tbody>
          <?php foreach ($btByPair as $r): ?>
            <tr>
              <td><span class="badge-pair"><?= htmlspecialchars($r['pair']) ?></span></td>
              <td class="num"><?= number_format($r['cnt']) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (empty($btByPair)): ?>
            <tr><td colspan="2" style="color:#475569;text-align:center;padding:16px">データなし</td></tr>
          <?php endif; ?>
          </tbody>
        </table>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>時間足</th>
            <th class="num">件数</th>
          </tr></thead>
          <tbody>
          <?php foreach ($btByTf as $r): ?>
            <tr>
              <td><span class="badge-tf"><?= htmlspecialchars($r['tf']) ?></span></td>
              <td class="num"><?= number_format($r['cnt']) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (empty($btByTf)): ?>
            <tr><td colspan="2" style="color:#475569;text-align:center;padding:16px">データなし</td></tr>
          <?php endif; ?>
          </tbody>
        </table>
      </div>
    </div>
    <!-- 勝率上位10件 -->
    <div class="section-title" style="margin-bottom:10px">勝率上位10件（取引10件以上）</div>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>通貨ペア</th>
          <th>時間足</th>
          <th>指標名</th>
          <th class="num">勝率</th>
          <th class="num">取引数</th>
          <th>計算日時</th>
        </tr></thead>
        <tbody>
        <?php foreach ($btTopByWinRate as $r): ?>
          <tr>
            <td><span class="badge-pair"><?= htmlspecialchars($r['currency_pair']) ?></span></td>
            <td><span class="badge-tf"><?= htmlspecialchars($r['timeframe']) ?></span></td>
            <td style="font-size:12px"><?= htmlspecialchars($r['indicator_name']) ?></td>
            <td class="num" style="color:#4ade80;font-weight:700"><?= $r['win_rate'] ?>%</td>
            <td class="num"><?= number_format($r['total_trades']) ?></td>
            <td style="font-size:11px;color:#64748b"><?= htmlspecialchars(substr($r['calculated_at'], 0, 16)) ?></td>
          </tr>
        <?php endforeach; ?>
        <?php if (empty($btTopByWinRate)): ?>
          <tr><td colspan="6" style="color:#475569;text-align:center;padding:16px">データなし（取引10件以上のバックテストがありません）</td></tr>
        <?php endif; ?>
        </tbody>
      </table>
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
    fetch:       { action: 'run_fetch',         btnSel: '.run-btn.fetch', msgId: 'msg-fetch',        rtId: 'rt-fetch',  opKey: 'fetch_status',         rtKey: 'last_fetch' },
    backtest:    { action: 'run_backtest',      btnSel: '.run-btn.bt',    msgId: 'msg-backtest',     rtId: 'rt-bt',     opKey: 'backtest_status',      rtKey: 'last_bt' },
    signals:     { action: 'run_signals',       btnSel: '.run-btn.sig',   msgId: 'msg-signals',      rtId: 'rt-signal', opKey: 'signal_status',        rtKey: 'last_signal' },
    qfscores:    { action: 'run_quantflow_scores', btnSel: '.run-btn.qf', msgId: 'msg-qfscores',     rtId: null,        opKey: 'quantflow_scores_status', rtKey: null },
    quantflow:   { action: 'run_quantflow_bt',    btnSel: '.run-btn.qf-bt', msgId: 'msg-quantflow', rtId: null,        opKey: 'quantflow_bt_status',  rtKey: null },
  };
  var cfg = cfgs[op];
  var btn = document.querySelector(cfg.btnSel);
  var msg = document.getElementById(cfg.msgId);
  var origText = btn ? btn.textContent : '';

  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin"></span>開始中...'; }
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

async function runGitPull() {
  const btn = document.getElementById('btn-gitpull');
  const out = document.getElementById('git-output');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>実行中...';
  out.style.display = 'none';
  try {
    const res = await fetch('/admin/api.php?action=git_pull', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
    });
    const d = await res.json();
    out.style.display = '';
    out.style.color = d.status === 'ok' ? '#86efac' : '#fca5a5';
    out.textContent = d.output || '(出力なし)';
  } catch(e) {
    out.style.display = '';
    out.style.color = '#fca5a5';
    out.textContent = '通信エラー: ' + e.message;
  }
  btn.disabled = false;
  btn.textContent = 'git pull を実行';
}

async function runMigration() {
  const msgEl = document.getElementById('msg-migrate');
  msgEl.textContent = '実行中...';
  msgEl.style.color = '#94a3b8';
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ action: 'migrate_custom_indicators' }),
    }).then(r => r.json());
    msgEl.textContent = res.status === 'ok' ? '✅ ' + res.message : '❌ ' + res.message;
    msgEl.style.color = res.status === 'ok' ? '#4ade80' : '#f87171';
  } catch(e) {
    msgEl.textContent = '❌ 通信エラー: ' + e.message;
    msgEl.style.color = '#f87171';
  }
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

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
var _qf1hChartInst = null;
var _qf5mChartInst = null;

function _makeQfDatasets(labels, pts) {
  var scores = pts.map(function(x){ return x.score; });
  return [
    {
      label: 'Score', data: scores,
      borderWidth: 2, pointRadius: 0, tension: 0.15,
      segment: {
        borderColor: function(ctx) {
          var v = ctx.p1.parsed.y;
          return v >= 30 ? '#4ade80' : v <= -30 ? '#f87171' : '#60a5fa';
        },
        backgroundColor: function(ctx) {
          var v = ctx.p1.parsed.y;
          return v >= 30 ? 'rgba(74,222,128,0.08)' : v <= -30 ? 'rgba(248,113,113,0.08)' : 'transparent';
        }
      },
      fill: { target: { value: 0 }, above: 'rgba(74,222,128,0.05)', below: 'rgba(248,113,113,0.05)' },
    },
    {
      label: '+30', data: labels.map(function(){ return 30; }),
      borderColor: 'rgba(74,222,128,0.3)', borderWidth: 1, borderDash: [6,4],
      pointRadius: 0, fill: false,
    },
    {
      label: '-30', data: labels.map(function(){ return -30; }),
      borderColor: 'rgba(248,113,113,0.3)', borderWidth: 1, borderDash: [6,4],
      pointRadius: 0, fill: false,
    },
    {
      label: '0', data: labels.map(function(){ return 0; }),
      borderColor: 'rgba(71,85,105,0.4)', borderWidth: 1, pointRadius: 0, fill: false,
    }
  ];
}

function _makeQfOptions(pts, maxTicks, responsive) {
  return {
    responsive: responsive !== false,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        min: -100, max: 100,
        grid:  { color: 'rgba(51,65,85,0.5)' },
        ticks: {
          color: '#64748b', stepSize: 25,
          callback: function(v) { return (v > 0 ? '+' : '') + v; }
        },
        border: { color: '#334155' }
      },
      x: {
        grid:  { display: false },
        ticks: {
          color: '#64748b', maxTicksLimit: maxTicks || 12,
          maxRotation: 0, font: { size: 10 }
        },
        border: { color: '#334155' }
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f172a', borderColor: '#334155', borderWidth: 1,
        titleColor: '#94a3b8', bodyColor: '#f1f5f9', padding: 10,
        callbacks: {
          title: function(items) { return items[0].label; },
          label: function(ctx) {
            if (ctx.dataset.label !== 'Score') return null;
            var v = ctx.parsed.y;
            var level = v >= 50 ? 'Strong Buy' : v >= 30 ? 'Buy' : v <= -50 ? 'Strong Sell' : v <= -30 ? 'Sell' : 'Neutral';
            var pt = pts[ctx.dataIndex];
            var lines = ['Score: ' + (v > 0 ? '+' : '') + v + '  [' + level + ']'];
            if (pt && pt.close) lines.push('Close: ' + pt.close + ' JPY');
            if (pt && pt.trend != null) lines.push('Trend: ' + (pt.trend > 0 ? '+' : '') + pt.trend + ' / Ext: ' + (pt.ext > 0 ? '+' : '') + pt.ext);
            return lines;
          }
        }
      }
    }
  };
}

function _setQfLatest(prefix, latest) {
  if (!latest || latest.score === null) return;
  var s = latest.score;
  var level = s >= 50 ? 'Strong Buy' : s >= 30 ? 'Buy' : s <= -50 ? 'Strong Sell' : s <= -30 ? 'Sell' : 'Neutral';
  var color = s >= 30 ? '#4ade80' : s <= -30 ? '#f87171' : '#94a3b8';
  var scoreEl = document.getElementById(prefix + '-latest-score');
  scoreEl.textContent = (s > 0 ? '+' : '') + s;
  scoreEl.style.color = color;
  var lvEl = document.getElementById(prefix + '-latest-level');
  lvEl.textContent = level;
  lvEl.style.color = color;
  lvEl.style.borderColor = color + '55';
  document.getElementById(prefix + '-latest-close').textContent = latest.close ? latest.close + ' JPY' : '-';
}

function loadQf1hChart() {
  var loading = document.getElementById('qf1h-loading');
  var errDiv  = document.getElementById('qf1h-error');
  var empty   = document.getElementById('qf1h-empty');
  var wrap    = document.getElementById('qf1h-wrap');
  var limit   = document.getElementById('qf1h-range').value;
  loading.style.display = 'block';
  errDiv.style.display  = 'none';
  empty.style.display   = 'none';
  wrap.style.display    = 'none';

  fetch('/admin/api.php?action=quantflow_chart_data&limit=' + limit + '&tf=1h', {
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(function(r){ return r.json(); })
  .then(function(d) {
    loading.style.display = 'none';
    if (!d.ok) {
      errDiv.textContent = 'エラー: ' + (d.error || '不明');
      errDiv.style.display = 'block';
      return;
    }
    if (!d.data || d.data.length === 0) {
      empty.style.display = 'block';
      return;
    }

    var pts    = d.data;
    var labels = pts.map(function(x){ return x.ts; });
    _setQfLatest('qf1h', pts[pts.length - 1]);
    wrap.style.display = 'block';
    if (_qf1hChartInst) { _qf1hChartInst.destroy(); _qf1hChartInst = null; }
    _qf1hChartInst = new Chart(document.getElementById('qfChart1h').getContext('2d'), {
      type: 'line',
      data: { labels: labels, datasets: _makeQfDatasets(labels, pts) },
      options: _makeQfOptions(pts, 12, true)
    });
  })
  .catch(function(e) {
    loading.style.display = 'none';
    errDiv.textContent = '通信エラー: ' + e.message;
    errDiv.style.display = 'block';
  });
}

function loadQf5mChart() {
  var loading = document.getElementById('qf5m-loading');
  var errDiv  = document.getElementById('qf5m-error');
  var empty   = document.getElementById('qf5m-empty');
  var wrap    = document.getElementById('qf5m-wrap');
  var limit   = document.getElementById('qf5m-range').value;
  loading.style.display = 'block';
  errDiv.style.display  = 'none';
  empty.style.display   = 'none';
  wrap.style.display    = 'none';

  fetch('/admin/api.php?action=quantflow_chart_data&limit=' + limit + '&tf=5m', {
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(function(r){ return r.json(); })
  .then(function(d) {
    loading.style.display = 'none';
    if (!d.ok) { errDiv.textContent = 'エラー: ' + (d.error||'不明'); errDiv.style.display='block'; return; }
    if (!d.data || d.data.length === 0) { empty.style.display='block'; return; }

    var pts    = d.data;
    var labels = pts.map(function(x){ return x.ts; });
    _setQfLatest('qf5m', pts[pts.length - 1]);

    var BAR_W  = 4;
    var chartW = Math.max(pts.length * BAR_W, 600);
    var chartH = 220;
    var canvas = document.getElementById('qfChart5m');
    var cWrap  = document.getElementById('qf5m-canvas-wrap');
    canvas.width  = chartW;
    canvas.height = chartH;
    cWrap.style.width  = chartW + 'px';
    cWrap.style.height = chartH + 'px';

    wrap.style.display = 'block';
    if (_qf5mChartInst) { _qf5mChartInst.destroy(); _qf5mChartInst = null; }
    _qf5mChartInst = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels: labels, datasets: _makeQfDatasets(labels, pts) },
      options: _makeQfOptions(pts, 48, false)
    });

    setTimeout(function() {
      var s = document.getElementById('qf5m-scroll');
      s.scrollLeft = s.scrollWidth;
    }, 50);
  })
  .catch(function(e) {
    loading.style.display = 'none';
    errDiv.textContent = '通信エラー: ' + e.message;
    errDiv.style.display = 'block';
  });
}

document.getElementById('qf1h-range').addEventListener('change', loadQf1hChart);
document.getElementById('qf5m-range').addEventListener('change', loadQf5mChart);
loadQf1hChart();
loadQf5mChart();

// ---- QuantFlow ライブポジション ----
async function loadLivePosition() {
  var posLoad = document.getElementById('live-pos-loading');
  var posEl   = document.getElementById('live-pos-content');
  posLoad.style.display = 'block';
  posEl.style.display   = 'none';

  try {
    var res  = await fetch('/admin/api.php?action=quantflow_live_position');
    var data = await res.json();
    if (!data.ok) throw new Error(data.error || 'エラー');

    if (data.open) {
      var p        = data.open;
      var dirColor = p.direction === 'BUY' ? '#4ade80' : '#f87171';
      var dirLabel = p.direction === 'BUY' ? '買い (BUY)' : '売り (SELL)';
      posEl.innerHTML =
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px">' +
          '<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center">' +
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px">方向</div>' +
            '<div style="font-size:18px;font-weight:700;color:' + dirColor + '">' + dirLabel + '</div>' +
          '</div>' +
          '<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center">' +
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px">スコア</div>' +
            '<div style="font-size:18px;font-weight:700;color:#94a3b8">' + p.score_at_entry + '</div>' +
          '</div>' +
          '<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center">' +
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px">エントリー価格</div>' +
            '<div style="font-size:14px;font-weight:700;color:#e2e8f0">' + parseFloat(p.entry_price).toFixed(3) + '</div>' +
          '</div>' +
          '<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center">' +
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px">SL / TP</div>' +
            '<div style="font-size:13px;color:#94a3b8">' + parseFloat(p.sl_price).toFixed(3) + ' / ' + parseFloat(p.tp_price).toFixed(3) + '</div>' +
            '<div style="font-size:11px;color:#64748b">' + p.sl_pips + 'p / ' + p.tp_pips + 'p</div>' +
          '</div>' +
          '<div style="background:#0f172a;border-radius:8px;padding:12px;text-align:center">' +
            '<div style="font-size:11px;color:#64748b;margin-bottom:4px">エントリー日時(JST)</div>' +
            '<div style="font-size:12px;color:#94a3b8">' + p.entry_jst + '</div>' +
          '</div>' +
        '</div>';
    } else {
      posEl.innerHTML = '<div style="text-align:center;color:#64748b;font-size:13px;padding:20px 0">現在ポジションなし</div>';
    }
    posLoad.style.display = 'none';
    posEl.style.display   = 'block';
  } catch(e) {
    posLoad.style.display = 'none';
    posEl.innerHTML = '<div style="color:#f87171;font-size:13px">エラー: ' + e.message + '</div>';
    posEl.style.display = 'block';
  }
}
loadLivePosition();

// ---- QuantFlow バックテスト トレード履歴 ----
var _btActiveMonth = null;

function _btSwitchTab(ym) {
  _btActiveMonth = ym;
  document.querySelectorAll('.bt-month-tab').forEach(function(t) {
    t.style.background  = t.dataset.ym === ym ? '#1d4ed8' : '#1e293b';
    t.style.color       = t.dataset.ym === ym ? '#fff'    : '#94a3b8';
    t.style.borderColor = t.dataset.ym === ym ? '#1d4ed8' : '#334155';
  });
  document.querySelectorAll('.bt-month-panel').forEach(function(p) {
    p.style.display = p.dataset.ym === ym ? 'block' : 'none';
  });
}

function _btMakeRow(t) {
  var oc = t.outcome === 'WIN' ? '#4ade80' : '#f87171';
  var pp = t.profit_pips !== null ? (parseFloat(t.profit_pips)>=0?'+':'')+parseFloat(t.profit_pips).toFixed(2) : '-';
  return '<tr>'
    + '<td>' + (t.entry_jst||'-') + '</td>'
    + '<td style="color:'+(t.direction==='BUY'?'#4ade80':'#f87171')+'">' + t.direction + '</td>'
    + '<td style="text-align:right">' + (t.score_at_entry||'-') + '</td>'
    + '<td style="text-align:right">' + parseFloat(t.entry_price).toFixed(3) + '</td>'
    + '<td style="text-align:right">' + (t.exit_price ? parseFloat(t.exit_price).toFixed(3) : '-') + '</td>'
    + '<td>' + (t.exit_jst||'-') + '</td>'
    + '<td style="text-align:center;color:'+oc+'">' + (t.outcome||'-') + '</td>'
    + '<td style="text-align:right;color:'+oc+'">' + pp + '</td>'
    + '<td style="text-align:right;color:#64748b;font-size:11px">' + (t.sl_pips||'-') + 'p / ' + (t.tp_pips||'-') + 'p</td>'
    + '</tr>';
}

async function loadAllTrades() {
  var loading = document.getElementById('live-hist-loading');
  var errDiv  = document.getElementById('live-hist-error');
  var content = document.getElementById('live-hist-content');
  loading.style.display = 'block';
  errDiv.style.display  = 'none';
  content.style.display = 'none';

  try {
    var res  = await fetch('/admin/api.php?action=quantflow_bt_history&pair=USDJPY');
    var data = await res.json();
    if (!data.ok) throw new Error(data.error || 'エラー');

    // --- 統計カード ---
    var s = data.stats;
    var winRate = s.total > 0 ? (s.wins / s.total * 100).toFixed(1) : '-';
    var pfStr   = (s.loss_pips && s.loss_pips < 0) ? Math.abs(s.win_pips / s.loss_pips).toFixed(2) : '-';
    var statsCards = [
      { label:'総トレード数',          val: s.total,                                                             color:'#94a3b8' },
      { label:'勝ち',                  val: s.wins,                                                              color:'#4ade80' },
      { label:'負け',                  val: s.losses,                                                            color:'#f87171' },
      { label:'勝率',                  val: winRate !== '-' ? winRate+'%' : '-',                                 color: parseFloat(winRate)>=50?'#4ade80':'#f87171' },
      { label:'合計損益(pips)',         val: s.total_pips !== null ? (s.total_pips>=0?'+':'')+s.total_pips : '-', color:(s.total_pips||0)>=0?'#4ade80':'#f87171' },
      { label:'平均利益(pips)',         val: s.avg_win  !== null ? '+'+s.avg_win  : '-',                          color:'#4ade80' },
      { label:'平均損失(pips)',         val: s.avg_loss !== null ? s.avg_loss+''  : '-',                          color:'#f87171' },
      { label:'プロフィットファクター', val: pfStr,                                                               color:'#60a5fa' },
    ];
    document.getElementById('live-hist-stats').innerHTML = statsCards.map(function(c) {
      return '<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:12px;text-align:center">'
        + '<div style="font-size:10px;color:#64748b;margin-bottom:4px">' + c.label + '</div>'
        + '<div style="font-size:16px;font-weight:700;color:' + c.color + '">' + c.val + '</div>'
        + '</div>';
    }).join('');

    if (data.trades.length === 0) {
      document.getElementById('live-hist-table').innerHTML = '<div style="text-align:center;color:#64748b;font-size:13px;padding:20px 0">トレード履歴なし</div>';
      loading.style.display = 'none';
      content.style.display = 'block';
      return;
    }

    // --- 月ごとにグループ化 ---
    var grouped = {};
    var months  = [];
    data.trades.forEach(function(t) {
      var ym = t.year_month || '不明';
      if (!grouped[ym]) { grouped[ym] = []; months.push(ym); }
      grouped[ym].push(t);
    });
    // 降順ソート（例: "2025-04" > "2025-03"）
    months.sort(function(a, b) { return b > a ? 1 : -1; });
    if (!_btActiveMonth || !grouped[_btActiveMonth]) _btActiveMonth = months[0];

    var thead = '<thead><tr>'
      + '<th>エントリー(JST)</th><th>方向</th><th class="num">スコア</th>'
      + '<th class="num">Entry価格</th><th class="num">Exit価格</th>'
      + '<th>決済日時(JST)</th><th>結果</th><th class="num">損益(pips)</th><th class="num">SL/TP</th>'
      + '</tr></thead>';

    // --- タブ ---
    var tabsHtml = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px">';
    months.forEach(function(ym) {
      var cnt = grouped[ym].length;
      var wins = grouped[ym].filter(function(t){ return t.outcome==='WIN'; }).length;
      var wr   = cnt > 0 ? Math.round(wins/cnt*100) : 0;
      var isActive = ym === _btActiveMonth;
      tabsHtml += '<button class="bt-month-tab" data-ym="' + ym + '" onclick="_btSwitchTab(\'' + ym + '\')"'
        + ' style="background:' + (isActive?'#1d4ed8':'#1e293b') + ';border:1px solid '+(isActive?'#1d4ed8':'#334155')+';'
        + 'color:'+(isActive?'#fff':'#94a3b8')+';font-size:12px;padding:5px 12px;border-radius:6px;cursor:pointer">'
        + ym + ' <span style="font-size:10px;opacity:0.8">(' + cnt + '件 ' + wr + '%)</span></button>';
    });
    tabsHtml += '</div>';

    // --- 月ごとパネル（10件 + 折りたたみ）---
    var panelsHtml = '';
    months.forEach(function(ym) {
      var trades = grouped[ym];
      var first10 = trades.slice(0, 10);
      var rest    = trades.slice(10);
      var panelId = 'bt-panel-' + ym.replace('-','');
      var restId  = 'bt-rest-'  + ym.replace('-','');
      var btnId   = 'bt-btn-'   + ym.replace('-','');

      var rowsFirst = first10.map(_btMakeRow).join('');
      var rowsRest  = rest.map(_btMakeRow).join('');

      var monthStats = (function() {
        var tc = trades.length;
        var wc = trades.filter(function(t){ return t.outcome==='WIN'; }).length;
        var tp = trades.reduce(function(acc,t){ return acc + (parseFloat(t.profit_pips)||0); }, 0);
        var wr = tc > 0 ? (wc/tc*100).toFixed(1)+'%' : '-';
        return '月計: ' + tc + '件 / 勝率 ' + wr + ' / ' + (tp>=0?'+':'') + tp.toFixed(2) + 'pips';
      })();

      panelsHtml += '<div class="bt-month-panel" data-ym="' + ym + '" style="display:' + (ym===_btActiveMonth?'block':'none') + '">'
        + '<div style="font-size:11px;color:#64748b;margin-bottom:8px">' + monthStats + '</div>'
        + '<div class="table-wrap"><table class="data-table">' + thead
        + '<tbody>' + rowsFirst;

      if (rest.length > 0) {
        panelsHtml += '<tr id="' + restId + '" style="display:none"><td colspan="9" style="padding:0">'
          + '<table style="width:100%;border-collapse:collapse">' + rowsRest + '</table>'
          + '</td></tr>'
          + '<tr><td colspan="9" style="text-align:center;padding:8px">'
          + '<button id="' + btnId + '" onclick="(function(){'
          + 'var r=document.getElementById(\'' + restId + '\');'
          + 'var b=document.getElementById(\'' + btnId + '\');'
          + 'var open=r.style.display!==\'none\';'
          + 'r.style.display=open?\'none\':\'table-row\';'
          + 'b.textContent=open?\'▼ 残り'+rest.length+'件を表示\':\'▲ 折りたたむ\';'
          + '})()" style="background:none;border:1px solid #334155;color:#64748b;font-size:12px;padding:5px 16px;border-radius:6px;cursor:pointer">'
          + '▼ 残り' + rest.length + '件を表示</button></td></tr>';
      }

      panelsHtml += '</tbody></table></div></div>';
    });

    document.getElementById('live-hist-table').innerHTML = tabsHtml + panelsHtml;
    loading.style.display = 'none';
    content.style.display = 'block';
  } catch(e) {
    loading.style.display = 'none';
    errDiv.textContent = 'エラー: ' + e.message;
    errDiv.style.display = 'block';
  }
}
loadAllTrades();

// ---- カスタム複合指標 ----
function escHtmlCi(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function loadCustomIndicators() {
  const el = document.getElementById('custom-indicator-list');
  if (!el) return;
  try {
    const res = await fetch('/admin/api.php?action=list_custom_indicators', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({}),
    }).then(r => r.json());
    if (res.status !== 'ok' || !res.indicators || res.indicators.length === 0) {
      el.innerHTML = '<div style="color:#475569;text-align:center;padding:12px">登録済み指標はありません</div>';
      return;
    }
    el.innerHTML = res.indicators.map(ind => `
      <div style="background:#0b1525;border:1px solid #${ind.is_active == 1 ? '1e3a5f' : '334155'};border-radius:8px;padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div style="flex:1;min-width:200px">
          <div style="font-size:14px;font-weight:600;color:${ind.is_active == 1 ? '#f1f5f9' : '#475569'}">${escHtmlCi(ind.display_name)}</div>
          <div style="font-size:11px;color:#475569;margin-top:2px;font-family:monospace">${escHtmlCi(ind.name)}</div>
          ${ind.description ? `<div style="font-size:11px;color:#64748b;margin-top:4px">${escHtmlCi(ind.description)}</div>` : ''}
          <div style="font-size:11px;color:#334155;margin-top:2px">登録日: ${(ind.created_at||'').slice(0,10)} ${ind.is_active == 1 ? '<span style="color:#22c55e">●アクティブ</span>' : '<span style="color:#475569">●無効</span>'}</div>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          <button onclick="runCustomBt(${JSON.stringify(ind.name)})"
                  style="background:#0e7490;color:#fff;border:none;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer">
            🔄 BT再実行
          </button>
          ${ind.is_active == 1 ? `<button onclick="deleteCustomInd(${JSON.stringify(ind.name)})"
                  style="background:#7f1d1d;color:#fca5a5;border:none;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer">
            🗑️ 無効化
          </button>` : ''}
        </div>
      </div>
    `).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:#ef4444;padding:12px">読み込みエラー: ' + e.message + '</div>';
  }
}

async function saveCustomIndicator() {
  const name        = document.getElementById('ci-name').value.trim();
  const displayName = document.getElementById('ci-display-name').value.trim();
  const description = document.getElementById('ci-description').value.trim();
  const goodTxt     = document.getElementById('ci-good').value.trim();
  const badTxt      = document.getElementById('ci-bad').value.trim();
  const btn         = document.getElementById('ci-save-btn');
  const stat        = document.getElementById('ci-save-status');

  if (!name || !displayName) {
    stat.textContent = '⚠ 内部キー名と表示名は必須です';
    stat.style.color = '#f59e0b';
    return;
  }
  if (!/^[A-Za-z0-9_]{1,80}$/.test(name)) {
    stat.textContent = '⚠ 内部キー名は半角英数字・アンダースコアのみ';
    stat.style.color = '#f59e0b';
    return;
  }

  const toArr = txt => txt.split('\n').map(s => s.trim()).filter(s => s.length > 0);

  // strategy_config を saved_strategies から name で取得
  let strategyCfg = null;
  try {
    const sr = await fetch('/admin/api.php?action=load_strategy', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name }),
    }).then(r => r.json());
    if (sr.ok && sr.strategy && sr.strategy.strategy_config) {
      strategyCfg = sr.strategy.strategy_config;
    }
  } catch(e) {}

  if (!strategyCfg) {
    stat.textContent = '⚠ バックテストv2で「' + name + '」という名前の保存済み戦略が見つかりません';
    stat.style.color = '#f59e0b';
    return;
  }

  btn.disabled = true;
  stat.textContent = '登録中...';
  stat.style.color = '#94a3b8';

  try {
    const res = await fetch('/admin/api.php?action=save_custom_indicator', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name,
        display_name:    displayName,
        description,
        good_markets:    toArr(goodTxt),
        bad_markets:     toArr(badTxt),
        strategy_config: strategyCfg,
      }),
    }).then(r => r.json());

    if (res.status === 'ok') {
      stat.textContent = '✓ ' + res.message;
      stat.style.color = '#22c55e';
      document.getElementById('ci-name').value = '';
      document.getElementById('ci-display-name').value = '';
      document.getElementById('ci-description').value = '';
      document.getElementById('ci-good').value = '';
      document.getElementById('ci-bad').value = '';
      setTimeout(loadCustomIndicators, 1000);
    } else {
      stat.textContent = 'エラー: ' + (res.message || '');
      stat.style.color = '#ef4444';
    }
  } catch(e) {
    stat.textContent = 'ネットワークエラー: ' + e.message;
    stat.style.color = '#ef4444';
  }
  btn.disabled = false;
}

async function runCustomBt(name) {
  if (!confirm(name + ' のバックテストを再実行しますか？')) return;
  try {
    const res = await fetch('/admin/api.php?action=run_custom_indicator_bt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name }),
    }).then(r => r.json());
    alert(res.status === 'ok' ? '✓ ' + res.message : 'エラー: ' + (res.message || ''));
  } catch(e) { alert('ネットワークエラー'); }
}

async function deleteCustomInd(name) {
  if (!confirm(name + ' を無効化しますか？（バックテストデータは残ります）')) return;
  try {
    const res = await fetch('/admin/api.php?action=delete_custom_indicator', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name }),
    }).then(r => r.json());
    if (res.status === 'ok') loadCustomIndicators();
    else alert('エラー: ' + (res.message || ''));
  } catch(e) { alert('ネットワークエラー'); }
}

loadCustomIndicators();
</script>
<?php endif; // end logged-in ?>
</body>
</html>
