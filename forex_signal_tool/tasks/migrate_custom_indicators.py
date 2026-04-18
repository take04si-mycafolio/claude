#!/usr/bin/env python3
"""
custom_v2_indicators テーブル作成マイグレーション
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQL = """
CREATE TABLE IF NOT EXISTS custom_v2_indicators (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(80)  NOT NULL UNIQUE,
    display_name    VARCHAR(120) NOT NULL,
    description     TEXT,
    good_markets    TEXT,
    bad_markets     TEXT,
    category        VARCHAR(30)  NOT NULL DEFAULT 'カスタム複合',
    strategy_config JSON         NOT NULL,
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_custom_ind_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def main():
    from app import create_app
    app = create_app()
    with app.app_context():
        from app import db
        db.session.execute(db.text(SQL))
        db.session.commit()
        logger.info("custom_v2_indicators テーブル作成完了")

if __name__ == "__main__":
    main()
