<?php
/**
 * アクションハンドラー
 * ボタン操作からPythonタスクをバックグラウンドで実行する
 */

header('Content-Type: application/json; charset=utf-8');

// POSTのみ受け付ける
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Method not allowed']);
    exit;
}

$action = isset($_POST['action']) ? trim($_POST['action']) : '';

$python  = '/home/xs539690/forex_env/bin/python3';
$runner  = '/home/xs539690/forex_project/forex_signal_tool/tasks/run_task.py';
$logDir  = '/home/xs539690/forex_project/logs';
$logFile = $logDir . '/action.log';

// 許可されたアクション
$allowed = ['fetch_data', 'backtest', 'signals', 'report', 'save_settings'];

if (!in_array($action, $allowed)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Unknown action: ' . htmlspecialchars($action)]);
    exit;
}

// 設定保存は同期処理
if ($action === 'save_settings') {
    $dataJson = isset($_POST['data']) ? $_POST['data'] : '{}';
    $decoded = json_decode($dataJson, true);
    if (!$decoded) {
        echo json_encode(['ok' => false, 'error' => 'Invalid JSON']);
        exit;
    }
    // Python で設定を保存してから settings_data.json も更新する
    $escaped = escapeshellarg($dataJson);
    $cmd = "$python $runner save_settings $escaped >> $logFile 2>&1";
    exec($cmd, $out, $ret);
    echo json_encode(['ok' => $ret === 0]);
    exit;
}

// 非同期タスク実行 (nohup でバックグラウンド)
$cmd = "nohup $python $runner " . escapeshellarg($action) . " >> $logFile 2>&1 &";
exec($cmd);

// すぐに OK を返す（タスクはバックグラウンドで実行中）
echo json_encode(['ok' => true, 'action' => $action]);
