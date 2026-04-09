<?php
/**
 * 管理パネル JSON API
 * すべてのレスポンスは Content-Type: application/json
 */
require_once __DIR__ . '/_config.php';

$action = $_GET['action'] ?? (json_decode(file_get_contents('php://input'), true)['action'] ?? '');

// POST ボディ (JSON)
$body = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $raw = file_get_contents('php://input');
    if ($raw) {
        $body = json_decode($raw, true) ?: [];
    }
    // フォーム POST もサポート
    if (empty($body)) {
        $body = $_POST;
    }
}

// ログ出力先 (バックグラウンドジョブ用)
define('LOG_FILE',    '/tmp/forex_admin_bg.log');
define('BT_PARAMS',   '/tmp/forex_bt_params.json');
define('BT_RESULT',   '/tmp/forex_bt_result.json');

switch ($action) {

    // ---- 認証 ----
    case 'login':
        session_start();
        $pw = $body['password'] ?? $_POST['password'] ?? '';
        if ($pw === ADMIN_PASSWORD) {
            $_SESSION['admin_logged_in'] = true;
            json_out(['status' => 'ok']);
        }
        json_out(['status' => 'error', 'message' => 'パスワードが違います']);
        break;

    case 'logout':
        session_start();
        $_SESSION = [];
        session_destroy();
        json_out(['status' => 'ok']);
        break;

    // ---- ダッシュボード統計 ----
    case 'stats':
        require_login();
        try {
            $pdo = get_pdo();
            $priceRows  = (int)$pdo->query('SELECT COUNT(*) FROM price_data')->fetchColumn();
            $signalCount = (int)$pdo->query("SELECT COUNT(*) FROM trading_signals WHERE is_active=1")->fetchColumn();
            $btCount    = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
            json_out([
                'status' => 'ok',
                'stats'  => ['price_rows' => $priceRows, 'signal_count' => $signalCount, 'bt_count' => $btCount],
                'last_fetch'  => setting_get('last_data_fetch_at',    '未実行'),
                'last_bt'     => setting_get('last_backtest_at',      '未実行'),
                'last_signal' => setting_get('last_signal_update_at', '未実行'),
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- データ操作 ----
    case 'run_fetch':
        require_login();
        setting_set('fetch_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/fetch_data.py');
        exec("nohup {$cmd} >> " . escapeshellarg(LOG_FILE) . " 2>&1 &");
        json_out(['status' => 'started', 'message' => 'データ取得をバックグラウンドで開始しました']);
        break;

    case 'run_backtest':
        require_login();
        setting_set('backtest_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/run_analysis.py');
        exec("nohup {$cmd} >> " . escapeshellarg(LOG_FILE) . " 2>&1 &");
        json_out(['status' => 'started', 'message' => 'バックテストをバックグラウンドで開始しました（数分かかります）']);
        break;

    case 'run_signals':
        require_login();
        setting_set('signal_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/run_signals_only.py');
        exec("nohup {$cmd} >> " . escapeshellarg(LOG_FILE) . " 2>&1 &");
        json_out(['status' => 'started', 'message' => 'シグナル更新をバックグラウンドで開始しました']);
        break;

    case 'op_status':
        require_login();
        $op = $_GET['op'] ?? '';
        $statusKey = $op . '_status';
        $status    = setting_get($statusKey, 'idle');
        $lastFetch  = setting_get('last_data_fetch_at',    '未実行');
        $lastBt     = setting_get('last_backtest_at',      '未実行');
        $lastSignal = setting_get('last_signal_update_at', '未実行');
        json_out([
            'status'      => 'ok',
            'op_status'   => $status,
            'last_fetch'  => $lastFetch,
            'last_bt'     => $lastBt,
            'last_signal' => $lastSignal,
        ]);
        break;

    // ---- カスタムバックテスト ----
    case 'bt_date_range':
        require_login();
        // 各ペア×TFのデータ範囲を返す
        try {
            $pdo    = get_pdo();
            $pairs  = ['USDJPY', 'GBPJPY', 'EURJPY'];
            $tfs    = ['15min', '1hr', '4hr', 'daily'];
            $ranges = [];
            foreach ($pairs as $pair) {
                $ranges[$pair] = [];
                foreach ($tfs as $tf) {
                    $stmt = $pdo->prepare(
                        'SELECT MIN(DATE(timestamp)) AS mn, MAX(DATE(timestamp)) AS mx
                         FROM price_data WHERE currency_pair=? AND timeframe=?'
                    );
                    $stmt->execute([$pair, $tf]);
                    $row = $stmt->fetch();
                    $ranges[$pair][$tf] = [
                        'min' => $row['mn'] ?? '',
                        'max' => $row['mx'] ?? '',
                    ];
                }
            }
            json_out(['status' => 'ok', 'ranges' => $ranges]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'bt_run':
        require_login();

        // 既に実行中チェック
        if (file_exists(BT_RESULT)) {
            $prev = json_decode(file_get_contents(BT_RESULT), true);
            if (($prev['status'] ?? '') === 'running') {
                $startedAt = $prev['started_at'] ?? 0;
                if (time() - $startedAt < 600) {
                    json_out(['status' => 'busy', 'message' => '別のバックテストが実行中です（最大10分で自動解除）']);
                }
            }
        }

        // パラメータ検証
        $pair       = $body['pair']            ?? 'USDJPY';
        $timeframe  = $body['timeframe']       ?? '1hr';
        $startDate  = $body['start_date']      ?? '';
        $endDate    = $body['end_date']        ?? '';
        $capital    = (float)($body['initial_capital'] ?? 1000000);
        $slPips     = (float)($body['sl_pips']         ?? 20);
        $rrRatio    = (float)($body['rr_ratio']        ?? 1.5);
        $indicators = $body['indicators']      ?? [];

        $slMode     = $body['sl_mode'] ?? 'pips';
        if (!in_array($slMode, ['pips', 'bb'], true)) $slMode = 'pips';

        $validPairs = ['USDJPY', 'GBPJPY', 'EURJPY'];
        $validTfs   = ['5min', '15min', '30min', '1hr', '4hr', 'daily'];
        if (!in_array($pair, $validPairs, true)) {
            json_out(['status' => 'error', 'message' => '無効な通貨ペアです']);
        }
        if (!in_array($timeframe, $validTfs, true)) {
            json_out(['status' => 'error', 'message' => '無効なタイムフレームです']);
        }
        if (empty($indicators)) {
            json_out(['status' => 'error', 'message' => '指標を1つ以上選択してください']);
        }

        // パラメータをファイルに書き出す
        $params = [
            'pair'            => $pair,
            'timeframe'       => $timeframe,
            'start_date'      => $startDate,
            'end_date'        => $endDate,
            'initial_capital' => $capital,
            'sl_pips'         => $slPips,
            'rr_ratio'        => $rrRatio,
            'sl_mode'         => $slMode,
            'indicators'      => $indicators,
        ];
        file_put_contents(BT_PARAMS, json_encode($params, JSON_UNESCAPED_UNICODE));

        // 初期ステータスをリザルトファイルに書く
        file_put_contents(BT_RESULT, json_encode([
            'status'     => 'running',
            'message'    => 'バックテスト実行中...',
            'started_at' => time(),
        ], JSON_UNESCAPED_UNICODE));

        // バックグラウンドで Python 起動
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/run_custom_bt.py');
        exec("nohup {$cmd} >> /tmp/forex_bt_bg.log 2>&1 &");

        json_out(['status' => 'started', 'message' => 'バックテストを開始しました']);
        break;

    case 'bt_status':
        require_login();
        if (!file_exists(BT_RESULT)) {
            json_out(['status' => 'idle']);
        }
        $result = json_decode(file_get_contents(BT_RESULT), true);
        if (!$result) {
            json_out(['status' => 'error', 'message' => 'ステータスファイルの読み込みに失敗しました']);
        }
        json_out($result);
        break;

    case 'bt_reset':
        require_login();
        if (file_exists(BT_RESULT)) {
            file_put_contents(BT_RESULT, json_encode(['status' => 'idle'], JSON_UNESCAPED_UNICODE));
        }
        json_out(['status' => 'ok', 'message' => '実行フラグをリセットしました']);
        break;

    default:
        json_out(['status' => 'error', 'message' => '不明なアクション: ' . htmlspecialchars($action)]);
}
