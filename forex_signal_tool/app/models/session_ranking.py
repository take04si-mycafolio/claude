from datetime import datetime, timezone
from app import db


class SessionRanking(db.Model):
    """セッション別ランキングスナップショット（日次・上位5件）"""
    __tablename__ = "session_ranking_results"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_key    = db.Column(db.String(10),  nullable=False)   # japan/london/ny
    snapshot_date  = db.Column(db.Date,        nullable=False)   # 保存日（JST）
    rank_position  = db.Column(db.Integer,     nullable=False)   # 1〜5
    indicator_name = db.Column(db.String(80),  nullable=False)
    win_rate       = db.Column(db.Numeric(5, 2))
    profit_factor  = db.Column(db.Numeric(8, 4))
    max_drawdown   = db.Column(db.Numeric(15, 2))
    total_trades   = db.Column(db.Integer)
    avg_pnl        = db.Column(db.Numeric(15, 2))
    score          = db.Column(db.Integer)
    computed_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint(
            "session_key", "snapshot_date", "indicator_name",
            name="uq_session_ranking",
        ),
        db.Index("idx_sr_session_date", "session_key", "snapshot_date"),
    )


class SessionTradeHistory(db.Model):
    """セッション別トレード履歴（30日ローリング）"""
    __tablename__ = "session_trade_history"

    id             = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    session_key    = db.Column(db.String(10),  nullable=False)   # japan/london/ny
    trade_date     = db.Column(db.Date,        nullable=False)   # 取引JST日付
    indicator_name = db.Column(db.String(80),  nullable=False)
    currency_pair  = db.Column(db.String(10),  nullable=False)
    timeframe      = db.Column(db.String(10),  nullable=False)
    entry_at       = db.Column(db.DateTime,    nullable=False)   # UTC naive
    direction      = db.Column(db.String(4))
    entry_price    = db.Column(db.Numeric(12, 5))
    tp_price       = db.Column(db.Numeric(12, 5))
    sl_price       = db.Column(db.Numeric(12, 5))
    sl_pips        = db.Column(db.Numeric(8, 2))
    tp_pips        = db.Column(db.Numeric(8, 2))
    exit_at        = db.Column(db.DateTime)
    exit_price     = db.Column(db.Numeric(12, 5))
    outcome        = db.Column(db.String(4))   # WIN/LOSS
    profit_loss    = db.Column(db.Numeric(15, 2))
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.Index("idx_sth_session_date", "session_key", "trade_date"),
        db.Index("idx_sth_indicator",    "indicator_name", "session_key"),
        db.Index("idx_sth_entry_at",     "entry_at"),
    )
