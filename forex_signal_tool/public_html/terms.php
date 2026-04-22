<?php
require_once __DIR__ . '/admin/_config.php';

$content    = '';
$updated_at = '';
try {
    $row = get_pdo()->prepare(
        'SELECT content_value, updated_at FROM site_content WHERE content_key = ?'
    );
    $row->execute(['terms_content']);
    $data = $row->fetch();
    if ($data) {
        $content    = $data['content_value'];
        $updated_at = $data['updated_at']
            ? date('Y年n月j日', strtotime($data['updated_at'])) : '';
    }
} catch (Exception $e) {}

if ($content === '') {
    $content = '<p>利用規約は現在準備中です。</p>';
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>利用規約 | AI×FX</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <link rel="stylesheet" href="/static/css/style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    .policy-wrap {
      max-width: 720px;
      margin: 0 auto;
      padding: 32px 16px 80px;
    }
    .policy-header {
      margin-bottom: 28px;
    }
    .policy-header h1 {
      font-size: 1.5rem;
      font-weight: 700;
      color: #1a1a2e;
      margin-bottom: 6px;
    }
    .policy-header .meta {
      font-size: 0.82rem;
      color: #9ca3af;
    }
    .policy-body {
      background: #fff;
      border-radius: 12px;
      padding: 28px 24px;
      font-size: 0.92rem;
      line-height: 1.9;
      color: #374151;
    }
    .policy-body h2 { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin: 24px 0 10px; }
    .policy-body h3 { font-size: 0.95rem; font-weight: 700; color: #1a1a2e; margin: 18px 0 8px; }
    .policy-body p  { margin-bottom: 12px; }
    .policy-body ul, .policy-body ol { padding-left: 1.5em; margin-bottom: 12px; }
    .policy-body li { margin-bottom: 6px; }
    .breadcrumb-nav {
      font-size: 0.8rem;
      color: #9ca3af;
      margin-bottom: 20px;
    }
    .breadcrumb-nav a { color: #6b7280; text-decoration: none; }
    .breadcrumb-nav a:hover { color: #1a1a2e; }
  </style>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-T57Y35NV5F"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-T57Y35NV5F');</script>
</head>
<body>

<header class="app-header">
  <div class="header-inner">
    <div class="header-logo">
      <a href="/" style="display:flex;align-items:center;gap:6px;color:inherit;text-decoration:none">
        <i class="bi bi-graph-up-arrow"></i>
        <span>AI×FX</span>
      </a>
    </div>
    <a href="/register.php" id="header-auth-btn" class="header-auth-btn">会員登録する</a>
  </div>
</header>

<main class="app-main">
  <div class="policy-wrap">
    <nav class="breadcrumb-nav">
      <a href="/">ホーム</a> &rsaquo; 利用規約
    </nav>
    <div class="policy-header">
      <h1>利用規約</h1>
      <?php if ($updated_at): ?>
      <p class="meta">最終更新: <?= htmlspecialchars($updated_at) ?></p>
      <?php endif; ?>
    </div>
    <div class="policy-body">
      <?= $content ?>
    </div>
  </div>
</main>
<footer style="text-align:center;font-size:12px;color:#9ca3af;padding:12px 16px 16px">
  <a href="/terms.php" style="color:#9ca3af;text-decoration:none">利用規約</a><span style="margin:0 3px">｜</span><a href="/privacy.php" style="color:#9ca3af;text-decoration:none">プライバシーポリシー</a><span style="margin:0 3px">｜</span><a href="/contact.php" style="color:#9ca3af;text-decoration:none">お問い合わせ</a>
</footer>

<nav class="bottom-nav">
  <a href="/" class="bottom-nav-item">
    <i class="bi bi-speedometer2"></i><span>ホーム</span>
  </a>
  <a href="/signals/" class="bottom-nav-item">
    <i class="bi bi-lightning-charge"></i><span>シグナル</span>
  </a>
  <a href="/technical-ranking/" class="bottom-nav-item">
    <i class="bi bi-bar-chart-line"></i><span>ランキング</span>
  </a>
  <a href="/reports.html" class="bottom-nav-item">
    <i class="bi bi-file-earmark-text"></i><span>レポート</span>
  </a>
</nav>

<script>
(function(){
  var btn = document.getElementById('header-auth-btn');
  if (!btn) return;
  var c = document.cookie.split(';').map(function(c){return c.trim();}).find(function(c){return c.startsWith('fx_auth_email=');});
  if (c) { btn.textContent = 'マイページ'; btn.href = '/mypage.php'; }
})();
</script>
</body>
</html>
