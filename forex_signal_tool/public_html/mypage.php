<?php
require_once __DIR__ . '/_user_config.php';
$user = require_user_login('/login.php');
$joined = date('Y年n月j日', strtotime($user['created_at']));
?>
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>マイページ | AI×FX</title>
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
      justify-content: space-between;
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
    .header-logout {
      font-size: 0.8rem;
      color: #94a3b8;
      text-decoration: none;
    }
    .header-logout:hover { color: #fff; }
    main {
      flex: 1;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 40px 16px;
    }
    .card {
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 2px 20px rgba(0,0,0,0.08);
      padding: 40px 32px;
      width: 100%;
      max-width: 480px;
    }
    .avatar {
      width: 64px; height: 64px;
      border-radius: 50%;
      background: #1a1a2e;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.8rem;
      color: #c9ff3b;
      margin-bottom: 20px;
    }
    h1 { font-size: 1.3rem; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
    .email { font-size: 0.88rem; color: #6b7280; margin-bottom: 28px; }
    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 0.9rem;
    }
    .info-row:last-of-type { border-bottom: none; }
    .info-row .key { color: #6b7280; }
    .info-row .val { font-weight: 600; color: #1a1a2e; }
    .badge-verified {
      display: inline-flex; align-items: center; gap: 4px;
      background: #f0fdf4; color: #16a34a;
      font-size: 0.78rem; font-weight: 600;
      padding: 3px 10px;
      border-radius: 99px;
    }
    .btn-logout {
      display: block;
      width: 100%;
      margin-top: 32px;
      padding: 12px;
      background: #f3f4f6;
      color: #374151;
      border: none;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
      transition: background .15s;
    }
    .btn-logout:hover { background: #e5e7eb; }
    .back-link {
      display: block;
      text-align: center;
      margin-top: 16px;
      font-size: 0.85rem;
      color: #6b7280;
      text-decoration: none;
    }
    .back-link:hover { color: #1a1a2e; }
  </style>
</head>
<body>
<header class="app-header">
  <a href="/" class="header-logo">
    <i class="bi bi-graph-up-arrow"></i>
    <span>AI×FX</span>
  </a>
  <a href="/logout.php" class="header-logout">ログアウト</a>
</header>

<main>
  <div class="card">
    <div class="avatar"><i class="bi bi-person-fill"></i></div>
    <h1>マイページ</h1>
    <p class="email"><?= htmlspecialchars($user['email']) ?></p>

    <div class="info-row">
      <span class="key">メールアドレス</span>
      <span class="val"><?= htmlspecialchars($user['email']) ?></span>
    </div>
    <div class="info-row">
      <span class="key">認証状態</span>
      <span class="badge-verified"><i class="bi bi-check-circle-fill"></i> 認証済み</span>
    </div>
    <div class="info-row">
      <span class="key">登録日</span>
      <span class="val"><?= $joined ?></span>
    </div>

    <a href="/logout.php" class="btn-logout">
      <i class="bi bi-box-arrow-right"></i> ログアウト
    </a>
    <a href="/" class="back-link">← トップページへ戻る</a>
  </div>
</main>
</body>
</html>
