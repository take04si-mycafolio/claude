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
$email_short = strlen($user['email']) > 20 ? substr($user['email'], 0, 18) . '…' : $user['email'];
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

    /* ヘッダー */
    .app-header {
      background: #1a1a2e;
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .header-inner {
      width: 100%;
      max-width: 480px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .header-logo {
      color: #fff;
      font-size: 1.05rem;
      font-weight: 700;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .header-logo i { color: #c9ff3b; }

    /* ドロップダウン */
    .dropdown { position: relative; }
    .dropdown-trigger {
      display: flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 8px;
      padding: 6px 12px;
      color: #e2e8f0;
      font-size: 0.78rem;
      cursor: pointer;
      transition: background .15s;
    }
    .dropdown-trigger:hover { background: rgba(255,255,255,0.14); }
    .dropdown-trigger i.bi-person-circle { font-size: 1rem; color: #c9ff3b; }
    .dropdown-trigger i.bi-chevron-down { font-size: 0.65rem; color: #94a3b8; transition: transform .2s; }
    .dropdown.open .dropdown-trigger i.bi-chevron-down { transform: rotate(180deg); }

    .dropdown-menu {
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
      min-width: 220px;
      z-index: 100;
      overflow: hidden;
    }
    .dropdown.open .dropdown-menu { display: block; }

    .dropdown-header {
      padding: 12px 16px 10px;
      background: #f9fafb;
      border-bottom: 1px solid #f3f4f6;
    }
    .dropdown-header .label { font-size: 10px; color: #9ca3af; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 2px; }
    .dropdown-header .email { font-size: 0.82rem; color: #374151; font-weight: 600; word-break: break-all; }

    .dropdown-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 11px 16px;
      font-size: 0.85rem;
      color: #374151;
      text-decoration: none;
      cursor: pointer;
      transition: background .12s;
      border: none;
      background: none;
      width: 100%;
      text-align: left;
    }
    .dropdown-item:hover { background: #f3f4f6; }
    .dropdown-item i { font-size: 1rem; color: #6b7280; }
    .dropdown-divider { border: none; border-top: 1px solid #f3f4f6; margin: 0; }
    .dropdown-item.danger { color: #dc2626; }
    .dropdown-item.danger i { color: #dc2626; }
    .dropdown-item.danger:hover { background: #fef2f2; }

    /* メイン */
    main {
      flex: 1;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 32px 16px 40px;
    }
    .card {
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 2px 20px rgba(0,0,0,0.08);
      padding: 32px 28px;
      width: 100%;
      max-width: 480px;
    }

    /* カード内 */
    .section-label {
      font-size: 11px;
      font-weight: 700;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: .06em;
      margin-bottom: 12px;
    }
    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 13px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 0.88rem;
    }
    .info-row:last-of-type { border-bottom: none; }
    .info-row .key { color: #6b7280; }
    .info-row .val { font-weight: 600; color: #1a1a2e; word-break: break-all; text-align: right; max-width: 60%; }
    .badge-verified {
      display: inline-flex; align-items: center; gap: 4px;
      background: #f0fdf4; color: #16a34a;
      font-size: 0.75rem; font-weight: 600;
      padding: 3px 10px; border-radius: 99px;
    }

    .divider-line { border: none; border-top: 1px solid #f3f4f6; margin: 24px 0 20px; }

    .btn-action {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: opacity .15s;
      margin-top: 10px;
    }
    .btn-action:hover { opacity: .85; }
    .btn-backtest { background: #172554; color: #93c5fd; }
    .btn-delete   { background: transparent; color: #dc2626; border: 1.5px solid #fca5a5; }
    .btn-delete:hover { background: #fef2f2; border-color: #dc2626; opacity: 1; }

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
      background: #fff; border-radius: 16px; padding: 32px 28px;
      width: 90%; max-width: 340px; text-align: center;
    }
    .modal-box h2 { font-size: 1.05rem; color: #1a1a2e; margin-bottom: 10px; }
    .modal-box p  { font-size: 0.83rem; color: #6b7280; line-height: 1.7; margin-bottom: 24px; }
    .modal-btns   { display: flex; gap: 10px; }
    .modal-btns button { flex: 1; padding: 11px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; cursor: pointer; border: none; }
    .modal-cancel  { background: #f3f4f6; color: #374151; }
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
  <div class="header-inner">
    <a href="/" class="header-logo">
      <i class="bi bi-graph-up-arrow"></i>
      <span>AI×FX</span>
    </a>

    <div class="dropdown" id="userDropdown">
      <button type="button" class="dropdown-trigger" onclick="toggleDropdown()">
        <i class="bi bi-person-circle"></i>
        <span><?= htmlspecialchars($email_short) ?></span>
        <i class="bi bi-chevron-down"></i>
      </button>
      <div class="dropdown-menu">
        <div class="dropdown-header">
          <div class="label">ログイン中</div>
          <div class="email"><?= htmlspecialchars($user['email']) ?></div>
        </div>
        <a href="/mypage.php" class="dropdown-item">
          <i class="bi bi-gear"></i> 会員設定
        </a>
        <hr class="dropdown-divider">
        <a href="/logout.php" class="dropdown-item danger">
          <i class="bi bi-box-arrow-right"></i> ログアウト
        </a>
      </div>
    </div>
  </div>
</header>

<main>
  <div class="card">
    <p class="section-label">会員設定</p>

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

    <a href="/backtest.php" class="btn-action btn-backtest">
      <i class="bi bi-bar-chart-steps"></i> バックテストを使う
    </a>

    <hr class="divider-line">

    <button type="button" class="btn-action btn-delete"
            onclick="document.getElementById('deleteModal').classList.add('open')">
      <i class="bi bi-person-x"></i> 会員を解除する
    </button>
    <?php if ($delete_error): ?>
      <div class="error-box"><?= htmlspecialchars($delete_error) ?></div>
    <?php endif; ?>
  </div>
</main>

<footer style="text-align:center;font-size:12px;color:#9ca3af;padding:16px 16px 24px">
  <a href="/terms.php" style="color:#9ca3af;text-decoration:none">利用規約</a><span style="margin:0 3px">｜</span><a href="/privacy.php" style="color:#9ca3af;text-decoration:none">プライバシーポリシー</a><span style="margin:0 3px">｜</span><a href="/contact.php" style="color:#9ca3af;text-decoration:none">お問い合わせ</a>
</footer>

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

<script>
function toggleDropdown() {
  document.getElementById('userDropdown').classList.toggle('open');
}
document.addEventListener('click', function(e) {
  const d = document.getElementById('userDropdown');
  if (!d.contains(e.target)) d.classList.remove('open');
});
</script>
</body>
</html>
