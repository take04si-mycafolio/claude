// FX Signal Tool - 共通ユーティリティ

/**
 * 通貨ペア表示名に変換
 * "USDJPY" → "USD/JPY"
 */
function formatPair(pair) {
  return pair.slice(0, 3) + '/' + pair.slice(3);
}

/**
 * 日時を "YYYY/MM/DD HH:MM UTC" 形式に変換
 */
function formatDateTime(isoString) {
  if (!isoString) return '--';
  const d = new Date(isoString);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const h = String(d.getUTCHours()).padStart(2, '0');
  const mi = String(d.getUTCMinutes()).padStart(2, '0');
  return `${y}/${mo}/${day} ${h}:${mi} UTC`;
}

/**
 * 数値を日本円形式にフォーマット
 */
function formatJPY(value) {
  return '¥' + Number(value).toLocaleString('ja-JP', { maximumFractionDigits: 0 });
}

/**
 * APIエラーをアラートで表示
 */
function showApiError(message) {
  console.error('[API Error]', message);
}
