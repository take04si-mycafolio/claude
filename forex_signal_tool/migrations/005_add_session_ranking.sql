-- セッション別ランキング（上位5件スナップショット・日次）
CREATE TABLE IF NOT EXISTS session_ranking_results (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_key    VARCHAR(10)    NOT NULL,
    snapshot_date  DATE           NOT NULL,
    rank_position  INT            NOT NULL,
    indicator_name VARCHAR(80)    NOT NULL,
    win_rate       DECIMAL(5,2),
    profit_factor  DECIMAL(8,4),
    max_drawdown   DECIMAL(15,2),
    total_trades   INT,
    avg_pnl        DECIMAL(15,2),
    score          INT,
    computed_at    DATETIME       NOT NULL DEFAULT UTC_TIMESTAMP(),
    CONSTRAINT uq_session_ranking UNIQUE (session_key, snapshot_date, indicator_name),
    INDEX idx_sr_session_date (session_key, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- セッション別トレード履歴（30日ローリング）
CREATE TABLE IF NOT EXISTS session_trade_history (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_key    VARCHAR(10)    NOT NULL,
    trade_date     DATE           NOT NULL,
    indicator_name VARCHAR(80)    NOT NULL,
    currency_pair  VARCHAR(10)    NOT NULL,
    timeframe      VARCHAR(10)    NOT NULL,
    entry_at       DATETIME       NOT NULL,
    direction      VARCHAR(4),
    entry_price    DECIMAL(12,5),
    tp_price       DECIMAL(12,5),
    sl_price       DECIMAL(12,5),
    sl_pips        DECIMAL(8,2),
    tp_pips        DECIMAL(8,2),
    exit_at        DATETIME,
    exit_price     DECIMAL(12,5),
    outcome        VARCHAR(4),
    profit_loss    DECIMAL(15,2),
    created_at     DATETIME       NOT NULL DEFAULT UTC_TIMESTAMP(),
    INDEX idx_sth_session_date (session_key, trade_date),
    INDEX idx_sth_indicator    (indicator_name, session_key),
    INDEX idx_sth_entry_at     (entry_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
