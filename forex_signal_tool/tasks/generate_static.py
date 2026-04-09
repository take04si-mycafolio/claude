#!/usr/bin/env python3
"""
静的HTML生成スクリプト
DBのデータを読み込み、各ページのHTMLを生成して public_html に保存する。

Cronジョブ設定例（30分ごと）:
  */30 * * * * cd /home/xs539690 && /home/xs539690/forex_env/bin/python3 \
    /home/xs539690/forex_project/forex_signal_tool/tasks/generate_static.py >> \
    /home/xs539690/forex_project/logs/generate.log 2>&1
"""

import sys
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))


def utc_str_to_jst(ts) -> str:
    """UTC datetime / str を JST文字列（Y/m/d H:M）に変換"""
    if ts is None:
        return ""
    try:
        if isinstance(ts, str):
            ts = ts[:19].replace("T", " ")
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elif hasattr(ts, "tzinfo"):
            dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        else:
            return str(ts)[:16]
        return dt.astimezone(JST).strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(ts)[:16]

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PUBLIC_HTML = "/home/xs539690/fx-trend.net/public_html"

INDICATOR_INFO = {
    "RSI_14": {
        "slug": "rsi_14", "category": "オシレーター",
        "display": "RSI（相対力指数）14期間",
        "description": "相対力指数（RSI）は、過去14本の値動きから相場の買われすぎ・売られすぎを0〜100のスケールで表すオシレーター指標です。モメンタムの変化を捉え、反転タイミングを探ります。",
        "feature": "30以下で売られすぎ（買いシグナル）、70以上で買われすぎ（売りシグナル）。ダイバージェンスでトレンド転換も検知できます。",
        "good": ["レンジ相場・横ばい相場", "トレンド転換の初動", "価格と乖離するダイバージェンス局面"],
        "bad": ["強いトレンド相場（高値圏・安値圏に張り付く）", "ニュース・重要指標発表直後の急変"],
    },
    "MACD_12_26_9": {
        "slug": "macd_12_26_9", "category": "オシレーター",
        "display": "MACD（12・26・9）",
        "description": "MACD（Moving Average Convergence Divergence）はEMA12とEMA26の差を取り、さらにその9期間EMAであるシグナル線との交差でエントリーを判断するモメンタム指標です。",
        "feature": "ヒストグラムがゼロ線を上抜けで買い、下抜けで売り。MACDラインとシグナル線のクロスでトレンド転換を捉えます。",
        "good": ["明確なトレンド相場", "トレンド転換の早期察知", "中長期の方向性確認"],
        "bad": ["レンジ相場（頻繁なクロスでダマシが多発）", "急騰・急落後の遅行"],
    },
    "Stochastic_14_3": {
        "slug": "stochastic_14_3", "category": "オシレーター",
        "display": "ストキャスティクス（14・3・3）",
        "description": "ストキャスティクスは過去14本の高値・安値に対する現在値の相対的位置を0〜100で表します。%K線と%D線の交差で売買シグナルを生成します。",
        "feature": "20以下の売られすぎゾーンでのゴールデンクロスが買いシグナル、80以上の買われすぎゾーンでのデッドクロスが売りシグナルです。",
        "good": ["レンジ相場・短期の反転狙い", "高値・安値圏での転換タイミング"],
        "bad": ["強いトレンド相場（一方に張り付く）", "ボラティリティが低い閑散相場"],
    },
    "CCI_20": {
        "slug": "cci_20", "category": "オシレーター",
        "display": "CCI（コモディティチャンネル指数）20期間",
        "description": "CCI（Commodity Channel Index）は価格の「典型価格」が移動平均からどれだけ乖離しているかを計測します。FXでも広く使われる汎用性の高いオシレーターです。",
        "feature": "+100超で買われすぎ（売り検討）、−100未満で売られすぎ（買い検討）。ゼロラインのクロスでトレンド方向も確認できます。",
        "good": ["サイクルが明確な相場", "ゼロラインクロスによるトレンドフォロー"],
        "bad": ["急騰・急落時の極端な値（ダイバージェンス判断が困難）"],
    },
    "Williams_R_14": {
        "slug": "williams_r_14", "category": "オシレーター",
        "display": "ウィリアムズ%R（14期間）",
        "description": "ウィリアムズ%Rは過去14本の高値から現在値の距離を−100〜0で表します。RSIと似た特性を持ちますが反応がやや早く、短期トレードで重宝されます。",
        "feature": "−80以下で売られすぎ（買いシグナル）、−20以上で買われすぎ（売りシグナル）。",
        "good": ["レンジ相場・短期スキャルピング", "転換点の素早い検知"],
        "bad": ["強いトレンド相場での逆張り", "スプレッドが広い閑散時間帯"],
    },
    "SMA_20": {
        "slug": "sma_20", "category": "トレンド",
        "display": "単純移動平均（SMA）20期間",
        "description": "過去20本の終値を単純平均したラインです。短〜中期のトレンド方向を示す基本指標で、価格との位置関係でトレンドの有無を判断します。",
        "feature": "価格がSMA20を上回れば上昇トレンド、下回れば下降トレンドと判断。動的なサポート・レジスタンスとしても機能します。",
        "good": ["中期トレンドフォロー", "押し目・戻り売りのタイミング確認"],
        "bad": ["レンジ相場（価格が頻繁にSMAを上下してダマシ多発）"],
    },
    "SMA_50": {
        "slug": "sma_50", "category": "トレンド",
        "display": "単純移動平均（SMA）50期間",
        "description": "過去50本の終値の単純平均で、中長期トレンドの方向性を示します。多くのトレーダーが注目する重要なテクニカルレベルです。",
        "feature": "価格がSMA50より上にある間は中長期的な上昇トレンド継続と判断。機関投資家も意識するキーレベルです。",
        "good": ["中長期トレンドフォロー", "押し目・戻り売りのポイント特定"],
        "bad": ["レンジ・短期の急変への対応（遅行性が大きい）"],
    },
    "SMA_Cross_20_50": {
        "slug": "sma_cross_20_50", "category": "トレンド",
        "display": "SMAクロス（20期間 / 50期間）",
        "description": "SMA20がSMA50を上抜けるゴールデンクロスで買いシグナル、下抜けるデッドクロスで売りシグナルを生成するトレンドフォロー系指標です。",
        "feature": "ゴールデンクロス：強気相場転換の確認。デッドクロス：弱気相場転換の確認。中長期のトレンド転換に有効です。",
        "good": ["中長期トレンドの転換確認", "方向性が明確な相場"],
        "bad": ["レンジ相場（頻繁なクロスでダマシが多発）", "短期の素早い動きへの対応"],
    },
    "EMA_Cross_9_21": {
        "slug": "ema_cross_9_21", "category": "トレンド",
        "display": "EMAクロス（9期間 / 21期間）",
        "description": "EMA9がEMA21を上抜け・下抜けでシグナルを生成します。指数移動平均はSMAより直近の価格に重みを置くため、SMAクロスより素早く反応します。",
        "feature": "EMA9がEMA21を上抜けで買い転換、下抜けで売り転換。短中期のトレンド初動を捉えるのに優れています。",
        "good": ["トレンドの初動を素早くキャッチ", "短中期スウィングトレード"],
        "bad": ["ノイズの多い相場（小さな動きにも過剰反応）", "低ボラティリティ時期"],
    },
    "EMA_21": {
        "slug": "ema_21", "category": "トレンド",
        "display": "指数移動平均（EMA）21期間",
        "description": "過去21本の終値に指数的な重みをかけた移動平均です。SMAより直近の価格変動を重視するため、トレンド変化への反応が早いのが特徴です。",
        "feature": "価格がEMA21の上に位置すれば上昇トレンド、下に位置すれば下降トレンドと判断。動的サポート・レジスタンスとして機能します。",
        "good": ["トレンドフォロー", "押し目・戻り売りの動的ライン確認"],
        "bad": ["横ばいレンジ相場でのダマシ"],
    },
    "BollingerBands_20_2": {
        "slug": "bollinger_bands_20_2", "category": "トレンド",
        "display": "ボリンジャーバンド（20期間・2σ）",
        "description": "移動平均線の上下に標準偏差×2のバンドを描きます。価格はバンド内に収まる確率が約95%とされ、バンドへの接触・逸脱が売買シグナルになります。",
        "feature": "下バンドタッチで買い、上バンドタッチで売り（逆張り）。バンドの拡張はトレンド加速、収縮はブレイクアウト前兆を示します。",
        "good": ["レンジ相場でのバンド回帰狙い", "ボラティリティの変化察知"],
        "bad": ["強いトレンド時のバンドウォーク（バンド沿いに一方向に走り続ける）"],
    },
    "BB_Squeeze": {
        "slug": "bb_squeeze", "category": "トレンド",
        "display": "BBスクイーズ（ボリンジャーバンド収縮）",
        "description": "ボリンジャーバンドのバンド幅が過去平均より大幅に縮小した「スクイーズ」状態を検出します。スクイーズ後には大きな価格変動が起きやすいとされます。",
        "feature": "バンド幅が平均の80%以下に収縮するとスクイーズ判定。ブレイクアウトの方向性を価格の位置（ミッドライン上下）で判断します。",
        "good": ["大きなブレイクアウト前の仕込み", "低ボラティリティからの急変動の予測"],
        "bad": ["既に大きく動いている高ボラティリティ相場", "方向感の事前確認が難しい"],
    },
    "Pivot_Classic": {
        "slug": "pivot_classic", "category": "ライン",
        "display": "クラシックピボットポイント",
        "description": "前日（または前期間）の高値・安値・終値から計算するピボットポイントと、3段階のサポート（S1〜S3）・レジスタンス（R1〜R3）レベルです。",
        "feature": "ピボットより価格が上にあれば強気、下にあれば弱気。R1突破で強気継続、S1割れで弱気継続と判断します。",
        "good": ["デイトレード・スキャルピング", "重要価格水準での反転・ブレイクアウト狙い"],
        "bad": ["強いトレンドでのレベル突き抜け", "週またぎや指標発表時の精度低下"],
    },
    "Fibonacci_Retracement": {
        "slug": "fibonacci_retracement", "category": "ライン",
        "display": "フィボナッチリトレースメント",
        "description": "スウィングの高値・安値間を黄金比（23.6%・38.2%・50%・61.8%・78.6%）で分割し、押し目・戻り売りの目標レベルを示します。多くのトレーダーが意識する重要レベルです。",
        "feature": "上昇トレンドでの押し目買いは38.2%〜61.8%が目安。61.8%（黄金比）付近は特に強い反転ポイントとして知られます。",
        "good": ["トレンド相場での押し目・戻り売りエントリー", "TP/SL目標価格の設定"],
        "bad": ["レンジ相場（スウィングの特定が困難）", "スウィングの起点終点の主観的判断"],
    },
    "Support_Resistance": {
        "slug": "support_resistance", "category": "ライン",
        "display": "動的サポート・レジスタンス",
        "description": "過去のスウィング高値・安値からサポートラインとレジスタンスラインを自動検出します。価格がこれらのレベルに近づいた際に反転・ブレイクアウトのシグナルを生成します。",
        "feature": "直近のサポートに近い→買いシグナル、直近のレジスタンスに近い→売りシグナル。チャートの節目を客観的に特定します。",
        "good": ["節目での反発・反落狙い", "ブレイクアウト後の値動き予測"],
        "bad": ["強いニュースや経済指標によるレベル崩壊", "高ボラティリティ時の急激なブレイク"],
    },
    "ATR_14": {
        "slug": "atr_14", "category": "ボラティリティ",
        "display": "ATR（平均真の値動き）14期間",
        "description": "ATR（Average True Range）は過去14本の「真の値動き（TR）」の平均で、現在のボラティリティ水準を客観的に把握できます。SL・TP設定の基準として広く使われます。",
        "feature": "ATRが平均より20%以上高い場合に高ボラティリティと判定し、トレンド方向へシグナルを生成。動的なSL（ATR×1.5）・TP（ATR×3）も提案します。",
        "good": ["ボラティリティに基づくSL/TP設定", "高ボラ時のトレンドフォロー"],
        "bad": ["ATR単独での方向性判断は難しい", "閑散相場・低ボラ時のシグナル不足"],
    },
    "Volatility_Index": {
        "slug": "volatility_index", "category": "ボラティリティ",
        "display": "ボラティリティインデックス（BBバンド幅）",
        "description": "ボリンジャーバンドのバンド幅をボラティリティの代理指標として使用します。バンド幅が過去平均より大幅に縮小した「スクイーズ」状態でブレイクアウトを予測します。",
        "feature": "バンド幅が平均の70%以下に縮小するとスクイーズ判定し、価格の位置（ミッドライン上下）で方向を判断します。",
        "good": ["静寂期後の大きな値動きへの備え", "エネルギー蓄積の確認"],
        "bad": ["方向予測の精度が低い", "偽のスクイーズ（すぐ反転することも）"],
    },
    "Hammer": {
        "slug": "hammer", "category": "ローソク足パターン",
        "display": "ハンマー（金槌）",
        "description": "下ヒゲが実体の2倍以上で上ヒゲがほとんどない陽線（または陰線）です。下降トレンドの末期に現れると買い転換のシグナルとされます。",
        "feature": "下ヒゲが長いほど買い圧力が強く信頼性が上がります。出来高増加・重要サポートレベル付近での出現は特に有効です。",
        "good": ["下降トレンドの末期・底値圏", "サポートレベルや過去の安値付近"],
        "bad": ["上昇トレンド中（逆張りとなり精度低下）", "上位足の確認なしの単独使用"],
    },
    "Inverted_Hammer": {
        "slug": "inverted_hammer", "category": "ローソク足パターン",
        "display": "逆ハンマー（倒立金槌）",
        "description": "上ヒゲが実体の2倍以上で下ヒゲがほとんどないローソク足です。上昇トレンドの末期に現れると弱気転換のシグナルとなります。",
        "feature": "上ヒゲが長いほど売り圧力が強く信頼性が上がります。レジスタンスレベル付近での出現と組み合わせると精度が向上します。",
        "good": ["上昇トレンドの末期・天井圏", "レジスタンスレベルや過去の高値付近"],
        "bad": ["下降トレンド中", "単独での使用（他の指標との組み合わせが重要）"],
    },
    "Doji": {
        "slug": "doji", "category": "ローソク足パターン",
        "display": "十字線（ドジ）",
        "description": "始値と終値がほぼ同値で、実体がほとんどない十字型のローソク足です。買いと売りが拮抗した状態を示し、相場の転換点を示唆することがあります。",
        "feature": "トレンドの末期に出現すると転換シグナル。上昇トレンド後のドジは弱気転換、下降トレンド後のドジは強気転換の前触れです。",
        "good": ["トレンド転換の前兆察知", "重要なチャートポイント（節目）での出現"],
        "bad": ["単独では方向性が不明（必ず前後のローソク足で確認）", "出現頻度が高くノイズも多い"],
    },
    "Bullish_Engulfing": {
        "slug": "bullish_engulfing", "category": "ローソク足パターン",
        "display": "強気の包み足（ブリッシュエンゲルフィング）",
        "description": "前日の陰線を、当日の大きな陽線が完全に包み込むパターンです。強い買い圧力の発生を示し、下降トレンドからの転換シグナルとして知られます。",
        "feature": "陽線の実体が大きいほど信頼性が高くなります。サポートレベルや過去の安値付近での出現は特に有効です。",
        "good": ["下降トレンドの末期・底値圏での転換", "サポートラインや重要水準付近"],
        "bad": ["上昇トレンド継続中（一時的な調整後に再上昇する場合も）", "流動性が低い時間帯"],
    },
    "Bearish_Engulfing": {
        "slug": "bearish_engulfing", "category": "ローソク足パターン",
        "display": "弱気の包み足（ベアリッシュエンゲルフィング）",
        "description": "前日の陽線を、当日の大きな陰線が完全に包み込むパターンです。強い売り圧力の発生を示し、上昇トレンドからの転換シグナルとして知られます。",
        "feature": "陰線の実体が大きいほど信頼性が高くなります。レジスタンスレベルや過去の高値付近での出現と組み合わせると精度が上がります。",
        "good": ["上昇トレンドの末期・天井圏での転換", "レジスタンスラインや重要水準付近"],
        "bad": ["下降トレンド継続中（戻り局面での出現）", "出来高が少ない場合"],
    },
    "Three_White_Soldiers": {
        "slug": "three_white_soldiers", "category": "ローソク足パターン",
        "display": "三白兵（スリーホワイトソルジャーズ）",
        "description": "3本連続して実体が大きく、前の終値より高い位置に始値がある陽線が並ぶパターンです。強い買い圧力の継続を示し、上昇トレンドの開始・継続を示唆します。",
        "feature": "3本とも実体が値動き幅の60%以上を占め、順次高値を更新することが条件。強いモメンタムの証明です。",
        "good": ["底打ち後の上昇トレンド開始確認", "押し目からの強い上昇再開"],
        "bad": ["高値圏での出現（過熱感・反転リスク）", "出現頻度が低いためチャンスが限られる"],
    },
    "Three_Black_Crows": {
        "slug": "three_black_crows", "category": "ローソク足パターン",
        "display": "三羽烏（スリーブラッククロウズ）",
        "description": "3本連続して実体が大きく、前の終値より低い位置に始値がある陰線が並ぶパターンです。強い売り圧力の継続を示し、下降トレンドの開始・継続を示唆します。",
        "feature": "3本とも実体が値動き幅の60%以上を占め、順次安値を更新することが条件。強い下落モメンタムの証明です。",
        "good": ["天井確認後の下降トレンド開始", "戻り売りからの強い下落再開"],
        "bad": ["安値圏での出現（売られすぎ・反転リスク）", "出現頻度が低い"],
    },
    "Pin_Bar": {
        "slug": "pin_bar", "category": "ローソク足パターン",
        "display": "ピンバー",
        "description": "ヒゲが全体の60%以上を占め、実体が30%以下の細いローソク足です。価格の一方向への強い拒絶を示し、キーレベルでの反転シグナルとして特に有効です。",
        "feature": "上ヒゲピンバー→売りシグナル（上方向への拒絶）、下ヒゲピンバー→買いシグナル（下方向への拒絶）。プライスアクション分析の核心的パターンです。",
        "good": ["サポート・レジスタンスや節目での反転", "高値・安値の更新失敗の確認"],
        "bad": ["トレンド継続中の調整局面での誤判断", "上位足での確認なしの単独使用"],
    },
}


