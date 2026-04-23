<?php
/**
 * 内部リンクマップ
 * site_content の記事HTMLから <a href> を抽出してグラフ可視化
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();

// ---- ページ定義（seo.php の PAGES と同一） ----
$PAGES = [
  ['type'=>'page',     'key'=>'top',                 'cat'=>'main',        'name'=>'TOPページ',               'url'=>'/'],
  ['type'=>'page',     'key'=>'ranking',             'cat'=>'main',        'name'=>'ランキング',               'url'=>'/technical-ranking/'],
  ['type'=>'signals',  'key'=>'index',               'cat'=>'main',        'name'=>'シグナル',                 'url'=>'/signals/'],
  ['type'=>'pair',     'key'=>'usdjpy',              'cat'=>'main',        'name'=>'ドル円',                   'url'=>'/usdjpy/'],
  ['type'=>'pair',     'key'=>'gbpjpy',              'cat'=>'main',        'name'=>'ポンド円',                 'url'=>'/gbpjpy/'],
  ['type'=>'pair',     'key'=>'eurjpy',              'cat'=>'main',        'name'=>'ユーロ円',                 'url'=>'/eurjpy/'],
  ['type'=>'category', 'key'=>'oscillator',          'cat'=>'category',    'name'=>'オシレーター',             'url'=>'/oscillator/'],
  ['type'=>'category', 'key'=>'trend',               'cat'=>'category',    'name'=>'トレンド',                 'url'=>'/trend/'],
  ['type'=>'category', 'key'=>'line',                'cat'=>'category',    'name'=>'ライン',                   'url'=>'/line/'],
  ['type'=>'category', 'key'=>'volatility',          'cat'=>'category',    'name'=>'ボラティリティ',           'url'=>'/volatility/'],
  ['type'=>'category', 'key'=>'candlestick',         'cat'=>'category',    'name'=>'ローソク足',               'url'=>'/candlestick/'],
  ['type'=>'category', 'key'=>'composite',           'cat'=>'category',    'name'=>'コンポジット',             'url'=>'/composite/'],
  ['type'=>'category', 'key'=>'bbsl',                'cat'=>'category',    'name'=>'BBバンドSL',               'url'=>'/bbsl/'],
  ['type'=>'indicator','key'=>'rsi',                 'cat'=>'oscillator',  'name'=>'RSI',                      'url'=>'/oscillator/rsi/'],
  ['type'=>'indicator','key'=>'macd',                'cat'=>'oscillator',  'name'=>'MACD',                     'url'=>'/oscillator/macd/'],
  ['type'=>'indicator','key'=>'stochastic',          'cat'=>'oscillator',  'name'=>'ストキャス',               'url'=>'/oscillator/stochastic/'],
  ['type'=>'indicator','key'=>'cci',                 'cat'=>'oscillator',  'name'=>'CCI',                      'url'=>'/oscillator/cci/'],
  ['type'=>'indicator','key'=>'williams_r',          'cat'=>'oscillator',  'name'=>'W%R',                      'url'=>'/oscillator/williams_r/'],
  ['type'=>'indicator','key'=>'sma20',               'cat'=>'trend',       'name'=>'SMA 20',                   'url'=>'/trend/sma20/'],
  ['type'=>'indicator','key'=>'sma50',               'cat'=>'trend',       'name'=>'SMA 50',                   'url'=>'/trend/sma50/'],
  ['type'=>'indicator','key'=>'sma_cross',           'cat'=>'trend',       'name'=>'SMAクロス',                'url'=>'/trend/sma_cross/'],
  ['type'=>'indicator','key'=>'ema_cross',           'cat'=>'trend',       'name'=>'EMAクロス',                'url'=>'/trend/ema_cross/'],
  ['type'=>'indicator','key'=>'ema21',               'cat'=>'trend',       'name'=>'EMA 21',                   'url'=>'/trend/ema21/'],
  ['type'=>'indicator','key'=>'bollinger_bands',     'cat'=>'trend',       'name'=>'ボリンジャーBB',           'url'=>'/trend/bollinger_bands/'],
  ['type'=>'indicator','key'=>'bb_squeeze',          'cat'=>'trend',       'name'=>'BBスクイーズ',             'url'=>'/trend/bb_squeeze/'],
  ['type'=>'indicator','key'=>'pivot',               'cat'=>'line',        'name'=>'ピボット',                 'url'=>'/line/pivot/'],
  ['type'=>'indicator','key'=>'fibonacci',           'cat'=>'line',        'name'=>'フィボナッチ',             'url'=>'/line/fibonacci/'],
  ['type'=>'indicator','key'=>'support_resistance',  'cat'=>'line',        'name'=>'動的SR',                   'url'=>'/line/support_resistance/'],
  ['type'=>'indicator','key'=>'atr',                 'cat'=>'volatility',  'name'=>'ATR',                      'url'=>'/volatility/atr/'],
  ['type'=>'indicator','key'=>'volatility_index',    'cat'=>'volatility',  'name'=>'ボラインデックス',         'url'=>'/volatility/volatility_index/'],
  ['type'=>'indicator','key'=>'hammer',              'cat'=>'candlestick', 'name'=>'ハンマー',                 'url'=>'/candlestick/hammer/'],
  ['type'=>'indicator','key'=>'inverted_hammer',     'cat'=>'candlestick', 'name'=>'逆ハンマー',               'url'=>'/candlestick/inverted_hammer/'],
  ['type'=>'indicator','key'=>'doji',                'cat'=>'candlestick', 'name'=>'十字線',                   'url'=>'/candlestick/doji/'],
  ['type'=>'indicator','key'=>'bullish_engulfing',   'cat'=>'candlestick', 'name'=>'強気包み足',               'url'=>'/candlestick/bullish_engulfing/'],
  ['type'=>'indicator','key'=>'bearish_engulfing',   'cat'=>'candlestick', 'name'=>'弱気包み足',               'url'=>'/candlestick/bearish_engulfing/'],
  ['type'=>'indicator','key'=>'three_white_soldiers','cat'=>'candlestick', 'name'=>'三白兵',                   'url'=>'/candlestick/three_white_soldiers/'],
  ['type'=>'indicator','key'=>'three_black_crows',   'cat'=>'candlestick', 'name'=>'三羽烏',                   'url'=>'/candlestick/three_black_crows/'],
  ['type'=>'indicator','key'=>'pin_bar',             'cat'=>'candlestick', 'name'=>'ピンバー',                 'url'=>'/candlestick/pin_bar/'],
];

// URL → ページID のマップを構築
$urlToId = [];
foreach ($PAGES as $p) {
    $urlToId[$p['url']] = $p['type'] . '_' . $p['key'];
}

// ---- DBから記事コンテンツを取得 ----
$articles = [];   // pageId => combined html
try {
    $pdo  = get_pdo();
    $rows = $pdo->query("SELECT content_key, content_value FROM site_content WHERE content_key NOT LIKE 'seo_strategy_%' AND content_value IS NOT NULL AND content_value != ''")->fetchAll();
    foreach ($rows as $r) {
        $k = $r['content_key'];
        $v = $r['content_value'];

        // キーからページIDを判定
        $pageId = null;
        if ($k === 'top_article' || $k === 'top_article_pre' || $k === 'top_article_post') {
            $pageId = 'page_top';
        } elseif (str_starts_with($k, 'indicator_article_') && !str_contains($k, '_css') && !str_contains($k, '_jsonld')) {
            $slug   = substr($k, strlen('indicator_article_'));
            $pageId = 'indicator_' . $slug;
        } elseif (str_starts_with($k, 'pair_article_') && !str_contains($k, '_css') && !str_contains($k, '_heading')) {
            $pair   = substr($k, strlen('pair_article_'));
            $pageId = 'pair_' . $pair;
        } elseif ($k === 'ranking_analysis' || $k === 'ranking_intro' || $k === 'ranking_title') {
            $pageId = 'page_ranking';
        } elseif ($k === 'signals_intro' || $k === 'signals_heading') {
            $pageId = 'signals_index';
        }

        if ($pageId) {
            $articles[$pageId] = ($articles[$pageId] ?? '') . ' ' . $v;
        }
    }
} catch (Exception $e) {
    $articles = [];
}

// ---- 記事HTMLからhrefを抽出してエッジ生成 ----
$articleLinks  = [];   // [{source, target, label}]
$articleLinkSet = []; // 重複排除用

foreach ($articles as $pageId => $html) {
    if (!$html) continue;
    // href="/..." または href='...' を抽出
    preg_match_all('/href=["\']([^"\']+)["\']/i', $html, $matches);
    foreach ($matches[1] as $href) {
        // 内部リンクのみ（/で始まり、//でない）
        if (!str_starts_with($href, '/') || str_starts_with($href, '//')) continue;
        // クエリ・アンカーを除去
        $path = strtok($href, '?#');
        // 末尾スラッシュ正規化
        if ($path !== '/' && !str_ends_with($path, '/')) $path .= '/';

        $targetId = $urlToId[$path] ?? null;
        if (!$targetId || $targetId === $pageId) continue;

        $edgeKey = $pageId . '|' . $targetId;
        if (!isset($articleLinkSet[$edgeKey])) {
            $articleLinkSet[$edgeKey] = true;
            $articleLinks[] = ['source' => $pageId, 'target' => $targetId, 'type' => 'article'];
        }
    }
}

// ---- 構造リンク（カテゴリ → 指標） ----
$structLinks = [];
foreach ($PAGES as $p) {
    if ($p['type'] !== 'indicator') continue;
    $structLinks[] = [
        'source' => 'category_' . $p['cat'],
        'target' => 'indicator_' . $p['key'],
        'type'   => 'structural',
    ];
}
// TOPページの構造リンク
foreach (['page_ranking','signals_index','pair_usdjpy','pair_gbpjpy','pair_eurjpy',
          'category_oscillator','category_trend','category_line','category_volatility',
          'category_candlestick','category_composite','category_bbsl'] as $t) {
    $structLinks[] = ['source'=>'page_top','target'=>$t,'type'=>'structural'];
}

// ---- ノードの被リンク数（ランキング用） ----
$inDegree = [];
foreach (array_merge($articleLinks, $structLinks) as $l) {
    $inDegree[$l['target']] = ($inDegree[$l['target']] ?? 0) + 1;
}

// ---- ノードデータ ----
$nodes = [];
foreach ($PAGES as $p) {
    $id      = $p['type'] . '_' . $p['key'];
    $hasArticle = isset($articles[$id]);
    $nodes[] = [
        'id'         => $id,
        'label'      => $p['name'],
        'url'        => $p['url'],
        'type'       => $p['type'],
        'cat'        => $p['cat'],
        'hasArticle' => $hasArticle,
        'inDegree'   => $inDegree[$id] ?? 0,
    ];
}

// ---- 統計 ----
$totalNodes   = count($nodes);
$articleCount = count($articleLinks);
$structCount  = count($structLinks);
$withArticle  = count($articles);
$orphans      = array_filter($nodes, fn($n) => ($inDegree[$n['id']] ?? 0) === 0 && $n['type'] === 'indicator');

$graphData = json_encode([
    'nodes' => $nodes,
    'links' => array_merge($structLinks, $articleLinks),
], JSON_UNESCAPED_UNICODE);
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>内部リンクマップ | AI×FX 管理</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;height:100vh;overflow:hidden;display:flex;flex-direction:column}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
/* ツールバー */
#toolbar{background:#1a2234;border-bottom:1px solid #1e293b;padding:8px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0}
.stats-chip{background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:4px 10px;font-size:11px;color:#64748b;white-space:nowrap}
.stats-chip b{color:#e2e8f0}
.ctrl-btn{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:6px;padding:5px 12px;font-size:11px;cursor:pointer;transition:all .15s;white-space:nowrap}
.ctrl-btn:hover{border-color:#475569;color:#e2e8f0}
.ctrl-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.ctrl-btn.warn{background:#1a0f0f;border-color:#dc2626;color:#f87171}
.ctrl-btn.warn.active{background:#7f1d1d}
#search-box{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:5px 10px;font-size:12px;outline:none;width:160px}
#search-box:focus{border-color:#3b82f6}
.legend{display:flex;gap:12px;margin-left:auto;flex-wrap:wrap}
.leg-item{display:flex;align-items:center;gap:5px;font-size:10px;color:#64748b}
.leg-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
/* グラフエリア */
#graph-wrap{flex:1;position:relative;overflow:hidden}
svg{width:100%;height:100%}
/* ノード */
.node circle{cursor:pointer}
.node text{pointer-events:none;font-size:9px;fill:#94a3b8;font-family:-apple-system,sans-serif}
.node.highlighted circle{filter:drop-shadow(0 0 6px currentColor)}
.node.faded{opacity:.15}
/* エッジ */
.link{fill:none}
.link.structural{stroke:#1e3a5f;stroke-width:1;stroke-opacity:.6}
.link.article{stroke:#3b82f6;stroke-width:1.5;stroke-opacity:.7}
/* ツールチップ */
#tooltip{position:fixed;background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 16px;font-size:12px;pointer-events:none;opacity:0;transition:opacity .15s;z-index:100;min-width:200px;max-width:260px;box-shadow:0 8px 24px rgba(0,0,0,.4)}
.tt-title{font-weight:700;color:#f1f5f9;font-size:13px;margin-bottom:4px}
.tt-url{font-size:10px;color:#60a5fa;font-family:monospace;margin-bottom:8px}
.tt-row{display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-top:3px}
.tt-row b{color:#e2e8f0}
.tt-badge{display:inline-block;font-size:9px;font-weight:700;border-radius:3px;padding:2px 6px;margin-top:5px}
.tt-hint{font-size:10px;color:#475569;margin-top:8px;border-top:1px solid #1e293b;padding-top:6px}
/* 孤立ページパネル */
#orphan-panel{position:absolute;bottom:12px;right:12px;background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 14px;max-width:220px;font-size:11px;color:#64748b;display:none}
#orphan-panel h4{font-size:12px;font-weight:600;color:#f87171;margin-bottom:6px}
#orphan-panel li{margin-left:14px;margin-top:2px;color:#94a3b8}
/* 操作ヒント */
#hint{position:absolute;bottom:12px;left:12px;font-size:10px;color:#334155}
</style>
</head>
<body>
<header>
  <h1>🗺 内部リンクマップ</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/articles.php">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/article_map.php" class="active">リンクマップ</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>

<div id="toolbar">
  <div class="stats-chip">ページ数: <b><?= $totalNodes ?></b></div>
  <div class="stats-chip">記事リンク: <b><?= $articleCount ?></b></div>
  <div class="stats-chip">構造リンク: <b><?= $structCount ?></b></div>
  <div class="stats-chip">記事あり: <b><?= $withArticle ?></b> / <?= $totalNodes ?></div>
  <?php if (count($orphans)): ?>
  <div class="stats-chip" style="border-color:#7f1d1d;color:#f87171">被リンク0: <b><?= count($orphans) ?></b></div>
  <?php endif; ?>
  <button class="ctrl-btn active" id="btn-structural" onclick="toggleType('structural',this)">構造リンク</button>
  <button class="ctrl-btn active" id="btn-article"    onclick="toggleType('article',this)">記事リンク</button>
  <button class="ctrl-btn <?= count($orphans)?'warn':'' ?>" id="btn-orphan" onclick="toggleOrphan(this)">被リンクなし</button>
  <input type="text" id="search-box" placeholder="ページ名で検索..." oninput="doSearch(this.value)">
  <button class="ctrl-btn" onclick="resetZoom()">表示リセット</button>
  <div class="legend">
    <div class="leg-item"><div class="leg-dot" style="background:#22c55e"></div>主要</div>
    <div class="leg-item"><div class="leg-dot" style="background:#a855f7"></div>通貨ペア</div>
    <div class="leg-item"><div class="leg-dot" style="background:#3b82f6"></div>カテゴリ</div>
    <div class="leg-item"><div class="leg-dot" style="background:#06b6d4"></div>オシレーター</div>
    <div class="leg-item"><div class="leg-dot" style="background:#8b5cf6"></div>トレンド</div>
    <div class="leg-item"><div class="leg-dot" style="background:#f59e0b"></div>ライン</div>
    <div class="leg-item"><div class="leg-dot" style="background:#ef4444"></div>ボラティリティ</div>
    <div class="leg-item"><div class="leg-dot" style="background:#ec4899"></div>ローソク足</div>
  </div>
</div>

<div id="graph-wrap">
  <svg id="graph"></svg>

  <?php if (count($orphans)): ?>
  <div id="orphan-panel">
    <h4>⚠ 被リンクなし（指標）</h4>
    <ul>
    <?php foreach ($orphans as $o): ?>
      <li><?= htmlspecialchars($o['name']) ?></li>
    <?php endforeach; ?>
    </ul>
  </div>
  <?php endif; ?>

  <div id="hint">ホバー: 詳細 ／ クリック: 関連リンク強調 ／ ダブルクリック: ページを開く ／ スクロール: ズーム</div>
</div>

<div id="tooltip">
  <div class="tt-title" id="tt-title"></div>
  <div class="tt-url"   id="tt-url"></div>
  <div class="tt-row"><span>発リンク</span><b id="tt-out">0</b></div>
  <div class="tt-row"><span>被リンク</span><b id="tt-in">0</b></div>
  <div id="tt-badge-wrap"></div>
  <div class="tt-hint" id="tt-hint"></div>
</div>

<script>
const RAW = <?= $graphData ?>;

// ---- カラー ----
const TYPE_COLOR = {main:'#22c55e', pair:'#a855f7', category:'#3b82f6', indicator:'#64748b', signals:'#22c55e'};
const CAT_COLOR  = {oscillator:'#06b6d4', trend:'#8b5cf6', line:'#f59e0b', volatility:'#ef4444', candlestick:'#ec4899', composite:'#6366f1', bbsl:'#84cc16', main:'#22c55e'};

function nodeColor(d) {
  if (d.type === 'indicator') return CAT_COLOR[d.cat] || '#64748b';
  if (d.type === 'category')  return CAT_COLOR[d.cat] || '#3b82f6';
  return TYPE_COLOR[d.type] || '#64748b';
}
function nodeRadius(d) {
  if (d.type === 'page' || d.type === 'signals') return 18;
  if (d.type === 'pair')     return 14;
  if (d.type === 'category') return 15;
  return 9 + Math.min(d.inDegree * 1.2, 6);
}

// ---- SVG セットアップ ----
const wrap   = document.getElementById('graph-wrap');
const svg    = d3.select('#graph');
const W = () => wrap.clientWidth;
const H = () => wrap.clientHeight;

const zoomBehavior = d3.zoom().scaleExtent([.05, 5]).on('zoom', e => root.attr('transform', e.transform));
svg.call(zoomBehavior);

const root = svg.append('g');

// マーカー
const defs = svg.append('defs');
['article','structural'].forEach(t => {
  defs.append('marker').attr('id','arr-'+t)
    .attr('viewBox','0 -4 8 8').attr('refX',16).attr('refY',0)
    .attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto')
    .append('path').attr('d','M0,-4L8,0L0,4Z')
    .attr('fill', t==='article'?'#3b82f6':'#1e3a5f').attr('opacity',.8);
});

// ---- エッジ ----
const linkG = root.append('g');
let linkSel = linkG.selectAll('line')
  .data(RAW.links).join('line')
  .attr('class', d => 'link '+d.type)
  .attr('marker-end', d => 'url(#arr-'+d.type+')');

// ---- ノード ----
const nodeG = root.append('g');
let nodeSel = nodeG.selectAll('g')
  .data(RAW.nodes).join('g')
  .attr('class','node')
  .call(d3.drag()
    .on('start',(e,d)=>{ if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x;d.fy=d.y; })
    .on('drag', (e,d)=>{ d.fx=e.x;d.fy=e.y; })
    .on('end',  (e,d)=>{ if(!e.active) sim.alphaTarget(0); d.fx=null;d.fy=null; })
  );

nodeSel.append('circle')
  .attr('r', nodeRadius)
  .attr('fill',  d => nodeColor(d)+'28')
  .attr('stroke',nodeColor)
  .attr('stroke-width', d => d.type==='page'||d.type==='signals'?2.5:1.5)
  .attr('stroke-dasharray', d => d.hasArticle ? null : '3,2');

nodeSel.append('text')
  .attr('dy', d => nodeRadius(d) + 11)
  .attr('text-anchor','middle')
  .text(d => d.label);

// ---- シミュレーション ----
const sim = d3.forceSimulation(RAW.nodes)
  .force('link',      d3.forceLink(RAW.links).id(d=>d.id).distance(d => d.type==='structural'?75:130).strength(.6))
  .force('charge',    d3.forceManyBody().strength(-220))
  .force('center',    d3.forceCenter(W()/2, H()/2))
  .force('collision', d3.forceCollide().radius(d=>nodeRadius(d)+6))
  .on('tick', tick);

function tick() {
  linkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
         .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  nodeSel.attr('transform',d=>`translate(${d.x},${d.y})`);
}

// ---- ツールチップ ----
const tt = document.getElementById('tooltip');
nodeSel
  .on('mouseover',(e,d)=>{
    const outLinks = RAW.links.filter(l => l.source.id===d.id||l.source===d.id);
    const inLinks  = RAW.links.filter(l => l.target.id===d.id||l.target===d.id);
    document.getElementById('tt-title').textContent = d.label;
    document.getElementById('tt-url').textContent   = d.url;
    document.getElementById('tt-out').textContent   = outLinks.length;
    document.getElementById('tt-in').textContent    = inLinks.length;
    const bw = document.getElementById('tt-badge-wrap');
    bw.innerHTML = '';
    if (d.hasArticle) bw.innerHTML += '<span class="tt-badge" style="background:#14532d;color:#4ade80">記事あり</span> ';
    else bw.innerHTML += '<span class="tt-badge" style="background:#1e293b;color:#475569">記事なし</span> ';
    document.getElementById('tt-hint').textContent = 'ダブルクリックでページを開く';
    tt.style.opacity = 1;
  })
  .on('mousemove', e=>{
    const bx = document.getElementById('graph-wrap').getBoundingClientRect();
    const x  = e.clientX + 16, y = e.clientY - 10;
    tt.style.left = (x + 270 > window.innerWidth ? e.clientX - 270 : x) + 'px';
    tt.style.top  = Math.min(y, window.innerHeight - 160) + 'px';
  })
  .on('mouseout', ()=>{ tt.style.opacity=0; })
  .on('click', (e,d)=>{ e.stopPropagation(); highlightNode(d); })
  .on('dblclick', (e,d)=>{ window.open(d.url,'_blank'); });

// ---- ハイライト ----
let highlighted = null;
function highlightNode(d) {
  if (highlighted === d.id) {
    highlighted = null;
    nodeSel.classed('faded',false).classed('highlighted',false);
    linkSel.classed('faded',false);
    return;
  }
  highlighted = d.id;
  const connected = new Set([d.id]);
  RAW.links.forEach(l => {
    const sid = l.source.id||l.source, tid = l.target.id||l.target;
    if (sid===d.id) connected.add(tid);
    if (tid===d.id) connected.add(sid);
  });
  nodeSel.classed('faded', n => !connected.has(n.id))
         .classed('highlighted', n => n.id===d.id);
  linkSel.classed('faded', l => {
    const sid=l.source.id||l.source, tid=l.target.id||l.target;
    return sid!==d.id && tid!==d.id;
  });
}
svg.on('click', ()=>{
  if (highlighted) {
    highlighted = null;
    nodeSel.classed('faded',false).classed('highlighted',false);
    linkSel.classed('faded',false);
  }
});

// ---- フィルタ ----
const visibility = {structural:true, article:true, orphan:false};
function toggleType(type, btn) {
  visibility[type] = !visibility[type];
  btn.classList.toggle('active');
  linkSel.filter(d=>d.type===type).style('display', visibility[type]?null:'none');
}
function toggleOrphan(btn) {
  visibility.orphan = !visibility.orphan;
  btn.classList.toggle('active');
  const panel = document.getElementById('orphan-panel');
  if (panel) panel.style.display = visibility.orphan ? '' : 'none';
  nodeSel.filter(d => d.type==='indicator' && d.inDegree===0)
    .classed('faded', !visibility.orphan)
    .style('display', null);
}

// ---- 検索 ----
function doSearch(q) {
  if (!q) {
    nodeSel.classed('faded',false);
    return;
  }
  const lower = q.toLowerCase();
  nodeSel.classed('faded', d => !d.label.toLowerCase().includes(lower) && !d.url.toLowerCase().includes(lower));
}

// ---- ズームリセット ----
function resetZoom() {
  svg.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity);
}

// ---- リサイズ対応 ----
window.addEventListener('resize', () => {
  sim.force('center', d3.forceCenter(W()/2, H()/2)).alpha(.2).restart();
});
</script>
</body>
</html>
