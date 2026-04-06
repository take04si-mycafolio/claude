from datetime import datetime, timezone
from app import db


class PriceData(db.Model):
    __tablename__ = "price_data"

    id = db.Column(db.BigInteger, primary_key=True)
    currency_pair = db.Column(db.String(10), nullable=False)
    timeframe = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    open = db.Column(db.Numeric(12, 5), nullable=False)
    high = db.Column(db.Numeric(12, 5), nullable=False)
    low = db.Column(db.Numeric(12, 5), nullable=False)
    close = db.Column(db.Numeric(12, 5), nullable=False)
    volume = db.Column(db.BigInteger, default=0)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint("currency_pair", "timeframe", "timestamp", name="uq_price"),
        db.Index("idx_price_pair_tf_ts", "currency_pair", "timeframe", "timestamp"),
    )

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": self.volume,
        }
