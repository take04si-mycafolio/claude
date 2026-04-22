-- 008: 会員バックテスト 日次使用ログ
CREATE TABLE IF NOT EXISTS member_bt_log (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id          BIGINT UNSIGNED NOT NULL,
    run_date         DATE            NOT NULL,
    run_count        INT             NOT NULL DEFAULT 0,
    last_result_json MEDIUMTEXT      NULL DEFAULT NULL,
    last_run_at      DATETIME        NULL DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_user_date (user_id, run_date),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
