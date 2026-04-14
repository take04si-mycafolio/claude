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
.csv-card{background:#0d1f2d;border:1px solid #164e63;border-radius:10px;padding:16px 20px;margin-top:16px}
.csv-card h3{font-size:12px;font-weight:600;color:#67e8f9;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
.csv-card p{font-size:12px;color:#94a3b8;line-height:1.7;margin-bottom:12px}
.csv-btn{display:inline-flex;align-items:center;gap:6px;background:#0e7490;color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer;transition:background .15s}
.csv-btn:hover{background:#0891b2;color:#fff;text-decoration:none}
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

<?php
$is_indicator = (bool)preg_match('/^indicator_article_/', $article['key']);
$ind_slug = '';
$indicator_name = '';
$current_page_bt = null;  // indicator_page_bt_results の現在設定
if ($is_indicator) {
    preg_match('/^indicator_article_([a-z0-9_]+)$/', $article['key'], $sm);
    $ind_slug = $sm[1] ?? '';
    // slug → indicator_name マッピング
    $slugMapFile = __DIR__ . '/indicator_slugs.json';
    if ($ind_slug && file_exists($slugMapFile)) {
        $slugMap = json_decode(file_get_contents($slugMapFile), true) ?? [];
        $indicator_name = $slugMap[$ind_slug] ?? '';
    }
    // テクニカルページ専用バックテストの現在設定を取得
    if ($indicator_name) {
        try {
            $pdo = get_pdo();
            $stmt = $pdo->prepare(
                'SELECT * FROM indicator_page_bt_results
                 WHERE indicator_name = ?
                 ORDER BY win_rate DESC LIMIT 1'
            );
            $stmt->execute([$indicator_name]);
            $current_page_bt = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;
        } catch (Exception $e) { /* テーブル未作成時はスキップ */ }
    }
}
?>

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

<?php if ($is_indicator && $indicator_name): ?>
<style>
.ind-bt-card{background:#0b1a2b;border:1px solid #1e3a5f;border-radius:10px;padding:18px 20px;margin-top:16px}
.ind-bt-card h3{font-size:12px;font-weight:600;color:#38bdf8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.ind-bt-card .current-badge{display:inline-block;background:#0d2137;border:1px solid #1e4976;border-radius:6px;padding:6px 12px;font-size:12px;color:#94a3b8;margin-bottom:12px}
.ind-bt-card .current-badge strong{color:#e2e8f0}
.ind-bt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-bottom:12px}
.ind-bt-grid label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:#94a3b8}
.ind-bt-grid input,.ind-bt-grid select{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:13px}
.ind-bt-chk-row{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}
.ind-bt-chk-row label{display:flex;align-items:center;gap:5px;font-size:12px;color:#cbd5e1;cursor:pointer}
.ind-bt-run{background:#0e7490;color:#fff;border:none;border-radius:8px;padding:9px 22px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.ind-bt-run:hover{background:#0891b2}
.ind-bt-run:disabled{background:#374151;cursor:not-allowed}
#ind-bt-log{margin-top:10px;font-size:12px;color:#94a3b8;min-height:20px}
#ind-bt-result-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px;display:none}
#ind-bt-result-table th{background:#0d2137;color:#67e8f9;padding:5px 8px;text-align:left}
#ind-bt-result-table td{padding:4px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1}
</style>

<div class="ind-bt-card">
  <h3>🔬 テクニカルページ専用バックテスト</h3>
  <p style="font-size:12px;color:#64748b;margin-bottom:10px">
    ランキング用バックテストとは独立して保存されます。AIの検証データ期間に合わせた日付範囲を設定することで、テクニカルページに表示するバックテスト結果を統一できます。
  </p>

  <?php if ($current_page_bt): ?>
  <div class="current-badge">
    現在の設定: <strong><?= htmlspecialchars($current_page_bt['start_date'] ?? '指定なし') ?></strong>
    〜 <strong><?= htmlspecialchars($current_page_bt['end_date'] ?? '指定なし') ?></strong>
    &nbsp;|&nbsp; SL <strong><?= (int)($current_page_bt['sl_pips'] ?? 20) ?>pips</strong>
    / TP <strong><?= (int)($current_page_bt['tp_pips'] ?? 40) ?>pips</strong>
    &nbsp;|&nbsp; 最終更新: <?= substr($current_page_bt['calculated_at'] ?? '', 0, 10) ?>
  </div>
  <?php endif; ?>

  <div style="font-size:12px;color:#64748b;margin-bottom:6px">通貨ペア</div>
  <div class="ind-bt-chk-row">
    <label><input type="checkbox" class="ibt-pair" value="USDJPY" checked> USD/JPY</label>
    <label><input type="checkbox" class="ibt-pair" value="GBPJPY" checked> GBP/JPY</label>
    <label><input type="checkbox" class="ibt-pair" value="EURJPY" checked> EUR/JPY</label>
  </div>
  <div style="font-size:12px;color:#64748b;margin-bottom:6px">時間足</div>
  <div class="ind-bt-chk-row">
    <label><input type="checkbox" class="ibt-tf" value="5min"> 5分足</label>
    <label><input type="checkbox" class="ibt-tf" value="15min"> 15分足</label>
    <label><input type="checkbox" class="ibt-tf" value="30min"> 30分足</label>
    <label><input type="checkbox" class="ibt-tf" value="1hr" checked> 1時間足</label>
    <label><input type="checkbox" class="ibt-tf" value="4hr" checked> 4時間足</label>
    <label><input type="checkbox" class="ibt-tf" value="daily" checked> 日足</label>
  </div>
  <div class="ind-bt-grid">
    <label>SL (pips)<input type="number" id="ibt-sl" value="20" min="1" max="200"></label>
    <label>TP (pips)<input type="number" id="ibt-tp" value="40" min="1" max="500"></label>
    <label>開始日（JST）<input type="date" id="ibt-start" value="<?= date('Y-m-d', strtotime('-1 year')) ?>"></label>
    <label>終了日（JST）<input type="date" id="ibt-end" value="<?= date('Y-m-d') ?>"></label>
  </div>
  <button class="ind-bt-run" id="ind-bt-run-btn" onclick="runIndicatorPageBt()">バックテスト実行</button>
  <div id="ind-bt-log"></div>
  <table id="ind-bt-result-table">
    <thead><tr><th>通貨ペア</th><th>時間足</th><th>勝率</th><th>PF</th><th>総トレード</th><th>損益(円)</th></tr></thead>
    <tbody id="ind-bt-result-body"></tbody>
  </table>
</div>

<script>
const IND_BT_INDICATOR = <?= json_encode($indicator_name) ?>;

function runIndicatorPageBt() {
  const pairs = [...document.querySelectorAll('.ibt-pair:checked')].map(el => el.value);
  const tfs   = [...document.querySelectorAll('.ibt-tf:checked')].map(el => el.value);
  if (!pairs.length || !tfs.length) { alert('通貨ペアと時間足を1つ以上選択してください'); return; }

  const sl    = parseFloat(document.getElementById('ibt-sl').value) || 20;
  const tp    = parseFloat(document.getElementById('ibt-tp').value) || 40;
  const start = document.getElementById('ibt-start').value || null;
  const end   = document.getElementById('ibt-end').value   || null;

  const btn = document.getElementById('ind-bt-run-btn');
  btn.disabled = true;
  document.getElementById('ind-bt-log').textContent = '実行中...（しばらくお待ちください）';
  document.getElementById('ind-bt-result-table').style.display = 'none';

  fetch('/admin/api.php?action=run_indicator_page_bt', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      indicator_name: IND_BT_INDICATOR,
      pairs, timeframes: tfs,
      sl_pips: sl, tp_pips: tp,
      start_date: start, end_date: end,
    })
  })
  .then(r => r.json())
  .then(d => {
    btn.disabled = false;
    if (!d.ok) {
      document.getElementById('ind-bt-log').textContent = 'エラー: ' + (d.error || JSON.stringify(d));
      return;
    }
    document.getElementById('ind-bt-log').textContent =
      '完了！generate_static を実行するとテクニカルページに反映されます。';
    const tbody = document.getElementById('ind-bt-result-body');
    tbody.innerHTML = '';
    const tfLabels = {
      '5min':'5分足','15min':'15分足','30min':'30分足',
      '1hr':'1時間足','4hr':'4時間足','daily':'日足'
    };
    for (const [pair, tfsData] of Object.entries(d.summary || {})) {
      for (const [tf, r] of Object.entries(tfsData)) {
        const tr = document.createElement('tr');
        if (!r.ok) {
          tr.innerHTML = `<td>${pair}</td><td>${tfLabels[tf]||tf}</td><td colspan="4" style="color:#ef4444">${r.error}</td>`;
        } else {
          const wr = r.win_rate;
          const col = wr >= 55 ? '#4ade80' : wr >= 40 ? '#facc15' : '#ef4444';
          tr.innerHTML = `<td>${pair}</td><td>${tfLabels[tf]||tf}</td>
            <td style="color:${col};font-weight:600">${wr}%</td>
            <td>${r.profit_factor}</td>
            <td>${r.total_trades}</td>
            <td style="color:${r.total_profit>=0?'#4ade80':'#ef4444'}">${r.total_profit?.toLocaleString()}円</td>`;
        }
        tbody.appendChild(tr);
      }
    }
    document.getElementById('ind-bt-result-table').style.display = 'table';
  })
  .catch(e => {
    btn.disabled = false;
    document.getElementById('ind-bt-log').textContent = 'ネットワークエラー: ' + e;
  });
}
</script>
<?php endif; ?>

<?php if ($is_indicator && $ind_slug): ?>
  <div class="csv-card">
    <h3>📊 バックテストデータ &amp; 改善分析</h3>
    <p>
      ① CSVをダウンロードしてAIに渡し、改善ポイントを分析します。<br>
      ② AIの提案条件を <strong>バックテストツール2</strong> に入力して同一期間で検証します。<br>
      収録: <code>backtest_summary_<?= htmlspecialchars($ind_slug) ?>.csv</code> ・
            <code>simulation_trades_<?= htmlspecialchars($ind_slug) ?>.csv</code>
    </p>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="csv-btn"
         href="/admin/api.php?action=indicator_csv&amp;slug=<?= urlencode($ind_slug) ?>">
        📥 CSVをダウンロード（ZIP）
      </a>
      <a class="csv-btn" style="background:#0f766e"
         href="/admin/backtest_v2.php">
        ⚙️ バックテストツール2で開く
      </a>
    </div>
  </div>
<?php endif; ?>
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
