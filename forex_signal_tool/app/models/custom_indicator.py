"""
custom_v2_indicators テーブル — V2条件式で定義したカスタム複合指標
"""

from datetime import datetime, timezone
from app import db


class CustomV2Indicator(db.Model):
    __tablename__ = "custom_v2_indicators"

    id              = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name            = db.Column(db.String(80),  nullable=False, unique=True)
    display_name    = db.Column(db.String(120), nullable=False)
    description     = db.Column(db.Text,        nullable=True)
    good_markets    = db.Column(db.Text,        nullable=True)   # JSON配列
    bad_markets     = db.Column(db.Text,        nullable=True)   # JSON配列
    category        = db.Column(db.String(30),  nullable=False, default="カスタム複合")
    strategy_config = db.Column(db.JSON,        nullable=False)
    is_active       = db.Column(db.Boolean,     nullable=False, default=True)
    created_at      = db.Column(db.DateTime(timezone=True), nullable=False,
                                default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index("idx_custom_ind_active", "is_active"),
    )

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "name":            self.name,
            "display_name":    self.display_name,
            "description":     self.description or "",
            "good_markets":    self.good_markets or "[]",
            "bad_markets":     self.bad_markets  or "[]",
            "category":        self.category,
            "strategy_config": self.strategy_config,
            "is_active":       self.is_active,
            "created_at":      self.created_at.isoformat() if self.created_at else None,
        }
