#!/usr/bin/env python3
"""
DBマイグレーション（テーブル追加）スクリプト
新しいテーブルを作成する。既存テーブルには影響なし。

サーバー上で1回だけ実行してください:
  /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/migrate_db.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    from app import create_app, db

    app = create_app()
    with app.app_context():
        # simulation_trades テーブルを SQL で直接作成（既存なら何もしない）
        sql = """
        CREATE TABLE IF NOT EXISTS simulation_trades (
            id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
            backtest_result_id BIGINT DEFAULT NULL,
            currency_pair      VARCHAR(10)  NOT NULL,
            timeframe          VARCHAR(10)  NOT NULL,
            indicator_name     VARCHAR(80)  NOT NULL,
            entry_at           DATETIME     NOT NULL,
            direction          VARCHAR(4)   NOT NULL,
            entry_price        DECIMAL(12,5),
            exit_at            DATETIME     DEFAULT NULL,
            exit_price         DECIMAL(12,5) DEFAULT NULL,
            tp_price           DECIMAL(12,5) DEFAULT NULL,
            sl_price           DECIMAL(12,5) DEFAULT NULL,
            sl_pips            DECIMAL(8,2)  DEFAULT NULL,
            tp_pips            DECIMAL(8,2)  DEFAULT NULL,
            outcome            VARCHAR(4)    DEFAULT NULL,
            profit_loss        DECIMAL(15,2) DEFAULT NULL,
            capital_after      DECIMAL(15,2) DEFAULT NULL,
            created_at         DATETIME      DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_st_pair_tf_ind (currency_pair, timeframe, indicator_name),
            INDEX idx_st_entry_at    (entry_at),
            INDEX idx_st_backtest_id (backtest_result_id),
            CONSTRAINT fk_st_backtest
                FOREIGN KEY (backtest_result_id)
                REFERENCES backtest_results(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        try:
            db.session.execute(db.text(sql))
            db.session.commit()
            logger.info("simulation_trades テーブルを作成しました（または既に存在します）")
        except Exception as e:
            logger.error("テーブル作成エラー: %s", e)
            raise

        # 確認
        result = db.session.execute(
            db.text("SELECT COUNT(*) FROM simulation_trades")
        ).scalar()
        logger.info("simulation_trades 現在の行数: %d", result)
        logger.info("マイグレーション完了")


if __name__ == "__main__":
    main()
