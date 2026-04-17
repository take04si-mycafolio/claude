#!/usr/bin/env python3
"""
quantflow_trades テーブル作成マイグレーション
サーバー上で1回だけ実行:
  python tasks/migrate_quantflow.py
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SQL = """
CREATE TABLE IF NOT EXISTS quantflow_trades (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_pair  VARCHAR(10)    NOT NULL,
    `year_month`   VARCHAR(7)     NOT NULL,
    entry_ts       DATETIME       NOT NULL,
    exit_ts        DATETIME       DEFAULT NULL,
    direction      VARCHAR(4)     NOT NULL,
    score_at_entry INT            NOT NULL,
    entry_price    DECIMAL(12,5)  NOT NULL,
    exit_price     DECIMAL(12,5)  DEFAULT NULL,
    outcome        VARCHAR(4)     DEFAULT NULL,
    profit_pips    DECIMAL(8,2)   DEFAULT NULL,
    sl_pips        DECIMAL(8,2)   DEFAULT NULL,
    tp_pips        DECIMAL(8,2)   DEFAULT NULL,
    created_at     DATETIME       DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_qft_pair_ym   (currency_pair, `year_month`),
    INDEX idx_qft_entry_ts  (entry_ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def main():
    from app import create_app, db
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(db.text(SQL))
            db.session.commit()
            logger.info("quantflow_trades テーブルを作成しました（または既に存在します）")
            count = db.session.execute(db.text("SELECT COUNT(*) FROM quantflow_trades")).scalar()
            logger.info("現在の行数: %d", count)
        except Exception as e:
            logger.error("エラー: %s", e)
            raise

if __name__ == "__main__":
    main()