def get_pair_data(pair: str) -> dict:
    from app.services.data_fetcher import get_latest_price
    from app.models.signal import TradingSignal
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade
    from app.models.settings import Setting
    from app.config import Config
    from sqlalchemy import or_

    price = get_latest_price(pair)
    now_utc = datetime.now(timezone.utc)

    signals = (
        TradingSignal.query
        .filter_by(currency_pair=pair, is_active=True)
        .filter(or_(TradingSignal.expired_at.is_(None),
                    TradingSignal.expired_at > now_utc))
        .order_by(TradingSignal.confidence_score.desc())
        .limit(10).all()
    )

    # 最新シグナル生成日時
    signal_latest_jst = utc_str_to_jst(signals[0].signal_time) if signals else ""
    top_bt = (
        BacktestResult.query
        .filter_by(currency_pair=pair)
        .filter(BacktestResult.win_rate >= 55)
        .order_by(BacktestResult.win_rate.desc())
        .limit(5).all()
    )

    buy_count = sum(1 for s in signals if s.signal_type == "BUY")
    sell_count = sum(1 for s in signals if s.signal_type == "SELL")

    if buy_count > sell_count:
        overall = "BUY"
    elif sell_count > buy_count:
        overall = "SELL"
    else:
        overall = "NEUTRAL"

    # 価格タイムスタンプをJSTに変換
    price_dict = None
    if price:
        price_dict = price if isinstance(price, dict) else {
            k: getattr(price, k, None) for k in ("close", "open", "high", "low", "timestamp")
        }
        ts = price_dict.get("timestamp")
        price_dict["timestamp_jst"] = utc_str_to_jst(ts)

    # シグナルに signal_time_jst を付加
    signal_dicts = []
    for s in signals:
        d = s.to_dict()
        d["signal_time_jst"] = utc_str_to_jst(s.signal_time)
        signal_dicts.append(d)

    # ===== シミュレーショントレード（TF別・最大15件ずつ） =====
    sl_pips = Setting.get_float("sl_pips", Config.DEFAULT_SL_PIPS)
    tp_pips = Setting.get_float("tp_pips", Config.DEFAULT_TP_PIPS)
    rr_ratio = round(tp_pips / sl_pips, 1) if sl_pips else 2.0
    sim_trades = []
    sim_trades_by_tf: dict = {}
    sim_no_data = False
    try:
        raw_st = (
            SimulationTrade.query
            .filter_by(currency_pair=pair)
            .order_by(SimulationTrade.entry_at.desc())
            .limit(500).all()
        )
        if not raw_st:
            sim_no_data = True
        else:
            for t in raw_st:
                tf = t.timeframe or "1hr"
                bucket = sim_trades_by_tf.setdefault(tf, [])
                if len(bucket) >= 15:
                    continue
                sl_v = float(t.sl_pips) if t.sl_pips else sl_pips
                tp_v = float(t.tp_pips) if t.tp_pips else tp_pips
                pips = tp_v if t.outcome == "WIN" else (-sl_v if t.outcome == "LOSS" else 0)
                trade_dict = {
                    "indicator":     t.indicator_name,
                    "timeframe":     tf,
                    "signal":        t.direction,
                    "entry_ts_jst":  utc_str_to_jst(t.entry_at),
                    "exit_ts_jst":   utc_str_to_jst(t.exit_at) if t.exit_at else "—",
                    "entry_ts_unix": _to_unix(t.entry_at) if t.entry_at else 0,
                    "exit_ts_unix":  _to_unix(t.exit_at)  if t.exit_at  else 0,
                    "entry_price":   float(t.entry_price) if t.entry_price else None,
                    "tp_price":      float(t.tp_price)    if t.tp_price    else None,
                    "sl_price":      float(t.sl_price)    if t.sl_price    else None,
                    "outcome":       t.outcome,
                    "pips":          pips,
                    "pnl":           float(t.profit_loss) if t.profit_loss else 0,
                }
                bucket.append(trade_dict)
                sim_trades.append(trade_dict)
    except Exception as e:
        logger.warning("Sim trades error %s: %s", pair, e)

    return {
        "pair": pair,
        "display": f"{pair[:3]}/{pair[3:]}",
        "price": price_dict,
        "signals": signal_dicts,
        "signal_latest_jst": signal_latest_jst,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "overall": overall,
        "top_backtest":     [r.to_dict() for r in top_bt],
        "sim_trades":       sim_trades,
        "sim_trades_by_tf": sim_trades_by_tf,
        "sim_tf_order":     [tf for tf in TF_ORDER if tf in sim_trades_by_tf],
        "tf_labels":        TF_LABELS,
        "sim_no_data":      sim_no_data,
        "sl_pips":          sl_pips,
        "tp_pips":          tp_pips,
        "rr_ratio":         rr_ratio,
    }


