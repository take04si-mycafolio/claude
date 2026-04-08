<?php
/**
 * 管理パネル 共通設定
 * ファイル名先頭の _ はURL直接アクセスを防ぐため (via .htaccess)
 */

// ---- .env 読み込み ----
$_home    = getenv('HOME') ?: '/home/xs539690';
$_envFile = "{$_home}/forex_project/.env";
if (file_exists($_envFile)) {
    foreach (file($_envFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        if ($line[0] === '#' || strpos($line, '=') === false) continue;
        [$k, $v] = explode('=', $line, 2);
        putenv(trim($k) . '=' . trim($v, " \t\n\r\"'"));
    }
}

// ---- 設定値 ----
define('ADMIN_PASSWORD', getenv('ADMIN_PASSWORD') ?: 'admin1234');
define('PYTHON_BIN',     "{$_home}/forex_env/bin/python3");
define('PROJECT_ROOT',   "{$_home}/forex_project/forex_signal_tool");
define('TASKS_DIR',      PROJECT_ROOT . '/tasks');

// ---- DB接続 (PDO) ----
function get_pdo(): PDO {
    static $pdo = null;
    if ($pdo) return $pdo;

    $url = getenv('DATABASE_URL') ?: 'mysql+pymysql://root:@localhost/forex_signal_db';
    preg_match('|://([^:]*):([^@]*)@([^/:]+)(?::\d+)?/([^?]+)|', $url, $m);
    $user = $m[1] ?? 'root';
    $pass = $m[2] ?? '';
    $host = $m[3] ?? 'localhost';
    $db   = $m[4] ?? 'forex_signal_db';

    $pdo = new PDO(
        "mysql:host={$host};dbname={$db};charset=utf8mb4",
        $user, $pass,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
         PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
    return $pdo;
}

// ---- Settings helper ----
function setting_get(string $key, string $default = ''): string {
    try {
        $s = get_pdo()->prepare('SELECT value FROM settings WHERE `key`=?');
        $s->execute([$key]);
        $row = $s->fetch();
        return $row ? $row['value'] : $default;
    } catch (Exception $e) { return $default; }
}

function setting_set(string $key, string $value): void {
    try {
        $s = get_pdo()->prepare(
            'INSERT INTO settings (`key`,value,updated_at) VALUES(?,?,NOW())
             ON DUPLICATE KEY UPDATE value=VALUES(value), updated_at=NOW()');
        $s->execute([$key, $value]);
    } catch (Exception $e) {}
}

// ---- 認証 ----
function require_login(): void {
    session_start();
    if (empty($_SESSION['admin_logged_in'])) {
        header('Location: /admin/');
        exit;
    }
}

function json_out(array $data): void {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}
