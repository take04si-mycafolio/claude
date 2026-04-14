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

$INDICATOR_ARTICLES = [
    // オシレーター
    ['key' => 'indicator_article_rsi',               'title' => 'RSI（14期間）',                     'slug' => 'rsi',               'page' => '/oscillator/rsi/'],
    ['key' => 'indicator_article_macd',              'title' => 'MACD（12・26・9）',                  'slug' => 'macd',              'page' => '/oscillator/macd/'],
    ['key' => 'indicator_article_stochastic',        'title' => 'ストキャスティクス（14・3・3）',      'slug' => 'stochastic',        'page' => '/oscillator/stochastic/'],
    ['key' => 'indicator_article_cci',               'title' => 'CCI（20期間）',                      'slug' => 'cci',               'page' => '/oscillator/cci/'],
    ['key' => 'indicator_article_williams_r',        'title' => 'ウィリアムズ%R（14期間）',            'slug' => 'williams_r',        'page' => '/oscillator/williams_r/'],
    // トレンド
    ['key' => 'indicator_article_sma20',             'title' => 'SMA（20期間）',                      'slug' => 'sma20',             'page' => '/trend/sma20/'],
    ['key' => 'indicator_article_sma50',             'title' => 'SMA（50期間）',                      'slug' => 'sma50',             'page' => '/trend/sma50/'],
    ['key' => 'indicator_article_sma_cross',         'title' => 'SMAクロス（20/50）',                 'slug' => 'sma_cross',         'page' => '/trend/sma_cross/'],
    ['key' => 'indicator_article_ema_cross',         'title' => 'EMAクロス（9/21）',                  'slug' => 'ema_cross',         'page' => '/trend/ema_cross/'],
    ['key' => 'indicator_article_ema21',             'title' => 'EMA（21期間）',                      'slug' => 'ema21',             'page' => '/trend/ema21/'],
    ['key' => 'indicator_article_bollinger_bands',   'title' => 'ボリンジャーバンド（20・2σ）',       'slug' => 'bollinger_bands',   'page' => '/trend/bollinger_bands/'],
    ['key' => 'indicator_article_bb_squeeze',        'title' => 'BBスクイーズ',                       'slug' => 'bb_squeeze',        'page' => '/trend/bb_squeeze/'],
    // ライン
    ['key' => 'indicator_article_pivot',             'title' => 'クラシックピボット',                  'slug' => 'pivot',             'page' => '/line/pivot/'],
    ['key' => 'indicator_article_fibonacci',         'title' => 'フィボナッチリトレースメント',         'slug' => 'fibonacci',         'page' => '/line/fibonacci/'],
    ['key' => 'indicator_article_support_resistance','title' => '動的サポート・レジスタンス',           'slug' => 'support_resistance','page' => '/line/support_resistance/'],
    // ボラティリティ
    ['key' => 'indicator_article_atr',               'title' => 'ATR（14期間）',                      'slug' => 'atr',               'page' => '/volatility/atr/'],
    ['key' => 'indicator_article_volatility_index',  'title' => 'ボリンジャーバンド幅（ボラティリティ）','slug' => 'volatility_index',  'page' => '/volatility/volatility_index/'],
    // ローソク足
    ['key' => 'indicator_article_hammer',            'title' => 'ハンマー',                            'slug' => 'hammer',            'page' => '/candlestick/hammer/'],
    ['key' => 'indicator_article_inverted_hammer',   'title' => '逆ハンマー',                          'slug' => 'inverted_hammer',   'page' => '/candlestick/inverted_hammer/'],
    ['key' => 'indicator_article_doji',              'title' => '十字線（ドジ）',                      'slug' => 'doji',              'page' => '/candlestick/doji/'],
    ['key' => 'indicator_article_bullish_engulfing', 'title' => '強気の包み足',                        'slug' => 'bullish_engulfing', 'page' => '/candlestick/bullish_engulfing/'],
    ['key' => 'indicator_article_bearish_engulfing', 'title' => '弱気の包み足',                        'slug' => 'bearish_engulfing', 'page' => '/candlestick/bearish_engulfing/'],
    ['key' => 'indicator_article_three_white_soldiers','title'=> '三白兵',                             'slug' => 'three_white_soldiers','page' => '/candlestick/three_white_soldiers/'],
    ['key' => 'indicator_article_three_black_crows', 'title' => '三羽烏',                              'slug' => 'three_black_crows', 'page' => '/candlestick/three_black_crows/'],
    ['key' => 'indicator_article_pin_bar',           'title' => 'ピンバー',                            'slug' => 'pin_bar',           'page' => '/candlestick/pin_bar/'],
];

