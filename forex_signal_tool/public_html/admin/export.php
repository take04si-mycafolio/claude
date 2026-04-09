<?php
/**
 * 分析用CSVエクスポート
 * AIによる分析に適した形式でデータをエクスポートする
 */
require_once __DIR__ . '/_config.php';
session_start();
require_login();

$type       = $_GET['type']      ?? '';
$pairFilter = $_GET['pair']      ?? 'all';
$tfFilter   = $_GET['tf']        ?? 'all';
$startDate  = $_GET['start']     ?? '';
$endDate    = $_GET['end']       ?? '';
$download   = isset($_GET['download']);

$validPairs = ['all', 'USDJPY', 'GBPJPY', 'EURJPY'];
$validTfs   = ['all', '5min', '15min', '30min', '1hr', '4hr', 'daily'];
if (!in_array($pairFilter, $validPairs, true)) $pairFilter = 'all';
if (!in_array($tfFilter, $validTfs, true))     $tfFilter   = 'all';

// ---- CSV ダウンロード処理 ----
if ($download && in_array($type, ['trades', 'daily', 'indicators'], true)) {
    try {
        $pdo = get_pdo();

        // WHERE句を組み立てる
        $where  = [];
        $params = [];

        if ($pairFilter !== 'all') {
            $where[]  = 'st.currency_pair = ?';
            $params[] = $pairFilter;
        }
        if ($tfFilter !== 'all') {
            $where[]  = 'st.timeframe = ?';
            $params[] = $tfFilter;
        }
        if ($startDate) {
            $where[]  = 'DATE(st.entry_at) >= ?';
            $params[] = $startDate;
        }
        if ($endDate) {
            $where[]  = 'DATE(st.entry_at) <= ?';
            $params[] = $endDate;
        }
        $whereSql = $where ? 'WHERE ' . implode(' AND ', $where) : '';

        // ---- タイムゾーン変換ヘルパー ----
        // DBはUTC保存前提、JSTはUTC+9
        // MySQLのCONVERT_TZ関数を使う（利用できない場合は DATE_ADD で +9h）
        $toJst = "DATE_ADD(%s, INTERVAL 9 HOUR)";

        if ($type === 'trades') {
            // ---- 取引履歴CSV ----
            $sql = "
                SELECT
                    st.id                                                           AS trade_id,
                    DATE(DATE_ADD(st.entry_at, INTERVAL 9 HOUR))                    AS date_jst,
                    DAYOFWEEK(DATE_ADD(st.entry_at, INTERVAL 9 HOUR))               AS dow_num,
                    ELT(DAYOFWEEK(DATE_ADD(st.entry_at, INTERVAL 9 HOUR)),
                        '日','月','火','水','木','金','土')                           AS day_of_week,
                    TIME_FORMAT(DATE_ADD(st.entry_at, INTERVAL 9 HOUR),'%H:%i')     AS entry_time_jst,
                    HOUR(DATE_ADD(st.entry_at, INTERVAL 9 HOUR))                    AS entry_hour_jst,
                    TIME_FORMAT(DATE_ADD(st.exit_at,  INTERVAL 9 HOUR),'%H:%i')     AS exit_time_jst,
                    TIMESTAMPDIFF(MINUTE, st.entry_at, st.exit_at)                  AS hold_minutes,
                    st.currency_pair,
                    st.timeframe,
                    st.indicator_name,
                    br.indicator_category,
                    st.direction,
                    st.entry_price,
                    st.exit_price,
                    st.sl_price,
                    st.tp_price,
                    st.sl_pips,
                    st.tp_pips,
                    CASE WHEN st.sl_pips > 0
                         THEN ROUND(st.tp_pips / st.sl_pips, 2)
                         ELSE NULL END                                               AS rr_ratio,
                    st.outcome,
                    st.profit_loss,
                    st.capital_after,
                    br.win_rate                                                      AS bt_win_rate,
                    br.profit_factor                                                 AS bt_profit_factor,
                    br.total_trades                                                  AS bt_total_trades,
                    br.sl_pips                                                       AS bt_sl_pips,
                    br.tp_pips                                                       AS bt_tp_pips,
                    br.max_drawdown                                                  AS bt_max_drawdown,
                    br.initial_capital                                               AS bt_initial_capital,
                    br.final_capital                                                 AS bt_final_capital
                FROM simulation_trades st
                LEFT JOIN backtest_results br
                    ON br.currency_pair  = st.currency_pair
                    AND br.timeframe     = st.timeframe
                    AND br.indicator_name = st.indicator_name
                {$whereSql}
                ORDER BY st.entry_at ASC
            ";
            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            $rows = $stmt->fetchAll();

            $headers = [
                'trade_id','日付_JST','曜日番号','曜日','エントリー時刻_JST','エントリー時間帯_JST',
                'エグジット時刻_JST','保有時間_分','通貨ペア','タイムフレーム','指標名','指標カテゴリ',
                'シグナル方向','エントリー価格','エグジット価格','SL価格','TP価格',
                'SL幅_pips','TP幅_pips','RR比','結果','損益_円','取引後残高_円',
                'BT勝率_%','BTプロフィットファクター','BT総取引数',
                'BT_SL_pips','BT_TP_pips','BT最大DD_円','BT初期資本_円','BT最終資本_円',
            ];
            $filename = 'trades_' . date('Ymd_His') . '.csv';

        } elseif ($type === 'daily') {
            // ---- 日別集計CSV ----
            $sql = "
                SELECT
                    DATE(DATE_ADD(st.entry_at, INTERVAL 9 HOUR))                AS date_jst,
                    DAYOFWEEK(DATE_ADD(st.entry_at, INTERVAL 9 HOUR))           AS dow_num,
                    ELT(DAYOFWEEK(DATE_ADD(st.entry_at, INTERVAL 9 HOUR)),
                        '日','月','火','水','木','金','土')                       AS day_of_week,
                    st.currency_pair,
                    st.timeframe,
                    st.indicator_name,
                    br.indicator_category,
                    COUNT(*)                                                     AS total_trades,
                    SUM(st.outcome = 'WIN')                                      AS wins,
                    SUM(st.outcome = 'LOSS')                                     AS losses,
                    ROUND(100.0 * SUM(st.outcome = 'WIN') / COUNT(*), 1)         AS win_rate_pct,
                    SUM(st.profit_loss)                                          AS total_pl_jpy,
                    SUM(st.direction = 'BUY')                                    AS buy_count,
                    SUM(st.direction = 'SELL')                                   AS sell_count,
                    AVG(TIMESTAMPDIFF(MINUTE, st.entry_at, st.exit_at))          AS avg_hold_min,
                    MAX(st.capital_after)                                        AS peak_capital,
                    MIN(st.capital_after)                                        AS trough_capital,
                    SUM(CASE WHEN st.profit_loss > 0 THEN st.profit_loss ELSE 0 END) AS gross_profit,
                    SUM(CASE WHEN st.profit_loss < 0 THEN ABS(st.profit_loss) ELSE 0 END) AS gross_loss
                FROM simulation_trades st
                LEFT JOIN backtest_results br
                    ON br.currency_pair   = st.currency_pair
                    AND br.timeframe      = st.timeframe
                    AND br.indicator_name = st.indicator_name
                {$whereSql}
                GROUP BY date_jst, st.currency_pair, st.timeframe, st.indicator_name, br.indicator_category
                ORDER BY date_jst ASC, st.currency_pair, st.timeframe, st.indicator_name
            ";
            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            $rows = $stmt->fetchAll();

            // gross_profit/gross_lossからPFを計算
            foreach ($rows as &$r) {
                $gl = (float)$r['gross_loss'];
                $gp = (float)$r['gross_profit'];
                $r['profit_factor'] = $gl > 0 ? round($gp / $gl, 3) : ($gp > 0 ? 999.999 : null);
            }
            unset($r);

            $headers = [
                '日付_JST','曜日番号','曜日','通貨ペア','タイムフレーム','指標名','指標カテゴリ',
                '取引数','勝ち','負け','勝率_%','損益合計_円',
                '買い回数','売り回数','平均保有時間_分',
                '最高残高_円','最低残高_円','総利益_円','総損失_円','プロフィットファクター',
            ];
            $filename = 'daily_' . date('Ymd_His') . '.csv';

        } else {
            // ---- 指標サマリーCSV ----
            $iWhere  = [];
            $iParams = [];
            if ($pairFilter !== 'all') { $iWhere[]  = 'currency_pair = ?'; $iParams[] = $pairFilter; }
            if ($tfFilter   !== 'all') { $iWhere[]  = 'timeframe = ?';     $iParams[] = $tfFilter; }
            $iWhereSql = $iWhere ? 'WHERE ' . implode(' AND ', $iWhere) : '';

            $sql = "
                SELECT
                    indicator_name,
                    indicator_category,
                    currency_pair,
                    timeframe,
                    signal_direction,
                    ROUND(win_rate, 2)                                       AS win_rate_pct,
                    total_trades,
                    winning_trades,
                    losing_trades,
                    ROUND(total_profit, 0)                                   AS total_profit_jpy,
                    ROUND(initial_capital, 0)                                AS initial_capital_jpy,
                    ROUND(final_capital, 0)                                  AS final_capital_jpy,
                    ROUND((final_capital - initial_capital)
                          / initial_capital * 100, 2)                        AS return_pct,
                    ROUND(sl_pips, 1)                                        AS sl_pips,
                    ROUND(tp_pips, 1)                                        AS tp_pips,
                    ROUND(tp_pips / NULLIF(sl_pips, 0), 2)                   AS rr_ratio,
                    ROUND(profit_factor, 4)                                  AS profit_factor,
                    ROUND(max_drawdown, 0)                                   AS max_drawdown_jpy,
                    DATE_FORMAT(DATE_ADD(calculated_at, INTERVAL 9 HOUR),
                                '%Y/%m/%d %H:%i')                            AS calculated_at_jst
                FROM backtest_results
                {$iWhereSql}
                ORDER BY win_rate DESC, total_trades DESC
            ";
            $stmt = $pdo->prepare($sql);
            $stmt->execute($iParams);
            $rows = $stmt->fetchAll();

            $headers = [
                '指標名','指標カテゴリ','通貨ペア','タイムフレーム','シグナル方向',
                '勝率_%','総取引数','勝ち数','負け数','総損益_円',
                '初期資本_円','最終資本_円','収益率_%',
                'SL_pips','TP_pips','RR比','プロフィットファクター',
                '最大DD_円','集計日時_JST',
            ];
            $filename = 'indicators_' . date('Ymd_His') . '.csv';
        }

        // ---- CSV 出力 ----
        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Cache-Control: no-cache, no-store');

        $out = fopen('php://output', 'w');
        // BOM (Excelで文字化けしないように)
        fwrite($out, "\xEF\xBB\xBF");
        fputcsv($out, $headers);

        foreach ($rows as $row) {
            $line = array_values($row);
            fputcsv($out, $line);
        }
        fclose($out);
        exit;

    } catch (Exception $e) {
        http_response_code(500);
        echo 'エラー: ' . htmlspecialchars($e->getMessage());
        exit;
    }
}

