<?php
require_once __DIR__ . '/_user_config.php';

user_session_start();

// すでにログイン済みならマイページへ
if (get_logged_in_user()) {
    header('Location: /mypage.php');
    exit;
}

$error    = '';
$redirect = $_GET['redirect'] ?? '/mypage.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!verify_csrf($_POST['csrf_token'] ?? '')) {
        $error = '不正なリクエストです。ページを再読み込みしてください。';
    } else {
        $email = trim(strtolower($_POST['email'] ?? ''));
        $pass  = $_POST['password'] ?? '';

        if ($email === '' || $pass === '') {
            $error = 'メールアドレスとパスワードを入力してください。';
        } else {
            try {
                $s = get_pdo()->prepare(
                    'SELECT id, email, password_hash, email_verified FROM users WHERE email = ?'
                );
                $s->execute([$email]);
                $user = $s->fetch();

                if (!$user || !password_verify($pass, $user['password_hash'])) {
                    $error = 'メールアドレスまたはパスワードが正しくありません。';
                } elseif (!$user['email_verified']) {
                    $error = 'メールアドレスの確認が完了していません。登録時に送ったメールのリンクをクリックしてください。';
                } else {
                    login_user((int)$user['id'], $user['email']);
                    $safe_redirect = filter_var($redirect, FILTER_VALIDATE_URL) ? '/mypage.php' : $redirect;
                    header('Location: ' . $safe_redirect);
                    exit;
                }
            } catch (Exception $e) {
                $error = 'ログイン処理に失敗しました。しばらく後でもう一度お試しください。';
            }
        }
    }
}

$csrf = csrf_token();
?>
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ログイン | AI×FX</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
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
    }
    .auth-card h1 {
      font-size: 1.4rem;
      font-weight: 700;
      color: #1a1a2e;
      margin-bottom: 8px;
    }
    .auth-card .sub {
      font-size: 0.85rem;
      color: #6b7280;
      margin-bottom: 32px;
    }
    .form-group { margin-bottom: 20px; }
    label {
      display: block;
      font-size: 0.82rem;
      font-weight: 600;
      color: #374151;
      margin-bottom: 6px;
    }
    input[type="email"],
    input[type="password"] {
      width: 100%;
      padding: 11px 14px;
      border: 1.5px solid #d1d5db;
      border-radius: 8px;
      font-size: 0.95rem;
      color: #111;
      outline: none;
      transition: border-color .15s;
    }
    input:focus { border-color: #1a1a2e; }
    .btn-submit {
      width: 100%;
      padding: 13px;
      background: #1a1a2e;
      color: #c9ff3b;
      border: none;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      margin-top: 8px;
      transition: opacity .15s;
    }
    .btn-submit:hover { opacity: .85; }
    .error-box {
      background: #fef2f2;
      border: 1px solid #fca5a5;
      border-radius: 8px;
      padding: 12px 14px;
      font-size: 0.85rem;
      color: #dc2626;
      margin-bottom: 20px;
    }
    .divider {
      text-align: center;
      font-size: 0.82rem;
      color: #9ca3af;
      margin: 24px 0 16px;
    }
    .link-btn {
      display: block;
      text-align: center;
      font-size: 0.88rem;
      color: #1a1a2e;
      text-decoration: none;
      font-weight: 600;
    }
    .link-btn:hover { text-decoration: underline; }
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
    <h1>ログイン</h1>
    <p class="sub">AI×FX 会員アカウントでログイン</p>

    <?php if ($error): ?>
      <div class="error-box"><i class="bi bi-exclamation-circle"></i> <?= htmlspecialchars($error) ?></div>
    <?php endif; ?>

    <form method="post" novalidate>
      <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf) ?>">

      <div class="form-group">
        <label for="email">メールアドレス</label>
        <input type="email" id="email" name="email"
               value="<?= htmlspecialchars($_POST['email'] ?? '') ?>"
               placeholder="example@email.com" required autocomplete="email">
      </div>

      <div class="form-group">
        <label for="password">パスワード</label>
        <input type="password" id="password" name="password"
               placeholder="パスワード" required autocomplete="current-password">
      </div>

      <button type="submit" class="btn-submit">ログイン</button>
    </form>

    <div class="divider">アカウントをお持ちでない方</div>
    <a href="/register.php" class="link-btn">無料会員登録はこちら</a>
  </div>
</main>
</body>
</html>
