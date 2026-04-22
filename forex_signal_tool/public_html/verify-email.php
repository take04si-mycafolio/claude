<?php
require_once __DIR__ . '/_user_config.php';

$token   = trim($_GET['token'] ?? '');
$success = false;
$error   = '';

if ($token === '') {
    $error = 'トークンが無効です。';
} else {
    try {
        $pdo = get_pdo();
        $s   = $pdo->prepare(
            'SELECT id FROM users
             WHERE verify_token = ? AND verify_token_expires > NOW() AND email_verified = 0'
        );
        $s->execute([$token]);
        $user = $s->fetch();

        if (!$user) {
            $error = 'このリンクは無効または期限切れです。再度登録を行ってください。';
        } else {
            $pdo->prepare(
                'UPDATE users SET email_verified = 1, verify_token = NULL, verify_token_expires = NULL WHERE id = ?'
            )->execute([$user['id']]);
            $success = true;
        }
    } catch (Exception $e) {
        $error = '処理に失敗しました。しばらく後でもう一度お試しください。';
    }
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>メール認証 | AI×FX</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <?php if ($success): ?>
  <meta http-equiv="refresh" content="4;url=/login.php">
  <?php endif; ?>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Noto Sans JP', 'Helvetica Neue', sans-serif;
      background: #f0f2f5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .app-header {
      background: #1a1a2e;
      height: 56px;
      display: flex;
      align-items: center;
      padding: 0 20px;
    }
    .header-logo {
      color: #fff;
      font-size: 1.1rem;
      font-weight: 700;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .header-logo i { color: #c9ff3b; }
    main {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px 16px;
    }
    .auth-card {
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 2px 20px rgba(0,0,0,0.08);
      padding: 40px 32px;
      width: 100%;
      max-width: 420px;
      text-align: center;
    }
    .icon-circle {
      width: 72px; height: 72px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 2rem;
      margin: 0 auto 24px;
    }
    .icon-circle.ok { background: #f0fdf4; color: #22c55e; }
    .icon-circle.ng { background: #fef2f2; color: #ef4444; }
    h1 { font-size: 1.3rem; font-weight: 700; color: #1a1a2e; margin-bottom: 12px; }
    p { font-size: 0.9rem; color: #6b7280; line-height: 1.7; }
    .btn {
      display: inline-block;
      margin-top: 28px;
      padding: 12px 32px;
      background: #1a1a2e;
      color: #c9ff3b;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 700;
      font-size: 0.95rem;
    }
    .hint { font-size: 0.8rem; color: #9ca3af; margin-top: 12px; }
  </style>
</head>
<body>
<header class="app-header">
  <a href="/" class="header-logo">
    <i class="bi bi-graph-up-arrow"></i>
    <span>AI×FX</span>
  </a>
</header>

<main>
  <div class="auth-card">
    <?php if ($success): ?>
      <div class="icon-circle ok"><i class="bi bi-check-lg"></i></div>
      <h1>メール認証が完了しました</h1>
      <p>AI×FX の会員登録が完了しました。<br>4秒後にログインページへ移動します。</p>
      <a href="/login.php" class="btn">ログインする</a>
    <?php else: ?>
      <div class="icon-circle ng"><i class="bi bi-x-lg"></i></div>
      <h1>認証リンクが無効です</h1>
      <p><?= htmlspecialchars($error) ?></p>
      <a href="/register.php" class="btn">再度登録する</a>
    <?php endif; ?>
  </div>
</main>
</body>
</html>