// ---- HTML 画面 ----
// 件数プレビュー取得
$counts = ['trades' => 0, 'indicators' => 0];
try {
    $pdo = get_pdo();
    $counts['trades']     = (int)$pdo->query('SELECT COUNT(*) FROM simulation_trades')->fetchColumn();
    $counts['indicators'] = (int)$pdo->query('SELECT COUNT(*) FROM backtest_results')->fetchColumn();
    $dateRange = $pdo->query(
        'SELECT MIN(DATE(entry_at)) AS mn, MAX(DATE(entry_at)) AS mx FROM simulation_trades'
    )->fetch();
} catch (Exception $e) {
    $dateRange = ['mn' => '', 'mx' => ''];
}
?>
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CSVエクスポート | FX Trend 管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
header{background:#1e293b;border-bottom:1px solid #334155;padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:18px;font-weight:700;color:#f1f5f9}
.nav a{color:#94a3b8;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:6px;margin-left:4px}
.nav a:hover{background:#334155;color:#f1f5f9}
.nav a.active{background:#1e3a5f;color:#60a5fa}
.nav a.logout-btn{color:#ef4444}
main{max-width:860px;margin:0 auto;padding:28px 20px}
h2{font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:6px}
.subtitle{font-size:13px;color:#64748b;margin-bottom:28px}
.export-card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:20px}
.export-card h3{font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
.export-card .desc{font-size:12px;color:#64748b;margin-bottom:16px;line-height:1.6}
.filter-row{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;align-items:flex-end}
.filter-group{display:flex;flex-direction:column;gap:5px}
.filter-group label{font-size:11px;color:#94a3b8}
.filter-group select,.filter-group input{background:#0f172a;border:1px solid #475569;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:12px;outline:none;min-width:120px}
.filter-group select:focus,.filter-group input:focus{border-color:#3b82f6}
.badge{display:inline-block;font-size:10px;background:#1e3a5f;color:#60a5fa;border-radius:4px;padding:2px 7px;margin-left:8px}
.btn-dl{display:inline-flex;align-items:center;gap:7px;background:#3b82f6;color:#fff;border:none;border-radius:7px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;transition:background .15s}
.btn-dl:hover{background:#2563eb}
.btn-dl svg{width:15px;height:15px}
.field-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.field-tag{font-size:10px;background:#0f172a;border:1px solid #334155;color:#94a3b8;border-radius:4px;padding:3px 8px}
.stats-row{display:flex;gap:16px;margin-bottom:20px}
.stat-box{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 18px;flex:1;text-align:center}
.stat-box .val{font-size:22px;font-weight:700;color:#60a5fa}
.stat-box .lbl{font-size:11px;color:#64748b;margin-top:2px}
</style>
</head>
<body>
<header>
  <h1>📊 CSVエクスポート</h1>
  <nav class="nav">
    <a href="/admin/">ダッシュボード</a>
    <a href="/admin/backtest.php">バックテスト</a>
    <a href="/admin/export.php" class="active">エクスポート</a>
    <a href="/admin/seo.php">SEO管理</a>
    <a href="/admin/settings.php">設定</a>
    <a href="#" class="logout-btn" onclick="logout()">ログアウト</a>
  </nav>
</header>

<main>
  <h2>分析用データエクスポート</h2>
  <p class="subtitle">AI分析・Excel解析向けにシミュレーション取引データをCSVでダウンロードできます。すべてのタイムスタンプはJST(日本時間)です。</p>

  <div class="stats-row">
    <div class="stat-box">
      <div class="val"><?= number_format($counts['trades']) ?></div>
      <div class="lbl">シミュレーション取引数</div>
    </div>
    <div class="stat-box">
      <div class="val"><?= number_format($counts['indicators']) ?></div>
      <div class="lbl">バックテスト指標数</div>
    </div>
    <div class="stat-box">
      <div class="val" style="font-size:14px">
        <?= $dateRange['mn'] ?? '—' ?><br>〜<br><?= $dateRange['mx'] ?? '—' ?>
      </div>
      <div class="lbl">取引データ期間</div>
    </div>
  </div>

  <!-- ---- 1. 取引履歴 ---- -->
  <div class="export-card">
    <h3>① 取引履歴 <span class="badge">1行=1取引</span></h3>
    <p class="desc">
      シミュレーショントレードの全履歴。曜日・時間帯・保有時間など時系列特徴量と、
      バックテスト統計（勝率・PF・DD）を結合済み。AI特徴量エンジニアリングに最適。
    </p>
    <form method="get" action="">
      <input type="hidden" name="type" value="trades">
      <input type="hidden" name="download" value="1">
      <div class="filter-row">
        <div class="filter-group">
          <label>通貨ペア</label>
          <select name="pair">
            <option value="all">全ペア</option>
            <option value="USDJPY">USDJPY</option>
            <option value="GBPJPY">GBPJPY</option>
            <option value="EURJPY">EURJPY</option>
          </select>
        </div>
        <div class="filter-group">
          <label>タイムフレーム</label>
          <select name="tf">
            <option value="all">全TF</option>
            <option value="5min">5分足</option>
            <option value="15min">15分足</option>
            <option value="30min">30分足</option>
            <option value="1hr">1時間足</option>
            <option value="4hr">4時間足</option>
            <option value="daily">日足</option>
          </select>
        </div>
        <div class="filter-group">
          <label>開始日</label>
          <input type="date" name="start" value="<?= htmlspecialchars($dateRange['mn'] ?? '') ?>">
        </div>
        <div class="filter-group">
          <label>終了日</label>
          <input type="date" name="end" value="<?= htmlspecialchars($dateRange['mx'] ?? '') ?>">
        </div>
        <button type="submit" class="btn-dl">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          ダウンロード (CSV)
        </button>
      </div>
    </form>
    <div class="field-list">
      <?php foreach ([
        'trade_id','日付_JST','曜日','エントリー時刻_JST','エントリー時間帯_JST',
        'エグジット時刻_JST','保有時間_分','通貨ペア','タイムフレーム','指標名','指標カテゴリ',
        '方向','エントリー価格','エグジット価格','SL価格','TP価格',
        'SL幅_pips','TP幅_pips','RR比','結果','損益_円','取引後残高_円',
        'BT勝率','BTプロフィットファクター','BT総取引数','BT_SL','BT_TP','BT最大DD'
      ] as $f): ?>
      <span class="field-tag"><?= $f ?></span>
      <?php endforeach; ?>
    </div>
  </div>

  <!-- ---- 2. 日別集計 ---- -->
  <div class="export-card">
    <h3>② 日別×指標 集計 <span class="badge">1行=1日×1指標</span></h3>
    <p class="desc">
      日付・通貨ペア・タイムフレーム・指標ごとに集計したサマリー。
      曜日別パフォーマンスや時期別トレンドの分析に適している。
    </p>
    <form method="get" action="">
      <input type="hidden" name="type" value="daily">
      <input type="hidden" name="download" value="1">
      <div class="filter-row">
        <div class="filter-group">
          <label>通貨ペア</label>
          <select name="pair">
            <option value="all">全ペア</option>
            <option value="USDJPY">USDJPY</option>
            <option value="GBPJPY">GBPJPY</option>
            <option value="EURJPY">EURJPY</option>
          </select>
        </div>
        <div class="filter-group">
          <label>タイムフレーム</label>
          <select name="tf">
            <option value="all">全TF</option>
            <option value="5min">5分足</option>
            <option value="15min">15分足</option>
            <option value="30min">30分足</option>
            <option value="1hr">1時間足</option>
            <option value="4hr">4時間足</option>
            <option value="daily">日足</option>
          </select>
        </div>
        <div class="filter-group">
          <label>開始日</label>
          <input type="date" name="start" value="<?= htmlspecialchars($dateRange['mn'] ?? '') ?>">
        </div>
        <div class="filter-group">
          <label>終了日</label>
          <input type="date" name="end" value="<?= htmlspecialchars($dateRange['mx'] ?? '') ?>">
        </div>
        <button type="submit" class="btn-dl">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          ダウンロード (CSV)
        </button>
      </div>
    </form>
    <div class="field-list">
      <?php foreach ([
        '日付_JST','曜日','通貨ペア','タイムフレーム','指標名','指標カテゴリ',
        '取引数','勝ち','負け','勝率_%','損益合計_円',
        '買い回数','売り回数','平均保有時間_分','最高残高_円','最低残高_円',
        '総利益_円','総損失_円','プロフィットファクター'
      ] as $f): ?>
      <span class="field-tag"><?= $f ?></span>
      <?php endforeach; ?>
    </div>
  </div>

  <!-- ---- 3. 指標サマリー ---- -->
  <div class="export-card">
    <h3>③ 指標サマリー <span class="badge">1行=1指標×1TF×1ペア</span></h3>
    <p class="desc">
      バックテスト結果の指標ごとの統計一覧。指標ランキングや収益性の比較に使用できる。
    </p>
    <form method="get" action="">
      <input type="hidden" name="type" value="indicators">
      <input type="hidden" name="download" value="1">
      <div class="filter-row">
        <div class="filter-group">
          <label>通貨ペア</label>
          <select name="pair">
            <option value="all">全ペア</option>
            <option value="USDJPY">USDJPY</option>
            <option value="GBPJPY">GBPJPY</option>
            <option value="EURJPY">EURJPY</option>
          </select>
        </div>
        <div class="filter-group">
          <label>タイムフレーム</label>
          <select name="tf">
            <option value="all">全TF</option>
            <option value="5min">5分足</option>
            <option value="15min">15分足</option>
            <option value="30min">30分足</option>
            <option value="1hr">1時間足</option>
            <option value="4hr">4時間足</option>
            <option value="daily">日足</option>
          </select>
        </div>
        <button type="submit" class="btn-dl">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          ダウンロード (CSV)
        </button>
      </div>
    </form>
    <div class="field-list">
      <?php foreach ([
        '指標名','指標カテゴリ','通貨ペア','タイムフレーム','シグナル方向',
        '勝率_%','総取引数','勝ち数','負け数','総損益_円',
        '初期資本_円','最終資本_円','収益率_%',
        'SL_pips','TP_pips','RR比','プロフィットファクター','最大DD_円','集計日時_JST'
      ] as $f): ?>
      <span class="field-tag"><?= $f ?></span>
      <?php endforeach; ?>
    </div>
  </div>
</main>

<script>
function logout() {
  fetch('/admin/api.php?action=logout', {method:'POST'}).then(() => location.href='/admin/');
}
</script>
</body>
</html>
