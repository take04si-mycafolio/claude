from datetime import datetime, timezone
from app import db


class TradingSignal(db.Model):
    __tablename__ = "trading_signals"

    id = db.Column(db.BigInteger, primary_key=True)
    currency_pair = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    signal_type = db.Column(db.String(10), nullable=False)   # BUY / SELL
    indicator_name = db.Column(db.String(80), nullable=False)
    indicator_category = db.Column(db.String(30))             # oscillator / trend / line / pattern / volatility
    entry_price = db.Column(db.Numeric(12, 5))
    sl_price = db.Column(db.Numeric(12, 5))
    tp_price = db.Column(db.Numeric(12, 5))
    sl_pips = db.Column(db.Numeric(8, 2))
    tp_pips = db.Column(db.Numeric(8, 2))
    win_rate = db.Column(db.Numeric(5, 2))
    confidence_score = db.Column(db.Numeric(5, 2))           # 0-100
    is_active = db.Column(db.Boolean, default=True)
    signal_time = db.Column(db.DateTime(timezone=True), nullable=False)
    expired_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.Index("idx_signal_pair_active", "currency_pair", "is_active"),
        db.Index("idx_signal_time", "signal_time"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "currency_pair": self.currency_pair,
            "timeframe": self.timeframe,
            "signal_type": self.signal_type,
            "indicator_name": self.indicator_name,
            "indicator_category": self.indicator_category,
            "entry_price": float(self.entry_price) if self.entry_price else None,
            "sl_price": float(self.sl_price) if self.sl_price else None,
            "tp_price": float(self.tp_price) if self.tp_price else None,
            "sl_pips": float(self.sl_pips) if self.sl_pips else None,
            "tp_pips": float(self.tp_pips) if self.tp_pips else None,
            "win_rate": float(self.win_rate) if self.win_rate else None,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "is_active": self.is_active,
            "signal_time": self.signal_time.isoformat() if self.signal_time else None,
        }
