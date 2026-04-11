from datetime import datetime, timezone
from app import db


class BacktestDailySnapshot(db.Model):
    """
    バックテスト日次スナップショット

    毎日1回（または手動バックテスト実行後）に backtest_results の値と
    ランキング順位をコピーして保存する。

    用途:
      - 「今日の勝率」「今週の傾向」: snapshot_date で日付を絞り込んで比較
      - 「ランキング変動」: rank_position の前日差を表示
      - スコア推移グラフ: score × date で時系列可視化
    """
    __tablename__ = "backtest_daily_snapshots"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    snapshot_date  = db.Column(db.Date, nullable=False)
    currency_pair  = db.Column(db.String(10), nullable=False)
    timeframe      = db.Column(db.String(10), nullable=False)
    indicator_name = db.Column(db.String(80), nullable=False)

    # バックテスト指標（その日時点の最新値）
    win_rate       = db.Column(db.Numeric(5, 2))
    profit_factor  = db.Column(db.Numeric(8, 4))
    total_trades   = db.Column(db.Integer)
    winning_trades = db.Column(db.Integer)
    losing_trades  = db.Column(db.Integer)
    final_capital  = db.Column(db.Numeric(15, 2))
    max_drawdown   = db.Column(db.Numeric(15, 2))
    sl_pips        = db.Column(db.Numeric(8, 2))
    tp_pips        = db.Column(db.Numeric(8, 2))

    # ランキング（pair × TF 内でのスコア順位）
    rank_position  = db.Column(db.Integer)
    score          = db.Column(db.Integer)   # 100点満点スコア

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_date", "currency_pair", "timeframe", "indicator_name",
            name="uq_snapshot",
        ),
        db.Index("idx_snap_date",          "snapshot_date"),
        db.Index("idx_snap_pair_tf_date",  "currency_pair", "timeframe", "snapshot_date"),
        db.Index("idx_snap_ind_date",      "indicator_name", "snapshot_date"),
    )

    def to_dict(self) -> dict:
        return {
            "snapshot_date":  self.snapshot_date.isoformat() if self.snapshot_date else None,
            "currency_pair":  self.currency_pair,
            "timeframe":      self.timeframe,
            "indicator_name": self.indicator_name,
            "win_rate":       float(self.win_rate)      if self.win_rate      else None,
            "profit_factor":  float(self.profit_factor) if self.profit_factor else None,
            "total_trades":   self.total_trades,
            "rank_position":  self.rank_position,
            "score":          self.score,
        }