def get_all_signals() -> list:
    from app.models.signal import TradingSignal
    from app.config import Config
    from sqlalchemy import or_
    now_utc = datetime.now(timezone.utc)
    result = []
    for pair in Config.CURRENCY_PAIRS:
        sigs = (
            TradingSignal.query
            .filter_by(currency_pair=pair, is_active=True)
            .filter(or_(TradingSignal.expired_at.is_(None),
                        TradingSignal.expired_at > now_utc))
            .order_by(TradingSignal.confidence_score.desc())
            .all()
        )
        result.extend([s.to_dict() for s in sigs])
    return sorted(result, key=lambda x: x.get("confidence_score") or 0, reverse=True)


def get_all_backtest() -> list:
    from app.models.backtest import BacktestResult
    from app.config import Config
    result = []
    for pair in Config.CURRENCY_PAIRS:
        recs = (
            BacktestResult.query
            .filter_by(currency_pair=pair)
            .order_by(BacktestResult.win_rate.desc())
            .limit(20).all()
        )
        result.extend([r.to_dict() for r in recs])
    return sorted(result, key=lambda x: x.get("win_rate") or 0, reverse=True)


def get_reports() -> list:
    from app.models.report import AiReport
    recs = AiReport.query.order_by(AiReport.created_at.desc()).limit(10).all()
    return [r.to_dict() for r in recs]


