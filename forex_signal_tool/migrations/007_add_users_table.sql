-- 007: 会員登録用 users テーブル
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    email         VARCHAR(255)     NOT NULL,
    password_hash VARCHAR(255)     NOT NULL,
    email_verified TINYINT(1)      NOT NULL DEFAULT 0,
    verify_token        VARCHAR(64) NULL DEFAULT NULL,
    verify_token_expires DATETIME  NULL DEFAULT NULL,
    reset_token         VARCHAR(64) NULL DEFAULT NULL,
    reset_token_expires  DATETIME  NULL DEFAULT NULL,
    created_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
