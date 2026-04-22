<?php
/**
 * 会員認証 共通設定
 * ファイル名先頭の _ はURL直接アクセスを防ぐため (.htaccess で制御)
 */

require_once __DIR__ . '/admin/_config.php';

// ---- セッション開始 ----
function user_session_start(): void {
    if (session_status() === PHP_SESSION_NONE) {
        session_set_cookie_params([
            'lifetime' => 86400 * 30,
            'path'     => '/',
            'secure'   => true,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        session_name('fx_user_sess');
        session_start();
    }
}

// ---- ログイン中ユーザー取得 (null = 未ログイン) ----
function get_logged_in_user(): ?array {
    user_session_start();
    if (empty($_SESSION['user_id'])) return null;
    try {
        $s = get_pdo()->prepare(
            'SELECT id, email, created_at FROM users WHERE id = ? AND email_verified = 1'
        );
        $s->execute([$_SESSION['user_id']]);
        return $s->fetch() ?: null;
    } catch (Exception $e) { return null; }
}

// ---- ログインを要求（未ログインならリダイレクト） ----
function require_user_login(string $redirect = '/login.php'): array {
    $u = get_logged_in_user();
    if (!$u) {
        header('Location: ' . $redirect);
        exit;
    }
    return $u;
}

// ---- ログイン処理（セッション＋JSから参照できる Cookie を設定） ----
function login_user(int $user_id, string $email): void {
    user_session_start();
    session_regenerate_id(true);
    $_SESSION['user_id'] = $user_id;
    // JS で読めるよう HttpOnly なし・同じドメイン
    setcookie('fx_auth_email', urlencode($email), [
        'expires'  => time() + 86400 * 30,
        'path'     => '/',
        'secure'   => true,
        'httponly' => false,
        'samesite' => 'Lax',
    ]);
}

// ---- ログアウト処理 ----
function logout_user(): void {
    user_session_start();
    $_SESSION = [];
    session_destroy();
    setcookie('fx_auth_email', '', ['expires' => time() - 3600, 'path' => '/']);
}

// ---- CSRF トークン生成・検証 ----
function csrf_token(): string {
    user_session_start();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function verify_csrf(string $token): bool {
    user_session_start();
    return !empty($_SESSION['csrf_token']) && hash_equals($_SESSION['csrf_token'], $token);
}

// ---- メール認証メール送信 ----
function send_verification_email(string $to, string $token): bool {
    $proto = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $base  = $proto . '://' . ($_SERVER['HTTP_HOST'] ?? 'kawase-ai.com');
    $link  = $base . '/verify-email.php?token=' . urlencode($token);

    $subject = '【AI×FX】メールアドレスの確認';
    $body    = implode("\n", [
        'AI×FX にご登録いただきありがとうございます。',
        '',
        '以下のリンクをクリックして、メールアドレスを確認してください。',
        '',
        $link,
        '',
        'このリンクは24時間有効です。',
        '',
        '──────────────────────────',
        'AI×FX  https://kawase-ai.com',
        '※このメールに心当たりがない場合は無視してください。',
    ]);

    $headers = implode("\r\n", [
        'From: AI×FX <noreply@kawase-ai.com>',
        'Content-Type: text/plain; charset=UTF-8',
    ]);

    $encoded_subject = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    return mail($to, $encoded_subject, $body, $headers);
}