CHART_TIMEFRAMES = ["15min", "1hr", "4hr", "daily"]
CHART_LIMITS = {"15min": 120, "1hr": 200, "4hr": 150, "daily": 300}

TF_ORDER  = ["5min", "15min", "30min", "1hr", "4hr", "daily"]
TF_LABELS = {
    "5min":  "5分足",
    "15min": "15分足",
    "30min": "30分足",
    "1hr":   "1時間足",
    "4hr":   "4時間足",
    "daily": "日足",
}

# カテゴリ定義（スラッグ・表示名・説明）
CATEGORY_INFO = {
    "オシレーター": {
        "slug":        "oscillator",
        "display":     "オシレーター系指標",
        "description": "相場の過熱感・売られすぎ・買われすぎを数値化し、レンジ相場での反転タイミングを捉えるのが得意な指標群です。RSI・MACD・ストキャスティクスなどが代表的で、トレンド指標と組み合わせると精度が向上します。",
    },
    "トレンド": {
        "slug":        "trend",
        "display":     "トレンド系指標",
        "description": "移動平均線やボリンジャーバンドなど、相場の方向性とトレンドの強さを判断するための指標群です。トレンド相場でのエントリー・エグジットの基準として広く使われています。",
    },
    "ライン": {
        "slug":        "line",
        "display":     "ライン系指標",
        "description": "ピボットポイントやフィボナッチなど、重要な価格水準（サポート・レジスタンス）を客観的に算出する指標群です。反転・ブレイクアウトのターゲット設定に活用されます。",
    },
    "ボラティリティ": {
        "slug":        "volatility",
        "display":     "ボラティリティ系指標",
        "description": "ATRやBBバンド幅など、相場の値動きの大きさ（ボラティリティ）を測定する指標群です。SL・TPの設定やポジションサイジングの基準として活用されます。",
    },
    "ローソク足パターン": {
        "slug":        "candlestick",
        "display":     "ローソク足パターン",
        "description": "ハンマー・包み足・ドジなど、ローソク足の形状から市場参加者の心理と売買圧力の変化を読み取るパターン群です。サポート・レジスタンスと組み合わせると特に有効です。",
    },
}

