-- ============================================================
-- FXシグナルツール 初期化SQL (MySQL / MariaDB用)
-- 実行方法:
--   mysql -u xs539690_forex -p xs539690_forex < migrations/001_init.sql
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 価格データ（ローソク足）
CREATE TABLE IF NOT EXISTS price_data (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_pair VARCHAR(10) NOT NULL,
    timeframe     VARCHAR(10) NOT NULL,
    timestamp     DATETIME NOT NULL,
    open          DECIMAL(12, 5) NOT NULL,
    high          DECIMAL(12, 5) NOT NULL,
    low           DECIMAL(12, 5) NOT NULL,
    close         DECIMAL(12, 5) NOT NULL,
    volume        BIGINT DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_price UNIQUE (currency_pair, timeframe, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_price_pair_tf_ts ON price_data (currency_pair, timeframe, timestamp);

-- バックテスト結果
CREATE TABLE IF NOT EXISTS backtest_results (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_pair     VARCHAR(10) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    indicator_name    VARCHAR(80) NOT NULL,
    indicator_category VARCHAR(30),
    signal_direction  VARCHAR(10),
    win_rate          DECIMAL(5, 2) NOT NULL,
    total_trades      INT NOT NULL,
    winning_trades    INT NOT NULL,
    losing_trades     INT NOT NULL,
    total_profit      DECIMAL(15, 2) NOT NULL,
    initial_capital   DECIMAL(15, 2) NOT NULL,
    final_capital     DECIMAL(15, 2) NOT NULL,
    sl_pips           DECIMAL(8, 2) NOT NULL,
    tp_pips           DECIMAL(8, 2) NOT NULL,
    backtest_hours    INT DEFAULT 12,
    max_drawdown      DECIMAL(15, 2),
    profit_factor     DECIMAL(8, 4),
    calculated_at     DATETIME NOT NULL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_bt_pair_tf_ind ON backtest_results (currency_pair, timeframe, indicator_name);
CREATE INDEX idx_bt_calculated ON backtest_results (calculated_at);

-- トレーディングシグナル
CREATE TABLE IF NOT EXISTS trading_signals (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_pair     VARCHAR(10) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    signal_type       VARCHAR(10) NOT NULL,
    indicator_name    VARCHAR(80) NOT NULL,
    indicator_category VARCHAR(30),
    entry_price       DECIMAL(12, 5),
    sl_price          DECIMAL(12, 5),
    tp_price          DECIMAL(12, 5),
    sl_pips           DECIMAL(8, 2),
    tp_pips           DECIMAL(8, 2),
    win_rate          DECIMAL(5, 2),
    confidence_score  DECIMAL(5, 2),
    is_active         TINYINT(1) DEFAULT 1,
    signal_time       DATETIME NOT NULL,
    expired_at        DATETIME,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_signal_pair_active ON trading_signals (currency_pair, is_active);
CREATE INDEX idx_signal_time ON trading_signals (signal_time);

-- AIレポート
CREATE TABLE IF NOT EXISTS ai_reports (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    report_type   VARCHAR(20) DEFAULT 'scheduled',
    content       TEXT NOT NULL,
    model_used    VARCHAR(80),
    tokens_used   INT,
    email_sent    TINYINT(1) DEFAULT 0,
    email_sent_at DATETIME,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_report_created ON ai_reports (created_at);

-- システム設定
CREATE TABLE IF NOT EXISTS settings (
    `key`       VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- デフォルト設定を挿入
INSERT IGNORE INTO settings (`key`, value, description) VALUES
  ('initial_capital', '1000000', 'バックテスト初期資金（円）'),
  ('sl_pips',         '20',      'ストップロス（pips）'),
  ('tp_pips',         '40',      'テイクプロフィット（pips）'),
  ('backtest_hours',  '12',      'バックテスト期間（時間）'),
  ('min_win_rate',    '55',      'シグナル表示最小勝率（%）'),
  ('min_trades',      '3',       'シグナル表示最小取引数'),
  ('report_times',    '06:00,12:00,18:00', 'レポート配信時刻（UTC、カンマ区切り）'),
  ('gemini_model',    'gemini-1.5-flash',  'Gemini AIモデル名');
