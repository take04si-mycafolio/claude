<?php
require_once __DIR__ . '/_config.php';
session_start();
require_login();

$ARTICLES = [
    ['key' => 'top_article_pre',  'title' => 'TOPページ（前半：KV・目次・概念説明）',  'page' => '/'],
    ['key' => 'top_article_post', 'title' => 'TOPページ（後半：手法解説・まとめ）',    'page' => '/'],
    ['key' => 'ranking_intro',    'title' => 'テクニカルランキング 導入文',             'page' => '/technical-ranking/'],
    ['key' => 'ranking_analysis', 'title' => 'テクニカルランキング 分析・考察',          'page' => '/technical-ranking/'],
];
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>記事管理 | FX Trend 管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
main{max-width:900px;margin:0 auto;padding:28px 16px}
h2{font-size:19px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.subtitle{font-size:12px;color:#64748b;margin-bottom:24px}
.article-table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}
.article-table th{background:#162032;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:12px 16px;text-align:left;border-bottom:1px solid #334155}
.article-table td{padding:14px 16px;border-bottom:1px solid #0f172a;vertical-align:middle}
.article-table tr:last-child td{border-bottom:none}
.article-table tr:hover td{background:#1a2844}
.art-title{font-size:14px;font-weight:600;color:#f1f5f9}
.art-page{font-size:11px;color:#475569;font-family:monospace;margin-top:3px}
.edit-btn{display:inline-block;background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f6;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:600;text-decoration:none;transition:background .15s;white-space:nowrap}
.edit-btn:hover{background:#1e4a8f}
.info-banner{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#94a3b8;line-height:1.7}
.info-banner strong{color:#60a5fa}
</style>
</head>
<body>
<header>
  <h1>📄 記事管理</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/backtest.php">バックテスト</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/articles.php" class="active">記事管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="#" class="logout-btn" onclick="fetch('/admin/api.php?action=logout').then(()=>location.href='/admin/')">ログアウト</a>
  </nav>
</header>
<main>
  <h2>記事管理</h2>
  <p class="subtitle">各記事を編集して保存後、管理画面の generate_static を実行してください。</p>

  <div class="info-banner">
    <strong>ℹ️ 使い方：</strong>
    編集したい記事の [編集] ボタンをクリックすると、その記事専用の編集ページが開きます。<br>
    HTMLを入力・保存後、<a href="/admin/backtest.php" style="color:#60a5fa">バックテスト管理</a> または <a href="/admin/seo.php" style="color:#60a5fa">SEO管理</a> から generate_static を実行すると公開に反映されます。
  </div>

  <table class="article-table">
    <thead>
      <tr>
        <th>記事タイトル</th>
        <th>対象ページ</th>
        <th style="width:90px;text-align:center">操作</th>
      </tr>
    </thead>
    <tbody>
      <?php foreach ($ARTICLES as $art): ?>
      <tr>
        <td>
          <div class="art-title"><?= htmlspecialchars($art['title']) ?></div>
        </td>
        <td>
          <div class="art-page"><?= htmlspecialchars($art['page']) ?></div>
        </td>
        <td style="text-align:center">
          <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>
</main>
</body>
</html>