# カテゴリ名 → スラッグ の逆引きマップ
CATEGORY_SLUGS = {name: info["slug"] for name, info in CATEGORY_INFO.items()}


def _to_unix(ts) -> int:
    """datetime / str / timestamp → Unix秒"""
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        from datetime import datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return int(datetime.strptime(ts[:19], fmt).timestamp())
            except ValueError:
                pass
        return 0
    if hasattr(ts, "timestamp"):
        return int(ts.timestamp())
    return 0


def get_chart_data(pair: str, timeframe: str) -> dict:
    """ローソク足 + テクニカル指標データを返す"""
    import pandas as pd
    from app.services.data_fetcher import get_candles

    limit = CHART_LIMITS.get(timeframe, 200)
    df = get_candles(pair, timeframe, limit)
    if df is None or df.empty:
        return {"candles": [], "sma20": [], "sma50": [], "ema21": [],
                "bb_upper": [], "bb_lower": [], "rsi": [], "signals": []}

    df = df.sort_values("timestamp").reset_index(drop=True)
    close = df["close"].astype(float)

    times = [_to_unix(row["timestamp"]) for _, row in df.iterrows()]

    import math as _math
    candles = []
    for i in range(len(df)):
        try:
            o = float(df.iloc[i]["open"])
            h = float(df.iloc[i]["high"])
            lo = float(df.iloc[i]["low"])
            c = float(df.iloc[i]["close"])
        except (TypeError, ValueError):
            continue
        if not (_math.isfinite(o) and _math.isfinite(h) and _math.isfinite(lo) and _math.isfinite(c)):
            continue
        candles.append({"time": times[i],
                         "open": round(o, 3), "high": round(h, 3),
                         "low": round(lo, 3), "close": round(c, 3)})

    def to_series(series, decimals=5):
        import math
        out = []
        for i, v in enumerate(series):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(fv):  # NaN と Inf を除外（pd.isna では Inf を除外できない）
                continue
            out.append({"time": times[i], "value": round(fv, decimals)})
        return out

    # SMA
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    # EMA21
    ema21 = close.ewm(span=21, adjust=False).mean()
    # Bollinger Bands (20, 2)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    # RSI(14) — Wilder's smoothing
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    # バックテスト取引マーカー（SimulationTradeテーブルから取得）
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade

    trade_markers = []
    try:
        top_bt = (BacktestResult.query
                  .filter_by(currency_pair=pair, timeframe=timeframe)
                  .filter(BacktestResult.win_rate >= 50)
                  .order_by(BacktestResult.win_rate.desc())
                  .first())
        if top_bt:
            sim_trades = (
                SimulationTrade.query
                .filter_by(currency_pair=pair, timeframe=timeframe,
                           indicator_name=top_bt.indicator_name)
                .order_by(SimulationTrade.entry_at.desc())
                .limit(30).all()
            )
            for t in sim_trades:
                et = _to_unix(t.entry_at)
                xt = _to_unix(t.exit_at) if t.exit_at else None
                is_buy = t.direction == "BUY"
                trade_markers.append({
                    "time": et,
                    "position": "belowBar" if is_buy else "aboveBar",
                    "color": "#22c55e" if is_buy else "#ef4444",
                    "shape": "arrowUp" if is_buy else "arrowDown",
                    "text": "IN",
                    "size": 1,
                })
                if xt:
                    win = t.outcome == "WIN"
                    trade_markers.append({
                        "time": xt,
                        "position": "aboveBar" if is_buy else "belowBar",
                        "color": "#22c55e" if win else "#ef4444",
                        "shape": "circle",
                        "text": "TP✓" if win else "SL✗",
                        "size": 1,
                    })
    except Exception as e:
        logger.warning("Trade markers error %s %s: %s", pair, timeframe, e)

    # アクティブシグナルのTP/SLレベル
    from app.models.signal import TradingSignal
    active_sig = (TradingSignal.query
                  .filter_by(currency_pair=pair, is_active=True)
                  .order_by(TradingSignal.confidence_score.desc())
                  .first())
    tp_level = float(active_sig.tp_price) if active_sig and active_sig.tp_price else None
    sl_level = float(active_sig.sl_price) if active_sig and active_sig.sl_price else None
    entry_level = float(active_sig.entry_price) if active_sig and active_sig.entry_price else None
    active_signal_type = active_sig.signal_type if active_sig else None

    return {
        "candles":     candles,
        "sma20":       to_series(sma20),
        "sma50":       to_series(sma50),
        "ema21":       to_series(ema21),
        "bb_upper":    to_series(bb_upper),
        "bb_lower":    to_series(bb_lower),
        "rsi":         to_series(rsi, decimals=2),
        "trades":      sorted(trade_markers, key=lambda x: x["time"]),
        "tp_level":    tp_level,
        "sl_level":    sl_level,
        "entry_level": entry_level,
        "signal_type": active_signal_type,
    }


