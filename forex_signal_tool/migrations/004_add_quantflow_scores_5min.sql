CREATE TABLE IF NOT EXISTS quantflow_scores_5min (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  currency_pair  VARCHAR(10)   NOT NULL,
  `timestamp`    DATETIME      NOT NULL,
  score          INT           NOT NULL,
  trend_score    INT           DEFAULT NULL,
  external_score INT           DEFAULT NULL,
  close_price    DECIMAL(12,5) DEFAULT NULL,
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_qfs5_pair_ts (currency_pair, `timestamp`),
  INDEX idx_qfs5_pair_ts (currency_pair, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
