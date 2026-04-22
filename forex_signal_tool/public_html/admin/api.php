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
define('LOG_FILE',           '/tmp/forex_admin_bg.log');
define('BT_PARAMS',          '/tmp/forex_bt_params.json');
define('BT_RESULT',          '/tmp/forex_bt_result.json');
define('RANKING_BT_PARAMS',  '/tmp/ranking_bt_params.json');
define('RANKING_BT_RESULT',  '/tmp/ranking_bt_result.json');

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

    // ---- コード更新 (git pull) ----
    case 'git_pull':
        require_login();
        $dir = PROJECT_ROOT;
        $out = [];
        $ret = 0;
        exec('git -C ' . escapeshellarg($dir) . ' pull 2>&1', $out, $ret);
        $output = implode("\n", $out);
        json_out(['status' => $ret === 0 ? 'ok' : 'error', 'output' => $output]);
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

    case 'quantflow_chart_data':
        require_login();
        try {
            $pdo   = get_pdo();
            $tf    = $_GET['tf'] ?? '1h';
            if ($tf === '5m') {
                $table   = 'quantflow_scores_5min';
                $default = 288; // 直近1日
            } else {
                $table   = 'quantflow_scores';
                $default = 168; // 直近7日
            }
            $limit = (int)($_GET['limit'] ?? $default);
            $stmt  = $pdo->prepare("
                SELECT DATE_FORMAT(CONVERT_TZ(`timestamp`, '+00:00', '+09:00'), '%m/%d %H:%i') AS ts,
                       score, trend_score, external_score, close_price
                FROM `$table`
                WHERE currency_pair = 'USDJPY'
                ORDER BY `timestamp` DESC
                LIMIT ?
            ");
            $stmt->bindValue(1, $limit, PDO::PARAM_INT);
            $stmt->execute();
            $rows = array_reverse($stmt->fetchAll(PDO::FETCH_ASSOC));
            $data = array_map(function($r) {
                return [
                    'ts'    => $r['ts'],
                    'score' => $r['score'] !== null ? (int)$r['score'] : null,
                    'trend' => $r['trend_score']    !== null ? (int)$r['trend_score']    : null,
                    'ext'   => $r['external_score'] !== null ? (int)$r['external_score'] : null,
                    'close' => $r['close_price']    !== null ? (float)$r['close_price']  : null,
                ];
            }, $rows);
            json_out(['ok' => true, 'data' => $data, 'count' => count($data), 'tf' => $tf]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'run_quantflow_scores':
        require_login();
        setting_set('quantflow_scores_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/update_quantflow_scores.py');
        exec("nohup {$cmd} >> /tmp/forex_quantflow_scores.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'QuantFlow スコア更新をバックグラウンドで開始しました']);
        break;

    case 'run_quantflow_scores_5min':
        require_login();
        setting_set('quantflow_scores_5min_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/update_quantflow_scores_5min.py');
        exec("nohup {$cmd} >> /tmp/forex_quantflow_5min.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'QuantFlow 5分足スコア更新を開始しました']);
        break;

    case 'run_quantflow_bt':
        require_login();
        setting_set('quantflow_bt_status', 'running');
        $cmd = escapeshellarg(PYTHON_BIN) . ' ' . escapeshellarg(TASKS_DIR . '/run_quantflow_bt.py');
        exec("nohup {$cmd} >> /tmp/forex_quantflow_bt.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'QuantFlow バックテストをバックグラウンドで開始しました（数分かかります）']);
        break;

    case 'qf_candles':
        $pair = strtoupper(preg_replace('/[^A-Za-z]/', '', $_GET['pair'] ?? 'USDJPY'));
        $from = $_GET['from'] ?? '';
        $to   = $_GET['to']   ?? '';
        if (!in_array($pair, ['USDJPY', 'GBPJPY', 'EURJPY'], true) || !$from || !$to) {
            json_out(['ok' => false, 'error' => '無効なパラメータ']);
        }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/', $from) ||
            !preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/', $to)) {
            json_out(['ok' => false, 'error' => '日時形式が不正です']);
        }
        try {
            $pdo  = get_pdo();
            $stmt = $pdo->prepare("
                SELECT DATE_FORMAT(timestamp, '%Y-%m-%dT%H:%i:%S') AS dt,
                       CAST(open  AS DECIMAL(12,5))       AS o,
                       CAST(high  AS DECIMAL(12,5))       AS h,
                       CAST(low   AS DECIMAL(12,5))       AS l,
                       CAST(close AS DECIMAL(12,5))       AS c
                FROM price_data
                WHERE currency_pair = ?
                  AND timeframe      = '5min'
                  AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
                LIMIT 500
            ");
            $fromSql = str_replace('T', ' ', $from);
            $toSql   = str_replace('T', ' ', $to);
            $stmt->execute([$pair, $fromSql, $toSql]);
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
            $candles = array_map(function($r) {
                return ['dt'=>$r['dt'],'o'=>(float)$r['o'],'h'=>(float)$r['h'],'l'=>(float)$r['l'],'c'=>(float)$r['c']];
            }, $rows);
            json_out(['ok' => true, 'candles' => $candles]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'test_quantflow_email':
        require_login();
        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/test_signal_email.py');
        $output = shell_exec("{$py} {$script} 2>&1");
        if ($output !== null && strpos($output, 'OK') !== false) {
            json_out(['status' => 'ok', 'message' => 'テストメールを送信しました']);
        } else {
            $detail = trim($output ?: '出力なし');
            json_out(['status' => 'error', 'message' => $detail]);
        }
        break;

    case 'quantflow_scores_5min_status':
        require_login();
        try {
            $pdo = get_pdo();
            $count = $pdo->query("SELECT COUNT(*) FROM quantflow_scores_5min WHERE currency_pair='USDJPY'")->fetchColumn();
            $latest = $pdo->query("
                SELECT score, close_price,
                       DATE_FORMAT(CONVERT_TZ(`timestamp`,'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS ts_jst
                FROM quantflow_scores_5min
                WHERE currency_pair='USDJPY'
                ORDER BY `timestamp` DESC LIMIT 5
            ")->fetchAll(PDO::FETCH_ASSOC);
            json_out(['ok' => true, 'count' => (int)$count, 'latest' => $latest]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'cron_health':
        require_login();
        try {
            $pdo = get_pdo();

            // 为替ペア 5min 最終データ
            $r = $pdo->query("
                SELECT DATE_FORMAT(CONVERT_TZ(MAX(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS last_jst,
                       TIMESTAMPDIFF(MINUTE, MAX(`timestamp`), UTC_TIMESTAMP()) AS min_ago
                FROM price_data WHERE currency_pair IN ('USDJPY','GBPJPY','EURJPY') AND timeframe='5min'
            ")->fetch(PDO::FETCH_ASSOC);
            $priceMin = $r['min_ago'] !== null ? (int)$r['min_ago'] : null;

            // マクロ指標 (US10Y/USBF/DXY)
            $r2 = $pdo->query("
                SELECT DATE_FORMAT(CONVERT_TZ(MAX(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS last_jst,
                       TIMESTAMPDIFF(MINUTE, MAX(`timestamp`), UTC_TIMESTAMP()) AS min_ago
                FROM price_data WHERE currency_pair IN ('US10Y','USBF','DXY')
            ")->fetch(PDO::FETCH_ASSOC);
            $macroMin = $r2['min_ago'] !== null ? (int)$r2['min_ago'] : null;

            // QuantFlow 5分足
            $r3 = $pdo->query("
                SELECT DATE_FORMAT(CONVERT_TZ(MAX(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS last_jst,
                       TIMESTAMPDIFF(MINUTE, MAX(`timestamp`), UTC_TIMESTAMP()) AS min_ago
                FROM quantflow_scores_5min WHERE currency_pair='USDJPY'
            ")->fetch(PDO::FETCH_ASSOC);
            $qf5mMin = $r3['min_ago'] !== null ? (int)$r3['min_ago'] : null;

            // QuantFlow 1時間足
            $r4 = $pdo->query("
                SELECT DATE_FORMAT(CONVERT_TZ(MAX(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS last_jst,
                       TIMESTAMPDIFF(MINUTE, MAX(`timestamp`), UTC_TIMESTAMP()) AS min_ago
                FROM quantflow_scores WHERE currency_pair='USDJPY'
            ")->fetch(PDO::FETCH_ASSOC);
            $qf1hMin = $r4['min_ago'] !== null ? (int)$r4['min_ago'] : null;

            // バックテスト / シグナル (settings テーブル)
            $lastBt     = setting_get('last_bt',     '未実行');
            $btStatus   = setting_get('backtest_status', '');
            $lastSignal = setting_get('last_signal', '未実行');
            $sigStatus  = setting_get('signal_status', '');

            function health_level($min_ago, $warn, $err) {
                if ($min_ago === null) return 'unknown';
                if ($min_ago >= $err)  return 'error';
                if ($min_ago >= $warn) return 'warn';
                return 'ok';
            }
            function format_ago($m) {
                if ($m === null) return '-';
                if ($m < 60)  return $m . '分前';
                if ($m < 1440) return round($m / 60, 1) . '時間前';
                return round($m / 1440, 1) . '日前';
            }

            $items = [
                [
                    'key'   => 'price',
                    'name'  => '価格データ取得（為替ペア 5min）',
                    'last'  => $r['last_jst']  ?? '-',
                    'ago'   => format_ago($priceMin),
                    'level' => health_level($priceMin, 420, 780),   // 1日2回クロン: warn=7h, error=13h
                    'note'  => $priceMin >= 780 ? 'fetch_data.py クロン未設定の可能性（*/5 * * * * で設定してください）' : '',
                ],
                [
                    'key'   => 'macro',
                    'name'  => 'マクロ指標取得（DXY / 米金利）',
                    'last'  => $r2['last_jst'] ?? '-',
                    'ago'   => format_ago($macroMin),
                    'level' => health_level($macroMin, 480, 1440),  // warn=8h, error=24h
                    'note'  => $macroMin >= 1440 ? 'fetch_data.py クロンが止まっている可能性' : '',
                ],
                [
                    'key'   => 'bt',
                    'name'  => 'バックテスト更新',
                    'last'  => $lastBt,
                    'ago'   => '',
                    'level' => ($btStatus === 'running') ? 'running' : 'ok',
                    'note'  => '',
                ],
                [
                    'key'   => 'signal',
                    'name'  => 'シグナル更新',
                    'last'  => $lastSignal,
                    'ago'   => '',
                    'level' => ($sigStatus === 'running') ? 'running' : 'ok',
                    'note'  => '',
                ],
                [
                    'key'   => 'qf5m',
                    'name'  => 'QuantFlow スコア（5分足）',
                    'last'  => $r3['last_jst'] ?? '-',
                    'ago'   => format_ago($qf5mMin),
                    'level' => health_level($qf5mMin, 30, 120),
                    'note'  => $qf5mMin >= 120 ? 'update_quantflow_scores_5min.py クロン未設定、または price_data.5min が古い' : '',
                ],
                [
                    'key'   => 'qf1h',
                    'name'  => 'QuantFlow スコア（1時間足）',
                    'last'  => $r4['last_jst'] ?? '-',
                    'ago'   => format_ago($qf1hMin),
                    'level' => health_level($qf1hMin, 90, 240),
                    'note'  => $qf1hMin >= 240 ? 'update_quantflow_scores.py クロンを確認してください' : '',
                ],
            ];

            json_out(['ok' => true, 'items' => $items, 'checked_at' => gmdate('H:i:s') . ' UTC']);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'data_coverage':
        require_login();
        try {
            $pdo = get_pdo();
            $stmt = $pdo->query(
                "SELECT currency_pair, timeframe, COUNT(*) AS cnt,
                        DATE_FORMAT(CONVERT_TZ(MIN(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS oldest_jst,
                        DATE_FORMAT(CONVERT_TZ(MAX(`timestamp`),'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS newest_jst
                 FROM price_data
                 GROUP BY currency_pair, timeframe
                 ORDER BY currency_pair, timeframe"
            );
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
            foreach ($rows as &$r) { $r['cnt'] = (int)$r['cnt']; }
            json_out(['ok' => true, 'rows' => $rows]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'quantflow_bt_history':
        require_login();
        try {
            $pdo  = get_pdo();
            $pair = strtoupper(preg_replace('/[^A-Za-z]/', '', $_GET['pair'] ?? 'USDJPY'));
            if (!in_array($pair, ['USDJPY','GBPJPY','EURJPY'], true)) $pair = 'USDJPY';

            $stats = $pdo->prepare("
                SELECT
                    COUNT(*)                                                        AS total,
                    COALESCE(SUM(outcome='WIN'),  0)                               AS wins,
                    COALESCE(SUM(outcome='LOSS'), 0)                               AS losses,
                    ROUND(COALESCE(SUM(profit_pips), 0), 2)                       AS total_pips,
                    ROUND(COALESCE(SUM(CASE WHEN outcome='WIN'  THEN profit_pips ELSE 0 END), 0), 2) AS win_pips,
                    ROUND(COALESCE(SUM(CASE WHEN outcome='LOSS' THEN profit_pips ELSE 0 END), 0), 2) AS loss_pips,
                    ROUND(AVG(CASE WHEN outcome='WIN'  THEN profit_pips END), 2)   AS avg_win,
                    ROUND(AVG(CASE WHEN outcome='LOSS' THEN profit_pips END), 2)   AS avg_loss
                FROM quantflow_trades WHERE currency_pair = ?
            ");
            $stats->execute([$pair]);
            $s = $stats->fetch(PDO::FETCH_ASSOC);
            foreach ($s as $k => $v) {
                $s[$k] = $v !== null
                    ? (strpos($k,'pips')!==false||strpos($k,'avg')!==false ? (float)$v : (int)$v)
                    : null;
            }

            $trades = $pdo->prepare("
                SELECT `year_month`,
                       DATE_FORMAT(CONVERT_TZ(entry_ts,'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS entry_jst,
                       DATE_FORMAT(CONVERT_TZ(exit_ts, '+00:00','+09:00'),'%Y/%m/%d %H:%i') AS exit_jst,
                       direction, score_at_entry,
                       CAST(entry_price AS DECIMAL(12,5)) AS entry_price,
                       CAST(exit_price  AS DECIMAL(12,5)) AS exit_price,
                       outcome,
                       CAST(profit_pips AS DECIMAL(8,2))  AS profit_pips,
                       CAST(sl_pips    AS DECIMAL(8,2))   AS sl_pips,
                       CAST(tp_pips    AS DECIMAL(8,2))   AS tp_pips
                FROM quantflow_trades
                WHERE currency_pair = ?
                ORDER BY entry_ts DESC
            ");
            $trades->execute([$pair]);
            json_out(['ok' => true, 'stats' => $s, 'trades' => $trades->fetchAll(PDO::FETCH_ASSOC)]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'quantflow_live_position':
        require_login();
        try {
            $pdo = get_pdo();
            $open = $pdo->query("
                SELECT id, direction, score_at_entry,
                       entry_price, sl_price, tp_price, sl_pips, tp_pips,
                       DATE_FORMAT(CONVERT_TZ(entry_ts,'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS entry_jst,
                       status
                FROM quantflow_live_signals
                WHERE currency_pair='USDJPY' AND status='OPEN'
                ORDER BY entry_ts DESC LIMIT 1
            ")->fetch(PDO::FETCH_ASSOC);

            $closed = $pdo->query("
                SELECT id, direction, score_at_entry,
                       entry_price, exit_price, outcome, profit_pips, exit_reason,
                       DATE_FORMAT(CONVERT_TZ(entry_ts,'+00:00','+09:00'),'%Y/%m/%d %H:%i') AS entry_jst,
                       DATE_FORMAT(CONVERT_TZ(exit_ts, '+00:00','+09:00'),'%Y/%m/%d %H:%i') AS exit_jst
                FROM quantflow_live_signals
                WHERE currency_pair='USDJPY' AND status='CLOSED'
                ORDER BY exit_ts DESC LIMIT 20
            ")->fetchAll(PDO::FETCH_ASSOC);

            json_out(['ok' => true, 'open' => $open ?: null, 'closed' => $closed]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'active_signals':
        require_login();
        try {
            $pdo  = get_pdo();
            $pairs = ['USDJPY', 'GBPJPY', 'EURJPY'];
            $data  = [];
            foreach ($pairs as $pair) {
                $stmt = $pdo->prepare("
                    SELECT signal_type, indicator_name, indicator_category, timeframe,
                           entry_price, sl_price, tp_price, win_rate, confidence_score,
                           DATE_FORMAT(CONVERT_TZ(signal_time,'+00:00','+09:00'),'%m/%d %H:%i') AS signal_jst
                    FROM trading_signals
                    WHERE currency_pair = ? AND is_active = 1
                      AND (expired_at IS NULL OR expired_at > UTC_TIMESTAMP())
                    ORDER BY confidence_score DESC
                    LIMIT 50
                ");
                $stmt->execute([$pair]);
                $data[$pair] = $stmt->fetchAll(PDO::FETCH_ASSOC);
            }
            json_out(['ok' => true, 'signals' => $data]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'qf_trades_csv':
        require_login();
        try {
            $pdo  = get_pdo();
            $pair = strtoupper(preg_replace('/[^A-Za-z]/', '', $_GET['pair'] ?? 'USDJPY'));
            if (!in_array($pair, ['USDJPY', 'GBPJPY', 'EURJPY'], true)) {
                $pair = 'USDJPY';
            }
            $stmt = $pdo->prepare("
                SELECT
                    `year_month`,
                    DATE_FORMAT(CONVERT_TZ(entry_ts, '+00:00', '+09:00'), '%Y/%m/%d %H:%i') AS entry_jst,
                    DATE_FORMAT(CONVERT_TZ(exit_ts,  '+00:00', '+09:00'), '%Y/%m/%d %H:%i') AS exit_jst,
                    direction,
                    score_at_entry,
                    CAST(entry_price  AS DECIMAL(12,5)) AS entry_price,
                    CAST(exit_price   AS DECIMAL(12,5)) AS exit_price,
                    outcome,
                    CAST(profit_pips  AS DECIMAL(8,2))  AS profit_pips,
                    CAST(sl_pips      AS DECIMAL(8,2))  AS sl_pips,
                    CAST(tp_pips      AS DECIMAL(8,2))  AS tp_pips
                FROM quantflow_trades
                WHERE currency_pair = ?
                ORDER BY entry_ts DESC
            ");
            $stmt->execute([$pair]);
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

            $filename = 'quantflow_trades_' . $pair . '_' . date('Ymd') . '.csv';
            header('Content-Type: text/csv; charset=UTF-8');
            header('Content-Disposition: attachment; filename="' . $filename . '"');
            header('Cache-Control: no-cache');

            $fh = fopen('php://output', 'w');
            fwrite($fh, "\xEF\xBB\xBF"); // UTF-8 BOM
            fputcsv($fh, ['年月', 'エントリー(JST)', 'エグジット(JST)', '方向', 'スコア',
                          'Entry価格', 'Exit価格', '結果', '損益(pips)', 'SL(pips)', 'TP(pips)']);
            foreach ($rows as $r) {
                fputcsv($fh, [
                    $r['year_month'],
                    $r['entry_jst']   ?? '',
                    $r['exit_jst']    ?? '',
                    $r['direction'],
                    $r['score_at_entry'],
                    $r['entry_price'] ?? '',
                    $r['exit_price']  ?? '',
                    $r['outcome']     ?? '',
                    $r['profit_pips'] ?? '',
                    $r['sl_pips']     ?? '',
                    $r['tp_pips']     ?? '',
                ]);
            }
            fclose($fh);
            exit;
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
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

    // ---- Gemini AI バックテスト分析 ----
    case 'ai_bt_analyze':
        require_login();
        $suffix     = date('YmdHis') . '_' . getmypid();
        $paramsFile = "/tmp/forex_ai_bt_{$suffix}.json";
        file_put_contents($paramsFile, json_encode($body, JSON_UNESCAPED_UNICODE));

        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/run_ai_bt_analyze.py');
        $pfile  = escapeshellarg($paramsFile);

        exec("{$py} {$script} {$pfile} 2>&1", $lines, $ret);
        @unlink($paramsFile);
        $raw = implode('', $lines);

        $result = json_decode($raw, true);
        if ($result === null) {
            json_out(['ok' => false, 'error' => 'Pythonスクリプト実行エラー', 'detail' => $raw]);
        }
        json_out($result);
        break;

    // ---- テクニカルページ専用バックテスト ----
    case 'run_indicator_page_bt':
        require_login();

        $suffix     = date('YmdHis') . '_' . getmypid();
        $paramsFile = "/tmp/forex_ind_bt_{$suffix}.json";
        file_put_contents($paramsFile, json_encode($body, JSON_UNESCAPED_UNICODE));

        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/run_indicator_page_bt.py');
        $pfile  = escapeshellarg($paramsFile);

        exec("{$py} {$script} {$pfile} 2>&1", $lines, $ret);
        @unlink($paramsFile);
        $raw = implode('', $lines);

        $result = json_decode($raw, true);
        if ($result === null) {
            json_out(['ok' => false, 'error' => 'Pythonスクリプト実行エラー', 'detail' => $raw]);
        }
        json_out($result);
        break;

    // ---- テクニカルページ専用バックテストのリセット ----
    case 'reset_indicator_page_bt':
        require_login();
        $indicatorName = trim($body['indicator_name'] ?? '');
        if (!$indicatorName) {
            json_out(['ok' => false, 'error' => '指標名が必要']);
            break;
        }
        try {
            $pdo = get_pdo();
            $pdo->prepare('DELETE FROM indicator_page_sim_trades WHERE indicator_name = ?')
                ->execute([$indicatorName]);
            $pdo->prepare('DELETE FROM indicator_page_bt_results WHERE indicator_name = ?')
                ->execute([$indicatorName]);
            json_out(['ok' => true]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    // ---- Phase 1 マルチ条件バックテスト ----
    case 'bt_v2':
        require_login();

        $paramsFile = '/tmp/forex_bt_v2_params.json';
        file_put_contents($paramsFile, json_encode($body, JSON_UNESCAPED_UNICODE));

        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/run_backtest_v2.py');
        $pfile  = escapeshellarg($paramsFile);

        exec("{$py} {$script} {$pfile} 2>&1", $lines, $ret);
        $raw = implode('', $lines);

        $result = json_decode($raw, true);
        if ($result === null) {
            json_out(['ok' => false, 'error' => 'Pythonスクリプト実行エラー', 'detail' => $raw]);
        }
        json_out($result);
        break;

    // ---- BT2インライン結果を indicator_page_bt_results に保存 ----
    case 'save_bt2_page_results':
        require_login();
        try {
            $pdo           = get_pdo();
            $indicatorName = trim($body['indicator_name'] ?? '');
            $results       = $body['results'] ?? [];  // [{pair, tf, dir, metrics, period}]
            if (!$indicatorName || !$results) {
                json_out(['ok' => false, 'error' => 'indicator_name と results が必要']);
                break;
            }

            // テーブル確保 + unique key に signal_direction を追加（旧キーを差し替え）
            $pdo->exec("CREATE TABLE IF NOT EXISTS indicator_page_bt_results (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                indicator_name  VARCHAR(80)  NOT NULL,
                currency_pair   VARCHAR(10)  NOT NULL,
                timeframe       VARCHAR(10)  NOT NULL,
                signal_direction VARCHAR(10) NOT NULL DEFAULT 'BOTH',
                win_rate        DECIMAL(5,2) NOT NULL DEFAULT 0,
                total_trades    INT          NOT NULL DEFAULT 0,
                winning_trades  INT          NOT NULL DEFAULT 0,
                losing_trades   INT          NOT NULL DEFAULT 0,
                total_profit    DECIMAL(15,2) NOT NULL DEFAULT 0,
                initial_capital DECIMAL(15,2) NOT NULL DEFAULT 1000000,
                final_capital   DECIMAL(15,2) NOT NULL DEFAULT 1000000,
                sl_pips         DECIMAL(8,2)  NOT NULL DEFAULT 20,
                tp_pips         DECIMAL(8,2)  NOT NULL DEFAULT 40,
                max_drawdown    DECIMAL(15,2) DEFAULT 0,
                profit_factor   DECIMAL(8,4)  DEFAULT 0,
                start_date      DATE NULL,
                end_date        DATE NULL,
                bars_used       INT DEFAULT 0,
                calculated_at   DATETIME NOT NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ind_page_bt (indicator_name, currency_pair, timeframe, signal_direction)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

            // 旧 unique key (direction なし) を direction 付きに差し替える
            try {
                $pdo->exec("ALTER TABLE indicator_page_bt_results DROP INDEX uq_ind_page_bt");
                $pdo->exec("ALTER TABLE indicator_page_bt_results ADD UNIQUE KEY uq_ind_page_bt (indicator_name, currency_pair, timeframe, signal_direction)");
            } catch (Exception $_e) { /* 既に新キーか、テーブルが空 → 無視 */ }

            // strategy_hash カラムを追加（初回のみ）
            try {
                $pdo->exec("ALTER TABLE indicator_page_bt_results ADD COLUMN strategy_hash VARCHAR(32) NULL DEFAULT NULL");
            } catch (Exception $_e) {}

            $stmt = $pdo->prepare("INSERT INTO indicator_page_bt_results
                (indicator_name, currency_pair, timeframe, signal_direction,
                 win_rate, total_trades, winning_trades, losing_trades,
                 total_profit, initial_capital, final_capital,
                 sl_pips, tp_pips, max_drawdown, profit_factor,
                 start_date, end_date, strategy_hash, calculated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())
                ON DUPLICATE KEY UPDATE
                    win_rate=VALUES(win_rate),
                    total_trades=VALUES(total_trades),
                    winning_trades=VALUES(winning_trades),
                    losing_trades=VALUES(losing_trades),
                    total_profit=VALUES(total_profit),
                    initial_capital=VALUES(initial_capital),
                    final_capital=VALUES(final_capital),
                    sl_pips=VALUES(sl_pips),
                    tp_pips=VALUES(tp_pips),
                    max_drawdown=VALUES(max_drawdown),
                    profit_factor=VALUES(profit_factor),
                    start_date=VALUES(start_date),
                    end_date=VALUES(end_date),
                    strategy_hash=VALUES(strategy_hash),
                    calculated_at=NOW()");

            // BUY/SELL それぞれ別行で保存（マージしない）
            foreach ($results as $r) {
                $pair = $r['pair'] ?? '';
                $tf   = $r['tf']   ?? '';
                $dir  = $r['dir']  ?: 'BOTH';
                $m    = $r['metrics'] ?? [];
                if (!$pair || !$tf) continue;

                $tt   = (int)($m['total_trades'] ?? 0);
                $wr01 = (float)($m['win_rate'] ?? 0);   // 0〜1 スケール
                $wt   = (int)round($wr01 * $tt);
                $lt   = $tt - $wt;
                $prof = (float)($m['total_profit'] ?? 0);
                $pf   = (float)($m['profit_factor'] ?? 0);
                $ic   = (float)($m['initial_capital'] ?? 1000000);
                $sl   = (float)($m['sl_pips'] ?? 20);
                $tp   = (float)($m['tp_pips'] ?? 40);
                $md   = (float)($m['max_drawdown'] ?? 0);
                $fc   = $ic + $prof;

                // 期間パース "YYYY-MM-DD〜YYYY-MM-DD"
                $startDate = $endDate = null;
                if (!empty($r['period'])) {
                    $parts = explode('〜', $r['period']);
                    $startDate = $parts[0] ?: null;
                    $endDate   = $parts[1] ?? null ?: null;
                }

                $stratHash = isset($r['strategy_hash']) ? substr((string)$r['strategy_hash'], 0, 32) : null;
                $stmt->execute([
                    $indicatorName, $pair, $tf, $dir,
                    round($wr01 * 100, 2), $tt, $wt, $lt,
                    round($prof, 2), round($ic, 2), round($fc, 2),
                    round($sl, 2), round($tp, 2),
                    round($md, 2), round(is_finite($pf) ? $pf : 0, 4),
                    $startDate, $endDate, $stratHash,
                ]);
            }

            // ---- 個別トレード履歴を indicator_page_sim_trades に保存 ----
            $pdo->exec("CREATE TABLE IF NOT EXISTS indicator_page_sim_trades (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                indicator_name  VARCHAR(80)  NOT NULL,
                currency_pair   VARCHAR(10)  NOT NULL,
                timeframe       VARCHAR(10)  NOT NULL,
                entry_at        DATETIME     NOT NULL,
                exit_at         DATETIME     NULL,
                direction       VARCHAR(10)  NOT NULL,
                entry_price     DECIMAL(12,5) NULL,
                exit_price      DECIMAL(12,5) NULL,
                tp_price        DECIMAL(12,5) NULL,
                sl_price        DECIMAL(12,5) NULL,
                sl_pips         DECIMAL(8,2)  NULL,
                tp_pips         DECIMAL(8,2)  NULL,
                outcome         VARCHAR(10)   NULL,
                profit_loss     DECIMAL(14,2) NULL,
                capital_after   DECIMAL(16,2) NULL,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ind_pair_tf (indicator_name, currency_pair, timeframe)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

            // 既存トレードを全削除してから再挿入
            $pdo->prepare('DELETE FROM indicator_page_sim_trades WHERE indicator_name = ?')
                ->execute([$indicatorName]);

            $stmtTrade = $pdo->prepare(
                "INSERT INTO indicator_page_sim_trades
                 (indicator_name, currency_pair, timeframe, entry_at, exit_at,
                  direction, entry_price, exit_price, tp_price, sl_price,
                  sl_pips, tp_pips, outcome, profit_loss, capital_after)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            );

            foreach ($results as $r) {
                $pair   = $r['pair'] ?? '';
                $tf     = $r['tf']   ?? '';
                $m      = $r['metrics'] ?? [];
                $slPips = (float)($m['sl_pips'] ?? 0) ?: null;
                $tpPips = (float)($m['tp_pips'] ?? 0) ?: null;
                if (!$pair || !$tf) continue;
                foreach (($r['trades'] ?? []) as $t) {
                    $exitReason = $t['exit_reason'] ?? '';
                    if ($exitReason === 'END_OF_DATA') continue; // 未決済は除外
                    // entry_time / exit_time は JST 文字列 → UTC に変換（-9h）
                    $entryAt = $exitAt = null;
                    if (!empty($t['entry_time'])) {
                        $dt = DateTime::createFromFormat('Y-m-d\TH:i:s', $t['entry_time']);
                        if ($dt) { $dt->modify('-9 hours'); $entryAt = $dt->format('Y-m-d H:i:s'); }
                    }
                    if (!empty($t['exit_time'])) {
                        $dt = DateTime::createFromFormat('Y-m-d\TH:i:s', $t['exit_time']);
                        if ($dt) { $dt->modify('-9 hours'); $exitAt = $dt->format('Y-m-d H:i:s'); }
                    }
                    if (!$entryAt) continue;
                    $outcome = ($exitReason === 'TP') ? 'WIN' : 'LOSS';
                    $stmtTrade->execute([
                        $indicatorName, $pair, $tf,
                        $entryAt, $exitAt,
                        $t['direction'] ?? 'BUY',
                        isset($t['entry_price'])     ? round((float)$t['entry_price'],     5) : null,
                        isset($t['exit_price'])      ? round((float)$t['exit_price'],      5) : null,
                        isset($t['tp_price'])        ? round((float)$t['tp_price'],        5) : null,
                        isset($t['sl_price'])        ? round((float)$t['sl_price'],        5) : null,
                        $slPips, $tpPips,
                        $outcome,
                        isset($t['pnl_currency'])    ? round((float)$t['pnl_currency'],    2) : null,
                        isset($t['running_capital']) ? round((float)$t['running_capital'], 2) : null,
                    ]);
                }
            }

            json_out(['ok' => true, 'saved' => count($results)]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'get_bt2_existing_results':
        require_login();
        $indicatorName = trim($body['indicator_name'] ?? '');
        if (!$indicatorName) { json_out(['ok' => false, 'data' => []]); break; }
        try {
            $pdo  = get_pdo();
            $rows = $pdo->prepare(
                "SELECT currency_pair, timeframe, signal_direction, strategy_hash, start_date, end_date
                 FROM indicator_page_bt_results WHERE indicator_name = ?"
            );
            $rows->execute([$indicatorName]);
            $data = [];
            foreach ($rows->fetchAll(PDO::FETCH_ASSOC) as $row) {
                $key = $row['currency_pair'] . '_' . $row['timeframe'] . '_' . ($row['signal_direction'] ?: 'BOTH');
                $data[$key] = [
                    'strategy_hash' => $row['strategy_hash'] ?? '',
                    'start_date'    => $row['start_date']    ? substr($row['start_date'], 0, 10) : '',
                    'end_date'      => $row['end_date']      ? substr($row['end_date'],   0, 10) : '',
                ];
            }
            json_out(['ok' => true, 'data' => $data]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'data' => [], 'error' => $e->getMessage()]);
        }
        break;

    // ---- 戦略保存 / 読込 / 一覧 ----
    case 'save_strategy':
        require_login();
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS saved_strategies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                config_json TEXT NOT NULL,
                linked_indicator_name VARCHAR(80) NULL,
                bt_result_json MEDIUMTEXT NULL,
                bt_ran_at DATETIME NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

            // カラム追加（旧テーブルとの互換）
            foreach ([
                "ALTER TABLE saved_strategies ADD COLUMN linked_indicator_name VARCHAR(80) NULL",
                "ALTER TABLE saved_strategies ADD COLUMN bt_result_json MEDIUMTEXT NULL",
                "ALTER TABLE saved_strategies ADD COLUMN bt_ran_at DATETIME NULL",
            ] as $_sql) {
                try { $pdo->exec($_sql); } catch (Exception $_e) { /* already exists */ }
            }

            $name        = trim($body['name'] ?? '');
            $config      = $body['config'] ?? null;
            $linkedInd   = trim($body['linked_indicator'] ?? '') ?: null;
            $btResult    = isset($body['bt_result']) ? $body['bt_result'] : null;
            $btRanAt     = $btResult ? date('Y-m-d H:i:s') : null;

            if (!$name)   json_out(['ok' => false, 'error' => '戦略名を入力してください']);
            if (!$config) json_out(['ok' => false, 'error' => 'config が必要です']);

            $stmt = $pdo->prepare(
                'INSERT INTO saved_strategies (name, config_json, linked_indicator_name, bt_result_json, bt_ran_at)
                 VALUES (?, ?, ?, ?, ?)'
            );
            $stmt->execute([
                $name,
                json_encode($config, JSON_UNESCAPED_UNICODE),
                $linkedInd,
                $btResult !== null ? json_encode($btResult, JSON_UNESCAPED_UNICODE) : null,
                $btRanAt,
            ]);
            json_out(['ok' => true, 'id' => (int)$pdo->lastInsertId()]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'get_strategies':
        require_login();
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS saved_strategies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                config_json TEXT NOT NULL,
                linked_indicator_name VARCHAR(80) NULL,
                bt_result_json MEDIUMTEXT NULL,
                bt_ran_at DATETIME NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

            $rows = $pdo->query(
                'SELECT id, name, linked_indicator_name, bt_ran_at, created_at
                 FROM saved_strategies ORDER BY id DESC'
            )->fetchAll();
            json_out(['ok' => true, 'strategies' => $rows]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'load_strategy':
        require_login();
        try {
            $pdo = get_pdo();
            $id  = (int)($body['id'] ?? 0);
            if (!$id) json_out(['ok' => false, 'error' => 'id が必要です']);
            $stmt = $pdo->prepare(
                'SELECT config_json, linked_indicator_name, bt_result_json, bt_ran_at
                 FROM saved_strategies WHERE id = ?'
            );
            $stmt->execute([$id]);
            $row = $stmt->fetch();
            if (!$row) json_out(['ok' => false, 'error' => '戦略が見つかりません']);
            json_out([
                'ok'              => true,
                'config'          => json_decode($row['config_json'], true),
                'linked_indicator'=> $row['linked_indicator_name'],
                'bt_result'       => $row['bt_result_json'] ? json_decode($row['bt_result_json'], true) : null,
                'bt_ran_at'       => $row['bt_ran_at'],
            ]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    // バックテスト済み指標の一覧（v2保存モーダル用）
    case 'get_indicators':
        require_login();
        try {
            $pdo  = get_pdo();
            $names = $pdo->query(
                "SELECT DISTINCT indicator_name
                 FROM backtest_results
                 WHERE indicator_name NOT LIKE '%_BBSL'
                 ORDER BY indicator_name"
            )->fetchAll(PDO::FETCH_COLUMN);
            // 日本語表示名マップを読み込む（generate_static.py が生成）
            $dispFile = __DIR__ . '/indicator_display_names.json';
            $dispMap  = file_exists($dispFile)
                ? (json_decode(file_get_contents($dispFile), true) ?? [])
                : [];
            $indicators = array_map(fn($n) => [
                'name'    => $n,
                'display' => $dispMap[$n] ?? $n,
            ], $names);
            json_out(['ok' => true, 'indicators' => $indicators]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    case 'delete_strategy':
        require_login();
        try {
            $pdo = get_pdo();
            $id  = (int)($body['id'] ?? 0);
            if (!$id) json_out(['ok' => false, 'error' => 'id が必要です']);
            $pdo->prepare('DELETE FROM saved_strategies WHERE id = ?')->execute([$id]);
            json_out(['ok' => true]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    // ---- Phase 1 グリッドサーチ最適化 ----
    case 'bt_optimize':
        require_login();

        $paramsFile = '/tmp/forex_bt_opt_params.json';
        file_put_contents($paramsFile, json_encode($body, JSON_UNESCAPED_UNICODE));

        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/run_optimize.py');
        $pfile  = escapeshellarg($paramsFile);

        exec("{$py} {$script} {$pfile} 2>&1", $lines, $ret);
        $raw = implode('', $lines);

        $result = json_decode($raw, true);
        if ($result === null) {
            json_out(['ok' => false, 'error' => 'Pythonスクリプト実行エラー', 'detail' => $raw]);
        }
        json_out($result);
        break;

    // ---- v2 戦略リアルタイムシグナル生成 ----
    case 'bt_v2_signal':
        require_login();

        $paramsFile = '/tmp/forex_bt_v2_signal_params.json';
        file_put_contents($paramsFile, json_encode($body, JSON_UNESCAPED_UNICODE));

        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/run_v2_signal.py');
        $pfile  = escapeshellarg($paramsFile);

        exec("{$py} {$script} {$pfile} 2>&1", $lines, $ret);
        $raw = implode('', $lines);

        $result = json_decode($raw, true);
        if ($result === null) {
            json_out(['ok' => false, 'error' => 'Pythonスクリプト実行エラー', 'detail' => $raw]);
        }
        json_out($result);
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

    case 'session_ranking_reset':
        require_login();
        try {
            $pdo = get_pdo();
            $rk_count = (int)$pdo->query('SELECT COUNT(*) FROM session_ranking_results')->fetchColumn();
            $th_count = (int)$pdo->query('SELECT COUNT(*) FROM session_trade_history')->fetchColumn();
            $pdo->exec('DELETE FROM session_ranking_results');
            $pdo->exec('DELETE FROM session_trade_history');
            json_out([
                'status'  => 'ok',
                'message' => "ランキング {$rk_count}件・トレード履歴 {$th_count}件 を削除しました。",
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'simulation_trades_reset':
        require_login();
        try {
            $pdo = get_pdo();
            // simulation_trades は backtest_results の CASCADE DELETE で連動するため
            // backtest_results を先に削除すれば両方クリアされる
            $st_count = (int)$pdo->query('SELECT COUNT(*) FROM simulation_trades')->fetchColumn();
            $bt_count = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
            $pdo->exec('DELETE FROM simulation_trades');
            $pdo->exec('DELETE FROM backtest_results');
            json_out([
                'status'  => 'ok',
                'message' => "シミュレーション履歴 {$st_count}件・バックテスト結果 {$bt_count}件 を削除しました。",
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- SEO 管理 ----
    case 'seo_init':
        require_login();
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS page_seo (
                page_type        VARCHAR(20)  NOT NULL,
                page_key         VARCHAR(100) NOT NULL,
                title            VARCHAR(200) DEFAULT '',
                meta_description TEXT,
                updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (page_type, page_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            $rows = $pdo->query("SELECT page_type, page_key, title, meta_description, updated_at FROM page_seo")->fetchAll();
            $data = [];
            foreach ($rows as $r) {
                $data[$r['page_type'] . ':' . $r['page_key']] = [
                    'title'            => $r['title'],
                    'meta_description' => $r['meta_description'],
                    'updated_at'       => $r['updated_at'],
                ];
            }
            json_out(['status' => 'ok', 'data' => $data]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'seo_save':
        require_login();
        $pageType = $body['page_type'] ?? '';
        $pageKey  = $body['page_key']  ?? '';
        $title    = trim($body['title']            ?? '');
        $meta     = trim($body['meta_description'] ?? '');
        if (!in_array($pageType, ['indicator', 'category', 'pair', 'signals'], true) || $pageKey === '') {
            json_out(['status' => 'error', 'message' => '無効なパラメータ']);
        }
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS page_seo (
                page_type        VARCHAR(20)  NOT NULL,
                page_key         VARCHAR(100) NOT NULL,
                title            VARCHAR(200) DEFAULT '',
                meta_description TEXT,
                updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (page_type, page_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            $stmt = $pdo->prepare(
                "INSERT INTO page_seo (page_type, page_key, title, meta_description)
                 VALUES (?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                   title=VALUES(title),
                   meta_description=VALUES(meta_description),
                   updated_at=NOW()"
            );
            $stmt->execute([$pageType, $pageKey, $title, $meta]);
            json_out(['status' => 'ok', 'message' => '保存しました']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- ランキングページ コンテンツ管理 ----
    case 'content_init':
        require_login();
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS site_content (
                content_key   VARCHAR(100) NOT NULL PRIMARY KEY,
                content_value MEDIUMTEXT,
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            $rows = $pdo->query("SELECT content_key, content_value, updated_at FROM site_content")->fetchAll();
            $data = [];
            foreach ($rows as $r) {
                $data[$r['content_key']] = [
                    'value'      => $r['content_value'],
                    'updated_at' => $r['updated_at'],
                ];
            }
            json_out(['status' => 'ok', 'data' => $data]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'content_save':
        require_login();
        $key   = trim($body['key']   ?? '');
        $value = $body['value'] ?? '';
        $allowed = ['ranking_analysis', 'ranking_short_term', 'ranking_day_trade', 'ranking_swing', 'ranking_title', 'ranking_intro', 'top_article', 'top_article_pre', 'top_article_post', 'signals_intro', 'signals_heading', 'terms_content', 'privacy_content'];
        $is_valid = in_array($key, $allowed, true)
            || preg_match('/^indicator_article_[a-z0-9_]+(_(css|jsonld))?$/', $key)
            || preg_match('/^indicator_ai_notes_[a-z0-9_]+$/', $key)
            || preg_match('/^indicator_(description|good|bad|feature)_[a-z0-9_]+$/', $key)
            || preg_match('/^pair_article_(usdjpy|gbpjpy|eurjpy)(_(css|heading))?$/', $key);
        if (!$is_valid) {
            json_out(['status' => 'error', 'message' => '無効なキーです']);
        }
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS site_content (
                content_key   VARCHAR(100) NOT NULL PRIMARY KEY,
                content_value MEDIUMTEXT,
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            $stmt = $pdo->prepare(
                "INSERT INTO site_content (content_key, content_value)
                 VALUES (?, ?)
                 ON DUPLICATE KEY UPDATE content_value=VALUES(content_value), updated_at=NOW()"
            );
            $stmt->execute([$key, $value]);
            json_out(['status' => 'ok', 'message' => '保存しました']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- 指標に紐づく保存済み戦略を取得 ----
    case 'get_linked_strategies':
        require_login();
        try {
            $indName = trim($body['indicator_name'] ?? '');
            if (!$indName) { json_out(['ok' => false, 'error' => '指標名が必要']); break; }
            $pdo  = get_pdo();
            $stmt = $pdo->prepare(
                'SELECT id, name, bt_ran_at, bt_result_json
                 FROM saved_strategies
                 WHERE linked_indicator_name = ?
                 ORDER BY COALESCE(bt_ran_at, created_at) DESC LIMIT 10'
            );
            $stmt->execute([$indName]);
            $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
            $strategies = array_map(function($r) {
                $bt = $r['bt_result_json'] ? json_decode($r['bt_result_json'], true) : null;
                return [
                    'id'       => $r['id'],
                    'name'     => $r['name'],
                    'bt_ran_at'=> $r['bt_ran_at'] ? substr($r['bt_ran_at'],0,16) : '',
                    'win_rate' => $bt['win_rate'] ?? null,
                    'pf'       => $bt['profit_factor'] ?? null,
                    'trades'   => $bt['total_trades'] ?? null,
                ];
            }, $rows);
            json_out(['ok' => true, 'strategies' => $strategies]);
        } catch (Exception $e) {
            json_out(['ok' => false, 'error' => $e->getMessage()]);
        }
        break;

    // ---- ランキングバックテスト管理 ----
    case 'ranking_bt_run':
        require_login();

        // 既に実行中チェック（30分で自動解除）
        if (file_exists(RANKING_BT_RESULT)) {
            $prev = json_decode(file_get_contents(RANKING_BT_RESULT), true);
            if (($prev['status'] ?? '') === 'running') {
                $startedAt = $prev['started_at'] ?? 0;
                if (time() - $startedAt < 1800) {
                    json_out(['status' => 'busy', 'message' => '別のバックテストが実行中です（最大30分で自動解除）']);
                }
            }
        }

        $startDate  = trim($body['start_date']       ?? '');
        $endDate    = trim($body['end_date']         ?? '');
        $swingStart = trim($body['swing_start_date'] ?? '') ?: $startDate;
        $swingEnd   = trim($body['swing_end_date']   ?? '') ?: $endDate;
        $forceFull  = !empty($body['force_full']);

        $params = [
            'start_date'       => $startDate,
            'end_date'         => $endDate,
            'swing_start_date' => $swingStart,
            'swing_end_date'   => $swingEnd,
            'force_full'       => $forceFull,
        ];
        file_put_contents(RANKING_BT_PARAMS, json_encode($params, JSON_UNESCAPED_UNICODE));
        file_put_contents(RANKING_BT_RESULT, json_encode([
            'status'     => 'running',
            'message'    => '初期化中...',
            'started_at' => time(),
        ], JSON_UNESCAPED_UNICODE));

        $script = escapeshellarg(TASKS_DIR . '/run_ranking_bt.py');
        $cmd    = escapeshellarg(PYTHON_BIN) . ' ' . $script;
        exec("nohup {$cmd} >> /tmp/ranking_bt_bg.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'ランキングバックテストを開始しました']);
        break;

    case 'ranking_bt_status':
        require_login();
        if (!file_exists(RANKING_BT_RESULT)) {
            json_out(['status' => 'idle']);
        }
        $result = json_decode(file_get_contents(RANKING_BT_RESULT), true);
        json_out($result ?: ['status' => 'idle']);
        break;

    case 'ranking_bt_info':
        require_login();
        try {
            $pdo     = get_pdo();
            $stCount  = (int)$pdo->query('SELECT COUNT(*) FROM simulation_trades')->fetchColumn();
            $btCount  = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
            $sigCount = (int)$pdo->query("SELECT COUNT(*) FROM trading_signals WHERE is_active=1")->fetchColumn();
            $lastBt   = setting_get('last_backtest_at', '未実行');
            json_out([
                'status'            => 'ok',
                'simulation_trades' => $stCount,
                'backtest_results'  => $btCount,
                'signals'           => $sigCount,
                'last_backtest_at'  => $lastBt,
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- 市場セッション別ランキング更新 ----
    case 'session_update_run':
        require_login();
        $sessResultFile = '/tmp/session_update_result.json';
        $sessParamsFile = '/tmp/session_update_params.json';
        if (file_exists($sessResultFile)) {
            $prev = json_decode(file_get_contents($sessResultFile), true);
            if (($prev['status'] ?? '') === 'running') {
                json_out(['status' => 'busy', 'message' => 'セッション更新が実行中です（最大5分で自動解除）']);
            }
        }
        $days       = max(1, min(90, (int)($body['days'] ?? 30)));
        $targetDate = trim($body['target_date'] ?? '');
        // YYYY-MM-DD 形式のみ受け付ける（未指定 or 不正 → 当日）
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $targetDate)) {
            $targetDate = '';
        }
        $params = ['days' => $days, 'target_date' => $targetDate];
        file_put_contents($sessParamsFile, json_encode($params, JSON_UNESCAPED_UNICODE));
        file_put_contents($sessResultFile, json_encode([
            'status'     => 'running',
            'message'    => '初期化中...',
            'started_at' => time(),
        ], JSON_UNESCAPED_UNICODE));
        $script = escapeshellarg(TASKS_DIR . '/run_session_update.py');
        $cmd    = escapeshellarg(PYTHON_BIN) . ' ' . $script;
        exec("nohup {$cmd} >> /tmp/session_update_bg.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'セッションランキング更新を開始しました']);
        break;

    case 'session_update_status':
        require_login();
        $sessResultFile = '/tmp/session_update_result.json';
        if (!file_exists($sessResultFile)) {
            json_out(['status' => 'idle']);
        }
        $result = json_decode(file_get_contents($sessResultFile), true);
        json_out($result ?: ['status' => 'idle']);
        break;

    // ---- セッション専用バックテスト ----
    case 'session_bt_run':
        require_login();
        $btResultFile = '/tmp/session_bt_result.json';
        $btParamsFile = '/tmp/session_bt_params.json';
        if (file_exists($btResultFile)) {
            $prev = json_decode(file_get_contents($btResultFile), true);
            if (($prev['status'] ?? '') === 'running') {
                json_out(['status' => 'busy', 'message' => 'セッション専用バックテストが実行中です']);
                break;
            }
        }
        $startDate = trim($body['start_date'] ?? '');
        $endDate   = trim($body['end_date']   ?? '');
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $startDate)) $startDate = '';
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $endDate))   $endDate   = '';
        $params = ['start_date' => $startDate, 'end_date' => $endDate];
        file_put_contents($btParamsFile, json_encode($params, JSON_UNESCAPED_UNICODE));
        file_put_contents($btResultFile, json_encode([
            'status'     => 'running',
            'message'    => '初期化中...',
            'started_at' => time(),
        ], JSON_UNESCAPED_UNICODE));
        $script = escapeshellarg(TASKS_DIR . '/run_session_bt.py');
        $cmd    = escapeshellarg(PYTHON_BIN) . ' ' . $script;
        exec("nohup {$cmd} >> /tmp/session_bt_bg.log 2>&1 &");
        json_out(['status' => 'started', 'message' => 'セッション専用バックテストを開始しました']);
        break;

    case 'session_bt_status':
        require_login();
        $btResultFile = '/tmp/session_bt_result.json';
        if (!file_exists($btResultFile)) {
            json_out(['status' => 'idle']);
            break;
        }
        $result = json_decode(file_get_contents($btResultFile), true);
        json_out($result ?: ['status' => 'idle']);
        break;

    case 'session_ranking_info':
        require_login();
        try {
            $pdo        = get_pdo();
            $rankCount  = (int)$pdo->query('SELECT COUNT(*) FROM session_ranking_results')->fetchColumn();
            $tradeCount = (int)$pdo->query('SELECT COUNT(*) FROM session_trade_history')->fetchColumn();
            $latestDate = $pdo->query('SELECT MAX(snapshot_date) FROM session_ranking_results')->fetchColumn();
            json_out([
                'status'        => 'ok',
                'ranking_count' => $rankCount,
                'trade_count'   => $tradeCount,
                'latest_date'   => $latestDate ?: '未取得',
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'session_trade_breakdown':
        require_login();
        try {
            $pdo = get_pdo();

            // 利用可能な日付一覧（session_trade_history から取得）
            $datesSQL = "
                SELECT DISTINCT trade_date
                FROM session_trade_history
                ORDER BY trade_date DESC
                LIMIT 30
            ";
            $dates = $pdo->query($datesSQL)->fetchAll(PDO::FETCH_COLUMN);

            // 対象日（指定なければ最新）
            $reqDate = trim($_GET['date'] ?? '');
            if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $reqDate)) {
                $reqDate = $dates[0] ?? date('Y-m-d');
            }

            // セッション別サマリー（session_trade_history から集計）
            $summarySQL = "
                SELECT
                    session_key,
                    COUNT(*)                       AS total,
                    SUM(outcome = 'WIN')           AS wins,
                    SUM(outcome = 'LOSS')          AS losses,
                    COUNT(DISTINCT indicator_name) AS indicator_count
                FROM session_trade_history
                WHERE trade_date = :d
                GROUP BY session_key
            ";
            $stmt = $pdo->prepare($summarySQL);
            $stmt->execute([':d' => $reqDate]);
            $summaryRows = $stmt->fetchAll(PDO::FETCH_ASSOC);

            // セッション別ランキング（session_ranking_results の最新スナップショット）
            // 「全期間BT集計」なので選択日付に関係なく、各セッションの最新スナップショットを表示
            $rankSQL = "
                SELECT r.session_key, r.rank_position, r.indicator_name,
                       r.win_rate, r.profit_factor, r.total_trades, r.score
                FROM session_ranking_results r
                INNER JOIN (
                    SELECT session_key, MAX(snapshot_date) AS max_date
                    FROM session_ranking_results
                    GROUP BY session_key
                ) latest ON r.session_key = latest.session_key
                        AND r.snapshot_date = latest.max_date
                ORDER BY r.session_key, r.rank_position
            ";
            $stmt2 = $pdo->prepare($rankSQL);
            $stmt2->execute();
            $rankRows = $stmt2->fetchAll(PDO::FETCH_ASSOC);

            $top = [];
            foreach ($rankRows as $r) {
                $sk = $r['session_key'];
                if (!isset($top[$sk])) $top[$sk] = [];
                $top[$sk][] = $r;
            }

            json_out([
                'status'       => 'ok',
                'dates'        => $dates,
                'current_date' => $reqDate,
                'summary'      => $summaryRows,
                'top'          => $top,
            ]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- BT2 保存済み戦略のトレード履歴を CSV/ZIP でダウンロード ----
    case 'bt2_csv':
        require_login();
        $id = (int)($_GET['id'] ?? $body['id'] ?? 0);
        if (!$id) { json_out(['status'=>'error','message'=>'id が必要です']); break; }

        try {
            $pdo  = get_pdo();
            $stmt = $pdo->prepare('SELECT name, bt_result_json FROM saved_strategies WHERE id = ?');
            $stmt->execute([$id]);
            $row  = $stmt->fetch();
            if (!$row || !$row['bt_result_json']) {
                json_out(['status'=>'error','message'=>'データが見つかりません（バックテストを実行してから保存してください）']);
                break;
            }

            $btResult = json_decode($row['bt_result_json'], true) ?? [];
            $safeName = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $row['name']);
            $suffix   = date('YmdHis') . '_' . getmypid();
            $tmpDir   = sys_get_temp_dir();
            $tmpFiles = [];

            // ① サマリーCSV（per_pair メトリクス）
            $sumFile  = "{$tmpDir}/bt2_summary_{$suffix}.csv";
            $tmpFiles[] = $sumFile;
            $fh = fopen($sumFile, 'w');
            fwrite($fh, "\xEF\xBB\xBF");
            fputcsv($fh, ['通貨ペア','TF','トレード数','勝率(%)','PF',
                          '純損益(pips)','総損益(円)','最大DD(pips)',
                          '平均勝ち(pips)','平均負け(pips)','期待値(pips)',
                          '最大連勝','最大連敗','ロング勝率(%)','ショート勝率(%)']);
            foreach ($btResult['per_pair'] ?? [] as $key => $m) {
                $parts = explode('_', $key, 2);
                fputcsv($fh, [
                    $parts[0], $parts[1] ?? '',
                    $m['total_trades']    ?? '',
                    isset($m['win_rate'])        ? round($m['win_rate']        * 100, 1) : '',
                    $m['profit_factor']   ?? '',
                    $m['net_profit_pips'] ?? '',
                    $m['total_profit']    ?? '',
                    $m['max_drawdown_pips'] ?? '',
                    $m['avg_win_pips']    ?? '',
                    $m['avg_loss_pips']   ?? '',
                    $m['expectancy_pips'] ?? '',
                    $m['max_win_streak']  ?? '',
                    $m['max_loss_streak'] ?? '',
                    isset($m['long_win_rate'])  ? round($m['long_win_rate']  * 100, 1) : '',
                    isset($m['short_win_rate']) ? round($m['short_win_rate'] * 100, 1) : '',
                ]);
            }
            fclose($fh);

            // ② トレードCSV（trades_by_key — 全ペア・TF）
            $tradeFile  = "{$tmpDir}/bt2_trades_{$suffix}.csv";
            $tmpFiles[] = $tradeFile;
            $fh2 = fopen($tradeFile, 'w');
            fwrite($fh2, "\xEF\xBB\xBF");
            fputcsv($fh2, ['通貨ペア','TF','エントリー日時(JST)','エグジット日時(JST)',
                           '方向','エントリー価格','エグジット価格','TP価格','SL価格',
                           '損益(pips)','損益(円)','資金残高(円)','終了理由','エントリー条件']);
            foreach ($btResult['trades_by_key'] ?? [] as $key => $trades) {
                $parts = explode('_', $key, 2);
                $pair  = $parts[0];
                $tf    = $parts[1] ?? '';
                foreach ((array)$trades as $t) {
                    $reasons = isset($t['entry_reasons'])
                        ? implode(' / ', (array)$t['entry_reasons'])
                        : '';
                    fputcsv($fh2, [
                        $pair, $tf,
                        $t['entry_time']      ?? '',
                        $t['exit_time']       ?? '',
                        $t['direction']       ?? '',
                        $t['entry_price']     ?? '',
                        $t['exit_price']      ?? '',
                        $t['tp_price']        ?? '',
                        $t['sl_price']        ?? '',
                        $t['pnl_pips']        ?? '',
                        $t['pnl_currency']    ?? '',
                        $t['running_capital'] ?? '',
                        $t['exit_reason']     ?? '',
                        $reasons,
                    ]);
                }
            }
            fclose($fh2);

            // ③ ZIP にまとめてダウンロード
            $zipFile = "{$tmpDir}/bt2_{$safeName}_{$suffix}.zip";
            $zip = new ZipArchive();
            if ($zip->open($zipFile, ZipArchive::CREATE) !== true) {
                throw new Exception('ZIP作成に失敗しました');
            }
            $zip->addFile($sumFile,   "summary_{$safeName}.csv");
            $zip->addFile($tradeFile, "trades_{$safeName}.csv");
            $zip->close();
            foreach ($tmpFiles as $f) { @unlink($f); }

            header('Content-Type: application/zip');
            header('Content-Disposition: attachment; filename="bt2_' . $safeName . '_' . date('Ymd') . '.zip"');
            header('Content-Length: ' . filesize($zipFile));
            header('Cache-Control: no-cache');
            readfile($zipFile);
            unlink($zipFile);
            exit;

        } catch (Exception $e) {
            foreach ($tmpFiles as $f) { @unlink($f); }
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- 通貨ペアページ HTML 再生成（generate_static.py --pair） ----
    case 'rebuild_pair_page':
        require_login();
        $pair = strtolower(trim($body['pair'] ?? ''));
        if (!in_array($pair, ['usdjpy', 'gbpjpy', 'eurjpy'], true)) {
            json_out(['ok' => false, 'error' => 'pair は usdjpy/gbpjpy/eurjpy のいずれかを指定してください']);
            break;
        }
        $py      = escapeshellarg(PYTHON_BIN);
        $script  = escapeshellarg(TASKS_DIR . '/generate_static.py');
        $pairArg = escapeshellarg('--pair=' . strtoupper($pair));
        exec("{$py} {$script} {$pairArg} 2>&1", $lines, $ret);
        $output = implode("\n", array_slice($lines, -30));
        json_out(['ok' => $ret === 0, 'output' => $output]);
        break;

    // ---- シグナルページ HTML 再生成（generate_static.py --page=signals） ----
    case 'rebuild_signals_page':
        require_login();
        $py     = escapeshellarg(PYTHON_BIN);
        $script = escapeshellarg(TASKS_DIR . '/generate_static.py');
        exec("{$py} {$script} --page=signals 2>&1", $lines, $ret);
        $output = implode("\n", array_slice($lines, -30));
        json_out(['ok' => $ret === 0, 'output' => $output]);
        break;

    // ---- 指標ページ HTML 再生成（generate_static.py --slug） ----
    case 'rebuild_indicator_page':
        require_login();
        $slug = preg_replace('/[^a-z0-9_\-]/', '', strtolower(trim($body['slug'] ?? '')));
        if (!$slug) { json_out(['ok' => false, 'error' => 'slug が必要です']); break; }
        $py      = escapeshellarg(PYTHON_BIN);
        $script  = escapeshellarg(TASKS_DIR . '/generate_static.py');
        $slugArg = escapeshellarg('--slug=' . $slug);
        exec("{$py} {$script} {$slugArg} 2>&1", $lines, $ret);
        // 最後の30行のみ返す（ログが長くなる場合に備え）
        $output = implode("\n", array_slice($lines, -30));
        json_out(['ok' => $ret === 0, 'output' => $output]);
        break;

    case 'indicator_csv':
        require_login();

        // indicator_name を直接受け取る（推奨）or slug から JSON ルックアップ（後方互換）
        $indicatorName = '';
        $slug = '';
        if (!empty($_GET['ind'])) {
            $indicatorName = preg_replace('/[^A-Za-z0-9_]/', '', trim($_GET['ind']));
            $slug = strtolower(preg_replace('/[^a-z0-9]/i', '_', $indicatorName));
        } else {
            $slug = preg_replace('/[^a-z0-9_]/', '', strtolower(trim($_GET['slug'] ?? '')));
            $mapFile = __DIR__ . '/indicator_slugs.json';
            if (file_exists($mapFile)) {
                $slugMap = json_decode(file_get_contents($mapFile), true) ?? [];
                $indicatorName = $slugMap[$slug] ?? '';
            }
        }
        if (!$indicatorName) {
            json_out(['status' => 'error', 'message' => '指標名が指定されていません']);
            break;
        }
        $pdo    = get_pdo();
        $suffix = date('YmdHis') . '_' . getmypid();
        $tmpDir = sys_get_temp_dir();
        $tmpFiles = [];

        try {
            // ① バックテストサマリー CSV
            $btFile = "{$tmpDir}/bt_summary_{$suffix}.csv";
            $tmpFiles[] = $btFile;
            $fh = fopen($btFile, 'w');
            fwrite($fh, "\xEF\xBB\xBF");
            fputcsv($fh, ['通貨ペア', 'TF', '指標名', 'シグナル方向', '勝率(%)', 'PF',
                          'トレード数', '勝ち', '負け', '総損益(円)', 'SL(pips)', 'TP(pips)',
                          '最大DD(円)', '検証開始日', '検証終了日', '検証日時']);
            $stmt = $pdo->prepare(
                'SELECT currency_pair, timeframe, indicator_name, signal_direction,
                        win_rate, profit_factor, total_trades, winning_trades, losing_trades,
                        total_profit, sl_pips, tp_pips, max_drawdown,
                        start_date, end_date, calculated_at
                 FROM indicator_page_bt_results WHERE indicator_name = ?
                 ORDER BY currency_pair, timeframe'
            );
            $stmt->execute([$indicatorName]);
            while ($r = $stmt->fetch(PDO::FETCH_ASSOC)) { fputcsv($fh, array_values($r)); }
            fclose($fh);

            // ② シミュレーショントレード CSV（チャンク取得）
            $simFile = "{$tmpDir}/sim_trades_{$suffix}.csv";
            $tmpFiles[] = $simFile;
            $fh2 = fopen($simFile, 'w');
            fwrite($fh2, "\xEF\xBB\xBF");
            fputcsv($fh2, ['ID', '通貨ペア', 'TF', '指標名', 'エントリー日時(UTC)', 'エグジット日時(UTC)',
                           '方向', 'エントリー価格', 'エグジット価格', 'TP価格', 'SL価格',
                           'SL(pips)', 'TP(pips)', '結果', '損益(円)', '資金残高(円)']);
            $offset = 0; $chunk = 1000;
            $stmt2 = $pdo->prepare(
                'SELECT id, currency_pair, timeframe, indicator_name,
                        entry_at, exit_at, direction, entry_price,
                        exit_price, tp_price, sl_price, sl_pips, tp_pips,
                        outcome, profit_loss, capital_after
                 FROM indicator_page_sim_trades WHERE indicator_name = ?
                 ORDER BY entry_at LIMIT ? OFFSET ?'
            );
            do {
                $stmt2->bindValue(1, $indicatorName, PDO::PARAM_STR);
                $stmt2->bindValue(2, $chunk,         PDO::PARAM_INT);
                $stmt2->bindValue(3, $offset,        PDO::PARAM_INT);
                $stmt2->execute();
                $rows = $stmt2->fetchAll(PDO::FETCH_ASSOC);
                foreach ($rows as $t) {
                    fputcsv($fh2, [
                        $t['id'], $t['currency_pair'], $t['timeframe'], $t['indicator_name'],
                        $t['entry_at'], $t['exit_at'] ?? '', $t['direction'],
                        $t['entry_price'], $t['exit_price'] ?? '',
                        $t['tp_price'] ?? '', $t['sl_price'] ?? '',
                        $t['sl_pips'] ?? '', $t['tp_pips'] ?? '',
                        $t['outcome'] ?? '', $t['profit_loss'] ?? '', $t['capital_after'] ?? '',
                    ]);
                }
                $offset += $chunk;
            } while (count($rows) === $chunk);
            fclose($fh2);

            // ③ ZIP 作成・ダウンロード
            $zipFile = "{$tmpDir}/indicator_{$slug}_{$suffix}.zip";
            $zip = new ZipArchive();
            if ($zip->open($zipFile, ZipArchive::CREATE) !== true) {
                throw new Exception('ZIP ファイルの作成に失敗しました');
            }
            $zip->addFile($btFile,  "backtest_summary_{$slug}.csv");
            $zip->addFile($simFile, "simulation_trades_{$slug}.csv");
            $zip->close();
            foreach ($tmpFiles as $f) { @unlink($f); }

            $dlName = "{$indicatorName}_backtest_" . date('Ymd') . ".zip";
            header('Content-Type: application/zip');
            header('Content-Disposition: attachment; filename="' . $dlName . '"');
            header('Content-Length: ' . filesize($zipFile));
            header('Cache-Control: no-cache');
            readfile($zipFile);
            unlink($zipFile);
            exit;

        } catch (Exception $e) {
            foreach ($tmpFiles as $f) { @unlink($f); }
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    case 'ranking_csv':
        require_login();
        $tmpFiles = [];
        try {
            $pdo     = get_pdo();
            $pairs   = ['USDJPY', 'GBPJPY', 'EURJPY'];
            $tmpDir  = sys_get_temp_dir();
            $suffix  = date('YmdHis') . '_' . getmypid();

            // ---- ペアごとのシミュレーショントレードCSV（チャンク取得でメモリ節約）----
            foreach ($pairs as $pair) {
                $tmpFile   = "{$tmpDir}/sim_{$pair}_{$suffix}.csv";
                $tmpFiles[] = $tmpFile;
                $fh = fopen($tmpFile, 'w');
                fwrite($fh, "\xEF\xBB\xBF"); // UTF-8 BOM
                fputcsv($fh, ['ID','通貨ペア','TF','指標名','エントリー日時','エグジット日時',
                              '方向','エントリー価格','エグジット価格','TP価格','SL価格',
                              'SL_pips','TP_pips','結果','損益','資金残高']);

                $offset = 0;
                $chunk  = 1000;
                $stmt   = $pdo->prepare(
                    'SELECT id, currency_pair, timeframe, indicator_name,
                            entry_at, exit_at, direction, entry_price,
                            exit_price, tp_price, sl_price, sl_pips, tp_pips,
                            outcome, profit_loss, capital_after
                     FROM simulation_trades
                     WHERE currency_pair = ?
                     ORDER BY indicator_name, entry_at DESC
                     LIMIT ? OFFSET ?'
                );
                do {
                    $stmt->bindValue(1, $pair,   PDO::PARAM_STR);
                    $stmt->bindValue(2, $chunk,  PDO::PARAM_INT);
                    $stmt->bindValue(3, $offset, PDO::PARAM_INT);
                    $stmt->execute();
                    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
                    foreach ($rows as $t) {
                        fputcsv($fh, [
                            $t['id'], $t['currency_pair'], $t['timeframe'], $t['indicator_name'],
                            $t['entry_at'], $t['exit_at'] ?? '',
                            $t['direction'],
                            $t['entry_price'], $t['exit_price'] ?? '',
                            $t['tp_price'] ?? '', $t['sl_price'] ?? '',
                            $t['sl_pips'] ?? '', $t['tp_pips'] ?? '',
                            $t['outcome'] ?? '',
                            $t['profit_loss'] ?? '', $t['capital_after'] ?? '',
                        ]);
                    }
                    $offset += $chunk;
                } while (count($rows) === $chunk);
                fclose($fh);
                unset($rows);
            }

            // ---- バックテスト結果サマリーCSV ----
            $sumFile   = "{$tmpDir}/backtest_summary_{$suffix}.csv";
            $tmpFiles[] = $sumFile;
            $fh = fopen($sumFile, 'w');
            fwrite($fh, "\xEF\xBB\xBF");
            fputcsv($fh, ['通貨ペア','TF','指標名','勝率','PF','トレード数',
                          'SL_pips','TP_pips','最大ドローダウン']);
            $btStmt = $pdo->query(
                'SELECT currency_pair, timeframe, indicator_name,
                        win_rate, profit_factor, total_trades,
                        sl_pips, tp_pips, max_drawdown
                 FROM backtest_results ORDER BY currency_pair, timeframe, win_rate DESC'
            );
            while ($r = $btStmt->fetch(PDO::FETCH_ASSOC)) {
                fputcsv($fh, array_values($r));
            }
            fclose($fh);

            // ---- シグナルCSV ----
            $sigFile   = "{$tmpDir}/signals_{$suffix}.csv";
            $tmpFiles[] = $sigFile;
            $fh = fopen($sigFile, 'w');
            fwrite($fh, "\xEF\xBB\xBF");
            fputcsv($fh, ['ID','通貨ペア','TF','シグナル','指標名',
                          'エントリー価格','SL価格','TP価格','SL_pips','TP_pips',
                          '勝率','信頼度','アクティブ','シグナル日時']);
            $sigStmt = $pdo->query(
                'SELECT id, currency_pair, timeframe, signal_type, indicator_name,
                        entry_price, sl_price, tp_price, sl_pips, tp_pips,
                        win_rate, confidence_score, is_active, signal_time
                 FROM trading_signals ORDER BY signal_time DESC LIMIT 10000'
            );
            while ($s = $sigStmt->fetch(PDO::FETCH_ASSOC)) {
                $s['is_active'] = $s['is_active'] ? '1' : '0';
                fputcsv($fh, array_values($s));
            }
            fclose($fh);

            // ---- ZIP作成 ----
            $zipFile = "{$tmpDir}/ranking_data_{$suffix}.zip";
            $zip = new ZipArchive();
            if ($zip->open($zipFile, ZipArchive::CREATE) !== true) {
                throw new Exception('ZIPファイルの作成に失敗しました');
            }
            $zipNames = [
                "simulation_trades_USDJPY.csv",
                "simulation_trades_GBPJPY.csv",
                "simulation_trades_EURJPY.csv",
                "backtest_summary.csv",
                "signals.csv",
            ];
            foreach ($tmpFiles as $i => $f) {
                $zip->addFile($f, $zipNames[$i] ?? basename($f));
            }
            $zip->close();

            // 一時ファイルを削除
            foreach ($tmpFiles as $f) { @unlink($f); }

            // ---- ダウンロード ----
            $filename = 'ranking_bt_data_' . date('Ymd') . '.zip';
            header('Content-Type: application/zip');
            header('Content-Disposition: attachment; filename="' . $filename . '"');
            header('Content-Length: ' . filesize($zipFile));
            header('Cache-Control: no-cache');
            readfile($zipFile);
            unlink($zipFile);
            exit;

        } catch (Exception $e) {
            foreach ($tmpFiles as $f) { @unlink($f); }
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: 1件取得 ----
    case 'get_custom_indicator':
        require_login();
        try {
            $name = trim($body['name'] ?? '');
            if (!$name) { json_out(['status' => 'error', 'message' => 'name が必要です']); }
            $pdo  = get_pdo();
            $stmt = $pdo->prepare(
                "SELECT name, display_name, description, good_markets, bad_markets,
                        strategy_config, is_active
                 FROM custom_v2_indicators WHERE name = ? LIMIT 1"
            );
            $stmt->execute([$name]);
            $row = $stmt->fetch(PDO::FETCH_ASSOC);
            if (!$row) { json_out(['status' => 'not_found']); }
            // strategy_config は JSON文字列 or 配列どちらの場合もある
            if (is_string($row['strategy_config'])) {
                $row['strategy_config'] = json_decode($row['strategy_config'], true);
            }
            json_out(['status' => 'ok', 'indicator' => $row]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: 登録 ----
    case 'save_custom_indicator':
        require_login();
        try {
            $name         = trim($body['name']         ?? '');
            $display_name = trim($body['display_name'] ?? '');
            $description  = trim($body['description']  ?? '');
            $good_markets = $body['good_markets'] ?? '[]';
            $bad_markets  = $body['bad_markets']  ?? '[]';
            $strategy_cfg = $body['strategy_config'] ?? null;

            if (!$name || !$display_name || !$strategy_cfg) {
                json_out(['status' => 'error', 'message' => 'name / display_name / strategy_config は必須です']);
            }
            if (!preg_match('/^[A-Za-z0-9_]{1,80}$/', $name)) {
                json_out(['status' => 'error', 'message' => 'name は半角英数字・アンダースコアのみ (1-80文字)']);
            }
            if (!is_array($strategy_cfg)) {
                json_out(['status' => 'error', 'message' => 'strategy_config が不正です']);
            }

            $cfgJson  = json_encode($strategy_cfg, JSON_UNESCAPED_UNICODE);
            $goodJson = is_array($good_markets) ? json_encode($good_markets, JSON_UNESCAPED_UNICODE) : (string)$good_markets;
            $badJson  = is_array($bad_markets)  ? json_encode($bad_markets,  JSON_UNESCAPED_UNICODE) : (string)$bad_markets;

            $pdo  = get_pdo();
            $stmt = $pdo->prepare(
                "INSERT INTO custom_v2_indicators
                    (name, display_name, description, good_markets, bad_markets, strategy_config)
                 VALUES (?, ?, ?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                    display_name   = VALUES(display_name),
                    description    = VALUES(description),
                    good_markets   = VALUES(good_markets),
                    bad_markets    = VALUES(bad_markets),
                    strategy_config= VALUES(strategy_config),
                    is_active      = 1"
            );
            $stmt->execute([$name, $display_name, $description, $goodJson, $badJson, $cfgJson]);

            // バックグラウンドでバックテスト実行
            $py     = escapeshellarg(PYTHON_BIN);
            $script = escapeshellarg(TASKS_DIR . '/run_custom_indicator_bt.py');
            $nameEsc = escapeshellarg($name);
            exec("nohup {$py} {$script} --name {$nameEsc} >> /tmp/forex_custom_ind_bt.log 2>&1 &");

            json_out(['status' => 'ok', 'message' => '登録しました。バックテストをバックグラウンドで開始しました。']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: 設定保存のみ（BT再実行なし・ページ反映用）----
    case 'save_indicator_config_only':
        require_login();
        try {
            $name         = trim($body['name']         ?? '');
            $display_name = trim($body['display_name'] ?? '');
            $description  = trim($body['description']  ?? '');
            $good_markets = $body['good_markets'] ?? '[]';
            $bad_markets  = $body['bad_markets']  ?? '[]';
            $strategy_cfg = $body['strategy_config'] ?? null;

            if (!$name || !$display_name || !$strategy_cfg) {
                json_out(['status' => 'error', 'message' => 'name / display_name / strategy_config は必須です']);
            }
            if (!is_array($strategy_cfg)) {
                json_out(['status' => 'error', 'message' => 'strategy_config が不正です']);
            }

            $cfgJson  = json_encode($strategy_cfg, JSON_UNESCAPED_UNICODE);
            $goodJson = is_array($good_markets) ? json_encode($good_markets, JSON_UNESCAPED_UNICODE) : (string)$good_markets;
            $badJson  = is_array($bad_markets)  ? json_encode($bad_markets,  JSON_UNESCAPED_UNICODE) : (string)$bad_markets;

            $pdo  = get_pdo();
            $stmt = $pdo->prepare(
                "INSERT INTO custom_v2_indicators
                    (name, display_name, description, good_markets, bad_markets, strategy_config)
                 VALUES (?, ?, ?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                    display_name   = VALUES(display_name),
                    description    = VALUES(description),
                    good_markets   = VALUES(good_markets),
                    bad_markets    = VALUES(bad_markets),
                    strategy_config= VALUES(strategy_config),
                    is_active      = 1"
            );
            $stmt->execute([$name, $display_name, $description, $goodJson, $badJson, $cfgJson]);
            // BT は起動しない
            json_out(['status' => 'ok', 'message' => '設定を保存しました']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: 一覧取得 ----
    case 'list_custom_indicators':
        require_login();
        try {
            $pdo  = get_pdo();
            $rows = $pdo->query(
                "SELECT id, name, display_name, description, good_markets, bad_markets,
                        is_active, created_at
                 FROM custom_v2_indicators
                 ORDER BY created_at DESC"
            )->fetchAll(PDO::FETCH_ASSOC);
            json_out(['status' => 'ok', 'indicators' => $rows]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: 削除（soft delete） ----
    case 'delete_custom_indicator':
        require_login();
        try {
            $name = trim($body['name'] ?? '');
            if (!$name) { json_out(['status' => 'error', 'message' => 'name が必要です']); }
            $pdo  = get_pdo();
            $stmt = $pdo->prepare("UPDATE custom_v2_indicators SET is_active=0 WHERE name=?");
            $stmt->execute([$name]);
            json_out(['status' => 'ok', 'message' => '無効化しました']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: バックテスト再実行 ----
    case 'run_custom_indicator_bt':
        require_login();
        try {
            $name = trim($body['name'] ?? '');
            if (!$name) { json_out(['status' => 'error', 'message' => 'name が必要です']); }
            $py     = escapeshellarg(PYTHON_BIN);
            $script = escapeshellarg(TASKS_DIR . '/run_custom_indicator_bt.py');
            $nameEsc = escapeshellarg($name);
            exec("nohup {$py} {$script} --name {$nameEsc} >> /tmp/forex_custom_ind_bt.log 2>&1 &");
            json_out(['status' => 'ok', 'message' => 'バックテストを開始しました']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- マイグレーション: custom_v2_indicators テーブル作成 ----
    case 'migrate_custom_indicators':
        require_login();
        try {
            $pdo = get_pdo();
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS custom_v2_indicators (
                    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                    name            VARCHAR(80)  NOT NULL UNIQUE,
                    display_name    VARCHAR(120) NOT NULL,
                    description     TEXT,
                    good_markets    TEXT,
                    bad_markets     TEXT,
                    category        VARCHAR(30)  NOT NULL DEFAULT 'カスタム複合',
                    strategy_config JSON         NOT NULL,
                    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
                    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_custom_ind_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ");
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS quantflow_live_signals (
                    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    currency_pair  VARCHAR(10)   NOT NULL,
                    entry_ts       DATETIME      NOT NULL,
                    exit_ts        DATETIME      NULL,
                    direction      VARCHAR(4)    NOT NULL,
                    score_at_entry INT           NOT NULL,
                    entry_price    DECIMAL(12,5) NOT NULL,
                    exit_price     DECIMAL(12,5) NULL,
                    sl_price       DECIMAL(12,5) NOT NULL,
                    tp_price       DECIMAL(12,5) NOT NULL,
                    sl_pips        DECIMAL(8,2)  NOT NULL,
                    tp_pips        DECIMAL(8,2)  NOT NULL,
                    outcome        VARCHAR(4)    NULL,
                    profit_pips    DECIMAL(8,2)  NULL,
                    status         VARCHAR(8)    NOT NULL DEFAULT 'OPEN',
                    exit_reason    VARCHAR(16)   NULL,
                    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_qls_pair_status (currency_pair, status),
                    INDEX idx_qls_entry_ts    (entry_ts)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ");
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS quantflow_scores_5min (
                    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    currency_pair  VARCHAR(10)   NOT NULL,
                    `timestamp`    DATETIME      NOT NULL,
                    score          INT           NOT NULL,
                    trend_score    INT           DEFAULT NULL,
                    external_score INT           DEFAULT NULL,
                    close_price    DECIMAL(12,5) DEFAULT NULL,
                    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_qfs5_pair_ts (currency_pair, `timestamp`),
                    INDEX idx_qfs5_pair_ts (currency_pair, `timestamp`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ");
            json_out(['status' => 'ok', 'message' => 'テーブルを作成しました（既存の場合はスキップ）']);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    // ---- カスタム複合指標: スタブ作成（新規） ----
    case 'create_indicator_stub':
        require_login();
        $slug         = preg_replace('/[^a-z0-9_]/', '', strtolower(trim($body['slug'] ?? '')));
        $display_name = trim($body['display_name'] ?? '');
        if (!$slug || !$display_name) {
            json_out(['status' => 'error', 'message' => 'slug と display_name は必須です']);
        }
        if (strlen($slug) > 80) {
            json_out(['status' => 'error', 'message' => 'slug は 80文字以内にしてください']);
        }
        try {
            $pdo = get_pdo();
            $pdo->exec("CREATE TABLE IF NOT EXISTS custom_v2_indicators (
                id              BIGINT PRIMARY KEY AUTO_INCREMENT,
                name            VARCHAR(80)  NOT NULL UNIQUE,
                display_name    VARCHAR(120) NOT NULL,
                description     TEXT,
                good_markets    TEXT,
                bad_markets     TEXT,
                category        VARCHAR(30)  NOT NULL DEFAULT 'カスタム複合',
                strategy_config JSON         NOT NULL,
                is_active       TINYINT(1)   NOT NULL DEFAULT 1,
                created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_custom_ind_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
            $stmt = $pdo->prepare(
                "INSERT INTO custom_v2_indicators (name, display_name, strategy_config)
                 VALUES (?, ?, '{\"entry_conditions\":{\"logic\":\"AND\",\"conditions\":[]},\"direction\":\"BOTH\"}')
                 ON DUPLICATE KEY UPDATE display_name = VALUES(display_name)"
            );
            $stmt->execute([$slug, $display_name]);
            json_out(['status' => 'ok', 'slug' => $slug]);
        } catch (Exception $e) {
            json_out(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;

    default:
        json_out(['status' => 'error', 'message' => '不明なアクション: ' . htmlspecialchars($action)]);
}