def get_indicator_page_data(indicator_name: str, app) -> dict | None:
    """インジケーター個別ページのデータを取得"""
    from app.models.backtest import BacktestResult
    from app.models.simulation_trade import SimulationTrade
    from app.models.settings import Setting
    from app.config import Config

    info = INDICATOR_INFO.get(indicator_name)
    if not info:
        return None

    results = (BacktestResult.query
               .filter_by(indicator_name=indicator_name)
               .order_by(BacktestResult.win_rate.desc())
               .all())
    if not results:
        return None

    best = results[0]
    sl = Setting.get_float("sl_pips", 20)
    tp = Setting.get_float("tp_pips", 40)

    def _to_unix(dt):
        """naive UTC datetime → Unix timestamp"""
        if dt is None:
            return None
        from datetime import timezone as _tz
        return int(dt.replace(tzinfo=_tz.utc).timestamp())

    def _fmt_trade(t):
        sl_v = float(t.sl_pips) if t.sl_pips else sl
        tp_v = float(t.tp_pips) if t.tp_pips else tp
        is_win = t.outcome == "WIN"
        return {
            "entry_ts_jst":  utc_str_to_jst(t.entry_at),
            "entry_ts_unix": _to_unix(t.entry_at),
            "exit_ts_unix":  _to_unix(t.exit_at),
            "timeframe":     t.timeframe,
            "signal":        t.direction,
            "entry_price":   float(t.entry_price) if t.entry_price else None,
            "tp_price":      float(t.tp_price) if t.tp_price else None,
            "sl_price":      float(t.sl_price) if t.sl_price else None,
            "outcome":       t.outcome,
            "pnl":           (tp_v * 1000) if is_win else -(sl_v * 1000),
        }

    # 通貨ペアごとのバックテスト結果
    all_pairs = Config.CURRENCY_PAIRS  # ['USDJPY', 'GBPJPY', 'EURJPY']
    results_by_pair = {}
    for pair in all_pairs:
        results_by_pair[pair] = [r.to_dict() for r in results if r.currency_pair == pair]

    # 通貨ペアごとの15分足トレードシミュレーション（最大20件）
    trades_by_pair = {}
    for pair in all_pairs:
        raw = (SimulationTrade.query
               .filter_by(indicator_name=indicator_name, currency_pair=pair, timeframe="15min")
               .order_by(SimulationTrade.entry_at.desc())
               .limit(20).all())
        trades_by_pair[pair] = [_fmt_trade(t) for t in raw]

    # 関連指標（同カテゴリ優先、最大8件）
    related = []
    for name, i in INDICATOR_INFO.items():
        if name == indicator_name:
            continue
        br = (BacktestResult.query
              .filter_by(indicator_name=name)
              .order_by(BacktestResult.win_rate.desc())
              .first())
        related.append({
            "slug":     i["slug"],
            "display":  i["display"],
            "category": i["category"],
            "win_rate": br.win_rate if br else None,
        })
    cat = info["category"]
    related.sort(key=lambda x: (0 if x["category"] == cat else 1, -(x["win_rate"] or 0)))
    related = related[:8]

    return {
        "info":             info,
        "category_slug":    CATEGORY_SLUGS.get(info["category"], ""),
        "results":          [r.to_dict() for r in results],
        "results_by_pair":  results_by_pair,
        "trades_by_pair":   trades_by_pair,
        "pairs":            all_pairs,
        "best":             best.to_dict(),
        "sl":               int(sl),
        "tp":               int(tp),
        "related":          related,
    }


