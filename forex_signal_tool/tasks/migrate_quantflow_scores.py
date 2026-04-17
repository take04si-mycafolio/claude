#!/usr/bin/env python3
"""
quantflow_scores テーブル作成マイグレーション
サーバーで1回だけ実行:
  python tasks/migrate_quantflow_scores.py
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQL = """
CREATE TABLE IF NOT EXISTS quantflow_scores (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_pair  VARCHAR(10)   NOT NULL,
    `timestamp`    DATETIME      NOT NULL,
    score          INT           NOT NULL,
    trend_score    INT           DEFAULT NULL,
    external_score INT           DEFAULT NULL,
    close_price    DECIMAL(12,5) DEFAULT NULL,
    created_at     DATETIME      DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_qfs_pair_ts (currency_pair, `timestamp`),
    INDEX idx_qfs_pair_ts (currency_pair, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def main():
    from app import create_app, db
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(db.text(SQL))
            db.session.commit()
            logger.info("quantflow_scores テーブルを作成しました（または既に存在します）")
            count = db.session.execute(db.text("SELECT COUNT(*) FROM quantflow_scores")).scalar()
            logger.info("現在の行数: %d", count)
        except Exception as e:
            logger.error("エラー: %s", e)
            raise

if __name__ == "__main__":
    main()
