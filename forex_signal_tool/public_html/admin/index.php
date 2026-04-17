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
        <h3 style="color:#a5b4fc">QuantFlow 月次BT</h3>
        <p>USDJPYの5分足スキャルピングシミュレーションを再実行してDBに保存します（数分かかります）。</p>
        <button class="run-btn qf" onclick="runOp('quantflow')">QuantFlow BT を実行</button>
        <div class="result-msg" id="msg-quantflow"></div>
      </div>
      <div class="op-card" style="border-color:#1e40af">
        <h3 style="color:#93c5fd">コード更新 (git pull)</h3>
        <p>サーバー上のコードを最新に更新します。プッシュ後にここから反映できます。</p>
        <button class="run-btn" style="background:#1d4ed8" id="btn-gitpull" onclick="runGitPull()">git pull を実行</button>
        <div id="git-output" style="display:none;margin-top:10px;padding:10px;background:#0f172a;border:1px solid #334155;border-radius:6px;font-family:monospace;font-size:11px;color:#94a3b8;white-space:pre-wrap;word-break:break-all;max-height:160px;overflow-y:auto"></div>
      </div>
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
    fetch:    { action: 'run_fetch',         btnSel: '.run-btn.fetch', msgId: 'msg-fetch',      rtId: 'rt-fetch',  opKey: 'fetch_status',       rtKey: 'last_fetch' },
    backtest: { action: 'run_backtest',      btnSel: '.run-btn.bt',    msgId: 'msg-backtest',   rtId: 'rt-bt',     opKey: 'backtest_status',    rtKey: 'last_bt' },
    signals:  { action: 'run_signals',       btnSel: '.run-btn.sig',   msgId: 'msg-signals',    rtId: 'rt-signal', opKey: 'signal_status',      rtKey: 'last_signal' },
    quantflow:{ action: 'run_quantflow_bt',  btnSel: '.run-btn.qf',    msgId: 'msg-quantflow',  rtId: null,        opKey: 'quantflow_bt_status', rtKey: null },
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