def get_settings() -> dict:
    from app.models.settings import Setting
    return {
        "initial_capital": Setting.get("initial_capital", "1000000"),
        "sl_pips": Setting.get("sl_pips", "20"),
        "tp_pips": Setting.get("tp_pips", "40"),
        "backtest_hours": Setting.get("backtest_hours", "12"),
        "min_win_rate": Setting.get("min_win_rate", "55"),
        "min_trades": Setting.get("min_trades", "3"),
        "report_times": Setting.get("report_times", "06:00,12:00,18:00"),
        "gemini_model": Setting.get("gemini_model", "gemini-1.5-flash"),
    }


def get_category_page_data(category_name: str) -> dict | None:
    """カテゴリページのデータを返す"""
    from app.models.backtest import BacktestResult

    cat_info = CATEGORY_INFO.get(category_name)
    if not cat_info:
        return None

    # そのカテゴリに属する指標を収集
    indicators = []
    for ind_name, ind_info in INDICATOR_INFO.items():
        if ind_info["category"] != category_name:
            continue
        # 最高勝率・ペア・TFを BacktestResult から取得
        br = (BacktestResult.query
              .filter_by(indicator_name=ind_name)
              .order_by(BacktestResult.win_rate.desc())
              .first())
        indicators.append({
            "slug":          ind_info["slug"],
            "display":       ind_info["display"],
            "description":   ind_info["description"],
            "good":          ind_info.get("good", []),
            "best_win_rate": float(br.win_rate) if br else None,
            "best_pair":     br.currency_pair if br else None,
            "best_tf":       br.timeframe if br else None,
        })
    # 勝率降順ソート
    indicators.sort(key=lambda x: -(x["best_win_rate"] or 0))

    # 全カテゴリの概要リスト（ナビ用）
    all_categories = []
    for name, info in CATEGORY_INFO.items():
        count = sum(1 for i in INDICATOR_INFO.values() if i["category"] == name)
        all_categories.append({
            "slug":        info["slug"],
            "name":        name,
            "display":     info["display"],
            "description": info["description"],
            "count":       count,
        })

    return {
        "category":       {**cat_info, "name": category_name},
        "indicators":     indicators,
        "all_categories": all_categories,
    }


def render_html(app, template_name: str, context: dict) -> str:
    from flask import render_template
    with app.app_context():
        with app.test_request_context("/"):
            return render_template(template_name, **context)


