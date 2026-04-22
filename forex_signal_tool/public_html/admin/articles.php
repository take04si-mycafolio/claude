<?php
require_once __DIR__ . '/_config.php';
session_start();
require_login();

$ARTICLES = [
    ['key' => 'top_article_pre',   'title' => 'TOPページ（前半：KV・目次・概念説明）',                'page' => '/'],
    ['key' => 'top_article_post',  'title' => 'TOPページ（後半：手法解説・まとめ）',                  'page' => '/'],
    ['key' => 'signals_intro',     'title' => 'シグナル一覧 導入文',                                  'page' => '/signals/'],
    ['key' => 'ranking_title',     'title' => 'テクニカルランキング ページタイトル',                   'page' => '/technical-ranking/'],
    ['key' => 'ranking_intro',     'title' => 'テクニカルランキング 導入文',                          'page' => '/technical-ranking/'],
    ['key' => 'ranking_analysis',  'title' => 'テクニカルランキング 分析・考察',                      'page' => '/technical-ranking/'],
    ['key' => 'ranking_short_term','title' => 'テクニカルランキング 手法別おすすめ（短期トレード）',   'page' => '/technical-ranking/'],
    ['key' => 'ranking_day_trade', 'title' => 'テクニカルランキング 手法別おすすめ（デイトレード）',   'page' => '/technical-ranking/'],
    ['key' => 'ranking_swing',     'title' => 'テクニカルランキング 手法別おすすめ（スイングトレード）','page' => '/technical-ranking/'],
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

// DB からカスタム複合指標を取得してリストに追加
try {
    $pdo = get_pdo();
    $pdo->exec("CREATE TABLE IF NOT EXISTS custom_v2_indicators (
        id              BIGINT PRIMARY KEY AUTO_INCREMENT,
        name            VARCHAR(80)  NOT NULL UNIQUE,
        display_name    VARCHAR(120) NOT NULL,
        description     TEXT,
        good_markets    TEXT,
        bad_markets     TEXT,
        category        VARCHAR(30)  NOT NULL DEFAULT 'カスタム複合',
        strategy_config JSON         NOT NULL,
        is_active       TINYINT(1)   NOT NULL DEFAULT 1,
        created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_custom_ind_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
    $customRows = $pdo->query(
        "SELECT name, display_name FROM custom_v2_indicators WHERE is_active=1 ORDER BY created_at DESC"
    )->fetchAll(PDO::FETCH_ASSOC);
    foreach ($customRows as $ci) {
        $INDICATOR_ARTICLES[] = [
            'key'            => 'indicator_article_' . $ci['name'],
            'slug'           => $ci['name'],
            'title'          => $ci['display_name'],
            'page'           => '',
            'indicator_name' => $ci['name'],
            'is_custom'      => true,
        ];
    }
} catch (Exception $e) {}
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
.badge-custom{display:inline-block;background:#4c1d95;color:#c4b5fd;border-radius:4px;padding:2px 7px;font-size:10px;font-weight:600;margin-left:6px;vertical-align:middle}
.add-btn{background:#0f766e;color:#fff;border:none;border-radius:7px;padding:8px 18px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.add-btn:hover{background:#0d9488}

/* モーダル */
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:100}
.modal-overlay.open{display:flex}
.modal-box{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:28px 32px;width:480px;max-width:95vw}
.modal-title{font-size:17px;font-weight:700;color:#f1f5f9;margin-bottom:20px}
.modal-label{font-size:11px;font-weight:600;color:#94a3b8;display:block;margin-bottom:4px}
.modal-input{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:9px 12px;font-size:13px;outline:none;margin-bottom:14px}
.modal-input:focus{border-color:#3b82f6}
.modal-hint{font-size:11px;color:#475569;margin-top:-10px;margin-bottom:14px}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:6px}
.modal-cancel{background:none;border:1px solid #334155;color:#94a3b8;border-radius:6px;padding:7px 18px;font-size:13px;cursor:pointer}
.modal-ok{background:#7c3aed;color:#fff;border:none;border-radius:6px;padding:7px 18px;font-size:13px;font-weight:600;cursor:pointer}
.modal-err{font-size:12px;color:#ef4444;margin-bottom:8px;min-height:16px}

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
    <a href="/admin/articles.php" class="active">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>
<main>
  <h2>記事管理</h2>
  <p class="subtitle">各記事を編集して保存後、管理画面の generate_static を実行してください。</p>

  <div class="info-banner">
    <strong>ℹ️ 使い方：</strong>
    [編集] ボタンで記事・条件設定・バックテストをまとめて管理できます。<br>
    新しいカスタム指標は [➕ 新規テクニカル追加] から作成してください。保存後、<a href="/admin/backtest.php">バックテスト管理</a> から generate_static を実行すると公開に反映されます。
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
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
    <h2>テクニカル指標 SEO記事</h2>
    <button class="add-btn" onclick="document.getElementById('new-modal').classList.add('open')">➕ 新規テクニカル追加</button>
  </div>
  <p class="subtitle">各指標の記事・テクニカル条件・バックテストを管理します。</p>

  <table class="article-table">
    <thead><tr>
      <th>指標名</th>
      <th>対象ページ</th>
      <th style="width:80px;text-align:right">操作</th>
    </tr></thead>
    <tbody>
      <?php foreach ($INDICATOR_ARTICLES as $art):
        $slug      = $art['slug'];
        $isCustom  = !empty($art['is_custom']);
      ?>
      <tr class="art-row">
        <td>
          <div class="art-title">
            <?= htmlspecialchars($art['title']) ?>
            <?php if ($isCustom): ?>
            <span class="badge-custom">カスタム複合</span>
            <?php endif; ?>
          </div>
        </td>
        <td><div class="art-page"><?= $art['page'] ? htmlspecialchars($art['page']) : '—' ?></div></td>
        <td style="text-align:right">
          <a href="/admin/article_edit.php?key=<?= urlencode($art['key']) ?>" class="edit-btn">編集</a>
        </td>
      </tr>
      <?php endforeach; ?>
    </tbody>
  </table>
</main>

<!-- 新規テクニカル追加モーダル -->
<div class="modal-overlay" id="new-modal" onclick="if(event.target===this)this.classList.remove('open')">
  <div class="modal-box">
    <div class="modal-title">➕ 新規テクニカル指標を追加</div>
    <label class="modal-label">内部スラッグ（英数字・アンダースコアのみ）</label>
    <input class="modal-input" id="nm-slug" placeholder="例: rsi_bb_combo">
    <div class="modal-hint">半角英数字とアンダースコアのみ。作成後は変更不可。</div>
    <label class="modal-label">表示名</label>
    <input class="modal-input" id="nm-display" placeholder="例: RSI+BB 複合シグナル">
    <div class="modal-err" id="nm-err"></div>
    <div class="modal-actions">
      <button class="modal-cancel" onclick="document.getElementById('new-modal').classList.remove('open')">キャンセル</button>
      <button class="modal-ok" onclick="createIndicator()">作成して編集画面へ →</button>
    </div>
  </div>
</div>

<script>
async function createIndicator() {
  const slug    = document.getElementById('nm-slug').value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '');
  const display = document.getElementById('nm-display').value.trim();
  const errEl   = document.getElementById('nm-err');
  errEl.textContent = '';
  if (!slug || !display) { errEl.textContent = 'スラッグと表示名は必須です'; return; }
  if (slug.length > 80)  { errEl.textContent = 'スラッグは80文字以内にしてください'; return; }
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ action: 'create_indicator_stub', slug, display_name: display }),
    }).then(r => r.json());
    if (res.status === 'ok') {
      location.href = '/admin/article_edit.php?key=indicator_article_' + res.slug;
    } else {
      errEl.textContent = 'エラー: ' + (res.message || '');
    }
  } catch(e) {
    errEl.textContent = 'ネットワークエラー: ' + e.message;
  }
}
</script>
</body>
</html>
