<?php
/**
 * 会員向け バックテスト API
 * GET  ?action=csv   → 直近結果を ZIP でダウンロード
 * POST ?action=run   → バックテスト実行（1日2回制限）
 */
require_once __DIR__ . '/_user_config.php';
require_once __DIR__ . '/admin/_config.php';   // get_pdo / PYTHON_BIN / TASKS_DIR

const BT_DAILY_LIMIT = 2;

$action = $_GET['action'] ?? ($body_raw = file_get_contents('php://input'), $tmp = json_decode($body_raw, true), $tmp['action'] ?? '');
$user   = get_logged_in_user();

if (!$user) {
    http_response_code(401);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => 'ログインが必要です']);
    exit;
}

// ---- ヘルパー ----
function member_json(array $data): void {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function get_today_log(int $user_id): array {
    try {
        $pdo = get_pdo();
        $pdo->exec("CREATE TABLE IF NOT EXISTS member_bt_log (
            id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id          BIGINT UNSIGNED NOT NULL,
            run_date         DATE            NOT NULL,
            run_count        INT             NOT NULL DEFAULT 0,
            last_result_json MEDIUMTEXT      NULL,
            last_run_at      DATETIME        NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uk_user_date (user_id, run_date),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

        $today = date('Y-m-d');
        $s = $pdo->prepare('SELECT run_count, last_result_json FROM member_bt_log WHERE user_id=? AND run_date=?');
        $s->execute([$user_id, $today]);
        return $s->fetch() ?: ['run_count' => 0, 'last_result_json' => null];
    } catch (Exception $e) {
        return ['run_count' => 0, 'last_result_json' => null];
    }
}

// ======================================================
// action=run
// ======================================================
if ($action === 'run') {
    $body = json_decode(file_get_contents('php://input'), true) ?? [];

    $log = get_today_log((int)$user['id']);
    if ((int)$log['run_count'] >= BT_DAILY_LIMIT) {
        member_json(['ok' => false, 'error' => '本日の実行回数（' . BT_DAILY_LIMIT . '回）に達しました。明日またお試しください。', 'limit_reached' => true]);
    }

    // パラメータバリデーション
    $allowed_pairs = ['USDJPY', 'GBPJPY', 'EURJPY'];
    $allowed_tfs   = ['5min', '15min', '30min', '1hr', '4hr', 'daily'];
    $allowed_dirs  = ['BUY', 'SELL', 'BOTH'];

    $pairs    = array_values(array_filter((array)($body['pairs'] ?? ['USDJPY']),    fn($p) => in_array($p, $allowed_pairs)));
    $tfs      = array_values(array_filter((array)($body['timeframes'] ?? ['1hr']),  fn($t) => in_array($t, $allowed_tfs)));
    $dir      = in_array($body['direction'] ?? 'BOTH', $allowed_dirs) ? $body['direction'] : 'BOTH';
    $strategy = $body['strategy_config'] ?? null;

    if (!$pairs || !$tfs || !$strategy) {
        member_json(['ok' => false, 'error' => '通貨ペア・時間軸・ストラテジー設定が必要です']);
    }
    if (($strategy['strategy_version'] ?? '') !== '1.0') {
        member_json(['ok' => false, 'error' => 'strategy_version は "1.0" にしてください']);
    }

    // バックテスト実行（ペア×TF の組み合わせ）
    $all_results  = [];
    $total_trades = 0;
    $py     = escapeshellarg(PYTHON_BIN);
    $script = escapeshellarg(TASKS_DIR . '/run_backtest_v2.py');

    foreach ($pairs as $pair) {
        foreach ($tfs as $tf) {
            $params = [
                'pair'            => $pair,
                'timeframe'       => $tf,
                'limit'           => (int)min((int)($body['limit'] ?? 500), 1000),
                'start_date'      => $body['start_date'] ?? null,
                'end_date'        => $body['end_date']   ?? null,
                'strategy_config' => $strategy,
                'sim_params'      => $body['sim_params'] ?? [],
            ];
            $pfile = '/tmp/forex_bt_v2_member_' . (int)$user['id'] . '.json';
            file_put_contents($pfile, json_encode($params, JSON_UNESCAPED_UNICODE));

            exec("{$py} {$script} " . escapeshellarg($pfile) . " 2>&1", $lines, $ret);
            $raw    = implode('', $lines);
            $result = json_decode($raw, true);

            if ($result && ($result['ok'] ?? false)) {
                $key = $pair . '_' . $tf;
                $all_results[$key] = $result;
                $total_trades += (int)(($result['metrics']['total_trades'] ?? 0));
            }
        }
    }

    if (!$all_results) {
        member_json(['ok' => false, 'error' => 'バックテストの実行に失敗しました。条件設定を確認してください。']);
    }

    $result_to_save = ['results' => $all_results, 'direction' => $dir, 'run_at' => date('Y-m-d H:i:s')];

    // 使用カウント更新・結果保存
    try {
        $pdo   = get_pdo();
        $today = date('Y-m-d');
        $pdo->prepare(
            "INSERT INTO member_bt_log (user_id, run_date, run_count, last_result_json, last_run_at)
             VALUES (?, ?, 1, ?, NOW())
             ON DUPLICATE KEY UPDATE
               run_count        = run_count + 1,
               last_result_json = VALUES(last_result_json),
               last_run_at      = NOW()"
        )->execute([$user['id'], $today, json_encode($result_to_save, JSON_UNESCAPED_UNICODE)]);
    } catch (Exception $e) {
        error_log('[member-api] log save error: ' . $e->getMessage());
    }

    $new_count = (int)$log['run_count'] + 1;
    member_json([
        'ok'        => true,
        'results'   => $all_results,
        'direction' => $dir,
        'used_today'=> $new_count,
        'remaining' => max(0, BT_DAILY_LIMIT - $new_count),
    ]);
}

// ======================================================
// action=csv
// ======================================================
if ($action === 'csv') {
    $log = get_today_log((int)$user['id']);
    if (!$log['last_result_json']) {
        http_response_code(400);
        echo 'バックテスト結果がありません。先に実行してください。';
        exit;
    }

    $saved    = json_decode($log['last_result_json'], true) ?? [];
    $results  = $saved['results'] ?? [];
    $suffix   = date('YmdHis');
    $tmpDir   = sys_get_temp_dir();
    $tmpFiles = [];

    // ① サマリーCSV
    $sumFile    = "{$tmpDir}/bt_summary_{$suffix}.csv";
    $tmpFiles[] = $sumFile;
    $fh = fopen($sumFile, 'w');
    fwrite($fh, "\xEF\xBB\xBF");
    fputcsv($fh, ['通貨ペア','TF','トレード数','勝率(%)','PF','純損益(pips)','最大DD(pips)','期待値(pips)']);
    foreach ($results as $key => $r) {
        $m    = $r['metrics'] ?? [];
        $parts = explode('_', $key, 2);
        fputcsv($fh, [
            $parts[0], $parts[1] ?? '',
            $m['total_trades']    ?? '',
            isset($m['win_rate'])        ? round($m['win_rate'] * 100, 1) : '',
            isset($m['profit_factor'])   ? round($m['profit_factor'], 3)  : '',
            $m['net_profit_pips'] ?? '',
            $m['max_drawdown_pips'] ?? '',
            isset($m['expectancy_pips']) ? round($m['expectancy_pips'], 2) : '',
        ]);
    }
    fclose($fh);

    // ② トレード明細CSV
    $tradeFile  = "{$tmpDir}/bt_trades_{$suffix}.csv";
    $tmpFiles[] = $tradeFile;
    $fh2 = fopen($tradeFile, 'w');
    fwrite($fh2, "\xEF\xBB\xBF");
    fputcsv($fh2, ['通貨ペア','TF','エントリー日時(JST)','エグジット日時(JST)','方向','損益(pips)','損益(円)','終了理由']);
    foreach ($results as $key => $r) {
        $parts = explode('_', $key, 2);
        foreach ($r['trades'] ?? [] as $t) {
            fputcsv($fh2, [
                $parts[0], $parts[1] ?? '',
                $t['entry_time']  ?? '',
                $t['exit_time']   ?? '',
                $t['direction']   ?? '',
                isset($t['pnl_pips'])  ? round($t['pnl_pips'], 2) : '',
                isset($t['pnl'])       ? round($t['pnl'])         : '',
                $t['exit_reason'] ?? '',
            ]);
        }
    }
    fclose($fh2);

    // ZIP 圧縮
    $zipFile = "{$tmpDir}/bt_result_{$suffix}.zip";
    $zip = new ZipArchive();
    if ($zip->open($zipFile, ZipArchive::CREATE) === true) {
        $zip->addFile($sumFile,   'summary.csv');
        $zip->addFile($tradeFile, 'trades.csv');
        $zip->close();
        header('Content-Type: application/zip');
        header('Content-Disposition: attachment; filename="backtest_' . date('Ymd') . '.zip"');
        header('Content-Length: ' . filesize($zipFile));
        readfile($zipFile);
        foreach (array_merge($tmpFiles, [$zipFile]) as $f) { @unlink($f); }
    } else {
        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="bt_summary_' . date('Ymd') . '.csv"');
        readfile($sumFile);
        foreach ($tmpFiles as $f) { @unlink($f); }
    }
    exit;
}

member_json(['ok' => false, 'error' => '無効なアクション']);
