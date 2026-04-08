from datetime import datetime, timezone
from app import db


class SimulationTrade(db.Model):
    """
    シミュレーショントレード（バックテスト個別取引ログ）

    バックテストで発生した1取引ごとのエントリー・エグジット情報を保存する。
    backtest_results テーブルとテクニカル指標で紐づく。
    """
    __tablename__ = "simulation_trades"

    id               = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # どのバックテスト結果に属するか（NULLableにしてカスタムBTにも使えるようにする）
    backtest_result_id = db.Column(
        db.BigInteger,
        db.ForeignKey("backtest_results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # 識別キー
    currency_pair    = db.Column(db.String(10),  nullable=False)
    timeframe        = db.Column(db.String(10),  nullable=False)
    indicator_name   = db.Column(db.String(80),  nullable=False)

    # エントリー情報
    entry_at         = db.Column(db.DateTime,    nullable=False)
    direction        = db.Column(db.String(4),   nullable=False)   # BUY / SELL
    entry_price      = db.Column(db.Numeric(12, 5), nullable=False)
    tp_price         = db.Column(db.Numeric(12, 5))
    sl_price         = db.Column(db.Numeric(12, 5))
    sl_pips          = db.Column(db.Numeric(8, 2))
    tp_pips          = db.Column(db.Numeric(8, 2))

    # エグジット情報
    exit_at          = db.Column(db.DateTime,    nullable=True)
    exit_price       = db.Column(db.Numeric(12, 5), nullable=True)
    outcome          = db.Column(db.String(4),   nullable=True)    # WIN / LOSS

    # 損益・残高
    profit_loss      = db.Column(db.Numeric(15, 2))  # 円（プラスが利益）
    capital_after    = db.Column(db.Numeric(15, 2))  # 取引後の残高

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.Index("idx_st_pair_tf_ind",  "currency_pair", "timeframe", "indicator_name"),
        db.Index("idx_st_entry_at",     "entry_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "backtest_result_id": self.backtest_result_id,
            "currency_pair":      self.currency_pair,
            "timeframe":          self.timeframe,
            "indicator_name":     self.indicator_name,
            "entry_at":           self.entry_at.strftime("%Y/%m/%d %H:%M") if self.entry_at else None,
            "exit_at":            self.exit_at.strftime("%Y/%m/%d %H:%M") if self.exit_at else None,
            "direction":          self.direction,
            "entry_price":        float(self.entry_price) if self.entry_price else None,
            "exit_price":         float(self.exit_price)  if self.exit_price  else None,
            "tp_price":           float(self.tp_price)    if self.tp_price    else None,
            "sl_price":           float(self.sl_price)    if self.sl_price    else None,
            "sl_pips":            float(self.sl_pips)     if self.sl_pips     else None,
            "tp_pips":            float(self.tp_pips)     if self.tp_pips     else None,
            "outcome":            self.outcome,
            "profit_loss":        float(self.profit_loss)  if self.profit_loss  else None,
            "capital_after":      float(self.capital_after) if self.capital_after else None,
        }
