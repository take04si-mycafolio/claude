<?php
require_once __DIR__ . '/_user_config.php';
$user = require_user_login('/login.php');
$joined = date('Y年n月j日', strtotime($user['created_at']));

// 会員解除処理
$delete_error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'delete') {
    if (!verify_csrf($_POST['csrf_token'] ?? '')) {
        $delete_error = '不正なリクエストです。';
    } else {
        try {
            get_pdo()->prepare('DELETE FROM users WHERE id = ?')->execute([$user['id']]);
            logout_user();
            header('Location: /?withdrawn=1');
            exit;
        } catch (Exception $e) {
            error_log('[mypage.php] delete error: ' . $e->getMessage());
            $delete_error = '処理に失敗しました。しばらく後でお試しください。';
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
      max-width: 910px;
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
    .divider-line {
      border: none; border-top: 1px solid #f3f4f6;
      margin: 28px 0 20px;
    }
    .btn-delete {
      display: block;
      width: 100%;
      padding: 11px;
      background: transparent;
      color: #dc2626;
      border: 1.5px solid #fca5a5;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
      transition: background .15s, border-color .15s;
    }
    .btn-delete:hover { background: #fef2f2; border-color: #dc2626; }
    /* 確認モーダル */
    .modal-overlay {
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.5);
      z-index: 200;
      align-items: center; justify-content: center;
    }
    .modal-overlay.open { display: flex; }
    .modal-box {
      background: #fff;
      border-radius: 16px;
      padding: 32px 28px;
      width: 90%; max-width: 360px;
      text-align: center;
    }
    .modal-box h2 { font-size: 1.1rem; color: #1a1a2e; margin-bottom: 10px; }
    .modal-box p { font-size: 0.85rem; color: #6b7280; line-height: 1.7; margin-bottom: 24px; }
    .modal-btns { display: flex; gap: 12px; }
    .modal-btns button {
      flex: 1; padding: 11px;
      border-radius: 8px; font-size: 0.9rem; font-weight: 600;
      cursor: pointer; border: none;
    }
    .modal-cancel { background: #f3f4f6; color: #374151; }
    .modal-cancel:hover { background: #e5e7eb; }
    .modal-confirm { background: #dc2626; color: #fff; }
    .modal-confirm:hover { background: #b91c1c; }
    .error-box {
      background: #fef2f2; border: 1px solid #fca5a5;
      border-radius: 8px; padding: 10px 14px;
      font-size: 0.82rem; color: #dc2626; margin-top: 12px;
    }
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

    <hr class="divider-line">
    <button type="button" class="btn-delete" onclick="document.getElementById('deleteModal').classList.add('open')">
      <i class="bi bi-person-x"></i> 会員を解除する
    </button>
    <?php if ($delete_error): ?>
      <div class="error-box"><?= htmlspecialchars($delete_error) ?></div>
    <?php endif; ?>
  </div>
</main>

<!-- 退会確認モーダル -->
<div class="modal-overlay" id="deleteModal">
  <div class="modal-box">
    <h2><i class="bi bi-exclamation-triangle" style="color:#dc2626"></i> 会員解除の確認</h2>
    <p>退会するとアカウントのデータはすべて削除されます。<br>本当に解除しますか？</p>
    <div class="modal-btns">
      <button type="button" class="modal-cancel"
              onclick="document.getElementById('deleteModal').classList.remove('open')">
        キャンセル
      </button>
      <form method="post" style="flex:1">
        <input type="hidden" name="action" value="delete">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf) ?>">
        <button type="submit" class="modal-confirm" style="width:100%">退会する</button>
      </form>
    </div>
  </div>
</div>
</body>
</html>
