<?php
require_once __DIR__ . '/_user_config.php';

user_session_start();

$error   = '';
$success = false;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // CSRF
    if (!verify_csrf($_POST['csrf_token'] ?? '')) {
        $error = '不正なリクエストです。ページを再読み込みしてください。';
    } else {
        $email  = trim(strtolower($_POST['email'] ?? ''));
        $pass   = $_POST['password'] ?? '';
        $pass2  = $_POST['password_confirm'] ?? '';

        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            $error = '有効なメールアドレスを入力してください。';
        } elseif (strlen($pass) < 8) {
            $error = 'パスワードは8文字以上で入力してください。';
        } elseif ($pass !== $pass2) {
            $error = 'パスワードが一致しません。';
        } else {
            try {
                $pdo = get_pdo();
                // 重複チェック
                $s = $pdo->prepare('SELECT id FROM users WHERE email = ?');
                $s->execute([$email]);
                if ($s->fetch()) {
                    $error = 'このメールアドレスはすでに登録されています。';
                } else {
                    $hash  = password_hash($pass, PASSWORD_BCRYPT);
                    $token = bin2hex(random_bytes(32));
                    $exp   = date('Y-m-d H:i:s', time() + 86400);

                    $s = $pdo->prepare(
                        'INSERT INTO users (email, password_hash, verify_token, verify_token_expires)
                         VALUES (?, ?, ?, ?)'
                    );
                    $s->execute([$email, $hash, $token, $exp]);

                    send_verification_email($email, $token);
                    $success = true;
                }
            } catch (Exception $e) {
                error_log('[register.php] ' . $e->getMessage());
                $error = '登録処理に失敗しました。しばらく後でもう一度お試しください。';
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
  <title>会員登録 | AI×FX</title>
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
    /* ヘッダー */
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
    /* メイン */
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
    .success-box {
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-radius: 8px;
      padding: 16px 18px;
      font-size: 0.9rem;
      color: #166534;
      line-height: 1.7;
    }
    .success-box strong { font-size: 1rem; display: block; margin-bottom: 6px; }
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
    .terms {
      font-size: 0.78rem;
      color: #9ca3af;
      text-align: center;
      margin-top: 20px;
      line-height: 1.6;
    }
    .pass-hint {
      font-size: 0.75rem;
      color: #9ca3af;
      margin-top: 4px;
    }
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
    <h1>会員登録</h1>
    <p class="sub">メールアドレスで無料登録</p>

    <?php if ($success): ?>
      <div class="success-box">
        <strong><i class="bi bi-envelope-check"></i> 確認メールを送信しました</strong>
        ご登録のメールアドレスに確認メールを送りました。<br>
        メール内のリンクをクリックして登録を完了してください。<br><br>
        メールが届かない場合は迷惑メールフォルダをご確認ください。
      </div>
      <div class="divider">または</div>
      <a href="/" class="link-btn">トップページへ戻る</a>
    <?php else: ?>
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
                 placeholder="8文字以上" required autocomplete="new-password">
          <p class="pass-hint">半角英数字・記号を使用できます（8文字以上）</p>
        </div>

        <div class="form-group">
          <label for="password_confirm">パスワード（確認）</label>
          <input type="password" id="password_confirm" name="password_confirm"
                 placeholder="もう一度入力してください" required autocomplete="new-password">
        </div>

        <button type="submit" class="btn-submit">会員登録する</button>
      </form>

      <div class="divider">すでにアカウントをお持ちの方</div>
      <a href="/login.php" class="link-btn">ログインはこちら</a>

      <p class="terms">登録することで利用規約およびプライバシーポリシーに同意したものとみなします。</p>
    <?php endif; ?>
  </div>
</main>
</body>
</html>
