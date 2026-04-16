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

$PAIR_ARTICLES = [
    ['key' => 'pair_article_usdjpy', 'pair' => 'USDJPY', 'title' => 'ドル円（USD/JPY）ページ',   'page' => '/usdjpy/'],
    ['key' => 'pair_article_gbpjpy', 'pair' => 'GBPJPY', 'title' => 'ポンド円（GBP/JPY）ページ', 'page' => '/gbpjpy/'],
    ['key' => 'pair_article_eurjpy', 'pair' => 'EURJPY', 'title' => 'ユーロ円（EUR/JPY）ページ', 'page' => '/eurjpy/'],
];

$INDICATOR_ARTICLES = [
    ['key' => 'indicator_article_rsi',               'slug' => 'rsi',                'title' => 'RSI（14期間）',                      'page' => '/oscillator/rsi/'],
    ['key' => 'indicator_article_macd',              'slug' => 'macd',               'title' => 'MACD（12・26・9）',                   'page' => '/oscillator/macd/'],
    ['key' => 'indicator_article_stochastic',        'slug' => 'stochastic',         'title' => 'ストキャスティクス（14・3・3）',       'page' => '/oscillator/stochastic/'],
    ['key' => 'indicator_article_cci',               'slug' => 'cci',                'title' => 'CCI（20期間）',                       'page' => '/oscillator/cci/'],
    ['key' => 'indicator_article_williams_r',        'slug' => 'williams_r',         'title' => 'ウィリアムズ%R（14期間）',             'page' => '/oscillator/williams_r/'],
    ['key' => 'indicator_article_sma20',             'slug' => 'sma20',              'title' => 'SMA（20期間）',                       'page' => '/trend/sma20/'],
    ['key' => 'indicator_article_sma50',             'slug' => 'sma50',              'title' => 'SMA（50期間）',                       'page' => '/trend/sma50/'],
    ['key' => 'indicator_article_sma_cross',         'slug' => 'sma_cross',          'title' => 'SMAクロス（20/50）',                  'page' => '/trend/sma_cross/'],
    ['key' => 'indicator_article_ema_cross',         'slug' => 'ema_cross',          'title' => 'EMAクロス（9/21）',                   'page' => '/trend/ema_cross/'],
    ['key' => 'indicator_article_ema21',             'slug' => 'ema21',              'title' => 'EMA（21期間）',                       'page' => '/trend/ema21/'],
    ['key' => 'indicator_article_bollinger_bands',   'slug' => 'bollinger_bands',    'title' => 'ボリンジャーバンド（20・2σ）',        'page' => '/trend/bollinger_bands/'],
    ['key' => 'indicator_article_bb_squeeze',        'slug' => 'bb_squeeze',         'title' => 'BBスクイーズ',                        'page' => '/trend/bb_squeeze/'],
    ['key' => 'indicator_article_pivot',             'slug' => 'pivot',              'title' => 'クラシックピボット',                   'page' => '/line/pivot/'],
    ['key' => 'indicator_article_fibonacci',         'slug' => 'fibonacci',          'title' => 'フィボナッチリトレースメント',          'page' => '/line/fibonacci/'],
    ['key' => 'indicator_article_support_resistance','slug' => 'support_resistance', 'title' => '動的サポート・レジスタンス',            'page' => '/line/support_resistance/'],
    ['key' => 'indicator_article_atr',               'slug' => 'atr',                'title' => 'ATR（14期間）',                       'page' => '/volatility/atr/'],
    ['key' => 'indicator_article_volatility_index',  'slug' => 'volatility_index',   'title' => 'ボリンジャーバンド幅（ボラティリティ）', 'page' => '/volatility/volatility_index/'],
    ['key' => 'indicator_article_hammer',            'slug' => 'hammer',             'title' => 'ハンマー',                             'page' => '/candlestick/hammer/'],
    ['key' => 'indicator_article_inverted_hammer',   'slug' => 'inverted_hammer',    'title' => '逆ハンマー',                           'page' => '/candlestick/inverted_hammer/'],
    ['key' => 'indicator_article_doji',              'slug' => 'doji',               'title' => '十字線（ドジ）',                       'page' => '/candlestick/doji/'],
    ['key' => 'indicator_article_bullish_engulfing', 'slug' => 'bullish_engulfing',  'title' => '強気の包み足',                         'page' => '/candlestick/bullish_engulfing/'],
    ['key' => 'indicator_article_bearish_engulfing', 'slug' => 'bearish_engulfing',  'title' => '弱気の包み足',                         'page' => '/candlestick/bearish_engulfing/'],
    ['key' => 'indicator_article_three_white_soldiers','slug'=> 'three_white_soldiers','title'=> '三白兵',                              'page' => '/candlestick/three_white_soldiers/'],
    ['key' => 'indicator_article_three_black_crows', 'slug' => 'three_black_crows',  'title' => '三羽烏',                               'page' => '/candlestick/three_black_crows/'],
    ['key' => 'indicator_article_pin_bar',           'slug' => 'pin_bar',            'title' => 'ピンバー',                             'page' => '/candlestick/pin_bar/'],
];

