<?php
/**
 * 管理パネル - 設定 & システム診断
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();

// UTC datetime string → JST (substring, +9h)
function utc_to_jst_str(string $utc, int $len = 16): string {
    if ($utc === '') return '';
    $ts = strtotime($utc . ' UTC');
    if ($ts === false) return substr($utc, 0, $len);
    return date('Y-m-d H:i', $ts + 9 * 3600);
}

// ---- 現在の設定値をDBから読み込む ----
$saved = '';
$saveError = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['save_settings'])) {
    try {
        $fields = [
            'initial_capital', 'sl_pips', 'tp_pips', 'backtest_hours',
            'min_win_rate', 'min_trades', 'quantflow_signal_recipients',
        ];
        foreach ($fields as $key) {
            if (isset($_POST[$key])) {
                setting_set($key, trim($_POST[$key]));
            }
        }
        $saved = '設定を保存しました';
    } catch (Exception $e) {
        $saveError = '保存エラー: ' . $e->getMessage();
    }
}

// 設定値
$cfg = [
    'initial_capital'              => setting_get('initial_capital',              '1000000'),
    'sl_pips'                      => setting_get('sl_pips',                      '20'),
    'tp_pips'                      => setting_get('tp_pips',                      '40'),
    'backtest_hours'               => setting_get('backtest_hours',               '12'),
    'min_win_rate'                 => setting_get('min_win_rate',                 '55'),
    'min_trades'                   => setting_get('min_trades',                   '3'),
    'quantflow_signal_recipients'  => setting_get('quantflow_signal_recipients',  ''),
];

// ---- .env から SMTP 設定を読み取る ----
// PROJECT_ROOT = ~/forex_project/forex_signal_tool → .env は1つ上の階層
$envFile = dirname(PROJECT_ROOT) . '/.env';
$smtpKeys = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER'];
$envMail  = array_fill_keys($smtpKeys, '');
$envLines = [];
if (file_exists($envFile)) {
    $envLines = file($envFile, FILE_IGNORE_NEW_LINES);
    foreach ($envLines as $line) {
        foreach ($smtpKeys as $key) {
            if (strpos($line, $key . '=') === 0) {
                $envMail[$key] = trim(substr($line, strlen($key) + 1));
            }
        }
    }
}

// ---- .env への SMTP 保存 ----
$savedSmtp  = '';
$smtpError  = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['save_smtp'])) {
    if (!file_exists($envFile) || !is_writable($envFile)) {
        $smtpError = '.env ファイルが見つからないか書き込み権限がありません';
    } else {
        $newEnv    = [];
        $replaced  = array_fill_keys($smtpKeys, false);
        foreach ($envLines as $line) {
            $matched = false;
            foreach ($smtpKeys as $key) {
                if (strpos($line, $key . '=') === 0) {
                    $val = $_POST[$key] ?? '';
                    // パスワードは空欄なら変更しない
                    if ($key === 'MAIL_PASSWORD' && $val === '') {
                        $newEnv[] = $line;
                    } else {
                        $newEnv[] = $key . '=' . $val;
                        $envMail[$key] = $val;
                    }
                    $replaced[$key] = true;
                    $matched = true;
                    break;
                }
            }
            if (!$matched) $newEnv[] = $line;
        }
        // .env に存在しなかったキーを末尾に追加
        foreach ($smtpKeys as $key) {
            if (!$replaced[$key] && isset($_POST[$key]) && $_POST[$key] !== '') {
                $newEnv[] = $key . '=' . $_POST[$key];
                $envMail[$key] = $_POST[$key];
            }
        }
        file_put_contents($envFile, implode("\n", $newEnv) . "\n");
        $savedSmtp = 'SMTP 設定を保存しました（次回タスク実行から反映されます）';
    }
}

// ---- システム診断 ----
$diag = [];

// DB接続テスト
try {
    $pdo = get_pdo();
    $diag['db'] = ['ok' => true, 'msg' => 'DB接続 OK'];

    // テーブル行数
    $diag['price_rows']  = (int)$pdo->query('SELECT COUNT(*) FROM price_data')->fetchColumn();
    $diag['signal_rows'] = (int)$pdo->query('SELECT COUNT(*) FROM trading_signals')->fetchColumn();
    $diag['bt_rows']     = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
    $diag['setting_rows']= (int)$pdo->query('SELECT COUNT(*) FROM settings')->fetchColumn();

    // ペア×TF ごとのデータ状況
    $stmt = $pdo->query(
        'SELECT currency_pair, timeframe, COUNT(*) AS cnt,
                MIN(timestamp) AS oldest, MAX(timestamp) AS newest
         FROM price_data
         GROUP BY currency_pair, timeframe
         ORDER BY currency_pair, timeframe'
    );
    $diag['coverage'] = $stmt->fetchAll();

    // 全 Settings キーを表示（デバッグ用）
    $stmt2 = $pdo->query('SELECT `key`, `value`, `updated_at` FROM settings ORDER BY `key`');
    $diag['all_settings'] = $stmt2->fetchAll();

} catch (Exception $e) {
    $diag['db'] = ['ok' => false, 'msg' => 'DB接続失敗: ' . $e->getMessage()];
}

// Pythonバイナリ確認
$pythonCheck = shell_exec(escapeshellarg(PYTHON_BIN) . ' --version 2>&1');
$diag['python'] = trim($pythonCheck ?: '取得失敗');

// タスクスクリプト存在確認
$scripts = ['fetch_data.py', 'run_analysis.py', 'run_signals_only.py', 'run_custom_bt.py'];
$diag['scripts'] = [];
foreach ($scripts as $s) {
    $path = TASKS_DIR . '/' . $s;
    $diag['scripts'][$s] = file_exists($path);
}

// バックグラウンドログ (直近20行)
$bgLog = '/tmp/forex_admin_bg.log';
$diag['bg_log'] = '';
if (file_exists($bgLog)) {
    $lines = file($bgLog, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    $diag['bg_log'] = implode("\n", array_slice($lines, -20));
}

// 最終実行時刻
$diag['last_fetch']  = setting_get('last_data_fetch_at',    '未実行');
$diag['last_bt']     = setting_get('last_backtest_at',      '未実行');
$diag['last_signal'] = setting_get('last_signal_update_at', '未実行');
$diag['fetch_status']  = setting_get('fetch_status',    'idle');
$diag['bt_status']     = setting_get('backtest_status', 'idle');
$diag['signal_status'] = setting_get('signal_status',   'idle');
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>設定 & 診断 | AI×FX 管理</title>
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
/* セクション */
.section{margin-bottom:32px}
.section-title{font-size:13px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.7px;margin-bottom:14px}
/* カード */
.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:16px}
/* フォーム */
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
.field-group label{display:block;font-size:12px;color:#64748b;margin-bottom:6px}
.field-group input{width:100%;background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:9px 10px;font-size:13px;outline:none}
.field-group input:focus{border-color:#3b82f6}
.field-group .hint{font-size:11px;color:#475569;margin-top:4px}
.btn-save{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 24px;font-size:13px;font-weight:600;cursor:pointer}
.btn-save:hover{background:#2563eb}
.flash-ok{background:#14532d;border:1px solid #4ade80;color:#4ade80;border-radius:8px;padding:10px 16px;font-size:13px;margin-bottom:16px}
.flash-err{background:#7f1d1d;border:1px solid #ef4444;color:#f87171;border-radius:8px;padding:10px 16px;font-size:13px;margin-bottom:16px}
/* 診断 */
.diag-row{display:flex;align-items:center;justify-content:space-between;padding:11px 0;border-bottom:1px solid #0f172a}
.diag-row:last-child{border-bottom:none}
.diag-label{font-size:13px;color:#94a3b8}
.diag-val{font-size:13px;color:#e2e8f0;font-family:'Courier New',monospace;text-align:right}
.badge-ok{background:#14532d;color:#4ade80;border-radius:4px;padding:2px 8px;font-size:11px;font-family:sans-serif}
.badge-ng{background:#7f1d1d;color:#f87171;border-radius:4px;padding:2px 8px;font-size:11px;font-family:sans-serif}
.badge-idle{background:#1e293b;color:#64748b;border:1px solid #334155;border-radius:4px;padding:2px 8px;font-size:11px;font-family:sans-serif}
.badge-run{background:#1e3a5f;color:#60a5fa;border-radius:4px;padding:2px 8px;font-size:11px;font-family:sans-serif}
/* カバレッジテーブル */
.cov-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:0}
.cov-table th{background:#0f172a;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}
.cov-table td{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1}
.cov-table tr:last-child td{border-bottom:none}
.cov-num{text-align:right;font-family:'Courier New',monospace}
.cov-date{font-family:'Courier New',monospace;font-size:11px}
.cov-oldest{color:#f59e0b}
/* ペアタブ */
.pair-tabs{display:flex;gap:4px;margin-bottom:0}
.pair-tab{padding:6px 18px;border-radius:6px 6px 0 0;font-size:12px;font-weight:600;cursor:pointer;border:1px solid #334155;border-bottom:none;background:#0f172a;color:#64748b;transition:background .15s,color .15s;user-select:none}
.pair-tab.active{background:#1e293b;color:#60a5fa}
.pair-tab-panel{display:none;background:#1e293b;border:1px solid #334155;border-radius:0 6px 6px 6px;padding:0;overflow:hidden}
.pair-tab-panel.active{display:block}
/* マクロ指標 */
.macro-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:#451a03;color:#fb923c}
.macro-ok{color:#4ade80;font-weight:600}
.macro-none{color:#ef4444;font-weight:600}
/* ログ表示 */
.log-box{background:#020617;border:1px solid #1e293b;border-radius:8px;padding:14px;font-family:'Courier New',monospace;font-size:11px;color:#94a3b8;white-space:pre-wrap;word-break:break-all;max-height:240px;overflow-y:auto;margin-top:8px}
/* 全設定テーブル */
.all-settings-table{width:100%;border-collapse:collapse;font-size:12px}
.all-settings-table th{background:#0f172a;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}
.all-settings-table td{padding:7px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1;font-family:'Courier New',monospace}
.all-settings-table tr:last-child td{border-bottom:none}
</style>
</head>
<body>
<header>
  <h1>AI×FX 管理パネル</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/articles.php">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php" class="active">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>

<main>
  <h2>設定 & システム診断</h2>
  <p class="subtitle">バックテストのデフォルト値変更・システム稼働状況の確認ができます</p>

  <!-- ===== 設定フォーム ===== -->
  <div class="section">
    <div class="section-title">バックテスト設定</div>
    <?php if ($saved): ?><div class="flash-ok"><?= htmlspecialchars($saved) ?></div><?php endif; ?>
    <?php if ($saveError): ?><div class="flash-err"><?= htmlspecialchars($saveError) ?></div><?php endif; ?>
    <div class="card">
      <form method="post">
        <div class="field-grid">
          <div class="field-group">
            <label>初期資金 (円)</label>
            <input type="number" name="initial_capital" value="<?= htmlspecialchars($cfg['initial_capital']) ?>" min="1000" step="1000">
            <div class="hint">デフォルト: 1,000,000円</div>
          </div>
          <div class="field-group">
            <label>バックテスト期間 (時間)</label>
            <input type="number" name="backtest_hours" value="<?= htmlspecialchars($cfg['backtest_hours']) ?>" min="1" max="8760">
            <div class="hint">デフォルト: 12時間</div>
          </div>
          <div class="field-group">
            <label>デフォルト SL (pips)</label>
            <input type="number" name="sl_pips" value="<?= htmlspecialchars($cfg['sl_pips']) ?>" min="1" max="500" step="0.1">
            <div class="hint">デフォルト: 20 pips</div>
          </div>
          <div class="field-group">
            <label>デフォルト TP (pips)</label>
            <input type="number" name="tp_pips" value="<?= htmlspecialchars($cfg['tp_pips']) ?>" min="1" max="500" step="0.1">
            <div class="hint">デフォルト: 40 pips (RR=2.0)</div>
          </div>
          <div class="field-group">
            <label>最低勝率フィルター (%)</label>
            <input type="number" name="min_win_rate" value="<?= htmlspecialchars($cfg['min_win_rate']) ?>" min="0" max="100" step="0.1">
            <div class="hint">この勝率以上の指標のみ表示</div>
          </div>
          <div class="field-group">
            <label>最低取引数フィルター (回)</label>
            <input type="number" name="min_trades" value="<?= htmlspecialchars($cfg['min_trades']) ?>" min="1" max="1000">
            <div class="hint">この取引数以上のみ有効とみなす</div>
          </div>
        </div>
        <button type="submit" name="save_settings" class="btn-save">設定を保存</button>
      </form>
    </div>
  </div>

  <!-- ===== QuantFlow メール通知設定 ===== -->
  <div class="section">
    <div class="section-title">QuantFlow メール通知</div>

    <!-- SMTP 設定フォーム -->
    <div class="card" style="margin-bottom:16px">
      <div style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:16px">SMTP 設定（.env ファイルに保存）</div>
      <?php if ($savedSmtp): ?><div class="flash-ok" style="margin-bottom:14px"><?= htmlspecialchars($savedSmtp) ?></div><?php endif; ?>
      <?php if ($smtpError):  ?><div class="flash-err" style="margin-bottom:14px"><?= htmlspecialchars($smtpError) ?></div><?php endif; ?>
      <form method="post">
        <div class="field-grid" style="margin-bottom:14px">
          <div class="field-group">
            <label>MAIL_SERVER（SMTPサーバー）</label>
            <input type="text" name="MAIL_SERVER"
                   value="<?= htmlspecialchars($envMail['MAIL_SERVER']) ?>"
                   placeholder="sv***.xserver.jp">
            <div class="hint">Xserver: サーバーパネル → メールアカウント設定 に記載のサーバー名</div>
          </div>
          <div class="field-group">
            <label>MAIL_PORT</label>
            <input type="number" name="MAIL_PORT"
                   value="<?= htmlspecialchars($envMail['MAIL_PORT'] ?: '587') ?>"
                   min="1" max="65535">
            <div class="hint">Xserver: 587（STARTTLS）</div>
          </div>
          <div class="field-group">
            <label>MAIL_USERNAME（メールアドレス）</label>
            <input type="email" name="MAIL_USERNAME"
                   value="<?= htmlspecialchars($envMail['MAIL_USERNAME']) ?>"
                   placeholder="info@example.com">
            <div class="hint">Xserver で作成したメールアドレス</div>
          </div>
          <div class="field-group">
            <label>MAIL_DEFAULT_SENDER（送信者アドレス）</label>
            <input type="email" name="MAIL_DEFAULT_SENDER"
                   value="<?= htmlspecialchars($envMail['MAIL_DEFAULT_SENDER']) ?>"
                   placeholder="info@example.com">
            <div class="hint">通常は MAIL_USERNAME と同じ</div>
          </div>
          <div class="field-group">
            <label>MAIL_PASSWORD</label>
            <input type="password" name="MAIL_PASSWORD"
                   placeholder="<?= ($envMail['MAIL_PASSWORD'] && strpos($envMail['MAIL_PASSWORD'], 'your_') !== 0) ? '●●●● 設定済み（変更する場合のみ入力）' : 'メールアカウントのパスワード' ?>">
            <div class="hint">Xserver のメールアカウント作成時に設定したパスワード</div>
          </div>
          <div class="field-group">
            <label>MAIL_USE_TLS</label>
            <select name="MAIL_USE_TLS"
                    style="width:100%;background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:9px 10px;font-size:13px;outline:none">
              <option value="true"  <?= ($envMail['MAIL_USE_TLS'] !== 'false') ? 'selected' : '' ?>>true（Xserver ポート587）</option>
              <option value="false" <?= ($envMail['MAIL_USE_TLS'] === 'false') ? 'selected' : '' ?>>false</option>
            </select>
          </div>
        </div>
        <button type="submit" name="save_smtp" class="btn-save">SMTP設定を保存</button>
      </form>
    </div>

    <!-- 通知先リスト -->
    <div class="card">
      <div style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:12px">通知先メールアドレス</div>
      <div id="recipient-list" style="margin-bottom:14px"></div>

      <div style="display:flex;gap:8px;margin-bottom:20px">
        <input id="new-email" type="email" placeholder="メールアドレスを入力"
               style="flex:1;background:#0f172a;border:1px solid #475569;border-radius:7px;color:#e2e8f0;padding:8px 10px;font-size:13px;outline:none">
        <button type="button" onclick="addEmail()"
                style="background:#0f766e;color:#fff;border:none;border-radius:7px;padding:8px 16px;font-size:13px;cursor:pointer">追加</button>
      </div>

      <form method="post" onsubmit="syncHidden()">
        <input type="hidden" id="recipients-hidden" name="quantflow_signal_recipients">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <button type="submit" name="save_settings" class="btn-save">保存</button>
          <button type="button" id="test-btn" onclick="sendTestEmail()"
                  style="background:#1e3a5f;color:#60a5fa;border:1px solid #334155;border-radius:8px;padding:10px 20px;font-size:13px;font-weight:600;cursor:pointer">
            テスト送信
          </button>
          <span id="test-msg" style="font-size:12px"></span>
        </div>
      </form>
      <div style="font-size:11px;color:#64748b;margin-top:10px">
        エントリー確定・TP/SL 決済・シグナル変更での決済時にメールを送信します。
      </div>
    </div>
  </div>

  <script>
  var _recipients = <?= json_encode(array_values(array_filter(array_map('trim', explode(',', $cfg['quantflow_signal_recipients']))))) ?>;

  function renderList() {
    var el = document.getElementById('recipient-list');
    if (_recipients.length === 0) {
      el.innerHTML = '<div style="color:#475569;font-size:12px;padding:6px 0">登録なし</div>';
      return;
    }
    el.innerHTML = _recipients.map(function(email, i) {
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#0f172a;border-radius:6px;margin-bottom:6px">' +
        '<span style="font-size:13px;color:#e2e8f0">' + email + '</span>' +
        '<button type="button" onclick="removeEmail(' + i + ')" style="background:#7f1d1d;color:#f87171;border:none;border-radius:5px;padding:3px 10px;font-size:11px;cursor:pointer">削除</button>' +
      '</div>';
    }).join('');
  }

  function addEmail() {
    var input = document.getElementById('new-email');
    var email = input.value.trim();
    if (!email || !email.includes('@')) { alert('正しいメールアドレスを入力してください'); return; }
    if (_recipients.indexOf(email) !== -1) { alert('既に追加済みです'); return; }
    _recipients.push(email);
    input.value = '';
    renderList();
  }

  function removeEmail(i) {
    _recipients.splice(i, 1);
    renderList();
  }

  function syncHidden() {
    document.getElementById('recipients-hidden').value = _recipients.join(',');
  }

  document.getElementById('new-email').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); addEmail(); }
  });

  async function sendTestEmail() {
    var btn = document.getElementById('test-btn');
    var msg = document.getElementById('test-msg');
    btn.disabled = true;
    msg.textContent = '送信中...';
    msg.style.color = '#94a3b8';
    try {
      var res = await fetch('/admin/api.php', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'test_quantflow_email'}),
      }).then(function(r){ return r.json(); });
      msg.textContent = res.status === 'ok' ? '✅ ' + res.message : '❌ ' + res.message;
      msg.style.color  = res.status === 'ok' ? '#4ade80' : '#f87171';
    } catch(e) {
      msg.textContent = '❌ 通信エラー';
      msg.style.color  = '#f87171';
    }
    btn.disabled = false;
  }

  renderList();
  </script>

  <!-- ===== システム診断 ===== -->
  <div class="section">
    <div class="section-title">システム診断</div>
    <div class="card">
      <!-- DB・Python -->
      <div class="diag-row">
        <span class="diag-label">DB接続</span>
        <span class="diag-val">
          <?php if ($diag['db']['ok']): ?>
            <span class="badge-ok">OK</span>
          <?php else: ?>
            <span class="badge-ng">NG</span> <?= htmlspecialchars($diag['db']['msg']) ?>
          <?php endif; ?>
        </span>
      </div>
      <div class="diag-row">
        <span class="diag-label">Python バイナリ (<?= htmlspecialchars(PYTHON_BIN) ?>)</span>
        <span class="diag-val"><?= htmlspecialchars($diag['python']) ?></span>
      </div>

      <?php if ($diag['db']['ok']): ?>
      <!-- テーブル行数 -->
      <div class="diag-row">
        <span class="diag-label">price_data 行数</span>
        <span class="diag-val"><?= number_format($diag['price_rows']) ?> 行</span>
      </div>
      <div class="diag-row">
        <span class="diag-label">trading_signals 行数</span>
        <span class="diag-val"><?= number_format($diag['signal_rows']) ?> 行</span>
      </div>
      <div class="diag-row">
        <span class="diag-label">backtest_results 行数</span>
        <span class="diag-val"><?= number_format($diag['bt_rows']) ?> 行</span>
      </div>
      <div class="diag-row">
        <span class="diag-label">settings 行数</span>
        <span class="diag-val"><?= number_format($diag['setting_rows']) ?> 行</span>
      </div>
      <?php endif; ?>

      <!-- スクリプト存在確認 -->
      <?php foreach ($diag['scripts'] as $name => $exists): ?>
      <div class="diag-row">
        <span class="diag-label">tasks/<?= htmlspecialchars($name) ?></span>
        <span class="diag-val">
          <?= $exists ? '<span class="badge-ok">存在</span>' : '<span class="badge-ng">見つからない</span>' ?>
        </span>
      </div>
      <?php endforeach; ?>
    </div>

    <!-- 最終実行状況 -->
    <div class="card">
      <div class="diag-row">
        <span class="diag-label">データ取得 最終実行</span>
        <span class="diag-val"><?= htmlspecialchars($diag['last_fetch']) ?>
          <?php
          $st = $diag['fetch_status'];
          if ($st === 'running') echo '<span class="badge-run">実行中</span>';
          elseif ($st === 'done')  echo '<span class="badge-ok">完了</span>';
          else                     echo '<span class="badge-idle">idle</span>';
          ?>
        </span>
      </div>
      <div class="diag-row">
        <span class="diag-label">バックテスト 最終実行</span>
        <span class="diag-val"><?= htmlspecialchars($diag['last_bt']) ?>
          <?php
          $st = $diag['bt_status'];
          if ($st === 'running') echo '<span class="badge-run">実行中</span>';
          elseif ($st === 'done')  echo '<span class="badge-ok">完了</span>';
          else                     echo '<span class="badge-idle">idle</span>';
          ?>
        </span>
      </div>
      <div class="diag-row">
        <span class="diag-label">シグナル更新 最終実行</span>
        <span class="diag-val"><?= htmlspecialchars($diag['last_signal']) ?>
          <?php
          $st = $diag['signal_status'];
          if ($st === 'running') echo '<span class="badge-run">実行中</span>';
          elseif ($st === 'done')  echo '<span class="badge-ok">完了</span>';
          else                     echo '<span class="badge-idle">idle</span>';
          ?>
        </span>
      </div>
    </div>
  </div>

  <!-- ===== データカバレッジ（リアルタイム）===== -->
  <div class="section">
    <div class="section-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>データカバレッジ（ペア×タイムフレーム）</span>
      <div style="display:flex;align-items:center;gap:10px">
        <span id="cov-updated" style="font-size:11px;color:#475569"></span>
        <button onclick="loadCoverage()" style="background:#1e293b;border:1px solid #334155;color:#94a3b8;font-size:12px;padding:4px 10px;border-radius:6px;cursor:pointer">再読込</button>
      </div>
    </div>
    <div id="cov-loading" style="text-align:center;color:#64748b;font-size:13px;padding:30px 0">
      <span class="spin" style="border-color:#33415599;border-top-color:#60a5fa"></span> 読み込み中...
    </div>
    <div id="cov-error" style="display:none;text-align:center;color:#f87171;font-size:13px;padding:20px 0"></div>
    <div id="cov-content" style="display:none"></div>
  </div>

  <!-- ===== 全設定値一覧 ===== -->
  <?php if (!empty($diag['all_settings'])): ?>
  <div class="section">
    <div class="section-title">DB 設定値一覧（settings テーブル）</div>
    <div class="card">
      <table class="all-settings-table">
        <thead><tr><th>キー</th><th>値</th><th>更新日時</th></tr></thead>
        <tbody>
          <?php foreach ($diag['all_settings'] as $row): ?>
          <tr>
            <td><?= htmlspecialchars($row['key']) ?></td>
            <td><?= htmlspecialchars(mb_strimwidth($row['value'], 0, 80, '…')) ?></td>
            <td><?= htmlspecialchars(substr($row['updated_at'] ?? '', 0, 16)) ?></td>
          </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  </div>
  <?php endif; ?>

  <!-- ===== バックグラウンドログ ===== -->
  <div class="section">
    <div class="section-title">バックグラウンドジョブ ログ（直近20行）</div>
    <div class="card">
      <?php if ($diag['bg_log']): ?>
        <div class="log-box"><?= htmlspecialchars($diag['bg_log']) ?></div>
      <?php else: ?>
        <div style="font-size:13px;color:#64748b">ログなし（/tmp/forex_admin_bg.log）</div>
      <?php endif; ?>
      <div style="margin-top:10px">
        <button onclick="location.reload()" style="background:none;border:1px solid #475569;color:#94a3b8;border-radius:6px;padding:6px 14px;font-size:12px;cursor:pointer">ページを再読み込み</button>
      </div>
    </div>
  </div>
</main>
<script>
var _covActivePair = 'USDJPY';
var _covAutoTimer  = null;

function covSwitchTab(pair) {
  _covActivePair = pair;
  document.querySelectorAll('.pair-tab').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('.pair-tab-panel').forEach(function(p){ p.classList.remove('active'); });
  var btn = document.querySelector('.pair-tab[data-pair="' + pair + '"]');
  var pnl = document.getElementById('cov-tab-' + pair);
  if (btn) btn.classList.add('active');
  if (pnl) pnl.classList.add('active');
}

function loadCoverage() {
  var loading = document.getElementById('cov-loading');
  var errDiv  = document.getElementById('cov-error');
  var content = document.getElementById('cov-content');
  loading.style.display = 'block';
  errDiv.style.display  = 'none';
  content.style.display = 'none';

  fetch('/admin/api.php?action=data_coverage', {headers:{'X-Requested-With':'XMLHttpRequest'}})
  .then(function(r){ return r.json(); })
  .then(function(d) {
    loading.style.display = 'none';
    if (!d.ok) { errDiv.textContent = 'エラー: '+(d.error||'不明'); errDiv.style.display='block'; return; }

    var forexPairs  = ['USDJPY','GBPJPY','EURJPY'];
    var macroPairs  = ['US10Y','USBF','DXY'];
    var macroLabels = {US10Y:'米10年債利回り（現物）',USBF:'米10年国債先物 ZN=F',DXY:'ドルインデックス'};
    var pairLabel   = {USDJPY:'ドル円',GBPJPY:'ポンド円',EURJPY:'ユーロ円'};

    var grouped = {};
    d.rows.forEach(function(r) {
      if (!grouped[r.currency_pair]) grouped[r.currency_pair] = [];
      grouped[r.currency_pair].push(r);
    });

    var html = '<div class="pair-tabs">';
    forexPairs.forEach(function(p, i) {
      html += '<div class="pair-tab' + (p===_covActivePair?' active':'') + '" data-pair="' + p + '" onclick="covSwitchTab(\'' + p + '\')">' + p + '</div>';
    });
    html += '</div>';

    forexPairs.forEach(function(p) {
      var rows = grouped[p] || [];
      html += '<div class="pair-tab-panel' + (p===_covActivePair?' active':'') + '" id="cov-tab-' + p + '">';
      html += '<div style="padding:10px 12px 6px;font-size:11px;color:#94a3b8">' + (pairLabel[p]||p) + '（' + rows.length + '足種）</div>';
      html += '<table class="cov-table"><thead><tr><th>足種</th><th>件数</th><th>最古データ (JST)</th><th>最新データ (JST)</th></tr></thead><tbody>';
      if (rows.length === 0) {
        html += '<tr><td colspan="4" style="text-align:center;color:#475569;padding:12px">データなし</td></tr>';
      } else {
        rows.forEach(function(r) {
          html += '<tr>'
            + '<td style="color:#94a3b8;font-family:\'Courier New\',monospace">' + r.timeframe + '</td>'
            + '<td class="cov-num">' + r.cnt.toLocaleString() + '</td>'
            + '<td class="cov-date cov-oldest">' + (r.oldest_jst||'-') + '</td>'
            + '<td class="cov-date">' + (r.newest_jst||'-') + '</td>'
            + '</tr>';
        });
      }
      html += '</tbody></table></div>';
    });

    html += '<div style="margin-top:20px">';
    html += '<div style="font-size:12px;color:#64748b;margin-bottom:8px">マクロ指標データ（US10Y / USBF / DXY）</div>';
    html += '<table class="cov-table"><thead><tr><th>指標</th><th>説明</th><th>足種</th><th>件数</th><th>最古データ (JST)</th><th>最新データ (JST)</th><th>状態</th></tr></thead><tbody>';
    macroPairs.forEach(function(mp) {
      var mrows = grouped[mp] || [];
      var mr    = mrows[0] || null;
      html += '<tr>'
        + '<td><span class="macro-badge">' + mp + '</span></td>'
        + '<td style="color:#94a3b8;font-size:11px">' + (macroLabels[mp]||mp) + '</td>'
        + '<td style="color:#94a3b8;font-family:\'Courier New\',monospace">' + (mr ? mr.timeframe : '-') + '</td>'
        + '<td class="cov-num">' + (mr ? mr.cnt.toLocaleString() : '0') + '</td>'
        + '<td class="cov-date cov-oldest">' + (mr && mr.oldest_jst ? mr.oldest_jst : '-') + '</td>'
        + '<td class="cov-date">' + (mr && mr.newest_jst ? mr.newest_jst : '-') + '</td>'
        + '<td>' + (mr && mr.cnt > 0 ? '<span class="macro-ok">✓ あり</span>' : '<span class="macro-none">✗ なし</span>') + '</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    html += '<div style="font-size:11px;color:#475569;margin-top:6px">※ QuantFlow の外部要因スコア（±30点）に使用。データなしの場合はスコアが常にマイナスバイアスになります。</div>';
    html += '</div>';

    content.innerHTML = html;
    content.style.display = 'block';

    var now = new Date();
    document.getElementById('cov-updated').textContent = '更新: ' + now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0') + ':' + now.getSeconds().toString().padStart(2,'0');
  })
  .catch(function(e) {
    document.getElementById('cov-loading').style.display = 'none';
    document.getElementById('cov-error').textContent = '通信エラー: ' + e.message;
    document.getElementById('cov-error').style.display = 'block';
  });
}

loadCoverage();
// 60秒ごとに自動更新
_covAutoTimer = setInterval(loadCoverage, 60000);
</script>
</body>
</html>
