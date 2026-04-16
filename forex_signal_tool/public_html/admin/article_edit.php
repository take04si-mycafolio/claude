<?php
require_once __DIR__ . '/_config.php';
session_start();
require_login();

$ARTICLES = [
    ['key' => 'top_article_pre',  'title' => 'TOPページ（前半：KV・目次・概念説明）',  'page' => '/'],
    ['key' => 'top_article_post', 'title' => 'TOPページ（後半：手法解説・まとめ）',    'page' => '/'],
    ['key' => 'ranking_intro',    'title' => 'テクニカルランキング 導入文',             'page' => '/technical-ranking/'],
    ['key' => 'ranking_analysis', 'title' => 'テクニカルランキング 分析・考察',          'page' => '/technical-ranking/'],
    ['key' => 'pair_article_usdjpy', 'title' => 'ドル円（USD/JPY）ページ',   'page' => '/usdjpy/'],
    ['key' => 'pair_article_gbpjpy', 'title' => 'ポンド円（GBP/JPY）ページ', 'page' => '/gbpjpy/'],
    ['key' => 'pair_article_eurjpy', 'title' => 'ユーロ円（EUR/JPY）ページ', 'page' => '/eurjpy/'],
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
// pair_article_{pair} キーを動的に許可
$is_pair = false;
$pair_slug = '';
if (!$article && preg_match('/^pair_article_(usdjpy|gbpjpy|eurjpy)$/', $key, $m)) {
    $pair_slug = $m[1];
    $pair_names = ['usdjpy' => 'ドル円（USD/JPY）', 'gbpjpy' => 'ポンド円（GBP/JPY）', 'eurjpy' => 'ユーロ円（EUR/JPY）'];
    $article = [
        'key'   => $key,
        'title' => ($pair_names[$pair_slug] ?? strtoupper($pair_slug)) . ' ページ',
        'page'  => '/' . $pair_slug . '/',
    ];
    $is_pair = true;
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
.rebuild-btn{display:inline-flex;align-items:center;gap:6px;background:#1d4ed8;color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;margin-left:8px}
.rebuild-btn:hover{background:#2563eb}
.rebuild-btn:disabled{background:#1e3a5f;color:#64748b;cursor:not-allowed}
.rebuild-status{font-size:12px;margin-left:8px}
.rebuild-status.ok{color:#22c55e}
.rebuild-status.err{color:#ef4444}
.rebuild-status.running{color:#64748b}
.rebuild-log{background:#0f172a;border:1px solid #1e3a5f;border-radius:6px;padding:10px 12px;font-size:11px;color:#64748b;font-family:monospace;line-height:1.6;white-space:pre-wrap;margin-top:8px;display:none;max-height:180px;overflow-y:auto}
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
    // slug → indicator_name マッピング（generate_static.py の INDICATOR_INFO と同期）
    $BUILTIN_SLUG_MAP = [
        'rsi_14'                => 'RSI_14',
        'macd_12_26_9'          => 'MACD_12_26_9',
        'stochastic_14_3'       => 'Stochastic_14_3',
        'cci_20'                => 'CCI_20',
        'williams_r_14'         => 'Williams_R_14',
        'sma_20'                => 'SMA_20',
        'sma_50'                => 'SMA_50',
        'sma_cross_20_50'       => 'SMA_Cross_20_50',
        'ema_cross_9_21'        => 'EMA_Cross_9_21',
        'ema_21'                => 'EMA_21',
        'bollinger_bands_20_2'  => 'BollingerBands_20_2',
        'bb_squeeze'            => 'BB_Squeeze',
        'pivot_classic'         => 'Pivot_Classic',
        'fibonacci_retracement' => 'Fibonacci_Retracement',
        'support_resistance'    => 'Support_Resistance',
        'atr_14'                => 'ATR_14',
        'volatility_index'      => 'Volatility_Index',
        'hammer'                => 'Hammer',
        'inverted_hammer'       => 'Inverted_Hammer',
        'doji'                  => 'Doji',
        'bullish_engulfing'     => 'Bullish_Engulfing',
        'bearish_engulfing'     => 'Bearish_Engulfing',
        'three_white_soldiers'  => 'Three_White_Soldiers',
        'three_black_crows'     => 'Three_Black_Crows',
        'pin_bar'               => 'Pin_Bar',
        'ichimoku_cloud'        => 'Ichimoku_Cloud',
        'rsi_macd_combo'        => 'RSI_MACD_Combo',
        'rsi_stoch_combo'       => 'RSI_Stoch_Combo',
        'macd_stoch_combo'      => 'MACD_Stoch_Combo',
        'triple_osc_combo'      => 'Triple_OSC_Combo',
        'all_and_consensus'     => 'All_AND_Consensus',
    ];
    if ($ind_slug) {
        // indicator_slugs.json が存在すればそちらを優先、なければ組み込みマップを使用
        $slugMapFile = __DIR__ . '/indicator_slugs.json';
        if (file_exists($slugMapFile)) {
            $slugMap = json_decode(file_get_contents($slugMapFile), true) ?? [];
            $indicator_name = $slugMap[$ind_slug] ?? ($BUILTIN_SLUG_MAP[$ind_slug] ?? '');
        } else {
            $indicator_name = $BUILTIN_SLUG_MAP[$ind_slug] ?? '';
        }
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
<?php elseif ($is_pair): ?>
  <!-- 通貨ペアページ：CSS + HTML -->
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label">① CSS（追加スタイル — &lt;style&gt;タグの中身のみ）</label>
    <div style="font-size:11px;color:#475569;margin-bottom:6px">ページ固有のスタイルを記述。body{} は自動除去されます。</div>
    <textarea id="editor-css" class="editor-textarea" style="min-height:180px" placeholder=".pair-intro { ... }"></textarea>
  </div>
  <div class="editor-card" style="margin-bottom:16px">
    <label class="editor-label">② 記事 HTML（チャート・シグナル一覧の下に追記されます）</label>
    <div style="font-size:11px;color:#475569;margin-bottom:6px">HTMLタグ使用可。ページ下部の「記事エリア」に表示されます。</div>
    <textarea id="editor" class="editor-textarea" placeholder="<section class=&quot;pair-intro&quot;>&#10;  <h2>ドル円の特徴</h2>&#10;  <p>...</p>&#10;</section>"></textarea>
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
<?php if ($is_indicator && $indicator_name): ?>
      <a class="csv-btn"
         href="/admin/api.php?action=indicator_csv&ind=<?= urlencode($indicator_name) ?>"
         style="margin-left:8px">
        📥 バックテストCSV（ZIP）
      </a>
<?php endif; ?>
<?php if (($is_indicator && $ind_slug) || $is_pair): ?>
      <button class="rebuild-btn" id="rebuild-btn" onclick="rebuildPage()">🔄 公開ページを更新</button>
      <span class="rebuild-status" id="rebuild-status"></span>
<?php endif; ?>
    </div>
<?php if (($is_indicator && $ind_slug) || $is_pair): ?>
    <div id="rebuild-log" class="rebuild-log"></div>
<?php endif; ?>
    <div class="info-banner">
<?php if (($is_indicator && $ind_slug) || $is_pair): ?>
      💡 <strong>公開ページを更新</strong> ボタンで保存内容をすぐに反映できます。SSHは不要です。
<?php else: ?>
      ℹ️ 保存後、管理画面の <strong>バックテスト</strong> または <strong>SEO管理 → ランキング管理</strong> から
      <strong>generate_static</strong> を実行すると公開ページに反映されます。
<?php endif; ?>
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
<style>
/* ===== BT2 inline card ===== */
.bt2-inline-card{background:#0b1a2b;border:1px solid #1e3a5f;border-radius:10px;padding:18px 20px;margin-top:16px}
.bt2-inline-card h3{font-size:12px;font-weight:600;color:#38bdf8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.bt2-section-hdr{font-size:12px;font-weight:600;color:#64748b;margin-bottom:6px;margin-top:12px}
/* condition builder */
.bt2-cond-row{background:#0f172a;border:1px solid #334155;border-radius:9px;padding:10px 12px;display:grid;grid-template-columns:1.6fr 1fr 1.3fr 1.6fr auto;gap:8px;align-items:end;margin-bottom:8px}
.bt2-fg{display:flex;flex-direction:column;gap:3px}
.bt2-fg label,.bt2-fg .bt2-lbl{font-size:10px;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.4px;display:block}
.bt2-fg select,.bt2-fg input[type=number],.bt2-fg input[type=text]{background:#0d1f2d;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:12px;outline:none;width:100%}
.bt2-fg select:focus,.bt2-fg input:focus{border-color:#0e7490}
.bt2-logic-row{display:flex;gap:6px;margin-bottom:10px;align-items:center}
.bt2-lb{background:#0f172a;border:1px solid #475569;color:#94a3b8;border-radius:6px;padding:4px 12px;font-size:11px;font-weight:600;cursor:pointer;transition:all .15s}
.bt2-lb.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.bt2-add-cond{background:none;border:1px dashed #334155;color:#475569;border-radius:7px;padding:7px 14px;font-size:12px;cursor:pointer;width:100%;transition:all .15s;margin-bottom:12px}
.bt2-add-cond:hover{border-color:#0e7490;color:#67e8f9}
.bt2-del-cond{background:none;border:1px solid #334155;color:#475569;border-radius:6px;padding:5px 8px;font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap}
.bt2-del-cond:hover{border-color:#ef4444;color:#ef4444}
/* filter block */
.bt2-filter-block{margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #0f172a}
.bt2-filter-block:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.bt2-filter-title{font-size:11px;font-weight:600;color:#475569;margin-bottom:8px;text-transform:uppercase;letter-spacing:.4px}
.bt2-hint{font-size:11px;color:#475569;margin-top:3px}
/* weekday buttons */
.bt2-wd-btns{display:flex;gap:5px;flex-wrap:wrap}
.bt2-wd-btn{background:#0f172a;border:1px solid #334155;color:#475569;border-radius:6px;padding:4px 10px;font-size:11px;font-weight:600;cursor:pointer;transition:all .15s;user-select:none}
.bt2-wd-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
/* SL/TP type panels */
.bt2-type-panel{display:none}
.bt2-type-panel.active{display:flex;gap:10px;flex-wrap:wrap}
/* trailing toggle */
.bt2-toggle-sw{position:relative;width:36px;height:20px;cursor:pointer;flex-shrink:0}
.bt2-toggle-sw input{opacity:0;width:0;height:0;position:absolute}
.bt2-toggle-track{position:absolute;inset:0;background:#334155;border-radius:10px;transition:background .2s}
.bt2-toggle-sw input:checked + .bt2-toggle-track{background:#3b82f6}
.bt2-toggle-thumb{position:absolute;top:2px;left:2px;width:16px;height:16px;background:#fff;border-radius:50%;transition:transform .2s}
.bt2-toggle-sw input:checked ~ .bt2-toggle-thumb{transform:translateX(16px)}
/* run/result */
.bt2-run-btn{background:#0e7490;color:#fff;border:none;border-radius:8px;padding:9px 22px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.bt2-run-btn:hover:not(:disabled){background:#0891b2}
.bt2-run-btn:disabled{background:#374151;color:#6b7280;cursor:not-allowed}
.bt2-result-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px;display:none}
.bt2-result-tbl th{background:#0d2137;color:#67e8f9;padding:5px 8px;text-align:left}
.bt2-result-tbl td{padding:4px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1}
/* ai feedback */
.ai-feedback-ta{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:10px;font-size:12px;line-height:1.6;resize:vertical;min-height:120px;font-family:inherit;outline:none}
.ai-feedback-ta:focus{border-color:#0e7490}
.ai-feedback-ta::placeholder{color:#334155}
.ai-fb-save-btn{background:#0f766e;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer;transition:background .15s}
.ai-fb-save-btn:hover{background:#0d9488}
.ai-fb-save-btn:disabled{background:#334155;cursor:not-allowed}
.ai-fb-status{font-size:11px}
.ai-fb-status.ok{color:#22c55e}
.ai-fb-status.err{color:#ef4444}
/* linked strategies */
.ls-item{background:#0f172a;border:1px solid #1e293b;border-radius:5px;padding:6px 10px;font-size:12px;margin-bottom:5px;display:flex;align-items:flex-start;gap:8px}
.ls-body{flex:1;min-width:0}
.ls-name{color:#e2e8f0;font-weight:600;margin-bottom:2px}
.ls-meta{color:#475569;font-size:11px;display:flex;gap:8px;flex-wrap:wrap}
.ls-wr{color:#4ade80;font-weight:600}
.ls-del{background:none;border:none;color:#475569;cursor:pointer;font-size:14px;padding:0 2px;line-height:1;flex-shrink:0;margin-top:1px}
.ls-del:hover{color:#f87171}
.ls-dl{background:none;border:none;color:#38bdf8;cursor:pointer;font-size:12px;padding:0 2px;line-height:1;flex-shrink:0;margin-top:1px;text-decoration:none}
.ls-dl:hover{color:#7dd3fc;text-decoration:none}
</style>

<div class="bt2-inline-card">
  <h3>⚙️ マルチ条件バックテスト（BT2）</h3>
  <p style="font-size:12px;color:#64748b;margin-bottom:14px">
    改善条件を設定して各時間足でバックテストを実行します。結果はAIへの入力として活用できます。
  </p>

  <!-- エントリー条件 -->
  <div class="bt2-section-hdr">エントリー条件</div>
  <div class="bt2-logic-row">
    <span style="font-size:11px;color:#475569">結合論理:</span>
    <button class="bt2-lb active" id="bt2-logic-and" onclick="bt2SetLogic('AND')">AND（全条件一致）</button>
    <button class="bt2-lb" id="bt2-logic-or" onclick="bt2SetLogic('OR')">OR（いずれか一致）</button>
  </div>
  <div id="bt2-cond-list"></div>
  <button class="bt2-add-cond" onclick="addBt2Cond()">＋ 条件を追加</button>

  <!-- 基本設定 -->
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:14px">
    <div class="bt2-fg">
      <label>エントリー方向</label>
      <select id="bt2-direction">
        <option value="BUY">BUY（買いのみ）</option>
        <option value="SELL">SELL（売りのみ）</option>
        <option value="BOTH" selected>BOTH（両方）</option>
      </select>
    </div>
    <div class="bt2-fg">
      <label>初期資金 (円)</label>
      <input type="number" id="bt2-capital" value="1000000" min="10000" step="10000">
    </div>
    <div class="bt2-fg">
      <label>pip 価値 (円/pip)</label>
      <input type="number" id="bt2-pip-value" value="100" min="1" step="10">
      <div class="bt2-hint">例: 1万通貨=100円/pip</div>
    </div>
    <div class="bt2-fg">
      <label>最大保有バー数</label>
      <input type="number" id="bt2-max-bars" value="200" min="10" max="1000" step="10">
      <div class="bt2-hint">未決済時の強制クローズ</div>
    </div>
  </div>

  <!-- フィルター設定 -->
  <div class="bt2-section-hdr">フィルター設定（任意）</div>
  <div style="background:#0d1a27;border:1px solid #1e293b;border-radius:8px;padding:14px 16px;margin-bottom:14px">

    <!-- 時間帯 -->
    <div class="bt2-filter-block">
      <div class="bt2-filter-title">時間帯（JST）</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px">
        <div class="bt2-fg">
          <label>セッション プリセット</label>
          <select id="bt2-f-session" onchange="bt2OnSession()">
            <option value="">-- フィルターなし --</option>
            <option value="tokyo">東京 (07:00〜16:00 JST)</option>
            <option value="london">ロンドン (17:00〜02:00 JST)</option>
            <option value="ny">ニューヨーク (22:00〜07:00 JST)</option>
            <option value="custom">カスタム</option>
          </select>
        </div>
      </div>
      <div id="bt2-custom-time" style="display:none;grid-template-columns:1fr 1fr;gap:10px">
        <div class="bt2-fg">
          <label>開始時刻 (JST・時)</label>
          <input type="number" id="bt2-f-start-hour" value="9" min="0" max="23" step="1">
        </div>
        <div class="bt2-fg">
          <label>終了時刻 (JST・時)</label>
          <input type="number" id="bt2-f-end-hour" value="17" min="0" max="23" step="1">
          <div class="bt2-hint">終了 &lt; 開始 の場合は日をまたぐ（例: 22〜7）</div>
        </div>
      </div>
    </div>

    <!-- 曜日 -->
    <div class="bt2-filter-block">
      <div class="bt2-filter-title">曜日（全選択 = フィルターなし）</div>
      <div class="bt2-wd-btns" id="bt2-wd-btns">
        <button class="bt2-wd-btn active" data-wd="0" onclick="bt2ToggleWd(this)">月</button>
        <button class="bt2-wd-btn active" data-wd="1" onclick="bt2ToggleWd(this)">火</button>
        <button class="bt2-wd-btn active" data-wd="2" onclick="bt2ToggleWd(this)">水</button>
        <button class="bt2-wd-btn active" data-wd="3" onclick="bt2ToggleWd(this)">木</button>
        <button class="bt2-wd-btn active" data-wd="4" onclick="bt2ToggleWd(this)">金</button>
        <button class="bt2-wd-btn" data-wd="5" onclick="bt2ToggleWd(this)">土</button>
        <button class="bt2-wd-btn" data-wd="6" onclick="bt2ToggleWd(this)">日</button>
      </div>
    </div>

    <!-- ATR ボラティリティ -->
    <div class="bt2-filter-block">
      <div class="bt2-filter-title">ボラティリティ（ATR フィルター）</div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
        <div class="bt2-fg">
          <label>ATR 期間</label>
          <input type="number" id="bt2-f-atr-period" value="14" min="1" step="1">
        </div>
        <div class="bt2-fg">
          <label>最小 pips</label>
          <input type="number" id="bt2-f-atr-min" value="0" min="0" step="1">
          <div class="bt2-hint">0 = 無効</div>
        </div>
        <div class="bt2-fg">
          <label>最大 pips</label>
          <input type="number" id="bt2-f-atr-max" value="0" min="0" step="1">
          <div class="bt2-hint">0 = 無制限</div>
        </div>
      </div>
    </div>
  </div>

  <!-- リスク管理 -->
  <div class="bt2-section-hdr">リスク管理（SL / TP / トレーリング）</div>
  <div style="background:#0d1a27;border:1px solid #1e293b;border-radius:8px;padding:14px 16px;margin-bottom:14px">

    <!-- SL -->
    <div style="margin-bottom:16px">
      <div style="font-size:11px;font-weight:600;color:#94a3b8;margin-bottom:8px">◆ ストップロス (SL)</div>
      <div class="bt2-fg" style="margin-bottom:8px;max-width:200px">
        <label>SL タイプ</label>
        <select id="bt2-sl-type" onchange="bt2OnSlType()">
          <option value="fixed">固定 pips</option>
          <option value="recentHighLow">直近高値/安値</option>
          <option value="atr">ATR 倍数</option>
        </select>
      </div>
      <div class="bt2-type-panel active" id="bt2-sl-fixed">
        <div class="bt2-fg"><label>SL pips</label>
          <input type="number" id="bt2-sl-pips" value="<?= $ibt_sl ?>" min="1" step="1" style="width:90px">
        </div>
      </div>
      <div class="bt2-type-panel" id="bt2-sl-recentHighLow">
        <div class="bt2-fg"><label>ルックバック本数</label>
          <input type="number" id="bt2-sl-lookback" value="10" min="1" step="1" style="width:90px">
        </div>
        <div class="bt2-fg"><label>バッファ pips</label>
          <input type="number" id="bt2-sl-buffer" value="3" min="0" step="0.5" style="width:90px">
        </div>
      </div>
      <div class="bt2-type-panel" id="bt2-sl-atr">
        <div class="bt2-fg"><label>ATR 期間</label>
          <input type="number" id="bt2-sl-atr-period" value="14" min="1" step="1" style="width:90px">
        </div>
        <div class="bt2-fg"><label>ATR 倍数</label>
          <input type="number" id="bt2-sl-atr-mult" value="1.5" min="0.1" step="0.1" style="width:90px">
        </div>
      </div>
    </div>

    <!-- TP -->
    <div style="margin-bottom:16px">
      <div style="font-size:11px;font-weight:600;color:#94a3b8;margin-bottom:8px">◆ テイクプロフィット (TP)</div>
      <div class="bt2-fg" style="margin-bottom:8px;max-width:200px">
        <label>TP タイプ</label>
        <select id="bt2-tp-type" onchange="bt2OnTpType()">
          <option value="rr">RR 比率（SL × 倍率）</option>
          <option value="fixed">固定 pips</option>
          <option value="atr">ATR 倍数</option>
        </select>
      </div>
      <div class="bt2-type-panel active" id="bt2-tp-rr">
        <div class="bt2-fg"><label>RR 比率</label>
          <select id="bt2-tp-rr-ratio" style="width:110px;background:#0d1f2d;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:12px;outline:none">
            <option value="1.0">1 : 1.0</option>
            <option value="1.5" selected>1 : 1.5</option>
            <option value="2.0">1 : 2.0</option>
            <option value="2.5">1 : 2.5</option>
            <option value="3.0">1 : 3.0</option>
          </select>
        </div>
      </div>
      <div class="bt2-type-panel" id="bt2-tp-fixed">
        <div class="bt2-fg"><label>TP pips</label>
          <input type="number" id="bt2-tp-pips" value="<?= $ibt_tp ?>" min="1" step="1" style="width:90px">
        </div>
      </div>
      <div class="bt2-type-panel" id="bt2-tp-atr">
        <div class="bt2-fg"><label>ATR 期間</label>
          <input type="number" id="bt2-tp-atr-period" value="14" min="1" step="1" style="width:90px">
        </div>
        <div class="bt2-fg"><label>ATR 倍数</label>
          <input type="number" id="bt2-tp-atr-mult" value="3.0" min="0.1" step="0.1" style="width:90px">
        </div>
      </div>
    </div>

    <!-- トレーリング -->
    <div>
      <div style="font-size:11px;font-weight:600;color:#94a3b8;margin-bottom:8px">◆ トレーリングストップ</div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <label class="bt2-toggle-sw">
          <input type="checkbox" id="bt2-trailing-on" onchange="bt2OnTrailing()">
          <div class="bt2-toggle-track"></div>
          <div class="bt2-toggle-thumb"></div>
        </label>
        <span id="bt2-trailing-lbl" style="font-size:12px;color:#64748b">OFF</span>
      </div>
      <div id="bt2-trailing-fields" style="display:none">
        <div class="bt2-fg" style="max-width:160px">
          <label>トレール幅 (pips)</label>
          <input type="number" id="bt2-trail-pips" value="10" min="1" step="1">
        </div>
      </div>
    </div>
  </div>

  <!-- 通貨ペア -->
  <div class="bt2-section-hdr" style="margin-top:4px">通貨ペア</div>
  <div class="ind-bt-chk-row" style="margin-bottom:10px">
    <label><input type="checkbox" class="bt2-pair" value="USDJPY" checked> USD/JPY</label>
    <label><input type="checkbox" class="bt2-pair" value="GBPJPY" checked> GBP/JPY</label>
    <label><input type="checkbox" class="bt2-pair" value="EURJPY" checked> EUR/JPY</label>
  </div>

  <!-- 時間足 & 期間設定 -->
  <div class="bt2-section-hdr">時間足 &amp; 期間設定</div>
  <table class="ibt-tf-table" style="margin-bottom:14px">
    <thead><tr>
      <th style="width:26px"></th>
      <th>時間足</th>
      <th>開始日</th>
      <th>終了日</th>
    </tr></thead>
    <tbody>
<?php foreach ($tf_defs as $tf => $def):
  $saved  = $page_bt_by_tf[$tf] ?? null;
  $fstart = $saved ? ($saved['start_date'] ?? $def['start']) : $def['start'];
  $fend   = $saved ? ($saved['end_date']   ?? $today)        : $today;
  $chk    = ($saved !== null) ? true : $def['checked'];
?>
      <tr>
        <td><input type="checkbox" class="bt2-tf" value="<?= $tf ?>"<?= $chk ? ' checked' : '' ?>></td>
        <td class="tf-label"><?= $def['label'] ?></td>
        <td><input type="date" class="bt2-tf-start" value="<?= htmlspecialchars($fstart) ?>"></td>
        <td><input type="date" class="bt2-tf-end"   value="<?= htmlspecialchars($fend) ?>"></td>
      </tr>
<?php endforeach; ?>
    </tbody>
  </table>

  <!-- 実行ボタン -->
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
    <button class="bt2-run-btn" id="bt2-run-btn" onclick="runBt2Inline()">バックテスト実行</button>
    <span id="bt2-log" style="font-size:12px;color:#94a3b8"></span>
  </div>

  <!-- 結果テーブル -->
  <table class="bt2-result-tbl" id="bt2-result-tbl">
    <thead><tr>
      <th>通貨ペア</th><th>時間足</th><th>勝率</th><th>PF</th><th>総取引</th><th>損益(円)</th><th>期間</th>
    </tr></thead>
    <tbody id="bt2-result-body"></tbody>
  </table>

  <!-- 保存セクション（実行後に表示） -->
  <div id="bt2-save-wrap" style="display:none;margin-top:12px;padding:12px 14px;background:#0a1628;border:1px solid #1e3a5f;border-radius:8px">
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <input type="text" id="bt2-save-name"
             placeholder="戦略名を入力（例: RSI逆張り改良版）"
             style="flex:1;min-width:180px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:13px;outline:none">
      <button class="bt2-run-btn" id="bt2-save-btn" onclick="saveBt2InlineStrategy()"
              style="background:#0f766e;padding:8px 18px;font-size:13px">💾 戦略を保存</button>
      <span id="bt2-save-status" style="font-size:12px;color:#94a3b8"></span>
    </div>
  </div>

  <!-- リンク済み保存戦略 -->
  <div style="margin-top:14px;border-top:1px solid #1e293b;padding-top:12px">
    <div class="bt2-section-hdr" style="margin-top:0">リンク済み保存戦略（BT2で保存済み）</div>
    <div id="linked-strategies-wrap"><span style="font-size:12px;color:#475569">読み込み中...</span></div>
  </div>

  <!-- AIフィードバック -->
  <div style="margin-top:14px;border-top:1px solid #1e293b;padding-top:12px">
    <div class="bt2-section-hdr" style="margin-top:0">🤖 AIフィードバック
      <span style="font-size:10px;font-weight:400;color:#67e8f9;margin-left:6px">HTMLタグ使用可 / 公開ページに表示されます</span>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:6px">
      <button class="ai-fb-tab-btn active" onclick="aiFbTab('edit',this)" style="background:#0e7490;color:#fff;border:none;border-radius:4px;padding:4px 12px;font-size:11px;cursor:pointer">編集</button>
      <button class="ai-fb-tab-btn" onclick="aiFbTab('preview',this)" style="background:#1e293b;color:#94a3b8;border:none;border-radius:4px;padding:4px 12px;font-size:11px;cursor:pointer">プレビュー</button>
    </div>
    <textarea id="ai-feedback-ta" class="ai-feedback-ta"
      placeholder="HTMLタグが使えます。公開ページの「AI分析ノート」欄に表示されます。&#10;&#10;例）&lt;h3&gt;改善ポイント&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;RSIが30以下かつEMA21が上向きの場合...&lt;/li&gt;&lt;/ul&gt;"
      oninput="aiFbSyncPreview()"></textarea>
    <div id="ai-fb-preview" style="display:none;background:#f8faff;border:1px solid #bfdbfe;border-radius:6px;padding:12px;font-size:12px;color:#1e293b;line-height:1.8;min-height:80px;max-height:400px;overflow-y:auto"></div>
    <div style="display:flex;align-items:center;gap:10px;margin-top:6px">
      <button class="ai-fb-save-btn" onclick="saveAiFeedback()">保存</button>
      <span id="ai-fb-status" class="ai-fb-status"></span>
    </div>
    <div id="ai-fb-updated" style="font-size:11px;color:#475569;margin-top:4px"></div>
  </div>
</div>

<script>
/* ===== BT2 inline condition builder ===== */
let _bt2InlineResults = [];  // 最終実行の pair×TF 結果を蓄積（保存用）

const BT2_IND = {
  RSI:         { label:'RSI',          params:[{n:'period',l:'期間',d:14}] },
  EMA:         { label:'EMA',          params:[{n:'period',l:'期間',d:21}] },
  EMA_SLOPE:   { label:'EMA 向き',     params:[{n:'period',l:'期間',d:21}], hint:'上向き≥1 / 下向き≤-1' },
  SMA:         { label:'SMA',          params:[{n:'period',l:'期間',d:20}] },
  MACD_HIST:   { label:'MACD ヒスト',  params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_LINE:   { label:'MACD ライン',  params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  MACD_SIGNAL: { label:'MACD シグナル',params:[{n:'fast',l:'Fast',d:12},{n:'slow',l:'Slow',d:26},{n:'signal',l:'Sig',d:9}] },
  STOCH_K:     { label:'Stoch %K',     params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  STOCH_D:     { label:'Stoch %D',     params:[{n:'k_period',l:'K期間',d:14},{n:'d_period',l:'D期間',d:3},{n:'smooth_k',l:'平滑K',d:3}] },
  CCI:         { label:'CCI',          params:[{n:'period',l:'期間',d:20}] },
  WILLIAMS_R:  { label:'Williams %R',  params:[{n:'period',l:'期間',d:14}] },
  ATR:         { label:'ATR',          params:[{n:'period',l:'期間',d:14}] },
  BB_UPPER:    { label:'BB 上バンド',  params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_LOWER:    { label:'BB 下バンド',  params:[{n:'period',l:'期間',d:20},{n:'std',l:'σ',d:2.0}] },
  BB_MID:      { label:'BB 中央',      params:[{n:'period',l:'期間',d:20}] },
  CLOSE:       { label:'終値',         params:[] },
  HIGH:        { label:'高値',         params:[] },
  LOW:         { label:'安値',         params:[] },
  BULLISH_ENGULFING:    { label:'強気の包み足', params:[], is_pattern:true },
  BEARISH_ENGULFING:    { label:'弱気の包み足', params:[], is_pattern:true },
  HAMMER:               { label:'ハンマー',     params:[], is_pattern:true },
  INVERTED_HAMMER:      { label:'逆ハンマー',   params:[], is_pattern:true },
  DOJI:                 { label:'十字線',        params:[], is_pattern:true },
  THREE_WHITE_SOLDIERS: { label:'三白兵',        params:[], is_pattern:true },
  THREE_BLACK_CROWS:    { label:'三羽烏',        params:[], is_pattern:true },
  BULLISH_PIN_BAR:      { label:'ピンバー(陽)',  params:[], is_pattern:true },
  BEARISH_PIN_BAR:      { label:'ピンバー(陰)',  params:[], is_pattern:true },
};

const BT2_COMPS = [
  { v:'less_than',             l:'< 小さい' },
  { v:'less_than_or_equal',    l:'≤ 以下' },
  { v:'greater_than',          l:'> 大きい' },
  { v:'greater_than_or_equal', l:'≥ 以上' },
  { v:'equals',                l:'= 等しい' },
  { v:'crosses_above',         l:'↑ クロスアップ' },
  { v:'crosses_below',         l:'↓ クロスダウン' },
];

function bt2IndOpts(excludePatterns) {
  const tech = ['RSI','EMA','EMA_SLOPE','SMA','MACD_HIST','MACD_LINE','MACD_SIGNAL',
                'STOCH_K','STOCH_D','CCI','WILLIAMS_R','ATR',
                'BB_UPPER','BB_LOWER','BB_MID','CLOSE','HIGH','LOW'];
  const pat  = ['BULLISH_ENGULFING','BEARISH_ENGULFING','HAMMER','INVERTED_HAMMER',
                'DOJI','THREE_WHITE_SOLDIERS','THREE_BLACK_CROWS',
                'BULLISH_PIN_BAR','BEARISH_PIN_BAR'];
  const techOpts = tech.map(k => `<option value="${k}">${BT2_IND[k].label}</option>`).join('');
  if (excludePatterns) return `<optgroup label="テクニカル指標">${techOpts}</optgroup>`;
  const patOpts = pat.map(k => `<option value="${k}">${BT2_IND[k].label}</option>`).join('');
  return `<optgroup label="テクニカル指標">${techOpts}</optgroup>
          <optgroup label="ローソク足パターン (検出=1)">${patOpts}</optgroup>`;
}

let _bt2Seq = 0;
let _bt2Logic = 'AND';

function bt2SetLogic(v) {
  _bt2Logic = v;
  document.getElementById('bt2-logic-and').classList.toggle('active', v === 'AND');
  document.getElementById('bt2-logic-or' ).classList.toggle('active', v === 'OR');
}

function bt2ParamInputs(indKey, rowId) {
  const ps = (BT2_IND[indKey] || {}).params || [];
  if (!ps.length) return '<span class="bt2-lbl">パラメータ</span><div style="color:#475569;font-size:11px;padding:7px 0">なし</div>';
  const inps = ps.map(p =>
    `<div style="display:flex;flex-direction:column;gap:2px">
       <span style="font-size:10px;color:#64748b">${p.l}</span>
       <input type="number" id="${rowId}-p-${p.n}" value="${p.d}" step="${p.n==='std'?0.1:1}"
              style="width:56px;background:#0d1f2d;border:1px solid #334155;border-radius:5px;color:#e2e8f0;padding:4px 5px;font-size:12px;outline:none">
     </div>`
  ).join('');
  const hint = (BT2_IND[indKey] || {}).hint || '';
  const hintHtml = hint ? `<div style="font-size:10px;color:#67e8f9;margin-top:3px">${hint}</div>` : '';
  return `<span class="bt2-lbl">パラメータ</span><div style="display:flex;gap:4px;flex-wrap:wrap">${inps}</div>${hintHtml}`;
}

function bt2RhsHtml(rowId) {
  return `<span class="bt2-lbl">比較値</span>
    <select id="${rowId}-cmp-ind" onchange="bt2OnCmpIndChange('${rowId}')"
      style="background:#0d1f2d;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:5px 6px;font-size:11px;width:100%;outline:none;margin-bottom:3px">
      <option value="">--- 固定値 ---</option>
      ${bt2IndOpts(true)}
    </select>
    <div id="${rowId}-rhs-val">
      <input type="number" id="${rowId}-val" value="0" step="0.1"
             style="background:#0d1f2d;border:1px solid #334155;border-radius:5px;color:#e2e8f0;padding:4px 6px;font-size:12px;width:100%;outline:none">
    </div>
    <div id="${rowId}-rhs-ind-params"></div>`;
}

function bt2OnCmpIndChange(rowId) {
  const sel      = document.getElementById(rowId + '-cmp-ind');
  const valDiv   = document.getElementById(rowId + '-rhs-val');
  const paramsDiv= document.getElementById(rowId + '-rhs-ind-params');
  if (valDiv)    valDiv.style.display = sel.value ? 'none' : 'block';
  if (paramsDiv) {
    if (sel.value) {
      const ps = (BT2_IND[sel.value] || {}).params || [];
      paramsDiv.innerHTML = ps.map(p =>
        `<div style="display:flex;align-items:center;gap:4px;margin-top:2px">
           <span style="font-size:10px;color:#64748b;min-width:26px">${p.l}</span>
           <input type="number" id="${rowId}-cind-p-${p.n}" value="${p.d}"
                  step="${p.n==='std'?0.1:1}"
                  style="width:54px;background:#0d1f2d;border:1px solid #334155;border-radius:5px;color:#e2e8f0;padding:3px 5px;font-size:11px;outline:none">
         </div>`
      ).join('');
    } else { paramsDiv.innerHTML = ''; }
  }
}

function addBt2Cond() {
  const id = 'bt2c-' + (++_bt2Seq);
  const row = document.createElement('div');
  row.className = 'bt2-cond-row';
  row.id = id;
  row.dataset.id = 'c' + _bt2Seq;
  row.innerHTML = `
    <div class="bt2-fg">
      <label>指標</label>
      <select onchange="bt2OnIndChange(this, '${id}')">
        ${bt2IndOpts(false)}
      </select>
    </div>
    <div class="bt2-fg" id="${id}-params">${bt2ParamInputs('RSI', id)}</div>
    <div class="bt2-fg">
      <label>比較</label>
      <select id="${id}-cmp">
        ${BT2_COMPS.map(c => `<option value="${c.v}">${c.l}</option>`).join('')}
      </select>
    </div>
    <div class="bt2-fg" id="${id}-rhs">${bt2RhsHtml(id)}</div>
    <div>
      <label style="visibility:hidden;font-size:10px">削除</label>
      <button class="bt2-del-cond" onclick="this.closest('.bt2-cond-row').remove()">✕</button>
    </div>`;
  document.getElementById('bt2-cond-list').appendChild(row);
}

function bt2OnIndChange(sel, rowId) {
  const k = sel.value;
  document.getElementById(rowId + '-params').innerHTML = bt2ParamInputs(k, rowId);
  if ((BT2_IND[k] || {}).is_pattern || k === 'EMA_SLOPE') {
    const cmpSel = document.getElementById(rowId + '-cmp');
    if (cmpSel) cmpSel.value = 'greater_than_or_equal';
    const valEl = document.getElementById(rowId + '-val');
    if (valEl) valEl.value = '1';
  }
}

function bt2BuildConds() {
  const conds = [];
  for (const row of document.querySelectorAll('#bt2-cond-list .bt2-cond-row')) {
    const condId = row.dataset.id;
    const indKey = row.querySelector('select').value;
    const rowId  = row.id;
    const cmpVal = document.getElementById(rowId + '-cmp')?.value || 'less_than';
    const params = {};
    ((BT2_IND[indKey] || {}).params || []).forEach(p => {
      const el = document.getElementById(rowId + '-p-' + p.n);
      if (el) params[p.n] = parseFloat(el.value);
    });
    let value = null, compare_to_indicator = null, compare_to_params = null;
    const cmpIndSel = document.getElementById(rowId + '-cmp-ind');
    if (cmpIndSel && cmpIndSel.value) {
      compare_to_indicator = cmpIndSel.value;
      compare_to_params = {};
      ((BT2_IND[cmpIndSel.value] || {}).params || []).forEach(p => {
        const el = document.getElementById(rowId + '-cind-p-' + p.n);
        compare_to_params[p.n] = el ? parseFloat(el.value) : p.d;
      });
    } else {
      const valEl = document.getElementById(rowId + '-val');
      value = valEl ? parseFloat(valEl.value) : null;
    }
    conds.push({ id: condId, indicator: indKey, params, comparison: cmpVal,
                 value, compare_to_indicator, compare_to_params });
  }
  return conds;
}

/* ===== フィルター ===== */
const BT2_SESSION_PRESETS = {
  tokyo:  { start: 7,  end: 16 },
  london: { start: 17, end: 2  },
  ny:     { start: 22, end: 7  },
};
function bt2OnSession() {
  const val = document.getElementById('bt2-f-session').value;
  const ct  = document.getElementById('bt2-custom-time');
  ct.style.display = val === 'custom' ? 'grid' : 'none';
  if (val && val !== 'custom') {
    const p = BT2_SESSION_PRESETS[val];
    document.getElementById('bt2-f-start-hour').value = p.start;
    document.getElementById('bt2-f-end-hour').value   = p.end;
  }
}
function bt2ToggleWd(btn) { btn.classList.toggle('active'); }

function bt2BuildFilters() {
  const conds = [];
  const session = document.getElementById('bt2-f-session').value;
  if (session) {
    const start = parseInt(document.getElementById('bt2-f-start-hour').value, 10);
    const end   = parseInt(document.getElementById('bt2-f-end-hour').value, 10);
    conds.push({ id:'f-time', indicator:'TIME_RANGE',
                 params:{start_hour:start, end_hour:end},
                 comparison:'filter_pass', value:null,
                 compare_to_indicator:null, compare_to_params:null });
  }
  const activeDays = [...document.querySelectorAll('#bt2-wd-btns .bt2-wd-btn.active')]
                       .map(b => parseInt(b.dataset.wd, 10));
  if (activeDays.length > 0 && activeDays.length < 7) {
    conds.push({ id:'f-weekday', indicator:'WEEKDAY',
                 params:{days:activeDays},
                 comparison:'filter_pass', value:null,
                 compare_to_indicator:null, compare_to_params:null });
  }
  const atrMin = parseFloat(document.getElementById('bt2-f-atr-min').value) || 0;
  const atrMax = parseFloat(document.getElementById('bt2-f-atr-max').value) || 0;
  if (atrMin > 0 || atrMax > 0) {
    conds.push({ id:'f-atr', indicator:'ATR_THRESHOLD',
                 params:{ period: parseInt(document.getElementById('bt2-f-atr-period').value,10),
                          min_pips: atrMin, max_pips: atrMax > 0 ? atrMax : null },
                 comparison:'filter_pass', value:null,
                 compare_to_indicator:null, compare_to_params:null });
  }
  return conds.length ? { logic:'AND', conditions:conds } : null;
}

/* ===== SL / TP / トレーリング ===== */
function bt2OnSlType() {
  const t = document.getElementById('bt2-sl-type').value;
  ['fixed','recentHighLow','atr'].forEach(k => {
    document.getElementById('bt2-sl-' + k).classList.toggle('active', k === t);
  });
}
function bt2OnTpType() {
  const t = document.getElementById('bt2-tp-type').value;
  ['rr','fixed','atr'].forEach(k => {
    document.getElementById('bt2-tp-' + k).classList.toggle('active', k === t);
  });
}
function bt2OnTrailing() {
  const on = document.getElementById('bt2-trailing-on').checked;
  document.getElementById('bt2-trailing-lbl').textContent = on ? 'ON' : 'OFF';
  document.getElementById('bt2-trailing-fields').style.display = on ? 'block' : 'none';
}

function bt2BuildSl() {
  const t = document.getElementById('bt2-sl-type').value;
  if (t === 'fixed')
    return { type:'fixed', pips:parseFloat(document.getElementById('bt2-sl-pips').value)||20,
             lookback_bars:null, buffer_pips:null, atr_period:null, atr_multiplier:null };
  if (t === 'recentHighLow')
    return { type:'recentHighLow', pips:null,
             lookback_bars:parseInt(document.getElementById('bt2-sl-lookback').value),
             buffer_pips:parseFloat(document.getElementById('bt2-sl-buffer').value),
             atr_period:null, atr_multiplier:null };
  return { type:'atr', pips:null, lookback_bars:null, buffer_pips:null,
           atr_period:parseInt(document.getElementById('bt2-sl-atr-period').value),
           atr_multiplier:parseFloat(document.getElementById('bt2-sl-atr-mult').value) };
}
function bt2BuildTp() {
  const t = document.getElementById('bt2-tp-type').value;
  if (t === 'rr')
    return { type:'rr', pips:null,
             rr_ratio:parseFloat(document.getElementById('bt2-tp-rr-ratio').value),
             atr_period:null, atr_multiplier:null };
  if (t === 'fixed')
    return { type:'fixed', pips:parseFloat(document.getElementById('bt2-tp-pips').value)||40,
             rr_ratio:null, atr_period:null, atr_multiplier:null };
  return { type:'atr', pips:null, rr_ratio:null,
           atr_period:parseInt(document.getElementById('bt2-tp-atr-period').value),
           atr_multiplier:parseFloat(document.getElementById('bt2-tp-atr-mult').value) };
}
function bt2BuildTrailing() {
  const on = document.getElementById('bt2-trailing-on').checked;
  return { enabled:on, type:on?'fixedTrailing':null,
           trail_pips:on?parseFloat(document.getElementById('bt2-trail-pips').value):null };
}

async function runBt2Inline() {
  const pairs = [...document.querySelectorAll('.bt2-pair:checked')].map(el => el.value);
  if (!pairs.length) { alert('通貨ペアを1つ以上選択してください'); return; }

  const tfRanges = {};
  document.querySelectorAll('.bt2-tf:checked').forEach(el => {
    const row = el.closest('tr');
    tfRanges[el.value] = {
      start: row.querySelector('.bt2-tf-start').value || null,
      end:   row.querySelector('.bt2-tf-end').value   || null,
    };
  });
  if (!Object.keys(tfRanges).length) { alert('時間足を1つ以上選択してください'); return; }

  const conds = bt2BuildConds();
  if (!conds.length) { alert('条件を1つ以上追加してください'); return; }

  const strategy = {
    strategy_version: '1.0',
    direction:        document.getElementById('bt2-direction').value,
    entry_conditions: { logic: _bt2Logic, conditions: conds },
    filters:          bt2BuildFilters(),
    sl_config:        bt2BuildSl(),
    tp_config:        bt2BuildTp(),
    trailing_config:  bt2BuildTrailing(),
  };
  const simParams = {
    initial_capital:  parseFloat(document.getElementById('bt2-capital').value)   || 1000000,
    pip_value:        parseFloat(document.getElementById('bt2-pip-value').value)  || 100,
    max_bars_to_exit: parseInt(document.getElementById('bt2-max-bars').value, 10) || 200,
  };

  const btn   = document.getElementById('bt2-run-btn');
  const log   = document.getElementById('bt2-log');
  const tbl   = document.getElementById('bt2-result-tbl');
  const tbody = document.getElementById('bt2-result-body');
  const saveWrap = document.getElementById('bt2-save-wrap');
  btn.disabled = true;
  tbody.innerHTML = '';
  tbl.style.display = 'none';
  saveWrap.style.display = 'none';
  _bt2InlineResults = [];

  const tfs   = Object.keys(tfRanges);
  const total = pairs.length * tfs.length;
  let done    = 0;
  const TF_LBL = {'5min':'5分足','15min':'15分足','30min':'30分足','1hr':'1時間足','4hr':'4時間足','daily':'日足'};

  for (const tf of tfs) {
    const rng = tfRanges[tf];
    for (const pair of pairs) {
      done++;
      log.textContent = `実行中 (${done}/${total}): ${pair} ${TF_LBL[tf]||tf}...`;
      const tr = document.createElement('tr');
      try {
        const payload = {
          action: 'bt_v2', pair, timeframe: tf,
          strategy_config: strategy, sim_params: simParams,
        };
        if (rng.start && rng.end) {
          payload.start_date = rng.start;
          payload.end_date   = rng.end;
        } else {
          payload.limit = 500;
        }
        const res = await fetch('/admin/api.php', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body:   JSON.stringify(payload),
        }).then(r => r.json());

        if (!res.ok) {
          tr.innerHTML = `<td>${pair}</td><td>${TF_LBL[tf]||tf}</td>
            <td colspan="5" style="color:#ef4444;font-size:11px">${res.error||'APIエラー'}</td>`;
        } else {
          const m  = res.metrics || {};
          const wr = m.win_rate != null ? (m.win_rate * 100).toFixed(1) : null;
          const wc = m.win_rate >= 0.55 ? '#4ade80' : m.win_rate >= 0.40 ? '#facc15' : '#f87171';
          const pf = m.profit_factor != null ? (isFinite(m.profit_factor) ? m.profit_factor.toFixed(2) : '∞') : '-';
          const tp = m.total_profit  != null ? Math.round(m.total_profit).toLocaleString() : '-';
          const period = [rng.start, rng.end].filter(Boolean).join('〜') || `${m.total_trades||0}本`;
          tr.innerHTML = `<td>${pair}</td><td>${TF_LBL[tf]||tf}</td>
            <td style="color:${wr!=null?wc:'#64748b'};font-weight:600">${wr!=null?wr+'%':'-'}</td>
            <td>${pf}</td><td>${m.total_trades||0}件</td>
            <td style="color:${m.total_profit>=0?'#4ade80':'#f87171'}">${tp}円</td>
            <td style="font-size:11px;color:#64748b">${period}</td>`;
          // 保存用に結果を蓄積（トレード履歴は最新20件に制限）
          _bt2InlineResults.push({ pair, tf, metrics: m, trades: (res.trades || []).slice(-20) });
        }
      } catch(e) {
        tr.innerHTML = `<td>${pair}</td><td>${TF_LBL[tf]||tf}</td>
          <td colspan="5" style="color:#ef4444;font-size:11px">${e.message}</td>`;
      }
      tbody.appendChild(tr);
      tbl.style.display = 'table';
    }
  }

  btn.disabled = false;
  log.textContent = `完了（${total}件実行）`;

  // 成功した結果が1件以上あれば保存セクションを表示
  if (_bt2InlineResults.length > 0) {
    saveWrap.style.display = 'block';
    document.getElementById('bt2-save-status').textContent = '';
  }
}

async function saveBt2InlineStrategy() {
  const name = document.getElementById('bt2-save-name').value.trim();
  if (!name) { alert('戦略名を入力してください'); return; }
  if (!_bt2InlineResults.length) { alert('先にバックテストを実行してください'); return; }

  const btn  = document.getElementById('bt2-save-btn');
  const stat = document.getElementById('bt2-save-status');
  btn.disabled = true;
  stat.textContent = '保存中...';
  stat.style.color = '#94a3b8';

  try {
    // 全結果から集計サマリーを作成
    let totalTrades = 0, totalWins = 0, totalPf = 0, pfCount = 0;
    for (const r of _bt2InlineResults) {
      const m = r.metrics;
      totalTrades += (m.total_trades || 0);
      totalWins   += Math.round((m.win_rate || 0) * (m.total_trades || 0));
      if (m.profit_factor != null && isFinite(m.profit_factor)) {
        totalPf += m.profit_factor; pfCount++;
      }
    }
    const btResult = {
      win_rate:      totalTrades > 0 ? totalWins / totalTrades : null,
      profit_factor: pfCount > 0 ? totalPf / pfCount : null,
      total_trades:  totalTrades,
      per_pair:      Object.fromEntries(_bt2InlineResults.map(r => [`${r.pair}_${r.tf}`, r.metrics])),
      trades_by_key: Object.fromEntries(_bt2InlineResults.filter(r => r.trades?.length).map(r => [`${r.pair}_${r.tf}`, r.trades])),
    };

    const config = {
      strategy:   {
        strategy_version: '1.0',
        direction:        document.getElementById('bt2-direction').value,
        entry_conditions: { logic: _bt2Logic, conditions: bt2BuildConds() },
        filters:          bt2BuildFilters(),
        sl_config:        bt2BuildSl(),
        tp_config:        bt2BuildTp(),
        trailing_config:  bt2BuildTrailing(),
      },
      sim_params: {
        initial_capital:  parseFloat(document.getElementById('bt2-capital').value)   || 1000000,
        pip_value:        parseFloat(document.getElementById('bt2-pip-value').value)  || 100,
        max_bars_to_exit: parseInt(document.getElementById('bt2-max-bars').value, 10) || 200,
      },
    };

    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        action:            'save_strategy',
        name,
        config,
        linked_indicator:  <?= json_encode($indicator_name ?: '') ?>,
        bt_result:         btResult,
      }),
    }).then(r => r.json());

    if (!res.ok) {
      stat.textContent = '❌ ' + (res.error || '保存エラー');
      stat.style.color = '#ef4444';
    } else {
      stat.textContent = '✅ 保存しました';
      stat.style.color = '#4ade80';
      document.getElementById('bt2-save-name').value = '';
      await loadLinkedStrategies();
      setTimeout(() => { stat.textContent = ''; }, 4000);
    }
  } catch(e) {
    stat.textContent = '❌ ' + e.message;
    stat.style.color = '#ef4444';
  } finally {
    btn.disabled = false;
  }
}

// 初期条件を1つ追加
addBt2Cond();
</script>
<?php endif; ?>
</main>

<script>
const ARTICLE_KEY    = <?= json_encode($article['key']) ?>;
const IS_INDICATOR   = <?= $is_indicator ? 'true' : 'false' ?>;
const IS_PAIR        = <?= $is_pair ? 'true' : 'false' ?>;
const IND_SLUG       = <?= json_encode($ind_slug) ?>;
const PAIR_SLUG      = <?= json_encode($pair_slug) ?>;
const AI_NOTES_KEY   = IND_SLUG ? ('indicator_ai_notes_' + IND_SLUG) : '';

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
        // AIフィードバックを復元
        if (AI_NOTES_KEY && document.getElementById('ai-feedback-ta')) {
          const notes = data[AI_NOTES_KEY];
          if (notes?.value) {
            document.getElementById('ai-feedback-ta').value = notes.value;
            document.getElementById('ai-fb-updated').textContent = '最終保存: ' + (notes.updated_at || '').slice(0,16);
          }
        }
      }
      if (IS_PAIR) {
        const cssEl = document.getElementById('editor-css');
        if (cssEl) cssEl.value = data[ARTICLE_KEY + '_css']?.value || '';
      }
    }
  } catch(e) {
    console.error('Failed to load content', e);
  } finally {
    document.getElementById('loading-overlay').style.display = 'none';
  }
  // リンク済み戦略を取得
  if (IS_INDICATOR && <?= json_encode($indicator_name) ?>) {
    loadLinkedStrategies();
  }
}

async function saveAiFeedback() {
  if (!AI_NOTES_KEY) return;
  const val  = document.getElementById('ai-feedback-ta').value;
  const btn  = document.querySelector('.ai-fb-save-btn');
  const stat = document.getElementById('ai-fb-status');
  btn.disabled = true;
  stat.textContent = '保存中...'; stat.className = 'ai-fb-status';
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'content_save', key: AI_NOTES_KEY, value: val}),
    }).then(r => r.json());
    if (res.status === 'ok') {
      stat.textContent = '✓ 保存しました'; stat.className = 'ai-fb-status ok';
      document.getElementById('ai-fb-updated').textContent = '最終保存: ' + new Date().toLocaleString('ja-JP');
    } else {
      stat.textContent = 'エラー: ' + (res.message || ''); stat.className = 'ai-fb-status err';
    }
  } catch(e) {
    stat.textContent = 'ネットワークエラー'; stat.className = 'ai-fb-status err';
  }
  btn.disabled = false;
  setTimeout(() => { stat.textContent = ''; stat.className = 'ai-fb-status'; }, 4000);
}

function aiFbTab(mode, btn) {
  const ta  = document.getElementById('ai-feedback-ta');
  const pre = document.getElementById('ai-fb-preview');
  document.querySelectorAll('.ai-fb-tab-btn').forEach(b => {
    b.style.background = '#1e293b'; b.style.color = '#94a3b8';
  });
  btn.style.background = '#0e7490'; btn.style.color = '#fff';
  if (mode === 'preview') {
    pre.innerHTML = ta.value;
    ta.style.display  = 'none';
    pre.style.display = 'block';
  } else {
    ta.style.display  = 'block';
    pre.style.display = 'none';
  }
}

function aiFbSyncPreview() {
  const pre = document.getElementById('ai-fb-preview');
  if (pre.style.display !== 'none') {
    pre.innerHTML = document.getElementById('ai-feedback-ta').value;
  }
}

async function loadLinkedStrategies() {
  const wrap = document.getElementById('linked-strategies-wrap');
  if (!wrap) return;
  try {
    const res = await fetch('/admin/api.php?action=get_linked_strategies', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({indicator_name: <?= json_encode($indicator_name) ?>}),
    }).then(r => r.json());
    if (!res.ok || !res.strategies?.length) {
      wrap.innerHTML = '<span style="font-size:12px;color:#334155">保存済み戦略はありません</span>';
      return;
    }
    wrap.innerHTML = res.strategies.map(s => {
      const wr  = s.win_rate  != null ? `<span class="ls-wr">${(parseFloat(s.win_rate) * 100).toFixed(1)}%</span>` : '';
      const pf  = s.pf        != null ? `<span>PF ${parseFloat(s.pf).toFixed(2)}</span>` : '';
      const tr  = s.trades    != null ? `<span>${s.trades}件</span>` : '';
      const ran = s.bt_ran_at ? s.bt_ran_at.slice(0,10) : '未実行';
      return `<div class="ls-item">
        <div class="ls-body">
          <div class="ls-name">${s.name.replace(/</g,'&lt;')}</div>
          <div class="ls-meta">${wr}${pf}${tr}<span>${ran}</span></div>
        </div>
        <a class="ls-dl" title="CSVダウンロード"
           href="/admin/api.php?action=bt2_csv&id=${s.id}"
           target="_blank">⬇</a>
        <button class="ls-del" title="削除" onclick="deleteStrategy(${s.id})">×</button>
      </div>`;
    }).join('');
  } catch(e) {
    wrap.innerHTML = '<span style="font-size:12px;color:#475569">読み込みエラー</span>';
  }
}

async function deleteStrategy(id) {
  if (!confirm('この戦略を削除しますか？\n（generate_static.py を再実行するまで公開ページには反映されません）')) return;
  try {
    const res = await fetch('/admin/api.php?action=delete_strategy', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id}),
    }).then(r => r.json());
    if (!res.ok) { alert('削除失敗: ' + (res.error || '')); return; }
    await loadLinkedStrategies();
  } catch(e) {
    alert('エラー: ' + e.message);
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
    if (IS_PAIR) {
      const cssEl = document.getElementById('editor-css');
      if (cssEl) saves.push(_save(ARTICLE_KEY + '_css', cssEl.value));
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

async function rebuildPage() {
  const btn  = document.getElementById('rebuild-btn');
  const stat = document.getElementById('rebuild-status');
  const log  = document.getElementById('rebuild-log');
  if (!btn || (!IND_SLUG && !PAIR_SLUG)) return;
  btn.disabled   = true;
  stat.textContent = 'ビルド中...';
  stat.className   = 'rebuild-status running';
  if (log) { log.textContent = ''; log.style.display = 'none'; }
  try {
    const action = IS_PAIR ? 'rebuild_pair_page' : 'rebuild_indicator_page';
    const body   = IS_PAIR ? { pair: PAIR_SLUG } : { slug: IND_SLUG };
    const res = await fetch('/admin/api.php?action=' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) {
      stat.textContent = '✅ 更新完了';
      stat.className   = 'rebuild-status ok';
      setTimeout(() => { stat.textContent = ''; stat.className = 'rebuild-status'; }, 5000);
    } else {
      stat.textContent = '❌ 失敗';
      stat.className   = 'rebuild-status err';
      if (log && data.output) {
        log.textContent = data.output;
        log.style.display = 'block';
      }
    }
    if (log && data.output && data.ok) {
      // 成功時も最終行だけ小さく表示
      const lastLine = data.output.trim().split('\n').pop();
      if (lastLine) {
        log.textContent = lastLine;
        log.style.display = 'block';
      }
    }
  } catch(e) {
    stat.textContent = '❌ ネットワークエラー';
    stat.className   = 'rebuild-status err';
  } finally {
    btn.disabled = false;
  }
}

loadContent();
</script>
</body>
</html>
