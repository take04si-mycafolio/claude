from datetime import datetime, timezone
from app import db


class BacktestResult(db.Model):
    __tablename__ = "backtest_results"

    id = db.Column(db.BigInteger, primary_key=True)
    currency_pair = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    indicator_name = db.Column(db.String(80), nullable=False)
    indicator_category = db.Column(db.String(30))
    signal_direction = db.Column(db.String(10))               # BUY / SELL / BOTH
    win_rate = db.Column(db.Numeric(5, 2), nullable=False)
    total_trades = db.Column(db.Integer, nullable=False)
    winning_trades = db.Column(db.Integer, nullable=False)
    losing_trades = db.Column(db.Integer, nullable=False)
    total_profit = db.Column(db.Numeric(15, 2), nullable=False)
    initial_capital = db.Column(db.Numeric(15, 2), nullable=False)
    final_capital = db.Column(db.Numeric(15, 2), nullable=False)
    sl_pips = db.Column(db.Numeric(8, 2), nullable=False)
    tp_pips = db.Column(db.Numeric(8, 2), nullable=False)
    backtest_hours = db.Column(db.Integer, default=12)
    max_drawdown = db.Column(db.Numeric(15, 2))
    profit_factor = db.Column(db.Numeric(8, 4))
    calculated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.Index("idx_bt_pair_tf_ind", "currency_pair", "timeframe", "indicator_name"),
        db.Index("idx_bt_calculated", "calculated_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "currency_pair": self.currency_pair,
            "timeframe": self.timeframe,
            "indicator_name": self.indicator_name,
            "indicator_category": self.indicator_category,
            "signal_direction": self.signal_direction,
            "win_rate": float(self.win_rate),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_profit": float(self.total_profit),
            "initial_capital": float(self.initial_capital),
            "final_capital": float(self.final_capital),
            "sl_pips": float(self.sl_pips),
            "tp_pips": float(self.tp_pips),
            "backtest_hours": self.backtest_hours,
            "max_drawdown": float(self.max_drawdown) if self.max_drawdown else None,
            "profit_factor": float(self.profit_factor) if self.profit_factor else None,
            "calculated_at": self.calculated_at.isoformat(),
        }
