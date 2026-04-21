<?php
/**
 * SEO 管理ページ
 * カテゴリ・指標ページのタイトルとメタ説明を一元管理する
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO管理 | FX Trend 管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
main{max-width:1100px;margin:0 auto;padding:24px 16px}
h2{font-size:19px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.subtitle{font-size:12px;color:#64748b;margin-bottom:20px}
/* フィルターバー */
.filter-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px;align-items:center}
.filter-btn{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:20px;padding:5px 14px;font-size:12px;cursor:pointer;transition:all .15s}
.filter-btn:hover{border-color:#475569;color:#e2e8f0}
.filter-btn.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.search-box{margin-left:auto;background:#0f172a;border:1px solid #334155;border-radius:7px;color:#e2e8f0;padding:6px 12px;font-size:12px;outline:none;width:200px}
.search-box:focus{border-color:#3b82f6}
/* テーブル */
.seo-table{width:100%;border-collapse:collapse}
.seo-table th{background:#1e293b;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left;border-bottom:1px solid #334155;white-space:nowrap}
.seo-row{border-bottom:1px solid #1e293b;transition:background .1s}
.seo-row:hover{background:#1a2234}
.seo-row.saved-flash{background:#1c3a2a}
.seo-row td{padding:10px 12px;vertical-align:top}
.page-type-badge{display:inline-block;font-size:10px;font-weight:700;border-radius:4px;padding:2px 7px;white-space:nowrap}
.badge-category{background:#1e3a5f;color:#60a5fa}
.badge-indicator{background:#1e293b;color:#94a3b8}
.page-name{font-size:13px;font-weight:600;color:#f1f5f9;margin-bottom:2px}
.page-url{font-size:10px;color:#475569;font-family:monospace}
/* 入力フィールド */
.seo-input{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:12px;outline:none;resize:none;font-family:inherit;line-height:1.4}
.seo-input:focus{border-color:#3b82f6}
.seo-input.modified{border-color:#f59e0b}
.seo-input.ok{border-color:#22c55e}
.char-count{font-size:10px;margin-top:3px;text-align:right}
.char-count.ok{color:#22c55e}
.char-count.warn{color:#f59e0b}
.char-count.over{color:#ef4444}
/* 保存ボタン */
.save-btn{background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:background .15s;white-space:nowrap}
.save-btn:hover{background:#2563eb}
.save-btn:disabled{background:#1e3a5f;color:#64748b;cursor:not-allowed}
.save-status{font-size:11px;margin-top:4px;min-height:14px}
.save-status.ok{color:#22c55e}
.save-status.err{color:#ef4444}
.save-status.saving{color:#64748b}
/* デフォルト表示 */
.default-val{font-size:10px;color:#334155;margin-top:3px;line-height:1.4;display:none}
.show-default .default-val{display:block}
/* ローディング */
#loading{text-align:center;padding:40px;color:#64748b}
.spinner{display:inline-block;width:20px;height:20px;border:2px solid #334155;border-top-color:#3b82f6;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* 一括保存バー */
.bulk-bar{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.bulk-bar span{font-size:12px;color:#64748b}
.bulk-btn{background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f6;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer}
.bulk-btn:hover{background:#1e4a8f}
</style>
</head>
<body>
<header>
  <h1>📝 SEO管理</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/articles.php">記事管理</a>
    <a href="/admin/backtest.php">バックテスト v1</a>
    <a href="/admin/backtest_v2.php">バックテスト v2</a>
    <a href="/admin/seo.php" class="active">SEO管理</a>
    <a href="/admin/export.php">エクスポート</a>
    <a href="/admin/settings.php">設定</a>
    <a href="/" target="_blank">サイトを見る</a>
    <a href="/admin/?logout=1" class="logout-btn">ログアウト</a>
  </nav>
</header>

<main>
  <!-- ページ切り替えタブ -->
  <div class="main-tabs" style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap">
    <button class="main-tab active" onclick="switchMainTab(this,'seo')">ページSEO設定</button>
    <button class="main-tab" onclick="switchMainTab(this,'content')">コンテンツ管理（ランキング）</button>
    <button class="main-tab" onclick="switchMainTab(this,'ranking')">ランキング管理</button>
  </div>

  <!-- SEOタブ -->
  <div id="tab-seo">
  <h2>ページ別 SEO 設定</h2>
  <p class="subtitle">
    タイトル・メタ説明を編集して「保存」を押してください。次回の generate_static 実行時に反映されます。
    <br>文字数目安：タイトル 30〜60文字 ／ メタ説明 60〜160文字
  </p>

  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterPages('all', this)">全て（30）</button>
    <button class="filter-btn" onclick="filterPages('category', this)">カテゴリ</button>
    <button class="filter-btn" onclick="filterPages('oscillator', this)">オシレーター</button>
    <button class="filter-btn" onclick="filterPages('trend', this)">トレンド</button>
    <button class="filter-btn" onclick="filterPages('line', this)">ライン</button>
    <button class="filter-btn" onclick="filterPages('volatility', this)">ボラティリティ</button>
    <button class="filter-btn" onclick="filterPages('candlestick', this)">ローソク足</button>
    <input type="text" class="search-box" id="searchBox" placeholder="ページ名で絞り込み..." oninput="filterBySearch()">
  </div>

  <div class="bulk-bar">
    <span id="modifiedCount">変更中のページ: 0件</span>
    <button class="bulk-btn" onclick="saveAll()">変更済みをすべて保存</button>
  </div>

  <div id="loading"><div class="spinner"></div><p style="margin-top:12px">読み込み中...</p></div>

  <div id="tableWrap" style="display:none">
    <table class="seo-table" id="seoTable">
      <thead>
        <tr>
          <th style="width:200px">ページ</th>
          <th style="width:280px">タイトル <span style="font-weight:400;color:#475569">(〜60文字)</span></th>
          <th>メタ説明 <span style="font-weight:400;color:#475569">(60〜160文字)</span></th>
          <th style="width:80px">操作</th>
        </tr>
      </thead>
      <tbody id="seoTbody"></tbody>
    </table>
  </div>
  </div><!-- /tab-seo -->

  <!-- コンテンツ管理タブ -->
  <div id="tab-content" style="display:none">
  <h2>ランキングページ コンテンツ管理</h2>
  <p class="subtitle">
    テクニカルランキングページの「分析・考察」と「手法別おすすめ」を編集します。<br>
    AIが週次で分析した内容をここに入力してください。保存後、generate_static を実行すると反映されます。
  </p>

  <div id="content-loading"><div class="spinner"></div><p style="margin-top:12px">読み込み中...</p></div>
  <div id="content-body" style="display:none">

    <!-- TOPページ記事 → 記事管理ページへ -->
    <div class="cont-section" style="border-left:3px solid #3b82f6">
      <h3 class="cont-title">⓪ TOPページ記事コンテンツ</h3>
      <p class="cont-sub" style="margin-bottom:14px">
        TOPページの記事（前半・後半）は <strong style="color:#f1f5f9">記事管理ページ</strong> で編集できます。
      </p>
      <a href="/admin/articles.php" style="display:inline-flex;align-items:center;gap:8px;background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f6;border-radius:8px;padding:10px 20px;font-size:13px;font-weight:600;text-decoration:none;transition:background .15s" onmouseover="this.style.background='#1e4a8f'" onmouseout="this.style.background='#1e3a5f'">
        📄 記事管理ページへ移動
      </a>
    </div>

    <!-- ページタイトル・導入文 -->
    <div class="cont-section">
      <h3 class="cont-title">① ページタイトル・導入文</h3>
      <p class="cont-sub">ランキングページのヒーローヘッダーに表示するタイトルと導入文を設定します。</p>
      <label class="cont-label">ページタイトル</label>
      <input type="text" id="ranking-title-input" class="cont-input"
        placeholder="テクニカル指標 バックテスト勝率ランキング">
      <label class="cont-label" style="margin-top:10px">導入文</label>
      <textarea id="ranking-intro-input" class="cont-textarea" rows="4"
        placeholder="FX主要テクニカル指標のバックテスト結果を勝率順にランキング。USD/JPY・GBP/JPY・EUR/JPYの3ペアで検証した実データをもとに、本当に使えるテクニカル指標を徹底比較します。"></textarea>
      <div class="cont-actions">
        <span id="pageinfo-status" class="cont-status"></span>
        <button class="save-btn" onclick="savePageInfo()">保存</button>
      </div>
    </div>

    <!-- 分析・考察 -->
    <div class="cont-section">
      <h3 class="cont-title">② 分析・考察</h3>
      <p class="cont-sub">バックテスト結果の分析・考察テキスト。改行もそのまま表示されます。</p>
      <textarea id="analysis-input" class="cont-textarea" rows="10"
        placeholder="今週のバックテスト結果を分析すると...&#10;&#10;（AIが自動生成したテキストをここに貼り付けてください）"></textarea>
      <div class="cont-actions">
        <span id="analysis-status" class="cont-status"></span>
        <button class="save-btn" onclick="saveAnalysis()">保存</button>
      </div>
    </div>

    <!-- 手法別おすすめ -->
    <div class="cont-section">
      <h3 class="cont-title">④ 手法別おすすめ</h3>
      <p class="cont-sub">各手法に対して指標・ペア・TF・説明を3つ入力してください。AIの分析結果をもとに入力します。</p>

      <div class="rec-tabs" style="display:flex;gap:8px;margin-bottom:16px">
        <button class="rec-tab active" onclick="switchRecTab(this,'short')">短期トレード</button>
        <button class="rec-tab" onclick="switchRecTab(this,'day')">デイトレ</button>
        <button class="rec-tab" onclick="switchRecTab(this,'swing')">スイング</button>
      </div>

      <div id="rec-short" class="rec-panel">
        <p class="cont-sub" style="margin-bottom:12px">5分足・15分足を使ったスキャルピング・短期トレード向け</p>
        <div id="recs-short"></div>
        <div class="cont-actions">
          <span id="short-status" class="cont-status"></span>
          <button class="save-btn" onclick="saveRecs('short','ranking_short_term')">保存</button>
        </div>
      </div>

      <div id="rec-day" class="rec-panel" style="display:none">
        <p class="cont-sub" style="margin-bottom:12px">1時間足・4時間足を使ったデイトレード向け</p>
        <div id="recs-day"></div>
        <div class="cont-actions">
          <span id="day-status" class="cont-status"></span>
          <button class="save-btn" onclick="saveRecs('day','ranking_day_trade')">保存</button>
        </div>
      </div>

      <div id="rec-swing" class="rec-panel" style="display:none">
        <p class="cont-sub" style="margin-bottom:12px">4時間足・日足を使ったスイングトレード向け</p>
        <div id="recs-swing"></div>
        <div class="cont-actions">
          <span id="swing-status" class="cont-status"></span>
          <button class="save-btn" onclick="saveRecs('swing','ranking_swing')">保存</button>
        </div>
      </div>
    </div>

  </div><!-- /content-body -->
  </div><!-- /tab-content -->

  <!-- ランキング管理タブ -->
  <div id="tab-ranking" style="display:none">
  <h2>ランキング管理</h2>
  <p class="subtitle">バックテスト期間を設定して手動実行します。完了後、手法別おすすめが自動生成され静的ページが更新されます。</p>

  <!-- データ件数 -->
  <div class="cont-section">
    <h3 class="cont-title">データ件数</h3>
    <div id="rk-counts-loading" style="font-size:12px;color:#64748b">読み込み中...</div>
    <div id="rk-counts" style="display:none">
      <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:6px">
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">シミュレーショントレード</div>
          <div class="rk-stat-val" id="rk-cnt-st">-</div>
        </div>
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">バックテスト結果</div>
          <div class="rk-stat-val" id="rk-cnt-bt">-</div>
        </div>
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">シグナル（アクティブ）</div>
          <div class="rk-stat-val" id="rk-cnt-sig">-</div>
        </div>
      </div>
      <div style="font-size:11px;color:#64748b">最終バックテスト実行: <span id="rk-last-bt">-</span></div>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="save-btn" onclick="loadRkInfo()" style="background:#334155">件数を更新</button>
      <button class="save-btn" onclick="downloadCsv()" id="rk-csv-btn" style="background:#059669">CSVダウンロード（ZIP）</button>
      <button class="save-btn" onclick="resetSimulationTrades()" style="background:#92400e;border:1px solid #f97316">シミュレーション履歴をリセット</button>
    </div>
  </div>

  <!-- 期間設定 -->
  <div class="cont-section">
    <h3 class="cont-title">バックテスト期間設定</h3>
    <p class="cont-sub">短期・デイトレ（5分〜4時間足）と スイング（日足）は別々に期間指定できます。</p>

    <div style="margin-bottom:16px">
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:8px">短期・デイトレ用（5分足 / 15分足 / 30分足 / 1時間足 / 4時間足）</div>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <div>
          <label class="cont-label">開始日</label>
          <input type="date" id="rk-start" class="cont-input" style="width:160px">
        </div>
        <div>
          <label class="cont-label">終了日</label>
          <input type="date" id="rk-end" class="cont-input" style="width:160px">
        </div>
      </div>
    </div>

    <div>
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:4px">スイング用（日足）</div>
      <p class="cont-sub" style="margin-bottom:8px">デフォルト: 6ヶ月前〜本日</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <div>
          <label class="cont-label">開始日（日足）</label>
          <input type="date" id="rk-swing-start" class="cont-input" style="width:160px">
        </div>
        <div>
          <label class="cont-label">終了日（日足）</label>
          <input type="date" id="rk-swing-end" class="cont-input" style="width:160px">
        </div>
      </div>
    </div>
  </div>

  <!-- 実行 -->
  <div class="cont-section">
    <h3 class="cont-title">バックテスト実行</h3>
    <p class="cont-sub">全通貨ペア（USD/JPY・GBP/JPY・EUR/JPY）× 全タイムフレームのバックテストを行います。<br>完了後、手法別おすすめ（ペア別トップ5）が自動生成され、静的ページが更新されます。</p>
    <div style="margin-top:12px;padding:12px 14px;background:#1a0f0f;border:1px solid #7f1d1d;border-radius:8px;display:flex;align-items:flex-start;gap:10px">
      <input type="checkbox" id="rk-force-full" style="margin-top:3px;width:15px;height:15px;accent-color:#ef4444;flex-shrink:0">
      <div>
        <label for="rk-force-full" style="font-size:13px;font-weight:600;color:#fca5a5;cursor:pointer">既存データをリセットしてフルバックテスト</label>
        <p style="font-size:12px;color:#94a3b8;margin:3px 0 0">チェックすると既存のバックテスト結果・シミュレーショントレードをすべて削除してから実行します。SL/TP設定を変更した場合や、計算をやり直したい場合に使用してください。</p>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;margin-top:12px;flex-wrap:wrap">
      <button class="save-btn" id="rk-run-btn" style="padding:10px 28px;font-size:14px;background:#dc2626" onclick="runRankingBt()">バックテスト実行</button>
      <span id="rk-run-status" class="cont-status"></span>
    </div>
    <div id="rk-progress" style="display:none;margin-top:12px;padding:12px 14px;background:#0f172a;border:1px solid #334155;border-radius:8px">
      <div style="font-size:12px;color:#94a3b8;line-height:1.6" id="rk-progress-msg">実行中...</div>
      <div style="margin-top:8px;height:3px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div id="rk-progress-bar" style="width:0%;height:100%;background:linear-gradient(90deg,#3b82f6,#60a5fa);transition:width .4s;border-radius:2px"></div>
      </div>
    </div>
  </div>
  <!-- 市場セッション別ランキング更新 -->
  <div class="cont-section" style="border-left:3px solid #0891b2">
    <h3 class="cont-title">市場セッション別ランキング更新</h3>
    <p class="cont-sub">
      フルバックテストは行わず、既存のシミュレーショントレードから東京・ロンドン・NY セッション別ランキングとトレード履歴のみ再集計します。<br>
      バックテスト後に個別更新したい場合や、分析期間を変えて確認したい場合に使用してください。
    </p>

    <!-- データ件数 -->
    <div id="sess-counts-loading" style="font-size:12px;color:#64748b">読み込み中...</div>
    <div id="sess-counts" style="display:none">
      <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:6px">
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">ランキングスナップショット</div>
          <div class="rk-stat-val" id="sess-cnt-rk">-</div>
        </div>
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">セッショントレード履歴</div>
          <div class="rk-stat-val" id="sess-cnt-tr">-</div>
        </div>
        <div class="rk-stat-box">
          <div class="rk-stat-lbl">最新スナップショット日</div>
          <div class="rk-stat-val" id="sess-latest" style="font-size:14px;padding-top:4px">-</div>
        </div>
      </div>
    </div>
    <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
      <button class="save-btn" onclick="loadSessInfo();loadSessBreakdown()" style="background:#334155">件数を更新</button>
    </div>

    <!-- セッション別トレード内訳 -->
    <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155">
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:10px">セッション別トレード内訳 <span style="font-size:11px;color:#64748b;font-weight:400">（simulation_trades 全件）</span></div>
      <div id="sess-breakdown-loading" style="font-size:12px;color:#64748b">読み込み中...</div>
      <div id="sess-breakdown" style="display:none">
        <!-- 日付タブ -->
        <div id="sess-date-tabs" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px"></div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
          <div id="sess-card-japan"  class="sess-card"></div>
          <div id="sess-card-london" class="sess-card"></div>
          <div id="sess-card-ny"     class="sess-card"></div>
        </div>
      </div>
    </div>

    <!-- 分析期間設定 -->
    <div style="margin-top:16px;padding-top:16px;border-top:1px solid #334155">
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:8px">分析期間（日数）</div>
      <p class="cont-sub" style="margin-bottom:10px">シミュレーショントレードのうち、何日前までを集計対象にするかを指定します。</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="sess-days-btn active" data-days="1" onclick="setSessDays(this)">1日</button>
        <button class="sess-days-btn" data-days="7" onclick="setSessDays(this)">7日</button>
        <button class="sess-days-btn" data-days="14" onclick="setSessDays(this)">14日</button>
        <button class="sess-days-btn" data-days="30" onclick="setSessDays(this)">30日</button>
        <button class="sess-days-btn" data-days="60" onclick="setSessDays(this)">60日</button>
        <button class="sess-days-btn" data-days="90" onclick="setSessDays(this)">90日</button>
      </div>
      <div style="margin-top:8px;font-size:12px;color:#94a3b8">選択中: <span id="sess-days-label">1日</span></div>
    </div>

    <!-- 実行 -->
    <div style="display:flex;align-items:center;gap:12px;margin-top:16px;flex-wrap:wrap">
      <button class="save-btn" id="sess-run-btn" style="padding:10px 24px;font-size:14px;background:#0891b2" onclick="runSessionUpdate(false)">当日分を更新</button>
      <button class="save-btn" id="sess-prev-btn" style="padding:10px 24px;font-size:14px;background:#0e7490" onclick="runSessionUpdate(true)">前日分を更新</button>
      <span id="sess-run-status" class="cont-status"></span>
    </div>
    <div id="sess-progress" style="display:none;margin-top:12px;padding:12px 14px;background:#0f172a;border:1px solid #334155;border-radius:8px">
      <div style="font-size:12px;color:#94a3b8" id="sess-progress-msg">実行中...</div>
      <div style="margin-top:8px;height:3px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div id="sess-progress-bar" style="width:30%;height:100%;background:linear-gradient(90deg,#0891b2,#22d3ee);animation:indeterminate 1.5s infinite;border-radius:2px"></div>
      </div>
    </div>
  </div>

  <!-- セッション専用バックテスト -->
  <div class="cont-section" style="border-left:3px solid #7c3aed">
    <h3 class="cont-title">セッション専用バックテスト</h3>
    <p class="cont-sub">
      東京・ロンドン・NY 各時間帯のローソク足のみを使った専用バックテストを実行します。<br>
      全テクニカル × 全通貨ペア × 全時間軸（日足除く）を処理するため、数十分かかります。
    </p>

    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px">
      <div>
        <label class="cont-label">開始日</label>
        <input type="date" id="sbt-start" class="cont-input" style="width:160px">
      </div>
      <div>
        <label class="cont-label">終了日</label>
        <input type="date" id="sbt-end" class="cont-input" style="width:160px">
      </div>
    </div>

    <div style="display:flex;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap">
      <button class="save-btn" id="sbt-run-btn" style="padding:10px 28px;font-size:14px;background:#7c3aed" onclick="runSessionBt()">セッション専用バックテスト実行</button>
      <span id="sbt-run-status" class="cont-status"></span>
    </div>
    <div id="sbt-progress" style="display:none;margin-top:12px;padding:12px 14px;background:#0f172a;border:1px solid #334155;border-radius:8px">
      <div style="font-size:12px;color:#94a3b8;line-height:1.6" id="sbt-progress-msg">実行中...</div>
      <div style="margin-top:8px;height:3px;background:#1e293b;border-radius:2px;overflow:hidden">
        <div id="sbt-progress-bar" style="width:30%;height:100%;background:linear-gradient(90deg,#7c3aed,#a78bfa);animation:indeterminate 1.5s infinite;border-radius:2px"></div>
      </div>
    </div>
  </div>

  </div><!-- /tab-ranking -->

</main>
<style>
@keyframes indeterminate{0%{transform:translateX(-100%)}100%{transform:translateX(400%)}}
.sess-card{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px}
.sess-date-tab{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:20px;padding:4px 12px;font-size:12px;cursor:pointer;transition:all .15s;white-space:nowrap}
.sess-date-tab:hover{border-color:#475569;color:#e2e8f0}
.sess-date-tab.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa;font-weight:600}
.sess-days-btn{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:20px;padding:5px 16px;font-size:12px;cursor:pointer;transition:all .15s}
.sess-days-btn:hover{border-color:#475569;color:#e2e8f0}
.sess-days-btn.active{background:#083344;border-color:#0891b2;color:#22d3ee}
</style>

<script>
// ページ定義データ（デフォルト値）- key はDBキーと一致するスラッグ
const PAGES = [
  // カテゴリ（key = category slug）
  {type:'category', key:'oscillator', cat:'category', name:'オシレーター系指標',
   url:'/oscillator/', defaultTitle:'FXオシレーターの勝率一覧｜RSI・MACDなどを検証',
   defaultMeta:'RSI・MACD・ストキャスティクスなどオシレーター系テクニカルの勝率を一覧で比較。バックテスト結果をもとに分析。'},
  {type:'category', key:'trend', cat:'category', name:'トレンド系指標',
   url:'/trend/', defaultTitle:'FXトレンド系テクニカルの勝率一覧｜移動平均など検証',
   defaultMeta:'移動平均線やボリンジャーバンドなどトレンド系指標の勝率を比較。バックテスト結果をもとに分析。'},
  {type:'category', key:'line', cat:'category', name:'ライン系指標',
   url:'/line/', defaultTitle:'ライン系テクニカルの勝率｜ピボット・フィボナッチ検証',
   defaultMeta:'ピボットポイントやフィボナッチなどライン系分析の勝率を検証。サポート・レジスタンスの精度を分析。'},
  {type:'category', key:'volatility', cat:'category', name:'ボラティリティ系指標',
   url:'/volatility/', defaultTitle:'FXボラティリティ指標の勝率｜ATR・BB幅を検証',
   defaultMeta:'ATRやボリンジャーバンド幅などボラティリティ指標の勝率を検証。相場の変動分析に活用。'},
  {type:'category', key:'candlestick', cat:'category', name:'ローソク足パターン',
   url:'/candlestick/', defaultTitle:'ローソク足パターンの勝率｜主要パターンを検証',
   defaultMeta:'ハンマー・包み足などローソク足パターンの勝率を検証。トレード精度をデータで分析。'},
  // オシレーター（key = url_slug）
  {type:'indicator', key:'rsi', cat:'oscillator', name:'RSI（14期間）',
   url:'/oscillator/rsi/', defaultTitle:'RSIの勝率｜FXで使えるシグナルを検証',
   defaultMeta:'RSIの勝率をバックテストで検証。買われすぎ・売られすぎシグナルの精度やトレード結果をデータで解説。'},
  {type:'indicator', key:'macd', cat:'oscillator', name:'MACD（12・26・9）',
   url:'/oscillator/macd/', defaultTitle:'MACDの勝率｜クロスシグナルの精度を検証',
   defaultMeta:'MACDのゴールデンクロス・デッドクロスの勝率を検証。FXトレードでの有効性をデータで解説。'},
  {type:'indicator', key:'stochastic', cat:'oscillator', name:'ストキャスティクス（14・3）',
   url:'/oscillator/stochastic/', defaultTitle:'ストキャスティクスの勝率｜逆張り精度を検証',
   defaultMeta:'ストキャスティクスの勝率をバックテストで分析。逆張りシグナルの精度やトレード結果を解説。'},
  {type:'indicator', key:'cci', cat:'oscillator', name:'CCI（20期間）',
   url:'/oscillator/cci/', defaultTitle:'CCIの勝率｜トレンド判定の精度を検証',
   defaultMeta:'CCIの勝率を検証。トレンド判断やエントリー精度をバックテスト結果から分析。'},
  {type:'indicator', key:'williams_r', cat:'oscillator', name:'ウィリアムズ%R（14期間）',
   url:'/oscillator/williams_r/', defaultTitle:'ウィリアムズ%Rの勝率｜逆張り指標を検証',
   defaultMeta:'ウィリアムズ%Rの勝率を検証。売買タイミングの精度やトレード結果をデータで解説。'},
  // トレンド
  {type:'indicator', key:'sma20', cat:'trend', name:'SMA 20期間',
   url:'/trend/sma20/', defaultTitle:'SMA20の勝率｜単純移動平均の精度を検証',
   defaultMeta:'SMA20の勝率をバックテストで検証。トレンドフォローの精度とエントリー結果を分析。'},
  {type:'indicator', key:'sma50', cat:'trend', name:'SMA 50期間',
   url:'/trend/sma50/', defaultTitle:'SMA50の勝率｜中期トレンドの精度を検証',
   defaultMeta:'SMA50の勝率を検証。中期トレンド分析におけるシグナル精度をデータで解説。'},
  {type:'indicator', key:'sma_cross', cat:'trend', name:'SMAクロス（20/50）',
   url:'/trend/sma_cross/', defaultTitle:'SMAクロスの勝率｜20/50クロスの精度を検証',
   defaultMeta:'SMA20とSMA50のクロス戦略の勝率を検証。ゴールデンクロスの有効性を分析。'},
  {type:'indicator', key:'ema_cross', cat:'trend', name:'EMAクロス（9/21）',
   url:'/trend/ema_cross/', defaultTitle:'EMAクロスの勝率｜9/21戦略を検証',
   defaultMeta:'EMAクロス（9/21）の勝率を検証。短期トレンド戦略の有効性を分析。'},
  {type:'indicator', key:'ema21', cat:'trend', name:'EMA 21期間',
   url:'/trend/ema21/', defaultTitle:'EMA21の勝率｜トレンド追従の精度を検証',
   defaultMeta:'EMA21の勝率を検証。トレンドフォローにおけるエントリー精度を分析。'},
  {type:'indicator', key:'bollinger_bands', cat:'trend', name:'ボリンジャーバンド（20・2σ）',
   url:'/trend/bollinger_bands/', defaultTitle:'ボリンジャーバンドの勝率｜2σ戦略を検証',
   defaultMeta:'ボリンジャーバンド（20期間・2σ）の勝率を検証。逆張り・順張りの精度を分析。'},
  {type:'indicator', key:'bb_squeeze', cat:'trend', name:'BBスクイーズ',
   url:'/trend/bb_squeeze/', defaultTitle:'BBスクイーズの勝率｜収縮からのブレイク検証',
   defaultMeta:'ボリンジャーバンド収縮後のブレイク戦略の勝率を検証。相場の変動タイミングを分析。'},
  // ライン
  {type:'indicator', key:'pivot', cat:'line', name:'クラシックピボット',
   url:'/line/pivot/', defaultTitle:'ピボットポイントの勝率｜反発ポイントの精度を検証',
   defaultMeta:'ピボットポイントの勝率を検証。サポート・レジスタンスでの反発精度をバックテスト結果から分析。'},
  {type:'indicator', key:'fibonacci', cat:'line', name:'フィボナッチリトレースメント',
   url:'/line/fibonacci/', defaultTitle:'フィボナッチの勝率｜押し目・戻りの精度を検証',
   defaultMeta:'フィボナッチリトレースメントの勝率を検証。押し目・戻り売りの精度をデータで分析。'},
  {type:'indicator', key:'support_resistance', cat:'line', name:'動的サポート・レジスタンス',
   url:'/line/support_resistance/', defaultTitle:'動的サポレジの勝率｜トレンドライン精度を検証',
   defaultMeta:'動的サポート・レジスタンスの勝率を検証。自動検出した価格水準での反転精度を分析。'},
  // ボラティリティ
  {type:'indicator', key:'atr', cat:'volatility', name:'ATR（14期間）',
   url:'/volatility/atr/', defaultTitle:'ATRの勝率｜ボラティリティ分析の精度を検証',
   defaultMeta:'ATRの勝率をバックテストで検証。ボラティリティに基づくエントリー精度とトレード結果を分析。'},
  {type:'indicator', key:'volatility_index', cat:'volatility', name:'ボラティリティインデックス',
   url:'/volatility/volatility_index/', defaultTitle:'ボリンジャーバンド幅の勝率｜変動率分析を検証',
   defaultMeta:'ボリンジャーバンド幅（ボラティリティインデックス）の勝率を検証。スクイーズからのブレイク精度を分析。'},
  // ローソク足
  {type:'indicator', key:'hammer', cat:'candlestick', name:'ハンマー（金槌）',
   url:'/candlestick/hammer/', defaultTitle:'ハンマーの勝率｜反転シグナルの精度を検証',
   defaultMeta:'ハンマーの勝率をバックテストで検証。底値圏での反転シグナルの精度をデータで分析。'},
  {type:'indicator', key:'inverted_hammer', cat:'candlestick', name:'逆ハンマー（倒立金槌）',
   url:'/candlestick/inverted_hammer/', defaultTitle:'逆ハンマーの勝率｜天井シグナルの精度を検証',
   defaultMeta:'逆ハンマーの勝率を検証。天井圏での反転シグナルの精度をデータで分析。'},
  {type:'indicator', key:'doji', cat:'candlestick', name:'十字線（ドジ）',
   url:'/candlestick/doji/', defaultTitle:'十字線（ドジ）の勝率｜転換シグナルの精度を検証',
   defaultMeta:'十字線（ドジ）の勝率を検証。相場の転換点を示すシグナルの精度を分析。'},
  {type:'indicator', key:'bullish_engulfing', cat:'candlestick', name:'強気の包み足',
   url:'/candlestick/bullish_engulfing/', defaultTitle:'強気の包み足の勝率｜上昇転換の精度を検証',
   defaultMeta:'強気の包み足（ブリッシュエンゲルフィング）の勝率を検証。上昇転換シグナルの精度を分析。'},
  {type:'indicator', key:'bearish_engulfing', cat:'candlestick', name:'弱気の包み足',
   url:'/candlestick/bearish_engulfing/', defaultTitle:'弱気の包み足の勝率｜下降転換の精度を検証',
   defaultMeta:'弱気の包み足（ベアリッシュエンゲルフィング）の勝率を検証。下降転換シグナルの精度を分析。'},
  {type:'indicator', key:'three_white_soldiers', cat:'candlestick', name:'三白兵',
   url:'/candlestick/three_white_soldiers/', defaultTitle:'三白兵の勝率｜上昇継続の精度を検証',
   defaultMeta:'三白兵（スリーホワイトソルジャーズ）の勝率を検証。上昇継続シグナルの精度を分析。'},
  {type:'indicator', key:'three_black_crows', cat:'candlestick', name:'三羽烏',
   url:'/candlestick/three_black_crows/', defaultTitle:'三羽烏の勝率｜下降継続の精度を検証',
   defaultMeta:'三羽烏（スリーブラッククロウズ）の勝率を検証。下降継続シグナルの精度を分析。'},
  {type:'indicator', key:'pin_bar', cat:'candlestick', name:'ピンバー',
   url:'/candlestick/pin_bar/', defaultTitle:'ピンバーの勝率｜反転シグナルの精度を検証',
   defaultMeta:'ピンバーの勝率を検証。サポート・レジスタンスでの反転精度をデータで分析。'},
];

let savedData = {};
let currentFilter = 'all';
let modifiedRows = new Set();

// 文字数カウント色
function charColor(len, min, warn, max) {
  if (len > max) return 'over';
  if (len >= min) return 'ok';
  if (len >= warn) return 'warn';
  return '';
}

function updateCharCount(el, min, warnAt, max) {
  const len = el.value.length;
  const cc = el.nextElementSibling;
  if (!cc || !cc.classList.contains('char-count')) return;
  cc.textContent = len + '文字';
  cc.className = 'char-count ' + charColor(len, min, warnAt, max);
}

function markModified(rowKey, titleEl, metaEl) {
  titleEl.classList.add('modified');
  metaEl.classList.add('modified');
  modifiedRows.add(rowKey);
  document.getElementById('modifiedCount').textContent = `変更中のページ: ${modifiedRows.size}件`;
}

function buildRow(p) {
  const key = p.type + ':' + p.key;
  const saved = savedData[key] || {};
  const curTitle = saved.title || '';
  const curMeta  = saved.meta_description || '';

  const tr = document.createElement('tr');
  tr.className = 'seo-row';
  tr.dataset.cat = p.cat;
  tr.dataset.type = p.type;
  tr.dataset.name = p.name.toLowerCase();
  tr.dataset.key = key;

  const badge = p.type === 'category'
    ? `<span class="page-type-badge badge-category">カテゴリ</span>`
    : `<span class="page-type-badge badge-indicator">指標</span>`;

  tr.innerHTML = `
    <td>
      ${badge}
      <div class="page-name" style="margin-top:4px">${p.name}</div>
      <div class="page-url">${p.url}</div>
      ${saved.updated_at ? `<div style="font-size:10px;color:#475569;margin-top:3px">更新: ${saved.updated_at.slice(0,16)}</div>` : ''}
    </td>
    <td>
      <textarea class="seo-input title-input" rows="2"
        placeholder="${p.defaultTitle}">${curTitle}</textarea>
      <div class="char-count"></div>
      <div class="default-val">デフォルト: ${p.defaultTitle}</div>
    </td>
    <td>
      <textarea class="seo-input meta-input" rows="3"
        placeholder="${p.defaultMeta}">${curMeta}</textarea>
      <div class="char-count"></div>
      <div class="default-val">デフォルト: ${p.defaultMeta}</div>
    </td>
    <td>
      <button class="save-btn" onclick="savePage('${p.type}','${p.key}',this)">保存</button>
      <div class="save-status"></div>
    </td>`;

  const titleInput = tr.querySelector('.title-input');
  const metaInput  = tr.querySelector('.meta-input');

  // 初期文字数
  updateCharCount(titleInput, 20, 12, 65);
  updateCharCount(metaInput,  60, 40, 165);

  titleInput.addEventListener('input', () => {
    updateCharCount(titleInput, 20, 12, 65);
    markModified(key, titleInput, metaInput);
  });
  metaInput.addEventListener('input', () => {
    updateCharCount(metaInput, 60, 40, 165);
    markModified(key, titleInput, metaInput);
  });

  // 既存保存値があれば緑に
  if (curTitle || curMeta) {
    titleInput.classList.add('ok');
    metaInput.classList.add('ok');
  }

  return tr;
}

async function savePage(type, key, btn) {
  const row = btn.closest('tr');
  const titleVal = row.querySelector('.title-input').value.trim();
  const metaVal  = row.querySelector('.meta-input').value.trim();
  const status   = row.querySelector('.save-status');

  btn.disabled = true;
  status.className = 'save-status saving';
  status.textContent = '保存中...';

  try {
    const res = await fetch('/admin/api.php?action=seo_save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({page_type: type, page_key: key, title: titleVal, meta_description: metaVal})
    });
    const d = await res.json();
    if (d.status === 'ok') {
      status.className = 'save-status ok';
      status.textContent = '✓ 保存しました';
      row.classList.add('saved-flash');
      row.querySelector('.title-input').classList.remove('modified');
      row.querySelector('.meta-input').classList.remove('modified');
      row.querySelector('.title-input').classList.add('ok');
      row.querySelector('.meta-input').classList.add('ok');
      const rk = type + ':' + key;
      modifiedRows.delete(rk);
      document.getElementById('modifiedCount').textContent = `変更中のページ: ${modifiedRows.size}件`;
      setTimeout(() => { row.classList.remove('saved-flash'); status.textContent = ''; }, 3000);
    } else {
      status.className = 'save-status err';
      status.textContent = 'エラー: ' + d.message;
    }
  } catch(e) {
    status.className = 'save-status err';
    status.textContent = 'ネットワークエラー';
  }
  btn.disabled = false;
}

async function saveAll() {
  const rows = document.querySelectorAll('.seo-row');
  for (const row of rows) {
    if (row.style.display === 'none') continue;
    const key = row.dataset.key.split(':');
    const btn = row.querySelector('.save-btn');
    const titleModified = row.querySelector('.title-input').classList.contains('modified');
    const metaModified  = row.querySelector('.meta-input').classList.contains('modified');
    if (titleModified || metaModified) {
      await savePage(key[0], key.slice(1).join(':'), btn);
    }
  }
}

function filterPages(cat, btn) {
  currentFilter = cat;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}

function filterBySearch() {
  applyFilters();
}

function applyFilters() {
  const q = document.getElementById('searchBox').value.toLowerCase();
  document.querySelectorAll('.seo-row').forEach(row => {
    const matchCat  = currentFilter === 'all'
      || currentFilter === row.dataset.type
      || currentFilter === row.dataset.cat;
    const matchName = !q || row.dataset.name.includes(q);
    row.style.display = (matchCat && matchName) ? '' : 'none';
  });
}

async function init() {
  try {
    const res = await fetch('/admin/api.php?action=seo_init');
    const d   = await res.json();
    if (d.status === 'ok') savedData = d.data || {};
  } catch(e) {}

  const tbody = document.getElementById('seoTbody');
  PAGES.forEach(p => tbody.appendChild(buildRow(p)));

  document.getElementById('loading').style.display = 'none';
  document.getElementById('tableWrap').style.display = 'block';
}

function logout() {
  fetch('/admin/api.php?action=logout', {method:'POST'}).then(() => location.href='/admin/');
}

// ===== メインタブ切り替え =====
function switchMainTab(btn, id) {
  document.querySelectorAll('.main-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-seo').style.display     = id === 'seo'     ? '' : 'none';
  document.getElementById('tab-content').style.display = id === 'content' ? '' : 'none';
  document.getElementById('tab-ranking').style.display = id === 'ranking' ? '' : 'none';
  if (id === 'content' && !contentLoaded) initContent();
  if (id === 'ranking' && !rkInfoLoaded) initRankingTab();
}

// ===== コンテンツ管理 =====
let contentLoaded = false;
let contentData = {};

const PAIRS_OPT  = ['USD/JPY','GBP/JPY','EUR/JPY','任意'];
const TF_OPT     = ['5分足','15分足','30分足','1時間足','4時間足','日足'];
const REC_METHODS = ['short','day','swing'];

function buildRecRow(idx, val) {
  const sel_pair = PAIRS_OPT.map(p => `<option value="${p}" ${val.pair===p?'selected':''}>${p}</option>`).join('');
  const sel_tf   = TF_OPT.map(t => `<option value="${t}" ${val.tf===t?'selected':''}>${t}</option>`).join('');
  return `<div class="rec-row" data-idx="${idx}">
    <div class="rec-row-header">
      <span class="rec-num">${idx+1}</span>
      <input type="text" class="rec-ind" placeholder="指標名（例: RSI（相対力指数））" value="${val.indicator||''}">
      <select class="rec-pair">${sel_pair}</select>
      <select class="rec-tf">${sel_tf}</select>
    </div>
    <textarea class="rec-desc" rows="2" placeholder="この指標のこの足での活用方法・特徴を記入">${val.description||''}</textarea>
  </div>`;
}

function renderRecPanels() {
  REC_METHODS.forEach(m => {
    const key = m === 'short' ? 'ranking_short_term' : m === 'day' ? 'ranking_day_trade' : 'ranking_swing';
    let recs = [];
    try { recs = JSON.parse(contentData[key]?.value || '[]'); } catch(e) {}
    while (recs.length < 3) recs.push({indicator:'',pair:'USD/JPY',tf:'1時間足',description:''});
    document.getElementById('recs-' + m).innerHTML = [0,1,2].map(i => buildRecRow(i, recs[i]||{})).join('');
  });
}

async function initContent() {
  contentLoaded = true;
  try {
    const res = await fetch('/admin/api.php?action=content_init');
    const d   = await res.json();
    if (d.status === 'ok') {
      contentData = d.data || {};
      document.getElementById('ranking-title-input').value = contentData['ranking_title']?.value || '';
      document.getElementById('ranking-intro-input').value = contentData['ranking_intro']?.value  || '';
      document.getElementById('analysis-input').value      = contentData['ranking_analysis']?.value || '';
    }
  } catch(e) {}
  renderRecPanels();
  document.getElementById('content-loading').style.display = 'none';
  document.getElementById('content-body').style.display    = 'block';
}

async function savePageInfo() {
  const title = document.getElementById('ranking-title-input').value.trim();
  const intro = document.getElementById('ranking-intro-input').value.trim();
  const st    = document.getElementById('pageinfo-status');
  st.textContent = '保存中...'; st.className = 'cont-status saving';
  try {
    await fetch('/admin/api.php?action=content_save', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key:'ranking_title', value: title})
    });
    const res2 = await fetch('/admin/api.php?action=content_save', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key:'ranking_intro', value: intro})
    });
    const d = await res2.json();
    st.textContent = d.status==='ok' ? '✓ 保存しました' : 'エラー: '+d.message;
    st.className = 'cont-status ' + (d.status==='ok' ? 'ok' : 'err');
    if (d.status==='ok') setTimeout(()=>{st.textContent=''},3000);
  } catch(e) { st.textContent='ネットワークエラー'; st.className='cont-status err'; }
}

async function _saveTopPart(key, val, stId) {
  const st = document.getElementById(stId);
  st.textContent = '保存中...'; st.className = 'cont-status saving';
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({action:'content_save', key, value: val})
    });
    const d = await res.json();
    if (d.status === 'ok') { st.textContent = '✅ 保存完了'; st.className = 'cont-status ok'; }
    else { st.textContent = '❌ 失敗: ' + (d.message||''); st.className = 'cont-status err'; }
  } catch(e) { st.textContent = 'ネットワークエラー'; st.className = 'cont-status err'; }
}
async function saveAnalysis() {
  const val = document.getElementById('analysis-input').value;
  const st  = document.getElementById('analysis-status');
  st.textContent = '保存中...'; st.className = 'cont-status saving';
  try {
    const res = await fetch('/admin/api.php?action=content_save', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key:'ranking_analysis', value: val})
    });
    const d = await res.json();
    st.textContent = d.status==='ok' ? '✓ 保存しました' : 'エラー: '+d.message;
    st.className = 'cont-status ' + (d.status==='ok' ? 'ok' : 'err');
    if (d.status==='ok') setTimeout(()=>{st.textContent=''},3000);
  } catch(e) { st.textContent='ネットワークエラー'; st.className='cont-status err'; }
}

async function saveRecs(method, key) {
  const panel = document.getElementById('recs-' + method);
  const recs  = Array.from(panel.querySelectorAll('.rec-row')).map(row => ({
    indicator:   row.querySelector('.rec-ind').value.trim(),
    pair:        row.querySelector('.rec-pair').value,
    tf:          row.querySelector('.rec-tf').value,
    description: row.querySelector('.rec-desc').value.trim(),
  }));
  const st = document.getElementById(method + '-status');
  st.textContent = '保存中...'; st.className = 'cont-status saving';
  try {
    const res = await fetch('/admin/api.php?action=content_save', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({key, value: JSON.stringify(recs)})
    });
    const d = await res.json();
    st.textContent = d.status==='ok' ? '✓ 保存しました' : 'エラー: '+d.message;
    st.className = 'cont-status ' + (d.status==='ok' ? 'ok' : 'err');
    if (d.status==='ok') setTimeout(()=>{st.textContent=''},3000);
  } catch(e) { st.textContent='ネットワークエラー'; st.className='cont-status err'; }
}

function switchRecTab(btn, id) {
  document.querySelectorAll('.rec-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.rec-panel').forEach(p => p.style.display = 'none');
  btn.classList.add('active');
  document.getElementById('rec-' + id).style.display = 'block';
}

init();

// ===== シミュレーション履歴リセット =====
async function resetSimulationTrades() {
  if (!confirm('シミュレーション履歴とバックテスト結果をすべて削除します。\nこの操作は元に戻せません。よろしいですか？')) return;
  try {
    const res = await fetch('/admin/api.php', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'simulation_trades_reset'}),
    });
    const d = await res.json();
    alert(d.status === 'ok' ? d.message : 'エラー: ' + (d.message || '不明'));
    if (d.status === 'ok') loadRkInfo();
  } catch(e) {
    alert('通信エラーが発生しました');
  }
}

// ===== ランキング管理 =====
let rkInfoLoaded = false;
let rkPollTimer  = null;

function initRankingTab() {
  rkInfoLoaded = true;
  // デフォルト日付をセット
  const today = new Date();
  const fmt   = d => d.toISOString().slice(0, 10);
  const minus = (months) => { const d = new Date(today); d.setMonth(d.getMonth() - months); return d; };
  document.getElementById('rk-end').value         = fmt(today);
  document.getElementById('rk-start').value       = fmt(minus(12));
  document.getElementById('rk-swing-end').value   = fmt(today);
  document.getElementById('rk-swing-start').value = fmt(minus(6));
  document.getElementById('sbt-end').value   = fmt(today);
  document.getElementById('sbt-start').value = fmt(minus(12));
  loadRkInfo();
  loadSessInfo();
  loadSessBreakdown();
  pollRkStatus();   // フルBT実行中なら表示を復元
  pollSessStatus(); // セッション更新実行中なら表示を復元
  pollSbtStatus();  // セッション専用BT実行中なら表示を復元
}

async function loadRkInfo() {
  document.getElementById('rk-counts-loading').style.display = '';
  document.getElementById('rk-counts').style.display         = 'none';
  try {
    const res = await fetch('/admin/api.php?action=ranking_bt_info');
    const d   = await res.json();
    if (d.status === 'ok') {
      document.getElementById('rk-cnt-st').textContent  = d.simulation_trades.toLocaleString() + ' 件';
      document.getElementById('rk-cnt-bt').textContent  = d.backtest_results.toLocaleString()  + ' 件';
      document.getElementById('rk-cnt-sig').textContent = d.signals.toLocaleString()            + ' 件';
      document.getElementById('rk-last-bt').textContent = d.last_backtest_at;
    }
  } catch(e) {}
  document.getElementById('rk-counts-loading').style.display = 'none';
  document.getElementById('rk-counts').style.display         = '';
}

async function runRankingBt() {
  const btn       = document.getElementById('rk-run-btn');
  const st        = document.getElementById('rk-run-status');
  const forceFull = document.getElementById('rk-force-full').checked;

  const confirmMsg = forceFull
    ? 'すべての既存バックテストデータを削除してフルバックテストを実行します。\nこの操作は取り消せません。続行しますか？'
    : 'バックテストを実行しますか？\n全ペア×全タイムフレームを処理するため、数分〜数十分かかります。';
  if (!confirm(confirmMsg)) return;

  btn.disabled = true;
  st.className = 'cont-status saving';
  st.textContent = '送信中...';

  const params = {
    start_date:       document.getElementById('rk-start').value,
    end_date:         document.getElementById('rk-end').value,
    swing_start_date: document.getElementById('rk-swing-start').value,
    swing_end_date:   document.getElementById('rk-swing-end').value,
    force_full:       forceFull,
  };

  try {
    const res = await fetch('/admin/api.php?action=ranking_bt_run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params),
    });
    const d = await res.json();
    if (d.status === 'started') {
      st.className = 'cont-status ok';
      st.textContent = '実行開始しました';
      document.getElementById('rk-progress').style.display = '';
      pollRkStatus();
    } else if (d.status === 'busy') {
      st.className = 'cont-status err';
      st.textContent = d.message;
      btn.disabled = false;
    } else {
      st.className = 'cont-status err';
      st.textContent = 'エラー: ' + d.message;
      btn.disabled = false;
    }
  } catch(e) {
    st.className = 'cont-status err';
    st.textContent = 'ネットワークエラー';
    btn.disabled = false;
  }
}

async function pollRkStatus() {
  if (rkPollTimer) clearTimeout(rkPollTimer);
  try {
    const res = await fetch('/admin/api.php?action=ranking_bt_status');
    const d   = await res.json();
    const btn = document.getElementById('rk-run-btn');
    const st  = document.getElementById('rk-run-status');
    const prog = document.getElementById('rk-progress');
    const msg  = document.getElementById('rk-progress-msg');
    const bar  = document.getElementById('rk-progress-bar');

    if (d.status === 'running') {
      prog.style.display = '';
      msg.textContent    = d.message || '実行中...';
      btn.disabled       = true;
      st.className       = 'cont-status saving';
      st.textContent     = '実行中...';
      // プログレスバー（メッセージから [n/m] を抽出）
      const m = (d.message || '').match(/\[(\d+)\/(\d+)\]/);
      if (m) {
        bar.style.width = Math.round(parseInt(m[1]) / parseInt(m[2]) * 100) + '%';
      }
      rkPollTimer = setTimeout(pollRkStatus, 3000);
    } else if (d.status === 'done') {
      prog.style.display = 'none';
      btn.disabled       = false;
      st.className       = 'cont-status ok';
      st.textContent     = '✓ 完了: ' + d.message;
      bar.style.width    = '100%';
      loadRkInfo(); // 件数を更新
    } else if (d.status === 'error') {
      prog.style.display = 'none';
      btn.disabled       = false;
      st.className       = 'cont-status err';
      st.textContent     = 'エラー: ' + d.message;
    } else if (d.status === 'generating') {
      prog.style.display = '';
      msg.textContent    = d.message || '静的ページ生成中...';
      bar.style.width    = '95%';
      btn.disabled       = true;
      st.className       = 'cont-status saving';
      st.textContent     = '静的ページ生成中...';
      rkPollTimer = setTimeout(pollRkStatus, 3000);
    }
  } catch(e) {
    rkPollTimer = setTimeout(pollRkStatus, 5000);
  }
}

function downloadCsv() {
  const btn = document.getElementById('rk-csv-btn');
  btn.disabled = true;
  btn.textContent = 'ダウンロード中...';
  // ZIPダウンロード（リダイレクト方式）
  const link = document.createElement('a');
  link.href  = '/admin/api.php?action=ranking_csv';
  link.click();
  setTimeout(() => {
    btn.disabled    = false;
    btn.textContent = 'CSVダウンロード（ZIP）';
  }, 3000);
}

// ===== 市場セッション別ランキング更新 =====
let sessDays      = 1;
let sessPollTimer = null;

function setSessDays(btn) {
  document.querySelectorAll('.sess-days-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  sessDays = parseInt(btn.dataset.days, 10);
  document.getElementById('sess-days-label').textContent = btn.textContent;
}

async function loadSessInfo() {
  document.getElementById('sess-counts-loading').style.display = '';
  document.getElementById('sess-counts').style.display         = 'none';
  try {
    const res = await fetch('/admin/api.php?action=session_ranking_info');
    const d   = await res.json();
    if (d.status === 'ok') {
      document.getElementById('sess-cnt-rk').textContent  = d.ranking_count.toLocaleString() + ' 件';
      document.getElementById('sess-cnt-tr').textContent  = d.trade_count.toLocaleString()   + ' 件';
      document.getElementById('sess-latest').textContent  = d.latest_date;
    } else {
      document.getElementById('sess-cnt-rk').textContent  = 'エラー';
      document.getElementById('sess-cnt-tr').textContent  = 'エラー';
      document.getElementById('sess-latest').textContent  = '-';
    }
  } catch(e) {}
  document.getElementById('sess-counts-loading').style.display = 'none';
  document.getElementById('sess-counts').style.display         = '';
}

const SESS_META = {
  japan:  { label: "東京時間",    hours: "JST 08:00〜15:00", color: "#ef4444" },
  london: { label: "ロンドン時間", hours: "JST 15:00〜21:00", color: "#3b82f6" },
  ny:     { label: "NY時間",      hours: "JST 21:00〜08:00", color: "#8b5cf6" },
};

let sessBreakdownDates = [];

function fmtDateTab(iso) {
  const d = new Date(iso + 'T00:00:00');
  return `${d.getMonth()+1}月${d.getDate()}日`;
}

async function loadSessBreakdown(date) {
  document.getElementById('sess-breakdown-loading').style.display = '';
  document.getElementById('sess-breakdown').style.display         = 'none';
  try {
    const url = '/admin/api.php?action=session_trade_breakdown' + (date ? '&date=' + date : '');
    const res = await fetch(url);
    const d   = await res.json();
    if (d.status !== 'ok') return;

    // 日付タブを初回のみ構築
    if (sessBreakdownDates.length === 0 && d.dates && d.dates.length > 0) {
      sessBreakdownDates = d.dates;
      const tabWrap = document.getElementById('sess-date-tabs');
      tabWrap.innerHTML = d.dates.map(dt =>
        `<button class="sess-date-tab" data-date="${dt}" onclick="loadSessBreakdown('${dt}')">${fmtDateTab(dt)}</button>`
      ).join('');
    }
    // アクティブタブを更新
    document.querySelectorAll('.sess-date-tab').forEach(b => {
      b.classList.toggle('active', b.dataset.date === d.current_date);
    });

    const summaryMap = {};
    (d.summary || []).forEach(r => summaryMap[r.session_key] = r);

    ['japan', 'london', 'ny'].forEach(sk => {
      const s      = summaryMap[sk] || {};
      const top    = (d.top || {})[sk] || [];
      const m      = SESS_META[sk];
      const total  = parseInt(s.total  || 0);
      const wins   = parseInt(s.wins   || 0);
      const losses = parseInt(s.losses || 0);
      const wr     = total > 0 ? (wins / total * 100).toFixed(1) : '0.0';
      const wrNum  = parseFloat(wr);
      const barColor = wrNum >= 55 ? '#22c55e' : wrNum >= 50 ? '#f59e0b' : '#ef4444';

      const topHTML = top.length === 0
        ? '<div style="font-size:11px;color:#475569;padding:6px 0">データなし（2回未満）</div>'
        : top.map(t => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #1e293b">
              <span style="font-size:11px;color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:65%">${t.indicator_name}</span>
              <span style="font-size:11px;font-weight:700;color:${parseFloat(t.win_rate)>=55?'#4ade80':parseFloat(t.win_rate)>=50?'#fbbf24':'#f87171'};flex-shrink:0">
                ${t.win_rate}% <span style="color:#475569;font-weight:400">(${t.total}回)</span>
              </span>
            </div>`).join('');

      document.getElementById('sess-card-' + sk).innerHTML = `
        <div style="font-size:13px;font-weight:700;color:#f1f5f9;margin-bottom:2px">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${m.color};margin-right:6px"></span>
          ${m.label}
        </div>
        <div style="font-size:10px;color:#475569;margin-bottom:10px">${m.hours}</div>
        <div style="display:flex;gap:8px;margin-bottom:10px">
          <div style="flex:1;background:#0f172a;border-radius:6px;padding:8px;text-align:center">
            <div style="font-size:20px;font-weight:800;color:#60a5fa">${total.toLocaleString()}</div>
            <div style="font-size:10px;color:#64748b">総トレード</div>
          </div>
          <div style="flex:1;background:#0f172a;border-radius:6px;padding:8px;text-align:center">
            <div style="font-size:20px;font-weight:800;color:${barColor}">${wr}%</div>
            <div style="font-size:10px;color:#64748b">勝率</div>
          </div>
        </div>
        <div style="display:flex;gap:6px;margin-bottom:10px;font-size:11px">
          <div style="flex:1;background:#052e16;border-radius:4px;padding:5px;text-align:center">
            <div style="color:#4ade80;font-weight:700">${wins.toLocaleString()}</div>
            <div style="color:#64748b">WIN</div>
          </div>
          <div style="flex:1;background:#2d0a0a;border-radius:4px;padding:5px;text-align:center">
            <div style="color:#f87171;font-weight:700">${losses.toLocaleString()}</div>
            <div style="color:#64748b">LOSS</div>
          </div>
          <div style="flex:1;background:#0f172a;border-radius:4px;padding:5px;text-align:center">
            <div style="color:#94a3b8;font-weight:700">${parseInt(s.indicator_count||0)}</div>
            <div style="color:#64748b">指標数</div>
          </div>
        </div>
        <div style="background:#1e293b;height:6px;border-radius:3px;overflow:hidden;margin-bottom:10px">
          <div style="width:${wr}%;height:100%;background:${barColor};border-radius:3px;transition:width .6s"></div>
        </div>
        <div style="font-size:11px;font-weight:600;color:#64748b;margin-bottom:4px;margin-top:8px">上位指標（勝率）</div>
        ${topHTML}
      `;
    });

    document.getElementById('sess-breakdown-loading').style.display = 'none';
    document.getElementById('sess-breakdown').style.display         = '';
  } catch(e) {
    document.getElementById('sess-breakdown-loading').textContent = '読み込み失敗';
  }
}

async function runSessionUpdate(prevDay = false) {
  const btn     = document.getElementById(prevDay ? 'sess-prev-btn' : 'sess-run-btn');
  const otherBtn = document.getElementById(prevDay ? 'sess-run-btn' : 'sess-prev-btn');
  const st      = document.getElementById('sess-run-status');

  // 前日日付を計算（JST: サーバーはJST運用なのでローカル日付でよい）
  let targetDate = '';
  let dateLabel  = '当日';
  if (prevDay) {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    targetDate = d.toISOString().slice(0, 10);
    dateLabel  = targetDate + '（前日）';
  }

  if (!confirm(`${dateLabel}・過去${sessDays}日分のセッション別ランキングを再集計します。\nよろしいですか？`)) return;

  btn.disabled      = true;
  otherBtn.disabled = true;
  st.className      = 'cont-status saving';
  st.textContent    = '送信中...';

  try {
    const payload = {days: sessDays};
    if (targetDate) payload.target_date = targetDate;
    const res = await fetch('/admin/api.php?action=session_update_run', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify(payload),
    });
    const d = await res.json();
    if (d.status === 'started') {
      st.className = 'cont-status ok';
      st.textContent = '実行開始しました';
      document.getElementById('sess-progress').style.display = '';
      pollSessStatus();
    } else if (d.status === 'busy') {
      st.className   = 'cont-status err';
      st.textContent = d.message;
      btn.disabled   = false;
    } else {
      st.className   = 'cont-status err';
      st.textContent = 'エラー: ' + d.message;
      btn.disabled   = false;
    }
  } catch(e) {
    st.className   = 'cont-status err';
    st.textContent = 'ネットワークエラー';
    btn.disabled   = false;
  }
}

async function pollSessStatus() {
  if (sessPollTimer) clearTimeout(sessPollTimer);
  try {
    const res  = await fetch('/admin/api.php?action=session_update_status');
    const d    = await res.json();
    const btn  = document.getElementById('sess-run-btn');
    const st   = document.getElementById('sess-run-status');
    const prog = document.getElementById('sess-progress');
    const msg  = document.getElementById('sess-progress-msg');

    const btnPrev = document.getElementById('sess-prev-btn');
    if (d.status === 'running') {
      prog.style.display = '';
      msg.textContent    = d.message || '実行中...';
      btn.disabled       = true;
      btnPrev.disabled   = true;
      st.className       = 'cont-status saving';
      st.textContent     = '実行中...';
      sessPollTimer = setTimeout(pollSessStatus, 3000);
    } else if (d.status === 'done') {
      prog.style.display = 'none';
      btn.disabled       = false;
      btnPrev.disabled   = false;
      st.className       = 'cont-status ok';
      st.textContent     = '✓ ' + d.message;
      loadSessInfo();
    } else if (d.status === 'error') {
      prog.style.display = 'none';
      btn.disabled       = false;
      btnPrev.disabled   = false;
      st.className       = 'cont-status err';
      st.textContent     = 'エラー: ' + d.message;
    }
  } catch(e) {
    sessPollTimer = setTimeout(pollSessStatus, 5000);
  }
}

// ===== セッション専用バックテスト =====
let sbtPollTimer = null;

async function runSessionBt() {
  const btn = document.getElementById('sbt-run-btn');
  const st  = document.getElementById('sbt-run-status');

  if (!confirm('セッション専用バックテストを実行します。\n全テクニカル × 全ペア × 全時間軸を処理するため、数十分かかります。\nよろしいですか？')) return;

  btn.disabled = true;
  st.className = 'cont-status saving';
  st.textContent = '送信中...';

  const payload = {
    start_date: document.getElementById('sbt-start').value,
    end_date:   document.getElementById('sbt-end').value,
  };

  try {
    const res = await fetch('/admin/api.php?action=session_bt_run', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify(payload),
    });
    const d = await res.json();
    if (d.status === 'started') {
      st.className = 'cont-status ok';
      st.textContent = '実行開始しました';
      document.getElementById('sbt-progress').style.display = '';
      pollSbtStatus();
    } else if (d.status === 'busy') {
      st.className   = 'cont-status err';
      st.textContent = d.message;
      btn.disabled   = false;
    } else {
      st.className   = 'cont-status err';
      st.textContent = 'エラー: ' + d.message;
      btn.disabled   = false;
    }
  } catch(e) {
    st.className   = 'cont-status err';
    st.textContent = 'ネットワークエラー';
    btn.disabled   = false;
  }
}

async function pollSbtStatus() {
  if (sbtPollTimer) clearTimeout(sbtPollTimer);
  try {
    const res  = await fetch('/admin/api.php?action=session_bt_status');
    const d    = await res.json();
    const btn  = document.getElementById('sbt-run-btn');
    const st   = document.getElementById('sbt-run-status');
    const prog = document.getElementById('sbt-progress');
    const msg  = document.getElementById('sbt-progress-msg');

    if (d.status === 'running') {
      prog.style.display = '';
      msg.textContent    = d.message || '実行中...';
      btn.disabled       = true;
      st.className       = 'cont-status saving';
      st.textContent     = '実行中...';
      sbtPollTimer = setTimeout(pollSbtStatus, 4000);
    } else if (d.status === 'done') {
      prog.style.display = 'none';
      btn.disabled       = false;
      st.className       = 'cont-status ok';
      st.textContent     = '✓ ' + d.message;
      loadSessInfo();
    } else if (d.status === 'error') {
      prog.style.display = 'none';
      btn.disabled       = false;
      st.className       = 'cont-status err';
      st.textContent     = 'エラー: ' + d.message;
    }
  } catch(e) {
    sbtPollTimer = setTimeout(pollSbtStatus, 5000);
  }
}
</script>
<style>
.main-tab{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:8px;padding:8px 18px;font-size:13px;cursor:pointer;transition:all .15s}
.main-tab:hover,.main-tab.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.cont-section{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:20px}
.cont-title{font-size:16px;font-weight:700;color:#f1f5f9;margin-bottom:6px}
.cont-sub{font-size:12px;color:#64748b;margin-bottom:12px;line-height:1.5}
.cont-label{display:block;font-size:11px;color:#64748b;margin-bottom:4px;font-weight:600;letter-spacing:.04em}
.cont-input{width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:10px 12px;font-size:13px;outline:none;font-family:inherit}
.cont-input:focus{border-color:#3b82f6}
.cont-textarea{width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:12px;font-size:13px;line-height:1.7;resize:vertical;outline:none;font-family:inherit}
.cont-textarea:focus{border-color:#3b82f6}
.cont-actions{display:flex;align-items:center;gap:12px;margin-top:10px;justify-content:flex-end}
.cont-status{font-size:12px;color:#64748b}
.cont-status.ok{color:#4ade80}
.cont-status.err{color:#f87171}
.cont-status.saving{color:#fbbf24}
.rec-tab{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:20px;padding:5px 14px;font-size:12px;cursor:pointer;transition:all .15s}
.rec-tab:hover,.rec-tab.active{background:#1e3a5f;border-color:#3b82f6;color:#60a5fa}
.rec-row{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:10px}
.rec-row-header{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.rec-num{font-size:18px;font-weight:900;color:#3b82f6;width:24px;text-align:center}
.rec-ind{flex:1;min-width:180px;background:#1e293b;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 10px;font-size:12px;outline:none}
.rec-ind:focus{border-color:#3b82f6}
.rec-pair,.rec-tf{background:#1e293b;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:12px;outline:none;cursor:pointer}
.rec-pair:focus,.rec-tf:focus{border-color:#3b82f6}
.rec-desc{width:100%;background:#1e293b;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px 10px;font-size:12px;resize:vertical;outline:none;font-family:inherit;line-height:1.6}
.rec-desc:focus{border-color:#3b82f6}
/* ランキング管理 */
.rk-stat-box{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 16px;min-width:120px}
.rk-stat-lbl{font-size:10px;color:#64748b;margin-bottom:4px;font-weight:600;letter-spacing:.04em}
.rk-stat-val{font-size:20px;font-weight:800;color:#60a5fa}
</style>
</body>
</html>
