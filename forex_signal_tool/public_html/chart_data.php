<?php
/**
 * チャートデータAPI（DBから動的生成）
 * /chart_data.php?pair=USDJPY&tf=15min
 *
 * 静的JSONファイルの代わりにこのエンドポイントを使用することで
 * generate_static.py の実行タイミングに関係なく常に最新データを返す
 */

$_home = getenv('HOME') ?: '/home/xs539690';
require_once __DIR__ . '/admin/_config.php';

// ---- パラメータ検証 ----
$pair  = strtoupper(preg_replace('/[^A-Za-z]/', '', $_GET['pair'] ?? 'USDJPY'));
$tf    = preg_replace('/[^a-z0-9]/', '', strtolower($_GET['tf'] ?? '15min'));

$valid_pairs = ['USDJPY', 'GBPJPY', 'EURJPY'];
$valid_tfs   = ['15min', '1hr', '4hr', 'daily'];
if (!in_array($pair, $valid_pairs, true)) $pair = 'USDJPY';
if (!in_array($tf,   $valid_tfs,   true)) $tf   = '15min';

$limits = ['15min' => 120, '1hr' => 200, '4hr' => 150, 'daily' => 300];
$limit  = $limits[$tf];

// ---- DBからローソク足を取得 ----
$candles = $times = $closes = [];
try {
    $pdo  = get_pdo();
    $stmt = $pdo->prepare(
        'SELECT timestamp, open, high, low, close FROM price_data
         WHERE currency_pair=? AND timeframe=?
         ORDER BY timestamp DESC LIMIT ?'
    );
    $stmt->execute([$pair, $tf, $limit]);
    $rows = array_reverse($stmt->fetchAll());

    foreach ($rows as $row) {
        $ts = strtotime($row['timestamp'] . ' UTC'); // DBはUTC naive
        $o  = (float)$row['open'];
        $h  = (float)$row['high'];
        $l  = (float)$row['low'];
        $c  = (float)$row['close'];
        if (!is_finite($o) || !is_finite($h) || !is_finite($l) || !is_finite($c)) continue;
        $times[]   = $ts;
        $closes[]  = $c;
        $candles[] = ['time' => $ts,
                      'open'  => round($o, 3), 'high' => round($h, 3),
                      'low'   => round($l, 3), 'close' => round($c, 3)];
    }
} catch (Exception $e) {}

// データ不足時は空レスポンス
if (empty($candles)) {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['candles'=>[],'sma20'=>[],'sma50'=>[],'ema21'=>[],
                      'bb_upper'=>[],'bb_lower'=>[],'rsi'=>[],'trades'=>[],
                      'tp_level'=>null,'sl_level'=>null,'entry_level'=>null,'signal_type'=>null]);
    exit;
}

$n = count($closes);

// ---- SMA ----
function sma_series(array $closes, array $times, int $period): array {
    $n = count($closes); $out = [];
    for ($i = $period - 1; $i < $n; $i++) {
        $out[] = ['time'  => $times[$i],
                  'value' => round(array_sum(array_slice($closes, $i - $period + 1, $period)) / $period, 5)];
    }
    return $out;
}

// ---- EMA (adjust=False: alpha = 2/(span+1)) ----
function ema_series(array $closes, array $times, int $span): array {
    $alpha = 2.0 / ($span + 1); $ema = null; $out = [];
    foreach ($closes as $i => $c) {
        $ema   = ($ema === null) ? $c : $alpha * $c + (1 - $alpha) * $ema;
        $out[] = ['time' => $times[$i], 'value' => round($ema, 5)];
    }
    return $out;
}

// ---- Bollinger Bands (20, 2σ, ddof=1) ----
function bb_series(array $closes, array $times, int $period, float $mult): array {
    $n = count($closes); $upper = []; $lower = [];
    for ($i = $period - 1; $i < $n; $i++) {
        $w    = array_slice($closes, $i - $period + 1, $period);
        $mean = array_sum($w) / $period;
        $var  = 0;
        foreach ($w as $v) $var += ($v - $mean) ** 2;
        $std     = sqrt($var / ($period - 1));
        $upper[] = ['time' => $times[$i], 'value' => round($mean + $mult * $std, 5)];
        $lower[] = ['time' => $times[$i], 'value' => round($mean - $mult * $std, 5)];
    }
    return [$upper, $lower];
}

// ---- RSI14 (Wilder: alpha=1/14 = EWM com=13) ----
function rsi_series(array $closes, array $times): array {
    $alpha = 1.0 / 14; $ag = null; $al = null; $out = [];
    $n = count($closes);
    for ($i = 1; $i < $n; $i++) {
        $d    = $closes[$i] - $closes[$i - 1];
        $g    = max(0.0, $d);
        $l    = max(0.0, -$d);
        $ag   = ($ag === null) ? $g : $alpha * $g + (1 - $alpha) * $ag;
        $al   = ($al === null) ? $l : $alpha * $l + (1 - $alpha) * $al;
        $rsi  = ($al == 0) ? 100.0 : 100.0 - (100.0 / (1.0 + $ag / $al));
        $out[] = ['time' => $times[$i], 'value' => round($rsi, 2)];
    }
    return $out;
}

$sma20 = sma_series($closes, $times, 20);
$sma50 = sma_series($closes, $times, 50);
$ema21 = ema_series($closes, $times, 21);
[$bb_upper, $bb_lower] = bb_series($closes, $times, 20, 2.0);
$rsi   = rsi_series($closes, $times);

// ---- アクティブシグナルのTP/SLレベル ----
$tp_level = $sl_level = $entry_level = $signal_type = null;
try {
    $stmt = $pdo->prepare(
        'SELECT signal_type, entry_price, tp_price, sl_price FROM trading_signals
         WHERE currency_pair=? AND is_active=1
         ORDER BY confidence_score DESC LIMIT 1'
    );
    $stmt->execute([$pair]);
    if ($sig = $stmt->fetch()) {
        $signal_type = $sig['signal_type'];
        $entry_level = $sig['entry_price'] !== null ? (float)$sig['entry_price'] : null;
        $tp_level    = $sig['tp_price']    !== null ? (float)$sig['tp_price']    : null;
        $sl_level    = $sig['sl_price']    !== null ? (float)$sig['sl_price']    : null;
    }
} catch (Exception $e) {}

// ---- レスポンス ----
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store, must-revalidate');
echo json_encode([
    'candles'     => $candles,
    'sma20'       => $sma20,
    'sma50'       => $sma50,
    'ema21'       => $ema21,
    'bb_upper'    => $bb_upper,
    'bb_lower'    => $bb_lower,
    'rsi'         => $rsi,
    'trades'      => [],
    'tp_level'    => $tp_level,
    'sl_level'    => $sl_level,
    'entry_level' => $entry_level,
    'signal_type' => $signal_type,
], JSON_UNESCAPED_UNICODE | JSON_NUMERIC_CHECK);