def save(filename: str, html: str):
    path = Path(PUBLIC_HTML) / filename
    path.write_text(html, encoding="utf-8")
    logger.info("Generated: %s", filename)


def deploy_static_files():
    """public_html + static/ ディレクトリを本番に同期する（CSS/JS/PHP/.htaccess/.cgi すべて含む）"""
    import shutil
    import stat

    base_dir = Path(__file__).parent.parent
    dst_dir  = Path(PUBLIC_HTML)

    # コピー元とコピー先のルートペア
    src_roots = [
        (base_dir / "public_html", dst_dir),          # PHP, .htaccess, .cgi
        (base_dir / "static",      dst_dir / "static"),  # CSS, JS
    ]

    for src_dir, dst_root in src_roots:
        if not src_dir.exists():
            logger.warning("Source dir not found: %s", src_dir)
            continue

        for src in src_dir.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(src_dir)
            dst = dst_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            # src と dst が同一ファイル（シンボリックリンク等）の場合はスキップ
            if dst.exists() and os.path.samefile(src, dst):
                continue
            shutil.copy2(src, dst)
            # .cgi ファイルは実行権限を付与
            if src.suffix == ".cgi":
                os.chmod(dst, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                              stat.S_IROTH | stat.S_IXOTH)  # 755
            logger.info("Deployed: %s -> %s", src_dir.name / rel, dst)


def main():
    from app import create_app
    from app.config import Config

    # PHP/.htaccess を public_html に同期
    deploy_static_files()

    # 管理パネルに移動した設定ページの古いファイルを削除
    for obsolete in ["settings.html", "settings_data.json"]:
        p = Path(PUBLIC_HTML) / obsolete
        if p.exists():
            p.unlink()
            logger.info("Removed obsolete file: %s", obsolete)

    app = create_app()
    with app.app_context():
        updated_at = datetime.now(JST).strftime("%Y/%m/%d %H:%M")
        pairs = Config.CURRENCY_PAIRS
        pair_pages = {"USDJPY": "index.html", "GBPJPY": "gbpjpy.html", "EURJPY": "eurjpy.html"}

        # 各通貨ペアのダッシュボード
        slug_map = {name: info["slug"] for name, info in INDICATOR_INFO.items()}
        for pair, filename in pair_pages.items():
            data = get_pair_data(pair)
            html = render_html(app, "dashboard_static.html", {
                "pairs": pairs,
                "pair_pages": pair_pages,
                "current_pair": pair,
                "data": data,
                "slug_map": slug_map,
                "updated_at": updated_at,
                "active_page": "home",
            })
            save(filename, html)

        # シグナル一覧
        all_signals = get_all_signals()
        html = render_html(app, "signals_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "signals": all_signals,
            "updated_at": updated_at,
            "active_page": "signals",
        })
        save("signals.html", html)

        # バックテスト
        slug_map = {name: info["slug"] for name, info in INDICATOR_INFO.items()}
        all_bt = get_all_backtest()
        html = render_html(app, "backtest_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "results": all_bt,
            "slug_map": slug_map,
            "updated_at": updated_at,
            "active_page": "backtest",
        })
        save("backtest.html", html)

        # レポート
        reports = get_reports()
        html = render_html(app, "reports_static.html", {
            "pairs": pairs,
            "pair_pages": pair_pages,
            "reports": reports,
            "updated_at": updated_at,
            "active_page": "reports",
        })
        save("reports.html", html)

        # 設定ページは管理パネルに移動したため生成しない

        # チャートデータ JSON（ペア×タイムフレーム）
        chart_dir = Path(PUBLIC_HTML) / "chart_data"
        chart_dir.mkdir(exist_ok=True)
        for pair in pairs:
            for tf in CHART_TIMEFRAMES:
                try:
                    cdata = get_chart_data(pair, tf)
                    fname = f"{pair.lower()}_{tf}.json"
                    (chart_dir / fname).write_text(
                        json.dumps(cdata, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8"
                    )
                    logger.info("Chart JSON: %s", fname)
                except Exception as e:
                    logger.warning("Chart JSON error %s %s: %s", pair, tf, e)

        # カテゴリ個別ページ生成（/category/oscillator.html 等）
        cat_dir = Path(PUBLIC_HTML) / "category"
        cat_dir.mkdir(exist_ok=True)
        for cat_name, cat_info in CATEGORY_INFO.items():
            try:
                page_data = get_category_page_data(cat_name)
                if page_data is None:
                    continue
                html = render_html(app, "category_static.html", {
                    **page_data,
                    "updated_at": updated_at,
                    "active_page": "backtest",
                })
                save(f"category/{cat_info['slug']}.html", html)
            except Exception as e:
                logger.warning("Category page error %s: %s", cat_name, e)

        # インジケーター個別ページ生成
        ind_dir = Path(PUBLIC_HTML) / "indicators"
        ind_dir.mkdir(exist_ok=True)
        for ind_name, ind_info in INDICATOR_INFO.items():
            try:
                page_data = get_indicator_page_data(ind_name, app)
                if page_data is None:
                    continue
                html = render_html(app, "indicator_static.html", {
                    **page_data,
                    "updated_at": updated_at,
                    "active_page": "backtest",
                })
                slug = ind_info["slug"]
                save(f"indicators/{slug}.html", html)
            except Exception as e:
                logger.warning("Indicator page error %s: %s", ind_name, e)

        logger.info("Static site generation complete")


if __name__ == "__main__":
    main()