// slug → indicator_name マッピング
$slugMapFile = __DIR__ . '/indicator_slugs.json';
$slugMap     = file_exists($slugMapFile) ? (json_decode(file_get_contents($slugMapFile), true) ?? []) : [];

foreach ($INDICATOR_ARTICLES as &$art) {
    $art['indicator_name'] = $slugMap[$art['slug']] ?? '';
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

/* テーブル */
.article-table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;margin-bottom:40px}
.article-table th{background:#162032;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:12px 16px;text-align:left;border-bottom:1px solid #334155}
.article-table td{padding:12px 16px;border-bottom:1px solid #0f172a;vertical-align:middle}
.art-row:last-child > td, .art-row:last-child ~ .panel-row:last-child > td{border-bottom:none}
.art-row:hover > td{background:#1a2844}
.art-title{font-size:14px;font-weight:600;color:#f1f5f9}
.art-page{font-size:11px;color:#475569;font-family:monospace;margin-top:2px}

/* ボタン群 */
.btn-group{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
.edit-btn{display:inline-block;background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f6;border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;text-decoration:none;white-space:nowrap;transition:background .15s}
.edit-btn:hover{background:#1e4a8f}
.expand-btn{display:inline-flex;align-items:center;gap:4px;background:#162032;color:#94a3b8;border:1px solid #334155;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .15s}
.expand-btn:hover{background:#1e293b;color:#e2e8f0}
.expand-btn.open{background:#0d2137;color:#38bdf8;border-color:#1e4976}

/* 展開パネル */
.panel-row{display:none}
.panel-row.open{display:table-row}
.panel-cell{background:#080f1a;padding:16px 20px;border-bottom:1px solid #0f172a}

/* パネル内レイアウト */
.panel-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:700px){.panel-grid{grid-template-columns:1fr}}
.panel-section{background:#0b1525;border:1px solid #1e3a5f;border-radius:8px;padding:14px}
.panel-section-title{font-size:11px;font-weight:600;color:#38bdf8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}

/* BT2セクション */
.bt2-link{display:inline-flex;align-items:center;gap:6px;background:#0e7490;color:#fff;border:none;border-radius:7px;padding:8px 16px;font-size:13px;font-weight:600;text-decoration:none;transition:background .15s}
.bt2-link:hover{background:#0891b2;color:#fff}
.bt2-desc{font-size:11px;color:#64748b;margin-top:8px;line-height:1.6}

/* AIフィードバック */
.ai-textarea{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:10px;font-size:12px;line-height:1.6;resize:vertical;min-height:140px;font-family:inherit;outline:none}
.ai-textarea:focus{border-color:#0e7490}
.ai-textarea::placeholder{color:#334155}
.ai-save-btn{margin-top:8px;background:#0f766e;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer;transition:background .15s}
.ai-save-btn:hover{background:#0d9488}
.ai-save-btn:disabled{background:#334155;cursor:not-allowed}
.ai-save-status{display:inline-block;margin-left:8px;font-size:11px;vertical-align:middle}
.ai-save-status.ok{color:#22c55e}
.ai-save-status.err{color:#ef4444}
.ai-updated{font-size:11px;color:#475569;margin-top:4px}

/* リンク済み戦略 */
.strategy-list{display:flex;flex-direction:column;gap:6px}
.strategy-item{background:#0f172a;border:1px solid #1e293b;border-radius:6px;padding:8px 10px;font-size:12px}
.strategy-name{color:#e2e8f0;font-weight:600;margin-bottom:3px}
.strategy-meta{color:#475569;font-size:11px;display:flex;gap:10px;flex-wrap:wrap}
.strategy-meta .wr{color:#4ade80;font-weight:600}
.strategy-empty{color:#334155;font-size:12px;padding:8px 0;text-align:center}
.strategy-loading{color:#475569;font-size:12px;padding:8px 0;text-align:center}

/* info-banner */
.info-banner{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#94a3b8;line-height:1.7}
.info-banner strong{color:#60a5fa}
.info-banner a{color:#60a5fa}
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
    編集したい記事の [編集] ボタン、または [▼ 詳細] から各種操作ができます。<br>
    保存後、<a href="/admin/backtest.php">バックテスト管理</a> または <a href="/admin/seo.php">SEO管理</a> から generate_static を実行すると公開に反映されます。
  </div>

  <!-- 通常記事 -->
  <table class="article-table">
    <thead><tr>
      <th>記事タイトル</th>
      <th>対象ページ</th>
      <th style="width:80px;text-align:right">操作</th>
    </tr></thead>
    <tbody>
      <?php foreach ($ARTICLES as $art): ?>
      <tr class="art-row">
        <td><div class="art-title"><?= htmlspecialchars($art['title']) ?></div></td>
        <td><div class="art-page"><?= htmlspecialchars($art['page']) ?></div></td>
        <td style="text-align:right">
          <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>

  <!-- 通貨ペアページ -->
  <h2>通貨ペアページ</h2>
  <p class="subtitle">ドル円・ポンド円・ユーロ円の記事コンテンツを編集します。URL: /usdjpy/ /gbpjpy/ /eurjpy/</p>

  <table class="article-table">
    <thead><tr>
      <th>ページ</th>
      <th>URL</th>
      <th style="width:80px;text-align:right">操作</th>
    </tr></thead>
    <tbody>
      <?php foreach ($PAIR_ARTICLES as $art): ?>
      <tr class="art-row">
        <td><div class="art-title"><?= htmlspecialchars($art['title']) ?></div></td>
        <td><div class="art-page"><?= htmlspecialchars($art['page']) ?></div></td>
        <td style="text-align:right">
          <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>

  <!-- テクニカル指標 SEO記事 -->
  <h2>テクニカル指標 SEO記事</h2>
  <p class="subtitle">各指標ページのSEO記事・バックテストツール2検証・AIフィードバックを管理します。</p>

  <table class="article-table">
    <thead><tr>
      <th>指標名</th>
      <th>対象ページ</th>
      <th style="width:150px;text-align:right">操作</th>
    </tr></thead>
    <tbody>
      <?php foreach ($INDICATOR_ARTICLES as $art):
        $slug = $art['slug'];
        $indName = $art['indicator_name'];
        $panelId = 'panel-' . $slug;
      ?>
      <tr class="art-row" id="row-<?= $slug ?>">
        <td>
          <div class="art-title"><?= htmlspecialchars($art['title']) ?></div>
          <?php if ($indName): ?>
          <div class="art-page"><?= htmlspecialchars($indName) ?></div>
          <?php endif; ?>
        </td>
        <td><div class="art-page"><?= htmlspecialchars($art['page']) ?></div></td>
        <td>
          <div class="btn-group">
            <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
            <?php if ($indName): ?>
            <button class="expand-btn" id="expand-<?= $slug ?>"
                    onclick="togglePanel(<?= htmlspecialchars(json_encode($slug)) ?>, <?= htmlspecialchars(json_encode($indName)) ?>)">
              ▼ 詳細
            </button>
            <?php endif; ?>
          </div>
        </td>
      </tr>
      <?php if ($indName): ?>
      <tr class="panel-row" id="<?= $panelId ?>">
        <td class="panel-cell" colspan="3">
          <div class="panel-grid">

            <!-- 左：BT2 + AIフィードバック -->
            <div>
              <!-- バックテストツール2 -->
              <div class="panel-section" style="margin-bottom:12px">
                <div class="panel-section-title">🔬 バックテストツール2</div>
                <a class="bt2-link"
                   href="/admin/backtest_v2.php?linked_ind=<?= urlencode($indName) ?>"
                   target="_blank">
                  ⚙️ バックテストツール2で検証
                </a>
                <div class="bt2-desc">
                  新しいタブで開きます。「この設定を保存」で保存すると、<br>
                  紐づけ先に <strong style="color:#e2e8f0"><?= htmlspecialchars($art['title']) ?></strong> が自動選択されます。
                </div>
              </div>

              <!-- AIフィードバック -->
              <div class="panel-section">
                <div class="panel-section-title">🤖 AIフィードバック</div>
                <textarea class="ai-textarea"
                          id="ai-notes-<?= $slug ?>"
                          placeholder="AIからの分析・改善提案をここに貼り付けてください...&#10;&#10;例）RSIが30以下の時にEMA21が上向きであれば反発の信頼性が上がる。&#10;バックテストツール2で「RSI &lt; 30 AND EMA(21)クロスアップ」を条件に検証を推奨。"></textarea>
                <div>
                  <button class="ai-save-btn"
                          id="ai-save-<?= $slug ?>"
                          onclick="saveAiNotes(<?= htmlspecialchars(json_encode($slug)) ?>)">保存</button>
                  <span class="ai-save-status" id="ai-save-status-<?= $slug ?>"></span>
                </div>
                <div class="ai-updated" id="ai-updated-<?= $slug ?>"></div>
              </div>
            </div>

            <!-- 右：リンク済み保存戦略 -->
            <div class="panel-section">
              <div class="panel-section-title">📊 リンク済み保存戦略</div>
              <div class="strategy-loading" id="strategy-list-<?= $slug ?>">
                読み込み中...
              </div>
            </div>

          </div>
        </td>
      </tr>
      <?php endif; ?>
      <?php endforeach; ?>
    </tbody>
  </table>
</main>

<script>
// コンテンツ（AIノート）をまとめて取得
let _content = {};  // key → {value, updated_at}
fetch('/admin/api.php?action=content_init')
  .then(r => r.json())
  .then(d => {
    if (d.status === 'ok') {
      _content = d.data || {};
    }
  })
  .catch(() => {});

function togglePanel(slug, indicatorName) {
  const panel   = document.getElementById('panel-' + slug);
  const btn     = document.getElementById('expand-' + slug);
  const isOpen  = panel.classList.contains('open');

  if (isOpen) {
    panel.classList.remove('open');
    btn.classList.remove('open');
    btn.textContent = '▼ 詳細';
    return;
  }

  panel.classList.add('open');
  btn.classList.add('open');
  btn.textContent = '▲ 閉じる';

  // AIノートを復元
  const notesKey = 'indicator_ai_notes_' + slug;
  const ta = document.getElementById('ai-notes-' + slug);
  if (_content[notesKey]) {
    ta.value = _content[notesKey].value || '';
    const upd = _content[notesKey].updated_at || '';
    if (upd) document.getElementById('ai-updated-' + slug).textContent = '最終保存: ' + upd.slice(0,16);
  }

  // リンク済み戦略を取得
  loadLinkedStrategies(slug, indicatorName);
}

async function saveAiNotes(slug) {
  const key  = 'indicator_ai_notes_' + slug;
  const val  = document.getElementById('ai-notes-' + slug).value;
  const btn  = document.getElementById('ai-save-' + slug);
  const stat = document.getElementById('ai-save-status-' + slug);
  btn.disabled = true;
  stat.textContent = '保存中...';
  stat.className   = 'ai-save-status';

  try {
    const res = await fetch('/admin/api.php?action=content_save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ key, value: val }),
    }).then(r => r.json());

    if (res.status === 'ok') {
      stat.textContent = '✓ 保存しました';
      stat.className   = 'ai-save-status ok';
      _content[key] = { value: val, updated_at: new Date().toISOString().slice(0,16) };
      document.getElementById('ai-updated-' + slug).textContent = '最終保存: ' + new Date().toLocaleString('ja-JP');
    } else {
      stat.textContent = 'エラー: ' + (res.message || '');
      stat.className   = 'ai-save-status err';
    }
  } catch(e) {
    stat.textContent = 'ネットワークエラー';
    stat.className   = 'ai-save-status err';
  }
  btn.disabled = false;
  setTimeout(() => { stat.textContent = ''; stat.className = 'ai-save-status'; }, 4000);
}

async function loadLinkedStrategies(slug, indicatorName) {
  const el = document.getElementById('strategy-list-' + slug);
  try {
    const res = await fetch('/admin/api.php?action=get_linked_strategies', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ indicator_name: indicatorName }),
    }).then(r => r.json());

    if (!res.ok || !res.strategies) {
      el.innerHTML = '<div class="strategy-empty">取得エラー</div>';
      return;
    }
    if (res.strategies.length === 0) {
      el.innerHTML = '<div class="strategy-empty">保存済み戦略はありません<br><span style="font-size:10px;color:#334155">バックテストツール2で検証→保存するとここに表示されます</span></div>';
      return;
    }
    el.className = 'strategy-list';
    el.innerHTML = res.strategies.map(s => {
      const wr  = s.win_rate  != null ? `<span class="wr">${parseFloat(s.win_rate).toFixed(1)}%</span>` : '';
      const pf  = s.pf        != null ? `PF ${parseFloat(s.pf).toFixed(2)}` : '';
      const tr  = s.trades    != null ? `${s.trades}件` : '';
      const ran = s.bt_ran_at ? s.bt_ran_at.slice(0,10) : '未実行';
      return `<div class="strategy-item">
        <div class="strategy-name">${escHtml(s.name)}</div>
        <div class="strategy-meta">${wr}${pf ? `<span>${pf}</span>` : ''}${tr ? `<span>${tr}</span>` : ''}<span>${ran}</span></div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="strategy-empty">読み込みエラー</div>';
  }
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>