// slug → indicator_name マッピング読み込み
$slugMapFile = __DIR__ . '/indicator_slugs.json';
$slugMap     = file_exists($slugMapFile) ? (json_decode(file_get_contents($slugMapFile), true) ?? []) : [];

// indicator_name → display_name マッピング読み込み
$dispMapFile = __DIR__ . '/indicator_display_names.json';
$dispMap     = file_exists($dispMapFile) ? (json_decode(file_get_contents($dispMapFile), true) ?? []) : [];

// 各指標の indicator_name を付与
foreach ($INDICATOR_ARTICLES as &$art) {
    $art['indicator_name'] = $slugMap[$art['slug']] ?? '';
    $art['display_name']   = $art['indicator_name'] ? ($dispMap[$art['indicator_name']] ?? $art['title']) : $art['title'];
}
unset($art);
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
main{max-width:960px;margin:0 auto;padding:28px 16px}
h2{font-size:19px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.subtitle{font-size:12px;color:#64748b;margin-bottom:24px}
.article-table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}
.article-table th{background:#162032;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:12px 16px;text-align:left;border-bottom:1px solid #334155}
.article-table td{padding:12px 16px;border-bottom:1px solid #0f172a;vertical-align:middle}
.article-table tr:last-child td{border-bottom:none}
.article-table tr:hover td{background:#1a2844}
.art-title{font-size:14px;font-weight:600;color:#f1f5f9}
.art-page{font-size:11px;color:#475569;font-family:monospace;margin-top:3px}
.edit-btn{display:inline-block;background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f6;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;text-decoration:none;transition:background .15s;white-space:nowrap}
.edit-btn:hover{background:#1e4a8f}
.ai-btn{display:inline-flex;align-items:center;gap:4px;background:#1a1f2e;color:#a78bfa;border:1px solid #5b21b6;border-radius:6px;padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;white-space:nowrap}
.ai-btn:hover{background:#2d1f5e;color:#c4b5fd}
.ai-btn:disabled{opacity:.4;cursor:not-allowed}
.info-banner{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#94a3b8;line-height:1.7}
.info-banner strong{color:#60a5fa}
/* AI分析モーダル */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:flex;align-items:flex-start;justify-content:center;padding:40px 16px;overflow-y:auto}
.modal-box{background:#1e293b;border:1px solid #334155;border-radius:14px;width:100%;max-width:760px;padding:28px;position:relative}
.modal-close{position:absolute;top:16px;right:16px;background:none;border:none;color:#64748b;font-size:20px;cursor:pointer;line-height:1;padding:4px}
.modal-close:hover{color:#e2e8f0}
.modal-title{font-size:16px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.modal-subtitle{font-size:12px;color:#64748b;margin-bottom:20px}
.modal-meta{display:flex;gap:12px;font-size:11px;color:#475569;margin-bottom:16px;flex-wrap:wrap}
.modal-meta span{background:#0f172a;border-radius:4px;padding:3px 8px}
/* AI分析結果テキスト */
.ai-result{background:#0b1525;border:1px solid #1e3a5f;border-radius:10px;padding:20px;font-size:13px;line-height:1.8;color:#cbd5e1;min-height:200px;white-space:pre-wrap;word-break:break-word}
.ai-result h3{font-size:14px;font-weight:700;color:#60a5fa;margin:16px 0 6px}
.ai-result h3:first-child{margin-top:0}
.ai-result strong{color:#e2e8f0}
/* ローディング */
.ai-loading{display:flex;align-items:center;gap:12px;color:#64748b;font-size:13px;padding:40px 0;justify-content:center}
.spin{display:inline-block;width:20px;height:20px;border:2px solid #334155;border-top-color:#a78bfa;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* モーダルフッター */
.modal-footer{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap;align-items:center}
.modal-btn{display:inline-flex;align-items:center;gap:6px;border:none;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;text-decoration:none}
.modal-btn.primary{background:#0e7490;color:#fff}
.modal-btn.primary:hover{background:#0891b2;color:#fff}
.modal-btn.secondary{background:#1e293b;color:#94a3b8;border:1px solid #334155}
.modal-btn.secondary:hover{background:#334155}
.modal-token{margin-left:auto;font-size:11px;color:#475569}
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
    HTMLを入力・保存後、<a href="/admin/backtest.php" style="color:#60a5fa">バックテスト管理</a> または <a href="/admin/seo.php" style="color:#60a5fa">SEO管理</a> から generate_static を実行すると公開に反映されます。<br>
    <strong>🤖 AI分析</strong> ボタン：Gemini がバックテスト結果を分析し、勝率改善のための追加条件を提案します（バックテスト実行済みの指標のみ有効）。
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
        <td><div class="art-title"><?= htmlspecialchars($art['title']) ?></div></td>
        <td><div class="art-page"><?= htmlspecialchars($art['page']) ?></div></td>
        <td style="text-align:center">
          <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>

  <h2 style="margin-top:40px">テクニカル指標 SEO記事</h2>
  <p class="subtitle">各指標ページのトレードシミュレーション下に表示されるSEO記事を管理します。</p>

  <table class="article-table">
    <thead>
      <tr>
        <th>指標名</th>
        <th>対象ページ</th>
        <th style="width:200px;text-align:center">操作</th>
      </tr>
    </thead>
    <tbody>
      <?php foreach ($INDICATOR_ARTICLES as $art): ?>
      <tr>
        <td>
          <div class="art-title"><?= htmlspecialchars($art['title']) ?></div>
          <?php if ($art['indicator_name']): ?>
          <div class="art-page"><?= htmlspecialchars($art['indicator_name']) ?></div>
          <?php endif; ?>
        </td>
        <td><div class="art-page"><?= htmlspecialchars($art['page']) ?></div></td>
        <td style="text-align:center">
          <div style="display:flex;gap:6px;justify-content:center;flex-wrap:wrap">
            <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
            <?php if ($art['indicator_name']): ?>
            <button class="ai-btn"
                    onclick="runAiAnalysis(<?= htmlspecialchars(json_encode($art['indicator_name'])) ?>, <?= htmlspecialchars(json_encode($art['display_name'])) ?>, this)">
              🤖 AI分析
            </button>
            <?php endif; ?>
          </div>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>
</main>

<!-- AI分析結果モーダル -->
<div id="ai-modal" class="modal-overlay" style="display:none" onclick="if(event.target===this)closeAiModal()">
  <div class="modal-box">
    <button class="modal-close" onclick="closeAiModal()">✕</button>
    <div class="modal-title" id="ai-modal-title">AI バックテスト分析</div>
    <div class="modal-subtitle" id="ai-modal-subtitle"></div>
    <div class="modal-meta" id="ai-modal-meta" style="display:none"></div>
    <div id="ai-modal-body">
      <div class="ai-loading"><div class="spin"></div>Gemini が分析中です...</div>
    </div>
    <div class="modal-footer" id="ai-modal-footer" style="display:none">
      <a href="/admin/backtest_v2.php" target="_blank" class="modal-btn primary">
        ⚙️ バックテストツール2で検証
      </a>
      <button class="modal-btn secondary" onclick="copyAnalysis()">📋 コピー</button>
      <span class="modal-token" id="ai-modal-token"></span>
    </div>
  </div>
</div>

<script>
let _aiAnalysisText = '';

async function runAiAnalysis(indicatorName, displayName, btn) {
  // モーダルを開いてローディング表示
  document.getElementById('ai-modal-title').textContent = `AI分析: ${displayName}`;
  document.getElementById('ai-modal-subtitle').textContent = `指標名: ${indicatorName}`;
  document.getElementById('ai-modal-meta').style.display   = 'none';
  document.getElementById('ai-modal-footer').style.display = 'none';
  document.getElementById('ai-modal-body').innerHTML =
    '<div class="ai-loading"><div class="spin"></div>Gemini が分析中です...（30秒〜1分かかる場合があります）</div>';
  document.getElementById('ai-modal').style.display = 'flex';
  _aiAnalysisText = '';

  // ボタン無効化
  const origText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '⏳ 分析中...';

  try {
    const res = await fetch('/admin/api.php?action=ai_bt_analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ indicator_name: indicatorName, indicator_display: displayName }),
    }).then(r => r.json());

    btn.disabled = false;
    btn.innerHTML = origText;

    if (!res.ok) {
      document.getElementById('ai-modal-body').innerHTML =
        `<div class="ai-result" style="color:#ef4444">エラー: ${res.error || JSON.stringify(res)}</div>`;
      return;
    }

    _aiAnalysisText = res.analysis || '';

    // Markdown的テキストをシンプルにHTMLへ変換
    const html = markdownToHtml(_aiAnalysisText);
    document.getElementById('ai-modal-body').innerHTML = `<div class="ai-result">${html}</div>`;

    // メタ情報
    const metaEl = document.getElementById('ai-modal-meta');
    metaEl.style.display = 'flex';
    metaEl.innerHTML = `<span>モデル: ${res.model}</span><span>トークン数: ${(res.tokens||0).toLocaleString()}</span>`;
    document.getElementById('ai-modal-token').textContent = '';
    document.getElementById('ai-modal-footer').style.display = 'flex';

  } catch(e) {
    btn.disabled = false;
    btn.innerHTML = origText;
    document.getElementById('ai-modal-body').innerHTML =
      `<div class="ai-result" style="color:#ef4444">ネットワークエラー: ${e}</div>`;
  }
}

function closeAiModal() {
  document.getElementById('ai-modal').style.display = 'none';
}

function copyAnalysis() {
  if (!_aiAnalysisText) return;
  navigator.clipboard.writeText(_aiAnalysisText).then(() => {
    const btn = event.target;
    btn.textContent = '✅ コピー済み';
    setTimeout(() => btn.textContent = '📋 コピー', 2000);
  });
}

function markdownToHtml(text) {
  // 最小限のMarkdown変換
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h3 style="font-size:15px;color:#93c5fd">$1</h3>')
    .replace(/^# (.+)$/gm, '<h3 style="font-size:16px;color:#f1f5f9">$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code style="background:#162032;padding:1px 5px;border-radius:3px;font-size:12px">$1</code>')
    .replace(/^\|(.+)\|$/gm, (m) => {
      const cells = m.split('|').slice(1,-1).map(c => c.trim());
      return '<div style="display:flex;gap:8px;font-size:12px;border-bottom:1px solid #1e293b;padding:4px 0">'
        + cells.map(c => `<span style="flex:1">${c}</span>`).join('') + '</div>';
    })
    .replace(/^---+$/gm, '<hr style="border-color:#1e293b;margin:8px 0">')
    .replace(/^- (.+)$/gm, '<div style="padding-left:12px;margin:2px 0">• $1</div>')
    .replace(/^\d+\. (.+)$/gm, '<div style="padding-left:12px;margin:2px 0">$1</div>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

// ESCキーでモーダルを閉じる
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAiModal(); });
</script>
</body>
</html>
