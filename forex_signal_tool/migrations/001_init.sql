-- ============================================================
-- FXシグナルツール 初期化SQL
-- PostgreSQL用
-- 実行方法: psql -U user -d forex_signal_db -f migrations/001_init.sql
-- ============================================================

-- 価格データ（ローソク足）
CREATE TABLE IF NOT EXISTS price_data (
    id          BIGSERIAL PRIMARY KEY,
    currency_pair VARCHAR(10) NOT NULL,
    timeframe   VARCHAR(10) NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(12, 5) NOT NULL,
    high        NUMERIC(12, 5) NOT NULL,
    low         NUMERIC(12, 5) NOT NULL,
    close       NUMERIC(12, 5) NOT NULL,
    volume      BIGINT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_price UNIQUE (currency_pair, timeframe, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_price_pair_tf_ts ON price_data (currency_pair, timeframe, timestamp);

-- バックテスト結果
CREATE TABLE IF NOT EXISTS backtest_results (
    id                BIGSERIAL PRIMARY KEY,
    currency_pair     VARCHAR(10) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    indicator_name    VARCHAR(80) NOT NULL,
    indicator_category VARCHAR(30),
    signal_direction  VARCHAR(10),
    win_rate          NUMERIC(5, 2) NOT NULL,
    total_trades      INT NOT NULL,
    winning_trades    INT NOT NULL,
    losing_trades     INT NOT NULL,
    total_profit      NUMERIC(15, 2) NOT NULL,
    initial_capital   NUMERIC(15, 2) NOT NULL,
    final_capital     NUMERIC(15, 2) NOT NULL,
    sl_pips           NUMERIC(8, 2) NOT NULL,
    tp_pips           NUMERIC(8, 2) NOT NULL,
    backtest_hours    INT DEFAULT 12,
    max_drawdown      NUMERIC(15, 2),
    profit_factor     NUMERIC(8, 4),
    calculated_at     TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bt_pair_tf_ind ON backtest_results (currency_pair, timeframe, indicator_name);
CREATE INDEX IF NOT EXISTS idx_bt_calculated ON backtest_results (calculated_at);

-- トレーディングシグナル
CREATE TABLE IF NOT EXISTS trading_signals (
    id                BIGSERIAL PRIMARY KEY,
    currency_pair     VARCHAR(10) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    signal_type       VARCHAR(10) NOT NULL,
    indicator_name    VARCHAR(80) NOT NULL,
    indicator_category VARCHAR(30),
    entry_price       NUMERIC(12, 5),
    sl_price          NUMERIC(12, 5),
    tp_price          NUMERIC(12, 5),
    sl_pips           NUMERIC(8, 2),
    tp_pips           NUMERIC(8, 2),
    win_rate          NUMERIC(5, 2),
    confidence_score  NUMERIC(5, 2),
    is_active         BOOLEAN DEFAULT TRUE,
    signal_time       TIMESTAMPTZ NOT NULL,
    expired_at        TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signal_pair_active ON trading_signals (currency_pair, is_active);
CREATE INDEX IF NOT EXISTS idx_signal_time ON trading_signals (signal_time);

-- AIレポート
CREATE TABLE IF NOT EXISTS ai_reports (
    id          BIGSERIAL PRIMARY KEY,
    report_type VARCHAR(20) DEFAULT 'scheduled',
    content     TEXT NOT NULL,
    model_used  VARCHAR(80),
    tokens_used INT,
    email_sent  BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_report_created ON ai_reports (created_at);

-- システム設定
CREATE TABLE IF NOT EXISTS settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- デフォルト設定を挿入
INSERT INTO settings (key, value, description) VALUES
  ('initial_capital', '1000000', 'バックテスト初期資金（円）'),
  ('sl_pips', '20', 'ストップロス（pips）'),
  ('tp_pips', '40', 'テイクプロフィット（pips）'),
  ('backtest_hours', '12', 'バックテスト期間（時間）'),
  ('min_win_rate', '55', 'シグナル表示最小勝率（%）'),
  ('min_trades', '3', 'シグナル表示最小取引数'),
  ('report_times', '06:00,12:00,18:00', 'レポート配信時刻（UTC、カンマ区切り）'),
  ('gemini_model', 'gemini-1.5-flash', 'Gemini AIモデル名')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- 確認クエリ
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';
-- SELECT * FROM settings;
-- ============================================================
