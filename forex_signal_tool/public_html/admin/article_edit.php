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

$key = $_GET['key'] ?? '';
$article = null;
foreach ($ARTICLES as $a) {
    if ($a['key'] === $key) { $article = $a; break; }
}
// indicator_article_{slug} キーを動的に許可
if (!$article && preg_match('/^indicator_article_([a-z0-9_]+)$/', $key, $m)) {
    $slug = $m[1];
    $article = [
        'key'   => $key,
        'title' => 'テクニカル指標 SEO記事（' . $slug . '）',
        'page'  => '/' . $slug . '/',
    ];
}
if (!$article) {
    header('Location: /admin/articles.php');
    exit;
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><?= htmlspecialchars($article['title']) ?> | FX Trend 管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
main{max-width:960px;margin:0 auto;padding:28px 16px}
.breadcrumb{display:flex;align-items:center;gap:8px;margin-bottom:20px;font-size:13px;color:#64748b}
.breadcrumb a{color:#60a5fa;text-decoration:none}
.breadcrumb a:hover{text-decoration:underline}
.breadcrumb .sep{color:#334155}
.art-header{margin-bottom:24px}
.art-header h2{font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.art-meta{font-size:12px;color:#64748b}
.art-meta span{font-family:monospace;color:#475569}
.editor-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
.editor-label{font-size:12px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;display:block}
.editor-textarea{width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:14px;font-size:13px;font-family:'Consolas','Monaco',monospace;line-height:1.6;outline:none;resize:vertical;min-height:520px}
.editor-textarea:focus{border-color:#3b82f6}
.editor-actions{display:flex;align-items:center;gap:16px;margin-top:16px}
.save-btn{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 28px;font-size:14px;font-weight:600;cursor:pointer;transition:background .15s}
.save-btn:hover{background:#2563eb}
.save-btn:disabled{background:#1e3a5f;color:#64748b;cursor:not-allowed}
.save-status{font-size:13px}
.save-status.ok{color:#22c55e}
.save-status.err{color:#ef4444}
.save-status.saving{color:#64748b}
.info-banner{background:#162032;border:1px solid #1e3a5f;border-radius:8px;padding:12px 16px;margin-top:16px;font-size:12px;color:#60a5fa;line-height:1.7}
#loading-overlay{position:fixed;inset:0;background:#0f172a;display:flex;align-items:center;justify-content:center;z-index:999}
.spinner{display:inline-block;width:24px;height:24px;border:2px solid #334155;border-top-color:#3b82f6;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div id="loading-overlay"><div class="spinner"></div></div>

<header>
  <h1>✏️ 記事編集</h1>
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
  <div class="breadcrumb">
    <a href="/admin/articles.php">← 記事一覧</a>
    <span class="sep">/</span>
    <span><?= htmlspecialchars($article['title']) ?></span>
  </div>

  <div class="art-header">
    <h2><?= htmlspecialchars($article['title']) ?></h2>
    <div class="art-meta">対象ページ: <span><?= htmlspecialchars($article['page']) ?></span></div>
  </div>

<?php $is_indicator = (bool)preg_match('/^indicator_article_/', $article['key']); ?>

<?php if ($is_indicator): ?>
  <!-- 指標記事：3フィールド（CSS / HTML / JSON-LD） -->
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label">① CSS（&lt;style&gt;タグの中身のみ。body{}は不要）</label>
    <div style="font-size:11px;color:#475569;margin-bottom:6px">:root{} はそのまま貼り付け可。body{} はページ全体に影響するため自動的に除去されます。</div>
    <textarea id="editor-css" class="editor-textarea" style="min-height:200px" placeholder="*, *::before, *::after { box-sizing: border-box; }
:root { --font-sans: ... }
.kv { ... }"></textarea>
  </div>
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label">② 記事 HTML（&lt;main class=&quot;page-wrap&quot;&gt;〜&lt;/main&gt; の中身）</label>
    <div style="font-size:11px;color:#475569;margin-bottom:6px">&lt;html&gt;/&lt;head&gt;/&lt;body&gt;タグは不要です。&lt;main&gt;タグ内のコンテンツのみ貼り付けてください。</div>
    <textarea id="editor" class="editor-textarea" placeholder="<header class=&quot;kv&quot;>..."></textarea>
  </div>
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label">③ 構造化データ JSON-LD（&lt;script type=&quot;application/ld+json&quot;&gt;の中身のみ）</label>
    <div style="font-size:11px;color:#475569;margin-bottom:6px">&lt;script&gt;タグは不要。{ "@context": "https://schema.org", ... } のJSONのみ貼り付けてください。</div>
    <textarea id="editor-jsonld" class="editor-textarea" style="min-height:160px" placeholder='{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [...]
}'></textarea>
  </div>
<?php else: ?>
  <!-- 通常記事：HTMLのみ -->
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label" for="editor">記事 HTML</label>
    <textarea id="editor" class="editor-textarea" placeholder="HTMLを入力してください..."></textarea>
  </div>
<?php endif; ?>

  <div class="editor-card">
    <div class="editor-actions">
      <button class="save-btn" id="save-btn" onclick="saveContent()">保存する</button>
      <span id="save-status" class="save-status"></span>
    </div>
    <div class="info-banner">
      ℹ️ 保存後、管理画面の <strong>バックテスト</strong> または <strong>SEO管理 → ランキング管理</strong> から
      <strong>generate_static</strong> を実行すると公開ページに反映されます。
    </div>
  </div>
</main>

<script>
const ARTICLE_KEY    = <?= json_encode($article['key']) ?>;
const IS_INDICATOR   = <?= $is_indicator ? 'true' : 'false' ?>;

async function loadContent() {
  try {
    const res = await fetch('/admin/api.php?action=content_init');
    const d   = await res.json();
    if (d.status === 'ok') {
      const data = d.data || {};
      document.getElementById('editor').value = data[ARTICLE_KEY]?.value || '';
      if (IS_INDICATOR) {
        document.getElementById('editor-css').value    = data[ARTICLE_KEY + '_css']?.value    || '';
        document.getElementById('editor-jsonld').value = data[ARTICLE_KEY + '_jsonld']?.value || '';
      }
    }
  } catch(e) {
    console.error('Failed to load content', e);
  } finally {
    document.getElementById('loading-overlay').style.display = 'none';
  }
}

async function _save(key, value) {
  const res = await fetch('/admin/api.php', {
    method:  'POST',
    headers: {'Content-Type': 'application/json'},
    body:    JSON.stringify({action: 'content_save', key, value}),
  });
  return res.json();
}

async function saveContent() {
  const st  = document.getElementById('save-status');
  const btn = document.getElementById('save-btn');
  st.textContent = '保存中...';
  st.className   = 'save-status saving';
  btn.disabled   = true;
  try {
    const saves = [
      _save(ARTICLE_KEY, document.getElementById('editor').value),
    ];
    if (IS_INDICATOR) {
      saves.push(_save(ARTICLE_KEY + '_css',    document.getElementById('editor-css').value));
      saves.push(_save(ARTICLE_KEY + '_jsonld', document.getElementById('editor-jsonld').value));
    }
    const results = await Promise.all(saves);
    const failed  = results.find(d => d.status !== 'ok');
    if (!failed) {
      st.textContent = '✅ 保存完了';
      st.className   = 'save-status ok';
      setTimeout(() => { st.textContent = ''; st.className = 'save-status'; }, 4000);
    } else {
      st.textContent = '❌ 失敗: ' + (failed.message || '');
      st.className   = 'save-status err';
    }
  } catch(e) {
    st.textContent = '❌ ネットワークエラー';
    st.className   = 'save-status err';
  } finally {
    btn.disabled = false;
  }
}

loadContent();
</script>
</body>
</html>
