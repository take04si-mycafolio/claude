#!/usr/bin/env python3
"""
QuantFlow ライブシグナル監視タスク

quantflow_scores テーブルを読み、スコア方向転換を検出してポジションを記録する。
OPEN ポジションがあれば最新5分足でTP/SLをチェックする。
エントリー・決済時にメール通知を送る。

cron 例（5分ごと）:
  */5 * * * * /path/to/python3 /path/to/tasks/check_live_signal.py >> /tmp/live_signal.log 2>&1
"""
import sys
import os
import logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PAIR          = "USDJPY"
SCORE_THRESH  = 30
PIP           = 0.01   # USDJPY: 1pips = 0.01円


def _score_dir(score):
    if score is None:
        return None
    if score >= SCORE_THRESH:
        return "BUY"
    if score <= -SCORE_THRESH:
        return "SELL"
    return None


def _check_tp_sl(sig, db):
    """OPEN ポジションの5分足でTP/SLヒットを確認する。ヒットしたら CLOSED に更新してメール送信。"""
    from app.services.data_fetcher import get_candles
    from app.services.email_sender import send_quantflow_signal_email

    hours_open = max((datetime.utcnow() - sig.entry_ts).total_seconds() / 3600, 1)
    limit = min(int(hours_open * 12) + 20, 1000)

    df_5m = get_candles(PAIR, "5min", limit=limit)
    if df_5m.empty:
        logger.warning("5分足データが取得できません")
        return

    df_since = df_5m[df_5m["timestamp"] > sig.entry_ts].sort_values("timestamp")
    if df_since.empty:
        return

    sl_p = float(sig.sl_price)
    tp_p = float(sig.tp_price)

    for _, bar in df_since.iterrows():
        high = float(bar["high"])
        low  = float(bar["low"])

        if sig.direction == "BUY":
            hit_tp = high >= tp_p
            hit_sl = low  <= sl_p
        else:
            hit_tp = low  <= tp_p
            hit_sl = high >= sl_p

        if not (hit_sl or hit_tp):
            continue

        exit_p = sl_p if hit_sl else tp_p
        pp = round((exit_p - float(sig.entry_price)) / PIP, 2)
        if sig.direction == "SELL":
            pp = -pp

        sig.exit_ts     = bar["timestamp"]
        sig.exit_price  = exit_p
        sig.profit_pips = pp
        sig.outcome     = "LOSS" if hit_sl else "WIN"
        sig.exit_reason = "SL" if hit_sl else "TP"
        sig.status      = "CLOSED"
        db.session.commit()

        event = "EXIT_SL" if hit_sl else "EXIT_TP"
        logger.info("TP/SL hit: %s  %s  profit=%.2f pips", PAIR, event, pp)
        send_quantflow_signal_email(sig, event)
        return


def _force_close(sig, db):
    """シグナル変更によりOPENポジションを強制決済する（最新5分足クローズ価格）。"""
    from app.services.data_fetcher import get_candles

    df_5m = get_candles(PAIR, "5min", limit=2)
    if df_5m.empty:
        return

    bar    = df_5m.iloc[-1]
    exit_p = float(bar["close"])
    pp = round((exit_p - float(sig.entry_price)) / PIP, 2)
    if sig.direction == "SELL":
        pp = -pp

    sig.exit_ts     = bar["timestamp"]
    sig.exit_price  = exit_p
    sig.profit_pips = pp
    sig.outcome     = "WIN" if pp > 0 else "LOSS"
    sig.exit_reason = "SIGNAL_END"
    sig.status      = "CLOSED"
    db.session.commit()
    logger.info("Force closed: %s  profit=%.2f pips", PAIR, pp)


def _create_signal(direction, score, sl_pips, tp_pips):
    """現在の5分足オープン価格でエントリーシグナルを作成する。"""
    from app.services.data_fetcher import get_candles
    from app.models.quantflow_live_signal import QuantFlowLiveSignal

    df_5m = get_candles(PAIR, "5min", limit=2)
    if df_5m.empty:
        logger.error("5分足データが取得できません。シグナル作成を中止。")
        return None

    bar = df_5m.iloc[-1]
    ep  = float(bar["open"])

    if direction == "BUY":
        sl_p = ep - sl_pips * PIP
        tp_p = ep + tp_pips * PIP
    else:
        sl_p = ep + sl_pips * PIP
        tp_p = ep - tp_pips * PIP

    sig = QuantFlowLiveSignal(
        currency_pair  = PAIR,
        entry_ts       = bar["timestamp"],
        direction      = direction,
        score_at_entry = score,
        entry_price    = ep,
        sl_price       = sl_p,
        tp_price       = tp_p,
        sl_pips        = sl_pips,
        tp_pips        = tp_pips,
        status         = "OPEN",
    )
    logger.info(
        "New signal: %s  %s  score=%d  entry=%.3f  SL=%.3f  TP=%.3f",
        PAIR, direction, score, ep, sl_p, tp_p,
    )
    return sig


def main():
    from app import create_app, db
    from app.models.settings import Setting
    from app.models.quantflow_live_signal import QuantFlowLiveSignal
    from app.services.email_sender import send_quantflow_signal_email
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        sl_pips = float(Setting.get("quantflow_sl_pips") or 10.0)
        tp_pips = float(Setting.get("quantflow_tp_pips") or 20.0)

        # 1. quantflow_scores から直近2件取得
        rows = db.session.execute(text(
            "SELECT score, `timestamp` FROM quantflow_scores "
            "WHERE currency_pair = :pair "
            "ORDER BY `timestamp` DESC LIMIT 2"
        ), {"pair": PAIR}).fetchall()

        if len(rows) < 2:
            logger.warning("スコアデータが不足しています（%d 件）", len(rows))
            return

        curr_score, curr_ts = rows[0].score, rows[0].timestamp
        prev_score          = rows[1].score

        # 2. OPEN ポジション取得
        open_sig = QuantFlowLiveSignal.query.filter_by(
            currency_pair=PAIR, status="OPEN"
        ).first()

        # 3. 既存OPENポジションのTP/SLチェック
        if open_sig:
            _check_tp_sl(open_sig, db)
            # _check_tp_sl が CLOSED にした可能性があるので再取得
            db.session.refresh(open_sig)

        # 4. 方向転換検出
        curr_dir = _score_dir(curr_score)
        prev_dir = _score_dir(prev_score)

        if not curr_dir or curr_dir == prev_dir:
            logger.info(
                "方向転換なし: curr=%d(%s) prev=%d(%s)",
                curr_score, curr_dir or "neutral",
                prev_score, prev_dir or "neutral",
            )
            return

        # 5. 重複エントリー防止: 今回のスコアタイムスタンプ以降に既入ポジションがあればスキップ
        if open_sig and open_sig.status == "OPEN" and open_sig.entry_ts >= curr_ts:
            logger.info("このシグナルは既に記録済みです（entry_ts=%s）", open_sig.entry_ts)
            return

        # 6. まだOPENなら強制決済（SIGNAL_END）
        if open_sig and open_sig.status == "OPEN":
            _force_close(open_sig, db)
            send_quantflow_signal_email(open_sig, "EXIT_SIGNAL_END")

        # 7. 新シグナル作成
        new_sig = _create_signal(curr_dir, curr_score, sl_pips, tp_pips)
        if new_sig is None:
            return

        db.session.add(new_sig)
        db.session.commit()
        send_quantflow_signal_email(new_sig, "ENTRY")
        logger.info("シグナル記録完了: id=%d", new_sig.id)


if __name__ == "__main__":
    main()
