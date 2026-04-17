from datetime import datetime, timezone
from app import db


class QuantFlowScore(db.Model):
    """1時間足ごとの QuantFlow スコア記録"""

    __tablename__ = "quantflow_scores"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    currency_pair  = db.Column(db.String(10), nullable=False)
    timestamp      = db.Column(db.DateTime, nullable=False)
    score          = db.Column(db.Integer, nullable=False)
    trend_score    = db.Column(db.Integer, nullable=True)
    external_score = db.Column(db.Integer, nullable=True)
    close_price    = db.Column(db.Numeric(12, 5), nullable=True)
    created_at     = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("currency_pair", "timestamp", name="uniq_qfs_pair_ts"),
        db.Index("idx_qfs_pair_ts", "currency_pair", "timestamp"),
    )
