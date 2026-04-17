from datetime import datetime, timezone
from app import db


class QuantFlowTrade(db.Model):
    """QuantFlow シグナルエンジンによる月次バックテストの個別トレード記録"""

    __tablename__ = "quantflow_trades"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    currency_pair  = db.Column(db.String(10), nullable=False, index=True)
    year_month     = db.Column("year_month", db.String(7), nullable=False, index=True, quote=True)  # "2026-01"
    entry_ts       = db.Column(db.DateTime,   nullable=False)
    exit_ts        = db.Column(db.DateTime,   nullable=True)
    direction      = db.Column(db.String(4),  nullable=False)   # BUY / SELL
    score_at_entry = db.Column(db.Integer,    nullable=False)
    entry_price    = db.Column(db.Numeric(12, 5), nullable=False)
    exit_price     = db.Column(db.Numeric(12, 5), nullable=True)
    outcome        = db.Column(db.String(4),  nullable=True)    # WIN / LOSS
    profit_pips    = db.Column(db.Numeric(8, 2),  nullable=True)
    sl_pips        = db.Column(db.Numeric(8, 2),  nullable=True)
    tp_pips        = db.Column(db.Numeric(8, 2),  nullable=True)
    created_at     = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.Index("idx_qft_pair_ym", "currency_pair", "year_month"),
        db.Index("idx_qft_entry_ts", "entry_ts"),
    )

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "currency_pair":  self.currency_pair,
            "year_month":     self.year_month,
            "entry_ts":       self.entry_ts.strftime("%Y/%m/%d %H:%M") if self.entry_ts else None,
            "exit_ts":        self.exit_ts.strftime("%Y/%m/%d %H:%M")  if self.exit_ts  else None,
            "direction":      self.direction,
            "score_at_entry": self.score_at_entry,
            "entry_price":    float(self.entry_price)  if self.entry_price  else None,
            "exit_price":     float(self.exit_price)   if self.exit_price   else None,
            "outcome":        self.outcome,
            "profit_pips":    float(self.profit_pips)  if self.profit_pips  else None,
            "sl_pips":        float(self.sl_pips)      if self.sl_pips      else None,
            "tp_pips":        float(self.tp_pips)      if self.tp_pips      else None,
        }
