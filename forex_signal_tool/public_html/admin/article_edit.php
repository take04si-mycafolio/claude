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
$page_bt_by_tf = [];   // TF別の現在設定 ['1hr' => [...], '4hr' => [...], ...]
if ($is_indicator) {
    preg_match('/^indicator_article_([a-z0-9_]+)$/', $article['key'], $sm);
    $ind_slug = $sm[1] ?? '';
    // slug → indicator_name マッピング
    $slugMapFile = __DIR__ . '/indicator_slugs.json';
    if ($ind_slug && file_exists($slugMapFile)) {
        $slugMap = json_decode(file_get_contents($slugMapFile), true) ?? [];
        $indicator_name = $slugMap[$ind_slug] ?? '';
    }
    // テクニカルページ専用バックテストの現在設定をTF別に取得
    if ($indicator_name) {
        try {
            $pdo = get_pdo();
            $stmt = $pdo->prepare(
                'SELECT timeframe, start_date, end_date, sl_pips, tp_pips,
                        win_rate, total_trades, calculated_at
                 FROM indicator_page_bt_results
                 WHERE indicator_name = ?
                 ORDER BY FIELD(timeframe,\'5min\',\'15min\',\'30min\',\'1hr\',\'4hr\',\'daily\')'
            );
            $stmt->execute([$indicator_name]);
            while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
                $page_bt_by_tf[$row['timeframe']] = $row;
            }
        } catch (Exception $e) { /* テーブル未作成時はスキップ */ }
    }
}
// 現在設定からSL/TPを取得（フォームのデフォルト値）
$ibt_first = $page_bt_by_tf ? reset($page_bt_by_tf) : null;
$ibt_sl    = $ibt_first ? (int)($ibt_first['sl_pips'] ?? 20) : 20;
$ibt_tp    = $ibt_first ? (int)($ibt_first['tp_pips'] ?? 40) : 40;
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
.ind-bt-card .saved-badge{background:#0d2137;border:1px solid #1e4976;border-radius:6px;padding:6px 12px;font-size:11px;color:#94a3b8;margin-bottom:12px;line-height:1.8}
.ind-bt-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin-bottom:12px}
.ind-bt-grid label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:#94a3b8}
.ind-bt-grid input{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:13px}
.ind-bt-chk-row{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}
.ind-bt-chk-row label{display:flex;align-items:center;gap:5px;font-size:12px;color:#cbd5e1;cursor:pointer}
/* TF別期間テーブル */
.ibt-tf-table{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:12px}
.ibt-tf-table thead th{color:#475569;font-weight:600;padding:3px 8px 5px;text-align:left;border-bottom:1px solid #1e293b;white-space:nowrap}
.ibt-tf-table tbody tr:hover{background:#0d1f30}
.ibt-tf-table tbody td{padding:5px 8px;vertical-align:middle;border-bottom:1px solid #0f172a}
.ibt-tf-table input[type=date]{background:#0f172a;border:1px solid #334155;border-radius:5px;color:#e2e8f0;padding:4px 6px;font-size:12px;width:130px}
.ibt-tf-table input[type=date]:focus{outline:none;border-color:#0e7490}
.ibt-tf-table input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#0e7490}
.ibt-tf-table .tf-label{color:#cbd5e1;width:72px}
.ibt-tf-table .saved-info{font-size:11px;color:#475569;white-space:nowrap}
/* ボタン */
.ind-bt-run{background:#0e7490;color:#fff;border:none;border-radius:8px;padding:9px 22px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.ind-bt-run:hover:not(:disabled){background:#0891b2}
.ind-bt-run:disabled{background:#374151;color:#6b7280;cursor:not-allowed}
.ind-bt-reset{background:transparent;color:#f87171;border:1px solid #7f1d1d;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s}
.ind-bt-reset:hover:not(:disabled){background:#7f1d1d;color:#fff}
.ind-bt-reset:disabled{opacity:.35;cursor:not-allowed}
#ind-bt-log{margin-top:10px;font-size:12px;color:#94a3b8;min-height:20px}
#ind-bt-result-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px;display:none}
#ind-bt-result-table th{background:#0d2137;color:#67e8f9;padding:5px 8px;text-align:left}
#ind-bt-result-table td{padding:4px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1}
</style>

<div class="ind-bt-card">
  <h3>🔬 テクニカルページ専用バックテスト</h3>
  <p style="font-size:12px;color:#64748b;margin-bottom:10px">
    ランキング用バックテストとは独立して保存されます。足ごとに期間を設定し、AIの検証データ期間に合わせた結果をテクニカルページに表示できます。
  </p>

  <?php if ($page_bt_by_tf): ?>
  <div class="saved-badge">
    保存済み:
    <?php foreach ($page_bt_by_tf as $tf => $r): ?>
      <span style="margin-right:12px">
        <strong style="color:#e2e8f0"><?= htmlspecialchars($tf) ?></strong>
        <?= htmlspecialchars($r['start_date'] ?? '?') ?>〜<?= htmlspecialchars($r['end_date'] ?? '最新') ?>
        <span style="color:#64748b">（勝率<?= round($r['win_rate'] ?? 0, 1) ?>%）</span>
      </span>
    <?php endforeach; ?>
    <span style="color:#475569;margin-left:4px">最終更新: <?= substr($ibt_first['calculated_at'] ?? '', 0, 10) ?></span>
  </div>
  <?php endif; ?>

  <div style="font-size:12px;color:#64748b;margin-bottom:6px">通貨ペア</div>
  <div class="ind-bt-chk-row">
    <label><input type="checkbox" class="ibt-pair" value="USDJPY" checked> USD/JPY</label>
    <label><input type="checkbox" class="ibt-pair" value="GBPJPY" checked> GBP/JPY</label>
    <label><input type="checkbox" class="ibt-pair" value="EURJPY" checked> EUR/JPY</label>
  </div>

  <div style="font-size:12px;color:#64748b;margin-bottom:6px;margin-top:8px">時間足 &amp; 期間設定</div>
  <table class="ibt-tf-table">
    <thead><tr>
      <th style="width:26px"></th>
      <th>時間足</th>
      <th>開始日</th>
      <th>終了日</th>
      <th>保存済み</th>
    </tr></thead>
    <tbody>
<?php
$tf_defs = [
  '5min'  => ['label'=>'5分足',   'start'=>date('Y-m-d',strtotime('-3 months')), 'checked'=>false],
  '15min' => ['label'=>'15分足',  'start'=>date('Y-m-d',strtotime('-6 months')), 'checked'=>false],
  '30min' => ['label'=>'30分足',  'start'=>date('Y-m-d',strtotime('-6 months')), 'checked'=>false],
  '1hr'   => ['label'=>'1時間足', 'start'=>date('Y-m-d',strtotime('-1 year')),   'checked'=>true],
  '4hr'   => ['label'=>'4時間足', 'start'=>date('Y-m-d',strtotime('-2 years')),  'checked'=>true],
  'daily' => ['label'=>'日足',    'start'=>date('Y-m-d',strtotime('-5 years')),  'checked'=>true],
];
$today = date('Y-m-d');
foreach ($tf_defs as $tf => $def):
  $saved   = $page_bt_by_tf[$tf] ?? null;
  $checked = ($saved !== null) ? true : $def['checked'];
  $fstart  = $saved ? ($saved['start_date'] ?? $def['start']) : $def['start'];
  $fend    = $saved ? ($saved['end_date']   ?? $today)        : $today;
?>
      <tr data-tf="<?= $tf ?>">
        <td><input type="checkbox" class="ibt-tf" value="<?= $tf ?>"<?= $checked ? ' checked' : '' ?>></td>
        <td class="tf-label"><?= $def['label'] ?></td>
        <td><input type="date" class="ibt-tf-start" value="<?= htmlspecialchars($fstart) ?>"></td>
        <td><input type="date" class="ibt-tf-end"   value="<?= htmlspecialchars($fend) ?>"></td>
        <td class="saved-info">
          <?php if ($saved): ?>
            <?= htmlspecialchars(substr($saved['start_date']??'',0,10)) ?>〜<?= htmlspecialchars(substr($saved['end_date']??'',0,10)) ?>
            (<?= round($saved['win_rate']??0,1) ?>% / <?= (int)($saved['total_trades']??0) ?>件)
          <?php else: ?>
            <span style="color:#334155">未実行</span>
          <?php endif; ?>
        </td>
      </tr>
<?php endforeach; ?>
    </tbody>
  </table>

  <div class="ind-bt-grid" style="max-width:300px">
    <label>SL (pips)<input type="number" id="ibt-sl" value="<?= $ibt_sl ?>" min="1" max="200"></label>
    <label>TP (pips)<input type="number" id="ibt-tp" value="<?= $ibt_tp ?>" min="1" max="500"></label>
  </div>

  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px">
    <button class="ind-bt-run" id="ind-bt-run-btn" onclick="runIndicatorPageBt()">バックテスト実行</button>
    <button class="ind-bt-reset" id="ind-bt-reset-btn" onclick="resetIndicatorPageBt()"
            <?= $page_bt_by_tf ? '' : 'disabled' ?>>リセット</button>
  </div>
  <div id="ind-bt-log"></div>
  <table id="ind-bt-result-table">
    <thead><tr><th>通貨ペア</th><th>時間足</th><th>勝率</th><th>PF</th><th>総トレード</th><th>損益(円)</th><th>期間</th></tr></thead>
    <tbody id="ind-bt-result-body"></tbody>
  </table>
</div>

<script>
const IND_BT_INDICATOR = <?= json_encode($indicator_name) ?>;

function runIndicatorPageBt() {
  const pairs = [...document.querySelectorAll('.ibt-pair:checked')].map(el => el.value);
  if (!pairs.length) { alert('通貨ペアを1つ以上選択してください'); return; }

  const tf_ranges = {};
  document.querySelectorAll('.ibt-tf:checked').forEach(el => {
    const tf  = el.value;
    const row = el.closest('tr');
    tf_ranges[tf] = {
      start: row.querySelector('.ibt-tf-start').value || null,
      end:   row.querySelector('.ibt-tf-end').value   || null,
    };
  });
  if (!Object.keys(tf_ranges).length) { alert('時間足を1つ以上選択してください'); return; }

  const sl  = parseFloat(document.getElementById('ibt-sl').value) || 20;
  const tp  = parseFloat(document.getElementById('ibt-tp').value) || 40;
  const btn = document.getElementById('ind-bt-run-btn');
  btn.disabled = true;
  document.getElementById('ind-bt-log').textContent = '実行中...（しばらくお待ちください）';
  document.getElementById('ind-bt-result-table').style.display = 'none';

  fetch('/admin/api.php?action=run_indicator_page_bt', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ indicator_name: IND_BT_INDICATOR, pairs, tf_ranges, sl_pips: sl, tp_pips: tp })
  })
  .then(r => r.json())
  .then(d => {
    btn.disabled = false;
    if (!d.ok) {
      document.getElementById('ind-bt-log').textContent = 'エラー: ' + (d.error || JSON.stringify(d));
      return;
    }
    document.getElementById('ind-bt-log').textContent = '完了！generate_static を実行するとテクニカルページに反映されます。';
    document.getElementById('ind-bt-reset-btn').disabled = false;
    const tbody = document.getElementById('ind-bt-result-body');
    tbody.innerHTML = '';
    const TF_LBL = {'5min':'5分足','15min':'15分足','30min':'30分足','1hr':'1時間足','4hr':'4時間足','daily':'日足'};
    for (const [pair, tfsData] of Object.entries(d.summary || {})) {
      for (const [tf, r] of Object.entries(tfsData)) {
        const tr = document.createElement('tr');
        const period = [r.start_date, r.end_date].filter(Boolean).join('〜') || '-';
        if (!r.ok) {
          tr.innerHTML = `<td>${pair}</td><td>${TF_LBL[tf]||tf}</td><td colspan="5" style="color:#ef4444">${r.error}</td>`;
        } else {
          const wr = r.win_rate;
          const wc = wr >= 55 ? '#4ade80' : wr >= 40 ? '#facc15' : '#ef4444';
          tr.innerHTML = `<td>${pair}</td><td>${TF_LBL[tf]||tf}</td>
            <td style="color:${wc};font-weight:600">${wr}%</td>
            <td>${r.profit_factor}</td><td>${r.total_trades}</td>
            <td style="color:${r.total_profit>=0?'#4ade80':'#ef4444'}">${(r.total_profit||0).toLocaleString()}円</td>
            <td style="font-size:11px;color:#64748b">${period}</td>`;
        }
        tbody.appendChild(tr);
      }
    }
    document.getElementById('ind-bt-result-table').style.display = 'table';
  })
  .catch(e => { btn.disabled = false; document.getElementById('ind-bt-log').textContent = 'ネットワークエラー: ' + e; });
}

function resetIndicatorPageBt() {
  if (!confirm(`${IND_BT_INDICATOR} のテクニカルページ専用バックテストをリセットしますか？\nランキング用バックテストへのフォールバックに戻ります。`)) return;
  const btn = document.getElementById('ind-bt-reset-btn');
  btn.disabled = true;
  document.getElementById('ind-bt-log').textContent = 'リセット中...';
  fetch('/admin/api.php?action=reset_indicator_page_bt', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ indicator_name: IND_BT_INDICATOR })
  })
  .then(r => r.json())
  .then(d => {
    if (d.ok) {
      document.getElementById('ind-bt-log').textContent = 'リセット完了。generate_static を実行するとテクニカルページに反映されます。';
    } else {
      btn.disabled = false;
      document.getElementById('ind-bt-log').textContent = 'エラー: ' + (d.error || JSON.stringify(d));
    }
  })
  .catch(e => { btn.disabled = false; document.getElementById('ind-bt-log').textContent = 'ネットワークエラー: ' + e; });
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
