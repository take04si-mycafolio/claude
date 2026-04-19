from datetime import datetime, timezone
from app import db


class QuantFlowLiveSignal(db.Model):
    __tablename__ = "quantflow_live_signals"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    currency_pair  = db.Column(db.String(10),    nullable=False)
    entry_ts       = db.Column(db.DateTime,      nullable=False)
    exit_ts        = db.Column(db.DateTime,      nullable=True)
    direction      = db.Column(db.String(4),     nullable=False)
    score_at_entry = db.Column(db.Integer,       nullable=False)
    entry_price    = db.Column(db.Numeric(12, 5), nullable=False)
    exit_price     = db.Column(db.Numeric(12, 5), nullable=True)
    sl_price       = db.Column(db.Numeric(12, 5), nullable=False)
    tp_price       = db.Column(db.Numeric(12, 5), nullable=False)
    sl_pips        = db.Column(db.Numeric(8, 2),  nullable=False)
    tp_pips        = db.Column(db.Numeric(8, 2),  nullable=False)
    outcome        = db.Column(db.String(4),     nullable=True)
    profit_pips    = db.Column(db.Numeric(8, 2),  nullable=True)
    status         = db.Column(db.String(8),     nullable=False, default="OPEN")
    exit_reason    = db.Column(db.String(16),    nullable=True)
    created_at     = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
