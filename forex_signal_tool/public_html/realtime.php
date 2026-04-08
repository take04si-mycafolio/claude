<?php
/**
 * Yahoo Finance からリアルタイム為替レートを取得するPHPプロキシ
 * ブラウザから直接Yahoo Finance を叩くとCORSエラーになるため、
 * サーバーサイドでプロキシする。
 */

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-cache, no-store');

$symbols = [
    'USDJPY' => 'USDJPY=X',
    'GBPJPY' => 'GBPJPY=X',
    'EURJPY' => 'EURJPY=X',
];

$raw_pair = isset($_GET['pair']) ? strtoupper($_GET['pair']) : 'USDJPY';
$pair = preg_replace('/[^A-Z]/', '', $raw_pair);

if (!isset($symbols[$pair])) {
    echo json_encode(['ok' => false, 'error' => 'Invalid pair']);
    exit;
}

$symbol = $symbols[$pair];
$url = "https://query1.finance.yahoo.com/v8/finance/chart/{$symbol}?interval=1m&range=1d";

// curlで取得（file_get_contentsよりタイムアウト制御がしやすい）
$ch = curl_init();
curl_setopt_array($ch, [
    CURLOPT_URL            => $url,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 8,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_HTTPHEADER     => [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept: application/json',
        'Accept-Language: ja,en-US;q=0.9',
    ],
]);

$body = curl_exec($ch);
$err  = curl_error($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($body === false || $code !== 200) {
    echo json_encode(['ok' => false, 'error' => "curl failed: $err (HTTP $code)"]);
    exit;
}

$data = json_decode($body, true);
$result = $data['chart']['result'][0] ?? null;

if (!$result) {
    echo json_encode(['ok' => false, 'error' => 'No chart result']);
    exit;
}

$meta   = $result['meta'];
$price  = isset($meta['regularMarketPrice']) ? round((float)$meta['regularMarketPrice'], 3) : null;
$prev   = isset($meta['chartPreviousClose']) ? round((float)$meta['chartPreviousClose'], 3) : null;
$change = ($price !== null && $prev !== null) ? round($price - $prev, 3) : null;
$pct    = ($price !== null && $prev !== null && $prev != 0)
            ? round(($price - $prev) / $prev * 100, 3) : null;

echo json_encode([
    'ok'         => true,
    'pair'       => $pair,
    'price'      => $price,
    'prev_close' => $prev,
    'change'     => $change,
    'change_pct' => $pct,
    'ts'         => time(),
]);
