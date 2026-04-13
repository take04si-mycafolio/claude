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
import re
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
    # ---- トレンド（追加） ----
    "Ichimoku_Cloud": {
        "slug": "ichimoku_cloud", "category": "トレンド",
        "display": "一目均衡表（雲・転換線・基準線）",
        "description": "転換線（9期間）・基準線（26期間）・先行スパンA・先行スパンB・遅行スパンの5本の線からなる総合的なトレンド指標です。「一目で均衡状態を把握する」というコンセプトのもと、日本で開発され世界中で使われています。",
        "feature": "価格が雲の上 AND 転換線 > 基準線 → 買いシグナル。価格が雲の下 AND 転換線 < 基準線 → 売りシグナル。雲の厚さはサポート・レジスタンスの強度を示します。",
        "good": ["中長期トレンドの方向性確認", "雲のサポート・レジスタンス機能の活用", "トレンド転換の早期察知"],
        "bad": ["雲の中に価格がある（揉み合い・迷い局面）", "設定期間が短い足でのノイズ増加", "急騰・急落時の遅行性"],
    },
    # ---- コンポジット ----
    "RSI_MACD_Combo": {
        "slug": "rsi_macd_combo", "category": "コンポジット",
        "display": "RSI + MACD コンボ",
        "description": "RSIとMACDが同じ方向のシグナルを示したときのみエントリーする複合指標です。単独指標より誤シグナル（ダマシ）を減らし、信頼度の高い局面だけをフィルタリングします。",
        "feature": "RSI の売買シグナルと MACD のクロスシグナルが一致した場合のみ買い・売りシグナルを発生。どちらかが NEUTRAL なら見送り。",
        "good": ["トレンドが明確な相場での精度向上", "ダマシを減らした厳選エントリー"],
        "bad": ["シグナル頻度が低下する（チャンスが減る）", "両指標が同時に遅行するケース"],
    },
    "RSI_Stoch_Combo": {
        "slug": "rsi_stoch_combo", "category": "コンポジット",
        "display": "RSI + ストキャスティクス コンボ",
        "description": "RSIとストキャスティクスの両方が同方向のシグナルを示した場合のみエントリーする複合指標です。どちらも過熱感を測るオシレーターのため、相互補完により精度が向上します。",
        "feature": "RSI とストキャスティクスが共に買われすぎ/売られすぎゾーンでシグナル一致 → エントリー。一方だけの場合は見送り。",
        "good": ["レンジ相場での逆張りエントリー精度向上", "過熱感の確実な確認"],
        "bad": ["強いトレンド相場での張り付き（両者ともに極値のまま）"],
    },
    "MACD_Stoch_Combo": {
        "slug": "macd_stoch_combo", "category": "コンポジット",
        "display": "MACD + ストキャスティクス コンボ",
        "description": "MACDとストキャスティクスが両方一致した場合のみシグナルを発生させます。トレンドフォロー系（MACD）と反転系（ストキャスティクス）の組み合わせで、押し目・戻り売りの精度を高めます。",
        "feature": "MACDのクロスシグナルとストキャスティクスのシグナルが同一方向 → シグナル発生。異なる場合は NEUTRAL。",
        "good": ["トレンド中の押し目・戻り売り", "ブレイクアウト後の確認エントリー"],
        "bad": ["レンジ相場でのMACDの頻繁なクロス（ノイズ増加）"],
    },
    "Triple_OSC_Combo": {
        "slug": "triple_osc_combo", "category": "コンポジット",
        "display": "トリプルオシレーター コンボ（RSI + MACD + Stoch）",
        "description": "RSI・MACD・ストキャスティクスの3指標すべてが同方向のシグナルを示した場合のみエントリーする高精度フィルター指標です。厳選されたシグナルで勝率向上を目指します。",
        "feature": "3指標すべてが BUY → 買いシグナル、すべてが SELL → 売りシグナル。1つでも不一致なら NEUTRAL。シグナル頻度は低いが信頼度が高い。",
        "good": ["最高精度が求められる局面での確認", "大きなトレンド転換の初動確認"],
        "bad": ["シグナルが極めて稀（機会損失リスク）", "レンジ相場での有効シグナル不足"],
    },
    "All_AND_Consensus": {
        "slug": "all_and_consensus", "category": "コンポジット",
        "display": "全指標コンセンサス（5指標以上一致）",
        "description": "オシレーター系・トレンド系を含む全指標のうち5つ以上が同一方向を示した場合のみシグナルを発生させる最上位フィルター指標です。市場参加者の総意が揃った局面だけを狙います。",
        "feature": "5指標以上が BUY/SELL で一致 → シグナル発生。一致数が多いほど信頼度が高く、強いトレンド局面でのみ機能します。",
        "good": ["最も強いトレンド局面の把握", "複数指標を手動確認する代替として使用"],
        "bad": ["シグナルが非常に稀（長期保有向き）", "乱高下時のノイズで誤発生する可能性"],
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
            .limit(200).all()
        )
        for r in recs:
            d = r.to_dict()
            name = d.get("indicator_name", "")
            sl = float(d.get("sl_pips") or 0)
            tp = float(d.get("tp_pips") or 0)
            d["rr_ratio"] = round(tp / sl, 1) if sl else 0
            ind_info = INDICATOR_INFO.get(name, {})
            d["display"]  = ind_info.get("display",  name)
            d["category"] = ind_info.get("category", "")
            result.append(d)
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

# カテゴリ定義（スラッグ・表示名・説明・SEO）
CATEGORY_INFO = {
    "オシレーター": {
        "slug":            "oscillator",
        "display":         "オシレーター系指標",
        "seo_title":       "FXオシレーターの勝率一覧｜RSI・MACDなどを検証",
        "seo_description": "RSI・MACD・ストキャスティクスなどオシレーター系テクニカルの勝率を一覧で比較。バックテスト結果をもとに分析。",
        "description":     "相場の過熱感・売られすぎ・買われすぎを数値化し、レンジ相場での反転タイミングを捉えるのが得意な指標群です。RSI・MACD・ストキャスティクスなどが代表的で、トレンド指標と組み合わせると精度が向上します。",
    },
    "トレンド": {
        "slug":            "trend",
        "display":         "トレンド系指標",
        "seo_title":       "FXトレンド系テクニカルの勝率一覧｜移動平均など検証",
        "seo_description": "移動平均線やボリンジャーバンドなどトレンド系指標の勝率を比較。バックテスト結果をもとに分析。",
        "description":     "移動平均線やボリンジャーバンドなど、相場の方向性とトレンドの強さを判断するための指標群です。トレンド相場でのエントリー・エグジットの基準として広く使われています。",
    },
    "ライン": {
        "slug":            "line",
        "display":         "ライン系指標",
        "seo_title":       "ライン系テクニカルの勝率｜ピボット・フィボナッチ検証",
        "seo_description": "ピボットポイントやフィボナッチなどライン系分析の勝率を検証。サポート・レジスタンスの精度を分析。",
        "description":     "ピボットポイントやフィボナッチなど、重要な価格水準（サポート・レジスタンス）を客観的に算出する指標群です。反転・ブレイクアウトのターゲット設定に活用されます。",
    },
    "ボラティリティ": {
        "slug":            "volatility",
        "display":         "ボラティリティ系指標",
        "seo_title":       "FXボラティリティ指標の勝率｜ATR・BB幅を検証",
        "seo_description": "ATRやボリンジャーバンド幅などボラティリティ指標の勝率を検証。相場の変動分析に活用。",
        "description":     "ATRやBBバンド幅など、相場の値動きの大きさ（ボラティリティ）を測定する指標群です。SL・TPの設定やポジションサイジングの基準として活用されます。",
    },
    "ローソク足パターン": {
        "slug":            "candlestick",
        "display":         "ローソク足パターン",
        "seo_title":       "ローソク足パターンの勝率｜主要パターンを検証",
        "seo_description": "ハンマー・包み足などローソク足パターンの勝率を検証。トレード精度をデータで分析。",
        "description":     "ハンマー・包み足・ドジなど、ローソク足の形状から市場参加者の心理と売買圧力の変化を読み取るパターン群です。サポート・レジスタンスと組み合わせると特に有効です。",
    },
    "コンポジット": {
        "slug":            "composite",
        "display":         "コンポジット（複合）指標",
        "seo_title":       "FX複合テクニカル指標の勝率｜コンボシグナルを検証",
        "seo_description": "RSI+MACD・トリプルオシレーターなど複数指標の組み合わせによるコンボシグナルの勝率を検証。ダマシを減らした高精度エントリーを分析。",
        "description":     "RSI・MACD・ストキャスティクスなど複数指標が同一方向を示したときのみシグナルを発生させる複合指標群です。単独指標よりダマシが少なく、確度の高い局面だけを厳選してトレードできます。",
    },
    "BBバンド損切り": {
        "slug":            "bbsl",
        "display":         "BBバンド損切りバリアント",
        "seo_title":       "BBバンド損切り戦略の勝率｜動的SL/TPの精度を検証",
        "seo_description": "ボリンジャーバンドをSL/TPに使用した動的損切り戦略の勝率を検証。各テクニカル指標のBBバンド版パフォーマンスをデータで比較分析。",
        "description":     "固定pipsではなくボリンジャーバンドの上下バンドをTP/SLとして使用するバリアント指標群です。相場のボラティリティに合わせてSL/TPが自動調整されるため、荒い相場での損失を抑えやすい特徴があります。",
    },
}

# カテゴリ名 → スラッグ の逆引きマップ
CATEGORY_SLUGS = {name: info["slug"] for name, info in CATEGORY_INFO.items()}

# 指標ごとのURL・SEO設定（INDICATOR_INFO にマージ）
INDICATOR_SEO = {
    "RSI_14":               {"url_slug": "rsi",                "seo_title": "RSIの勝率｜FXで使えるシグナルを検証",                "seo_description": "RSIの勝率をバックテストで検証。買われすぎ・売られすぎシグナルの精度やトレード結果をデータで解説。"},
    "MACD_12_26_9":         {"url_slug": "macd",               "seo_title": "MACDの勝率｜クロスシグナルの精度を検証",             "seo_description": "MACDのゴールデンクロス・デッドクロスの勝率を検証。FXトレードでの有効性をデータで解説。"},
    "Stochastic_14_3":      {"url_slug": "stochastic",         "seo_title": "ストキャスティクスの勝率｜逆張り精度を検証",        "seo_description": "ストキャスティクスの勝率をバックテストで分析。逆張りシグナルの精度やトレード結果を解説。"},
    "CCI_20":               {"url_slug": "cci",                "seo_title": "CCIの勝率｜トレンド判定の精度を検証",               "seo_description": "CCIの勝率を検証。トレンド判断やエントリー精度をバックテスト結果から分析。"},
    "Williams_R_14":        {"url_slug": "williams_r",         "seo_title": "ウィリアムズ%Rの勝率｜逆張り指標を検証",           "seo_description": "ウィリアムズ%Rの勝率を検証。売買タイミングの精度やトレード結果をデータで解説。"},
    "SMA_20":               {"url_slug": "sma20",              "seo_title": "SMA20の勝率｜単純移動平均の精度を検証",            "seo_description": "SMA20の勝率をバックテストで検証。トレンドフォローの精度とエントリー結果を分析。"},
    "SMA_50":               {"url_slug": "sma50",              "seo_title": "SMA50の勝率｜中期トレンドの精度を検証",            "seo_description": "SMA50の勝率を検証。中期トレンド分析におけるシグナル精度をデータで解説。"},
    "SMA_Cross_20_50":      {"url_slug": "sma_cross",          "seo_title": "SMAクロスの勝率｜20/50クロスの精度を検証",         "seo_description": "SMA20とSMA50のクロス戦略の勝率を検証。ゴールデンクロスの有効性を分析。"},
    "EMA_Cross_9_21":       {"url_slug": "ema_cross",          "seo_title": "EMAクロスの勝率｜9/21戦略を検証",                 "seo_description": "EMAクロス（9/21）の勝率を検証。短期トレンド戦略の有効性を分析。"},
    "EMA_21":               {"url_slug": "ema21",              "seo_title": "EMA21の勝率｜トレンド追従の精度を検証",            "seo_description": "EMA21の勝率を検証。トレンドフォローにおけるエントリー精度を分析。"},
    "BollingerBands_20_2":  {"url_slug": "bollinger_bands",    "seo_title": "ボリンジャーバンドの勝率｜2σ戦略を検証",         "seo_description": "ボリンジャーバンド（20期間・2σ）の勝率を検証。逆張り・順張りの精度を分析。"},
    "BB_Squeeze":           {"url_slug": "bb_squeeze",         "seo_title": "BBスクイーズの勝率｜収縮からのブレイク検証",       "seo_description": "ボリンジャーバンド収縮後のブレイク戦略の勝率を検証。相場の変動タイミングを分析。"},
    "Pivot_Classic":        {"url_slug": "pivot",              "seo_title": "ピボットポイントの勝率｜反発ポイントの精度を検証", "seo_description": "ピボットポイントの勝率を検証。サポート・レジスタンスでの反発精度をバックテスト結果から分析。"},
    "Fibonacci_Retracement":{"url_slug": "fibonacci",          "seo_title": "フィボナッチの勝率｜押し目・戻りの精度を検証",     "seo_description": "フィボナッチリトレースメントの勝率を検証。押し目・戻り売りの精度をデータで分析。"},
    "Support_Resistance":   {"url_slug": "support_resistance", "seo_title": "動的サポレジの勝率｜トレンドライン精度を検証",     "seo_description": "動的サポート・レジスタンスの勝率を検証。自動検出した価格水準での反転精度を分析。"},
    "ATR_14":               {"url_slug": "atr",                "seo_title": "ATRの勝率｜ボラティリティ分析の精度を検証",        "seo_description": "ATRの勝率をバックテストで検証。ボラティリティに基づくエントリー精度とトレード結果を分析。"},
    "Volatility_Index":     {"url_slug": "volatility_index",   "seo_title": "ボリンジャーバンド幅の勝率｜変動率分析を検証",     "seo_description": "ボリンジャーバンド幅（ボラティリティインデックス）の勝率を検証。スクイーズからのブレイク精度を分析。"},
    "Hammer":               {"url_slug": "hammer",             "seo_title": "ハンマーの勝率｜反転シグナルの精度を検証",         "seo_description": "ハンマーの勝率をバックテストで検証。底値圏での反転シグナルの精度をデータで分析。"},
    "Inverted_Hammer":      {"url_slug": "inverted_hammer",    "seo_title": "逆ハンマーの勝率｜天井シグナルの精度を検証",       "seo_description": "逆ハンマーの勝率を検証。天井圏での反転シグナルの精度をデータで分析。"},
    "Doji":                 {"url_slug": "doji",               "seo_title": "十字線（ドジ）の勝率｜転換シグナルの精度を検証",  "seo_description": "十字線（ドジ）の勝率を検証。相場の転換点を示すシグナルの精度を分析。"},
    "Bullish_Engulfing":    {"url_slug": "bullish_engulfing",  "seo_title": "強気の包み足の勝率｜上昇転換の精度を検証",        "seo_description": "強気の包み足（ブリッシュエンゲルフィング）の勝率を検証。上昇転換シグナルの精度を分析。"},
    "Bearish_Engulfing":    {"url_slug": "bearish_engulfing",  "seo_title": "弱気の包み足の勝率｜下降転換の精度を検証",        "seo_description": "弱気の包み足（ベアリッシュエンゲルフィング）の勝率を検証。下降転換シグナルの精度を分析。"},
    "Three_White_Soldiers": {"url_slug": "three_white_soldiers","seo_title": "三白兵の勝率｜上昇継続の精度を検証",             "seo_description": "三白兵（スリーホワイトソルジャーズ）の勝率を検証。上昇継続シグナルの精度を分析。"},
    "Three_Black_Crows":    {"url_slug": "three_black_crows",  "seo_title": "三羽烏の勝率｜下降継続の精度を検証",              "seo_description": "三羽烏（スリーブラッククロウズ）の勝率を検証。下降継続シグナルの精度を分析。"},
    "Pin_Bar":              {"url_slug": "pin_bar",            "seo_title": "ピンバーの勝率｜反転シグナルの精度を検証",         "seo_description": "ピンバーの勝率を検証。サポート・レジスタンスでの反転精度をデータで分析。"},
    # ---- トレンド（追加） ----
    "Ichimoku_Cloud":       {"url_slug": "ichimoku",           "seo_title": "一目均衡表の勝率｜雲・転換線の精度をFXで検証",     "seo_description": "一目均衡表（雲・転換線・基準線）の勝率をバックテストで検証。FXトレードでの有効性をデータで解説。"},
    # ---- コンポジット ----
    "RSI_MACD_Combo":       {"url_slug": "rsi_macd_combo",     "seo_title": "RSI＋MACDコンボの勝率｜複合シグナルを検証",       "seo_description": "RSIとMACDの複合シグナルの勝率を検証。ダマシを減らした厳選エントリーの精度を分析。"},
    "RSI_Stoch_Combo":      {"url_slug": "rsi_stoch_combo",    "seo_title": "RSI＋ストキャスコンボの勝率｜逆張り精度を検証",   "seo_description": "RSIとストキャスティクスの複合シグナルの勝率を検証。レンジ相場での逆張り精度を分析。"},
    "MACD_Stoch_Combo":     {"url_slug": "macd_stoch_combo",   "seo_title": "MACD＋ストキャスコンボの勝率｜押し目精度を検証",  "seo_description": "MACDとストキャスティクスの複合シグナルの勝率を検証。押し目・戻り売りの精度を分析。"},
    "Triple_OSC_Combo":     {"url_slug": "triple_osc_combo",   "seo_title": "トリプルオシレーターの勝率｜3指標一致の精度検証", "seo_description": "RSI・MACD・ストキャスの3指標コンボの勝率を検証。高精度シグナルの有効性をデータで分析。"},
    "All_AND_Consensus":    {"url_slug": "all_and_consensus",  "seo_title": "全指標コンセンサスの勝率｜5指標一致の精度を検証", "seo_description": "全テクニカル指標の総合コンセンサスの勝率を検証。5指標以上一致の高精度シグナルを分析。"},
}
# INDICATOR_INFO に SEO フィールドをマージ
for _k, _seo in INDICATOR_SEO.items():
    if _k in INDICATOR_INFO:
        INDICATOR_INFO[_k].update(_seo)

# ---- BBバンド損切りバリアント（_BBSL）を自動生成 ----
# backtester.py の bb_sl_modules と対応（oscillator + trend + composite）
_BBSL_BASE_INDICATORS = [
    # オシレーター
    "RSI_14", "MACD_12_26_9", "Stochastic_14_3", "CCI_20", "Williams_R_14",
    # トレンド
    "SMA_20", "SMA_50", "SMA_Cross_20_50", "EMA_Cross_9_21", "EMA_21",
    "BollingerBands_20_2", "BB_Squeeze", "Ichimoku_Cloud",
    # コンポジット
    "RSI_MACD_Combo", "RSI_Stoch_Combo", "MACD_Stoch_Combo",
    "Triple_OSC_Combo", "All_AND_Consensus",
]
for _base in _BBSL_BASE_INDICATORS:
    _bi = INDICATOR_INFO.get(_base)
    if not _bi:
        continue
    _bbsl_key  = f"{_base}_BBSL"
    _bbsl_slug = f"{_bi['slug']}_bbsl"
    _disp      = _bi["display"]
    INDICATOR_INFO[_bbsl_key] = {
        "slug":            _bbsl_slug,
        "url_slug":        _bbsl_slug,
        "category":        "BBバンド損切り",
        "display":         f"{_disp}（BBバンド損切り）",
        "description":     (
            f"{_bi['description']}"
            " ボリンジャーバンドの上下バンドをTP/SLとして使用するバリアントで、"
            "ボラティリティに応じた動的な損切り・利確が可能です。"
        ),
        "feature":         (
            f"{_bi.get('feature', '')} "
            "TP=BB上バンド、SL=BB下バンド（売りの場合は逆）で動的に設定。"
        ),
        "good":            _bi.get("good", []) + ["ボラティリティが変動しやすい相場での動的SL/TP設定"],
        "bad":             _bi.get("bad", []) + ["バンド幅が極端に広い高ボラティリティ時の過大リスク"],
        "seo_title":       f"{_disp}（BBバンド損切り）の勝率を検証｜動的SL/TP分析",
        "seo_description": (
            f"ボリンジャーバンドをSL/TPに使用した{_disp}の勝率をバックテストで検証。"
            "動的損切り設定での精度をデータで分析。"
        ),
    }


# ============================================================
# 用途別ランキング定義
# ============================================================
IND_ONE_LINERS = {
    "SMA_20":               "短期トレンドの方向をひとめで確認",
    "SMA_50":               "中長期の流れを把握するシンプルな基準線",
    "SMA_Cross_20_50":      "ゴールデン/デッドクロスでトレンド転換を確認",
    "EMA_Cross_9_21":       "素早い反応でトレンドの初動を捉える",
    "EMA_21":               "価格との位置関係でトレンド方向を判断",
    "Ichimoku_Cloud":       "雲・転換線・基準線で相場全体を総合判断",
    "RSI_14":               "過熱感を数値化し、反転タイミングを狙う",
    "Stochastic_14_3":      "売られすぎ/買われすぎゾーンからの反転",
    "CCI_20":               "価格乖離を計測し、転換点を早期に察知",
    "Williams_R_14":        "RSIより素早い反応の逆張り指標",
    "BollingerBands_20_2":  "バンドタッチで逆張りエントリーのタイミング",
    "Hammer":               "下ヒゲ長い足が底値圏の反転を示唆",
    "Inverted_Hammer":      "上ヒゲ長い足が天井圏の反転を示唆",
    "Doji":                 "十字線で売買拮抗、転換の前兆を読む",
    "Bullish_Engulfing":    "大陽線が示す強い買い圧力の発生",
    "Bearish_Engulfing":    "大陰線が示す強い売り圧力の発生",
    "Pin_Bar":              "ヒゲで価格拒絶を確認、反転狙い",
    "MACD_12_26_9":         "クロスでトレンド転換の初動を捉える",
    "BB_Squeeze":           "バンド収縮後のブレイクアウトを先取り",
    "Three_White_Soldiers": "3連続陽線でトレンド継続の強さを確認",
    "Three_Black_Crows":    "3連続陰線でトレンド継続の強さを確認",
    "Pivot_Classic":        "前日の値動きから重要な価格水準を算出",
    "Fibonacci_Retracement":"黄金比で押し目・戻りの目標値を設定",
    "Support_Resistance":   "過去の節目を自動検出してTP/SLに活用",
    "ATR_14":               "ボラティリティに応じた動的SL/TPを設定",
    "Volatility_Index":     "BBバンド幅でボラティリティの変化を捉える",
    "RSI_MACD_Combo":       "RSI×MACDの一致でダマシを大幅に削減",
    "RSI_Stoch_Combo":      "RSI×ストキャスで逆張り精度を向上",
    "MACD_Stoch_Combo":     "MACDとストキャスで押し目タイミングを精緻化",
    "Triple_OSC_Combo":     "3指標一致の高精度・低頻度シグナル",
    "All_AND_Consensus":    "全指標が揃った時だけの最高精度シグナル",
}

PURPOSE_GROUPS = [
    {
        "key":   "trend",
        "label": "方向判断（トレンド）",
        "icon":  "bi-compass",
        "color": "pur-blue",
        "desc":  "相場が上昇・下降どちらかを判断するのに有効な指標群",
        "note":  "トレンドが明確な相場で特に力を発揮します",
        "indicators": ["SMA_Cross_20_50", "EMA_Cross_9_21", "EMA_21",
                       "SMA_20", "SMA_50", "Ichimoku_Cloud"],
    },
    {
        "key":   "entry",
        "label": "エントリータイミング",
        "icon":  "bi-crosshair",
        "color": "pur-green",
        "desc":  "押し目・底値圏での買いや天井圏での売りタイミングを捉える指標群",
        "note":  "レンジ・逆張りに強く、反転シグナルの精度が高い",
        "indicators": ["RSI_14", "Stochastic_14_3", "CCI_20", "Williams_R_14",
                       "BollingerBands_20_2", "Hammer", "Inverted_Hammer",
                       "Doji", "Bullish_Engulfing", "Bearish_Engulfing", "Pin_Bar"],
    },
    {
        "key":   "breakout",
        "label": "ブレイク・継続",
        "icon":  "bi-lightning-charge",
        "color": "pur-amber",
        "desc":  "ブレイクアウトやトレンド継続を検知するのに適した指標群",
        "note":  "相場が動き出す初動を捉えるのが得意",
        "indicators": ["MACD_12_26_9", "BB_Squeeze",
                       "Three_White_Soldiers", "Three_Black_Crows"],
    },
    {
        "key":   "line",
        "label": "利確・損切りライン",
        "icon":  "bi-rulers",
        "color": "pur-purple",
        "desc":  "TP（利確）・SL（損切り）の価格水準設定に使う指標群",
        "note":  "重要な価格水準を客観的に算出できる",
        "indicators": ["Pivot_Classic", "Fibonacci_Retracement", "Support_Resistance"],
    },
    {
        "key":   "volatility",
        "label": "ボラティリティ管理",
        "icon":  "bi-activity",
        "color": "pur-red",
        "desc":  "相場の値動きの大きさを測定するリスク管理に活用する指標群",
        "note":  "ポジションサイジングやSL設定の基準として活用",
        "indicators": ["ATR_14", "Volatility_Index"],
    },
    {
        "key":   "composite",
        "label": "コンポジット（複合）",
        "icon":  "bi-diagram-3",
        "color": "pur-cyan",
        "desc":  "複数の指標が一致したときのみシグナルを出す、精度重視の複合指標群",
        "note":  "シグナル頻度は低いが、精度と信頼度が高い",
        "indicators": ["RSI_MACD_Combo", "RSI_Stoch_Combo", "MACD_Stoch_Combo",
                       "Triple_OSC_Combo", "All_AND_Consensus"],
    },
]


def _pur_score(wr: float, pf: float, trades: int) -> float:
    """用途別・時間帯別・相場タイプ別の簡易スコア（0〜100）"""
    wr_s = min(wr, 100) * 0.45
    pf_s = min(max(pf - 1.0, 0) * 25, 25) * 0.35
    n_s  = min(trades / 200 * 100, 100) * 0.20
    return round(wr_s + pf_s + n_s, 1)


def _ind_card(ind_name: str, bt_best: dict, url_map: dict) -> dict:
    """指標 1 件分のカードデータを生成"""
    info = INDICATOR_INFO.get(ind_name, {})
    disp = info.get("display", ind_name)
    wr   = float(bt_best.get("win_rate")      or 0)
    pf   = float(bt_best.get("profit_factor") or 0)
    n    = int(bt_best.get("total_trades")    or 0)
    return {
        "indicator":  ind_name,
        "display":    disp,
        "short":      disp.split("（")[0],
        "one_liner":  IND_ONE_LINERS.get(ind_name, ""),
        "win_rate":   round(wr, 1),
        "pf":         round(pf, 2),
        "trades":     n,
        "pair":       bt_best.get("currency_pair", ""),
        "tf":         TF_LABELS.get(bt_best.get("timeframe", ""), bt_best.get("timeframe", "")),
        "score":      _pur_score(wr, pf, n),
        "url":        url_map.get(ind_name, ""),
    }


def get_purpose_ranking(all_bt: list, url_map: dict) -> list:
    """用途別ランキングデータを生成"""
    best_by_ind: dict = {}
    for r in all_bt:
        ind = r.get("indicator_name", "")
        wr  = float(r.get("win_rate") or 0)
        if ind not in best_by_ind or wr > float(best_by_ind[ind].get("win_rate") or 0):
            best_by_ind[ind] = r

    result = []
    for grp in PURPOSE_GROUPS:
        cards = []
        for ind in grp["indicators"]:
            bt = best_by_ind.get(ind)
            if bt:
                cards.append(_ind_card(ind, bt, url_map))
        cards.sort(key=lambda x: x["score"], reverse=True)
        result.append({**grp, "ranking": cards[:5]})
    return result


def get_timezone_ranking(url_map: dict) -> list:
    """時間帯別ランキング。simulation_trades の entry_at（UTC）をJSTに変換して集計"""
    import sqlalchemy
    from app.config import Config

    sql = """
        SELECT
            indicator_name,
            CASE
                WHEN HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) >= 8
                 AND HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) < 15  THEN 'japan'
                WHEN HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) >= 15
                 AND HOUR(DATE_ADD(entry_at, INTERVAL 9 HOUR)) < 21  THEN 'london'
                ELSE 'ny'
            END AS session,
            COUNT(*)              AS total,
            SUM(outcome = 'WIN')  AS wins,
            AVG(profit_loss)      AS avg_pnl
        FROM simulation_trades
        WHERE outcome IN ('WIN', 'LOSS')
        GROUP BY indicator_name, session
        HAVING total >= 5
        ORDER BY indicator_name, session
    """
    try:
        engine = sqlalchemy.create_engine(Config.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text(sql)).fetchall()
    except Exception as e:
        logger.warning("timezone_ranking query failed: %s", e)
        return []

    SESSIONS = [
        {"key": "japan",  "label": "東京時間（9〜15時）",    "icon": "bi-brightness-high", "color": "tz-red",    "hours": "JST 09:00〜15:00"},
        {"key": "london", "label": "ロンドン時間（15〜21時）","icon": "bi-cloud-sun",       "color": "tz-blue",   "hours": "JST 15:00〜21:00"},
        {"key": "ny",     "label": "NY時間（21〜翌9時）",     "icon": "bi-moon-stars",      "color": "tz-purple", "hours": "JST 21:00〜09:00"},
    ]
    sess_data: dict = {s["key"]: [] for s in SESSIONS}

    for row in rows:
        ind, sess = row[0], row[1]
        total, wins = int(row[2]), int(row[3])
        avg_pnl = float(row[4] or 0)
        if sess not in sess_data:
            continue
        info = INDICATOR_INFO.get(ind, {})
        if not info:
            continue
        wr = round(wins / total * 100, 1) if total > 0 else 0
        sess_data[sess].append({
            "indicator": ind,
            "display":   info.get("display", ind),
            "short":     info.get("display", ind).split("（")[0],
            "one_liner": IND_ONE_LINERS.get(ind, ""),
            "win_rate":  wr,
            "trades":    total,
            "avg_pnl":   round(avg_pnl, 0),
            "score":     _pur_score(wr, 1.0, total),
            "url":       url_map.get(ind, ""),
        })

    result = []
    for s in SESSIONS:
        cards = sorted(sess_data[s["key"]], key=lambda x: x["score"], reverse=True)
        result.append({**s, "ranking": cards[:5]})
    return result


def get_market_type_ranking(url_map: dict) -> list:
    """
    相場タイプ別ランキング。
    BB幅の大小（広い=トレンド、狭い=レンジ）で各取引を分類し集計。
    """
    import sqlalchemy
    import numpy as np
    import pandas as pd
    from app.config import Config
    from app.services.data_fetcher import get_candles

    try:
        engine = sqlalchemy.create_engine(Config.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as conn:
            trades_df = pd.read_sql(
                sqlalchemy.text(
                    "SELECT indicator_name, currency_pair, timeframe, "
                    "entry_at, outcome FROM simulation_trades "
                    "WHERE outcome IN ('WIN','LOSS') LIMIT 15000"
                ),
                conn,
                parse_dates=["entry_at"],
            )
    except Exception as e:
        logger.warning("market_type: trades load failed: %s", e)
        return []

    if trades_df.empty:
        return []

    # pair+TF ごとに BB幅タイムスタンプ配列を事前構築
    bb_cache: dict = {}
    for (pair, tf), _ in trades_df.groupby(["currency_pair", "timeframe"]):
        try:
            df = get_candles(pair, tf, limit=2000)
            if df is None or df.empty:
                continue
            df = df.sort_values("timestamp").reset_index(drop=True)
            close   = df["close"].astype(float)
            bb_mid  = close.rolling(20).mean()
            bb_std  = close.rolling(20).std()
            bb_wid  = (4 * bb_std) / bb_mid.replace(0, np.nan)
            avg_wid = bb_wid.rolling(50).mean()
            cats = np.where(
                bb_wid.isna() | avg_wid.isna(), "unknown",
                np.where(bb_wid > avg_wid * 1.05, "trend",
                np.where(bb_wid < avg_wid * 0.95, "range", "mixed"))
            )
            ts = pd.to_datetime(df["timestamp"])
            if ts.dt.tz is not None:
                ts = ts.dt.tz_localize(None)
            bb_cache[(pair, tf)] = (ts.values.astype("datetime64[ns]"), cats)
        except Exception as ex:
            logger.debug("market_type: BB failed %s %s: %s", pair, tf, ex)

    def _classify(row):
        key = (row["currency_pair"], row["timeframe"])
        if key not in bb_cache:
            return "unknown"
        ts_arr, cat_arr = bb_cache[key]
        try:
            ent = np.datetime64(pd.Timestamp(row["entry_at"]).replace(tzinfo=None), "ns")
            idx = int(np.searchsorted(ts_arr, ent, side="right")) - 1
            return cat_arr[idx] if idx >= 0 else "unknown"
        except Exception:
            return "unknown"

    trades_df["market_type"] = trades_df.apply(_classify, axis=1)
    valid = trades_df[trades_df["market_type"].isin(["trend", "range"])]
    if valid.empty:
        return []

    agg = (valid.groupby(["indicator_name", "market_type"])
           .apply(lambda g: pd.Series({
               "total": len(g),
               "wins":  (g["outcome"] == "WIN").sum(),
           }))
           .reset_index())
    agg["win_rate"] = (agg["wins"] / agg["total"] * 100).round(1)

    MARKET_TYPES = [
        {"key": "trend", "label": "トレンド相場",  "icon": "bi-graph-up-arrow",
         "color": "mt-blue",  "desc": "BB幅が広がり、EMAが傾いている局面", "badge": "順張り向き"},
        {"key": "range", "label": "レンジ相場",    "icon": "bi-arrows-expand",
         "color": "mt-green", "desc": "BB幅が収縮し、EMAが横ばいの局面",  "badge": "逆張り向き"},
    ]
    result = []
    for mt in MARKET_TYPES:
        sub   = agg[agg["market_type"] == mt["key"]]
        cards = []
        for _, row in sub[sub["total"] >= 5].iterrows():
            ind  = row["indicator_name"]
            info = INDICATOR_INFO.get(ind, {})
            if not info:
                continue
            wr = float(row["win_rate"])
            cards.append({
                "indicator": ind,
                "display":   info.get("display", ind),
                "short":     info.get("display", ind).split("（")[0],
                "one_liner": IND_ONE_LINERS.get(ind, ""),
                "win_rate":  wr,
                "trades":    int(row["total"]),
                "score":     _pur_score(wr, 1.0, int(row["total"])),
                "url":       url_map.get(ind, ""),
            })
        cards.sort(key=lambda x: x["score"], reverse=True)
        result.append({**mt, "ranking": cards[:8]})
    return result


def _to_unix(ts) -> int:
    """datetime / str / timestamp → Unix秒 (UTC固定)"""
    from datetime import datetime, timezone
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts[:19], fmt)
                return int(dt.replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                pass
        return 0
    if hasattr(ts, "timestamp"):
        # naive datetime はUTCとして扱う（DBはUTC保存）
        if getattr(ts, "tzinfo", None) is None:
            return int(ts.replace(tzinfo=timezone.utc).timestamp())
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


def load_seo_db() -> dict:
    """page_seo テーブルから SEO 上書きデータを取得する（失敗時は空dict）"""
    try:
        import sqlalchemy
        from app.config import Config
        engine = sqlalchemy.create_engine(Config.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as conn:
            rows = conn.execute(
                sqlalchemy.text(
                    "SELECT page_type, page_key, title, meta_description FROM page_seo"
                )
            ).fetchall()
        result = {}
        for row in rows:
            result[f"{row[0]}:{row[1]}"] = {
                "title":            row[2] or "",
                "meta_description": row[3] or "",
            }
        return result
    except Exception as e:
        logger.warning("load_seo_db failed: %s", e)
        return {}


def scope_article_css(css, scope=".ind-seo-article"):
    """記事CSSをスコープクラスに閉じ込め、Bootstrapとの競合を防ぐ。"""
    if not css:
        return ""
    # :root {} → スコープクラスに変換（CSS変数をスコープ内に閉じ込める）
    css = re.sub(r':root\s*\{', f'{scope} {{', css)
    # body {} ブロックを削除（インジケーターページのbodyスタイルを汚染しない）
    css = re.sub(r'\bbody\s*\{[^{}]*\}', '', css, flags=re.DOTALL)
    # *, *::before, *::after → スコープ内に限定
    css = re.sub(
        r'(?m)^\s*\*\s*,\s*\*::before\s*,\s*\*::after\s*\{',
        f'\n{scope} *, {scope} *::before, {scope} *::after {{',
        css,
    )
    # 素のHTML要素セレクター（Bootstrap競合）をスコープ付きに
    for tag in ('table', 'th', 'td', 'tr', 'tbody', 'thead'):
        css = re.sub(rf'(?<![.#\w-])\b{tag}\b(?=\s*[{{,])', f'{scope} {tag}', css)
    # Bootstrapと競合するクラス
    for cls in ('badge', 'card'):
        css = re.sub(rf'(?<![\w-])\.{cls}\b', f'{scope} .{cls}', css)
    # テーブルセルの折り返し禁止を強制追加
    css += f"\n{scope} td, {scope} th {{ white-space: nowrap; }}"
    return css


def load_content_db() -> dict:
    """site_content テーブルからコンテンツを取得（失敗時は空dict）"""
    try:
        import sqlalchemy
        from app.config import Config
        engine = sqlalchemy.create_engine(Config.SQLALCHEMY_DATABASE_URI)
        with engine.connect() as conn:
            rows = conn.execute(
                sqlalchemy.text(
                    "SELECT content_key, content_value FROM site_content"
                )
            ).fetchall()
        return {row[0]: (row[1] or "") for row in rows}
    except Exception as e:
        logger.warning("load_content_db failed: %s", e)
        return {}


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
    bt_period = Setting.get("backtest_period", "")

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

    # 通貨ペアごとの最良バックテスト結果（ヒーロー3カラム用）
    best_by_pair = {}
    for pair in all_pairs:
        pair_bests = [r for r in results if r.currency_pair == pair]
        if pair_bests:
            best_by_pair[pair] = max(pair_bests, key=lambda r: r.win_rate).to_dict()

    # 全TF・通貨ペアごとのトレードシミュレーション（各TF最新20件）
    trades_by_pair_tf = {}
    for pair in all_pairs:
        trades_by_pair_tf[pair] = {}
        for tf in TF_ORDER:
            raw = (SimulationTrade.query
                   .filter_by(indicator_name=indicator_name, currency_pair=pair, timeframe=tf)
                   .order_by(SimulationTrade.entry_at.desc())
                   .limit(20).all())
            if raw:
                trades_by_pair_tf[pair][tf] = [_fmt_trade(t) for t in raw]

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
            "slug":          i["slug"],
            "url_slug":      i.get("url_slug", i["slug"]),
            "category_slug": CATEGORY_SLUGS.get(i["category"], "indicators"),
            "display":       i["display"],
            "category":      i["category"],
            "win_rate":      br.win_rate if br else None,
        })
    cat = info["category"]
    related.sort(key=lambda x: (0 if x["category"] == cat else 1, -(x["win_rate"] or 0)))
    related = related[:8]

    return {
        "info":             info,
        "category_slug":    CATEGORY_SLUGS.get(info["category"], ""),
        "results":          [r.to_dict() for r in results],
        "results_by_pair":  results_by_pair,
        "best_by_pair":     best_by_pair,
        "trades_by_pair_tf": trades_by_pair_tf,
        "tf_labels":        TF_LABELS,
        "pairs":            all_pairs,
        "best":             best.to_dict(),
        "sl":               int(sl),
        "tp":               int(tp),
        "bt_period":        bt_period,
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
            "url_slug":      ind_info.get("url_slug", ind_info["slug"]),
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
    path.parent.mkdir(parents=True, exist_ok=True)
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

    # 管理画面用 slug→indicator_name マッピング JSON を生成
    _slug_map = {
        info["url_slug"]: name
        for name, info in INDICATOR_INFO.items()
        if not name.endswith("_BBSL")
    }
    _slug_map_path = Path(PUBLIC_HTML) / "admin" / "indicator_slugs.json"
    _slug_map_path.write_text(
        json.dumps(_slug_map, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Generated: admin/indicator_slugs.json (%d entries)", len(_slug_map))

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
        pair_pages = {"USDJPY": "usdjpy/index.html", "GBPJPY": "gbpjpy/index.html", "EURJPY": "eurjpy/index.html"}

        # 指標名 → 新URL マップ（/<cat_slug>/<url_slug>/）
        ind_url_map = {
            name: "/{}/{}/".format(
                CATEGORY_SLUGS.get(info["category"], "indicators"),
                info.get("url_slug", info["slug"])
            )
            for name, info in INDICATOR_INFO.items()
        }
        slug_map    = {name: info["slug"]    for name, info in INDICATOR_INFO.items()}
        display_map = {name: info["display"] for name, info in INDICATOR_INFO.items()}

        # TOP ページ（記事コンテンツ）
        content_db_top = load_content_db()
        top_pre  = content_db_top.get("top_article_pre",  "")
        top_post = content_db_top.get("top_article_post", "")

        # 指標別集計データ（勝率一覧 s06 / ランキング s07 用）
        bt_top_table   = []
        bt_top_ranking = []
        try:
            from app.models.backtest import BacktestResult as _BT
            from sqlalchemy import func as _sqf

            _agg = (
                _BT.query
                .with_entities(
                    _BT.indicator_name,
                    _sqf.avg(_BT.win_rate).label("avg_wr"),
                    _sqf.min(_BT.win_rate).label("min_wr"),
                    _sqf.max(_BT.win_rate).label("max_wr"),
                    _sqf.avg(_BT.profit_factor).label("avg_pf"),
                    _sqf.avg(_BT.max_drawdown).label("avg_dd"),
                    _sqf.avg(_BT.initial_capital).label("avg_cap"),
                    _sqf.sum(_BT.total_trades).label("total_t"),
                    _sqf.avg(_BT.sl_pips).label("avg_sl"),
                    _sqf.avg(_BT.tp_pips).label("avg_tp"),
                )
                .filter(_BT.total_trades >= 5)
                .group_by(_BT.indicator_name)
                .all()
            )

            def _wr_cls(wr):
                if wr >= 55: return "b-up"
                if wr >= 45: return "b-mid"
                return "b-down"

            def _score_top(wr, pf, n, sl, tp, dd_abs, cap):
                dd_pct = abs(dd_abs) / max(cap, 1) * 100
                ev = (wr / 100) * tp - (1 - wr / 100) * sl
                wr_s = 30 if wr>=60 else 27 if wr>=58 else 24 if wr>=56 else 20 if wr>=54 else 16 if wr>=52 else 12 if wr>=50 else max(0, int(wr/50*8))
                pf_s = 25 if pf>=1.50 else 22 if pf>=1.40 else 18 if pf>=1.30 else 14 if pf>=1.20 else 10 if pf>=1.10 else 6 if pf>=1.00 else 0
                dd_s = 20 if dd_pct<5 else 17 if dd_pct<8 else 14 if dd_pct<12 else 10 if dd_pct<16 else 6 if dd_pct<20 else 2
                n_s  = 15 if n>=500 else 12 if n>=300 else 9 if n>=150 else 6 if n>=80 else 3 if n>=30 else 0
                ev_s = 10 if ev>5 else 8 if ev>2 else 6 if ev>0 else 3 if ev>-2 else 0
                return wr_s + pf_s + dd_s + n_s + ev_s

            _scored = []
            for _r in _agg:
                _info   = INDICATOR_INFO.get(_r.indicator_name, {})
                _avg_wr = float(_r.avg_wr or 0)
                _min_wr = float(_r.min_wr or 0)
                _max_wr = float(_r.max_wr or 0)
                _avg_pf = float(_r.avg_pf or 0)
                _avg_dd = float(_r.avg_dd or 0)
                _avg_cp = float(_r.avg_cap or 1_000_000)
                _total  = int(_r.total_t or 0)
                _avg_sl = float(_r.avg_sl or 20)
                _avg_tp = float(_r.avg_tp or 40)

                _short = _info.get("display", _r.indicator_name)
                for _cut in ["（", "/"]:
                    if _cut in _short:
                        _short = _short.split(_cut)[0].strip()
                        break

                _scored.append({
                    "ind":          _r.indicator_name,
                    "display":      _info.get("display", _r.indicator_name),
                    "short_name":   _short,
                    "category":     _info.get("category", ""),
                    "feature":      _info.get("feature", ""),
                    "wr_class":     _wr_cls(_avg_wr),
                    "wr_label":     f"{_min_wr:.0f}〜{_max_wr:.0f}%",
                    "avg_wr":       _avg_wr,
                    "pf_label":     f"{_avg_pf:.2f}",
                    "avg_pf":       _avg_pf,
                    "dd_label":     f"{abs(_avg_dd)/max(_avg_cp,1)*100:.1f}%",
                    "total_trades": _total,
                    "score":        _score_top(_avg_wr, _avg_pf, _total, _avg_sl, _avg_tp, _avg_dd, _avg_cp),
                })

            # TOPページ勝率一覧（固定順で最大7指標を表示）
            _TOP_TABLE_ORDER = [
                "SMA_Cross_20_50",
                "MACD_12_26_9",
                "RSI_14",
                "Ichimoku_Cloud",
                "BollingerBands_20_2",
                "Stochastic_14_3",
                "ATR_14",
            ]
            _scored_map  = {r["ind"]: r for r in _scored}
            bt_top_table = [_scored_map[k] for k in _TOP_TABLE_ORDER if k in _scored_map]
            bt_top_ranking = sorted(_scored, key=lambda x: x["score"], reverse=True)[:5]
            logger.info("TOP ページ集計: %d指標", len(bt_top_table))
        except Exception as _e:
            logger.warning("TOP page data aggregation failed: %s", _e)

        # 通貨ペア別パネルデータ（TOPページ内部リンク用 + ダッシュボード生成共用）
        _pair_url_map = {"USDJPY": "/usdjpy/", "GBPJPY": "/gbpjpy/", "EURJPY": "/eurjpy/"}
        _pair_data_cache = {}
        pair_panels = []
        for _pair in ["USDJPY", "GBPJPY", "EURJPY"]:
            try:
                _pd = get_pair_data(_pair)
                _pair_data_cache[_pair] = _pd
                _pr  = _pd.get("price") or {}
                _ov  = _pd.get("overall", "NEUTRAL")
                pair_panels.append({
                    "pair":        _pair,
                    "display":     _pd.get("display", _pair),
                    "url":         _pair_url_map[_pair],
                    "rate":        _pr.get("close"),
                    "buy_count":   _pd.get("buy_count", 0),
                    "sell_count":  _pd.get("sell_count", 0),
                    "overall":     _ov,
                    "overall_ja":  "買いシグナル優勢" if _ov == "BUY" else "売りシグナル優勢" if _ov == "SELL" else "中立",
                    "overall_cls": "pp-buy" if _ov == "BUY" else "pp-sell" if _ov == "SELL" else "pp-neutral",
                })
            except Exception as _pe:
                logger.warning("Pair panel data error %s: %s", _pair, _pe)
                pair_panels.append({
                    "pair": _pair, "display": f"{_pair[:3]}/{_pair[3:]}",
                    "url": _pair_url_map[_pair], "rate": None,
                    "buy_count": 0, "sell_count": 0,
                    "overall": "NEUTRAL", "overall_ja": "中立", "overall_cls": "pp-neutral",
                })

        html = render_html(app, "article_top_static.html", {
            "content_pre":     top_pre,
            "content_post":    top_post,
            "bt_top_table":    bt_top_table,
            "bt_top_ranking":  bt_top_ranking,
            "pair_panels":     pair_panels,
            "pair_pages":      pair_pages,
            "updated_at":      updated_at,
            "active_page":     "home",
        })
        save("index.html", html)
        logger.info("TOP ページ（記事）生成完了")

        # 各通貨ペアのダッシュボード
        for pair, filename in pair_pages.items():
            data = _pair_data_cache.get(pair) or get_pair_data(pair)
            html = render_html(app, "dashboard_static.html", {
                "pairs": pairs,
                "pair_pages": pair_pages,
                "current_pair": pair,
                "data": data,
                "slug_map": slug_map,
                "ind_url_map": ind_url_map,
                "display_map": display_map,
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

        # バックテスト（テクニカルランキング）
        import decimal as _decimal
        class _DecEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, _decimal.Decimal):
                    return float(obj)
                if hasattr(obj, "isoformat"):
                    return str(obj)
                return super().default(obj)

        content_db = load_content_db()

        def _parse_recs(key):
            raw = content_db.get(key, "")
            try:
                return json.loads(raw) if raw else []
            except Exception:
                return []

        all_bt = get_all_backtest()
        for r in all_bt:
            r["url"] = ind_url_map.get(r.get("indicator_name", ""), "")

        # ランキングページ用: BBバンド損切りバリアントを除外（単体シグナルのみ表示）
        all_bt_ranked = [r for r in all_bt if not r.get("indicator_name", "").endswith("_BBSL")]

        # 3軸ランキングデータ生成
        purpose_ranking  = []
        timezone_ranking = []
        market_ranking   = []
        try:
            purpose_ranking  = get_purpose_ranking(all_bt_ranked, ind_url_map)
        except Exception as _e:
            logger.warning("purpose_ranking failed: %s", _e)
        try:
            timezone_ranking = get_timezone_ranking(ind_url_map)
        except Exception as _e:
            logger.warning("timezone_ranking failed: %s", _e)
        try:
            market_ranking   = get_market_type_ranking(ind_url_map)
        except Exception as _e:
            logger.warning("market_type_ranking failed: %s", _e)

        # 検証条件データを抽出
        bt_sl_pips = bt_tp_pips = bt_rr_ratio = bt_timeframes = ""
        if all_bt:
            sl = float(all_bt[0].get("sl_pips") or 0)
            tp = float(all_bt[0].get("tp_pips") or 0)
            rr = float(all_bt[0].get("rr_ratio") or 0)
            bt_sl_pips  = str(int(sl)) if sl else ""
            bt_tp_pips  = str(int(tp)) if tp else ""
            bt_rr_ratio = str(round(rr, 1)) if rr else ""
            tfs = sorted(
                set(r.get("timeframe", "") for r in all_bt if r.get("timeframe")),
                key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99,
            )
            bt_timeframes = " · ".join(TF_LABELS.get(t, t) for t in tfs)

        # バックテスト取引数（BacktestResult.total_trades を TF 別に合算）
        # ※ SimulationTrade は 300 件上限で刈り込まれるため使用しない
        bt_sim_total = ""
        bt_sim_by_tf = ""
        try:
            from app.models.backtest import BacktestResult
            from sqlalchemy import func as _sf
            tf_rows = (
                BacktestResult.query
                .with_entities(BacktestResult.timeframe, _sf.sum(BacktestResult.total_trades))
                .group_by(BacktestResult.timeframe)
                .all()
            )
            tf_counts = {tf: int(cnt or 0) for tf, cnt in tf_rows if tf}
            total = sum(tf_counts.values())
            if total:
                bt_sim_total = f"{total:,}"
                ordered = sorted(
                    tf_counts.items(),
                    key=lambda x: TF_ORDER.index(x[0]) if x[0] in TF_ORDER else 99,
                )
                bt_sim_by_tf = " · ".join(
                    f"{TF_LABELS.get(tf, tf)}: {cnt:,}件" for tf, cnt in ordered
                )
        except Exception as _e:
            logger.warning("bt trade count failed: %s", _e)

        results_json   = json.dumps(all_bt_ranked, cls=_DecEncoder, ensure_ascii=False)
        tf_labels_json = json.dumps(TF_LABELS, ensure_ascii=False)

        from app.models.settings import Setting as _Setting
        bt_period = _Setting.get("backtest_period", "")

        html = render_html(app, "backtest_static.html", {
            "pairs":            pairs,
            "pair_pages":       pair_pages,
            "results":          all_bt_ranked,
            "results_json":     results_json,
            "tf_labels_json":   tf_labels_json,
            "ind_url_map":      ind_url_map,
            "content_analysis": content_db.get("ranking_analysis", ""),
            "ranking_title":    content_db.get("ranking_title", ""),
            "ranking_intro":    content_db.get("ranking_intro", ""),
            "recs_short":       _parse_recs("ranking_short_term"),
            "recs_day":         _parse_recs("ranking_day_trade"),
            "recs_swing":       _parse_recs("ranking_swing"),
            "bt_sl_pips":       bt_sl_pips,
            "bt_tp_pips":       bt_tp_pips,
            "bt_rr_ratio":      bt_rr_ratio,
            "bt_timeframes":    bt_timeframes,
            "bt_sim_total":     bt_sim_total,
            "bt_sim_by_tf":     bt_sim_by_tf,
            "bt_period":        bt_period,
            "updated_at":       updated_at,
            "active_page":      "backtest",
            "purpose_ranking":  purpose_ranking,
            "timezone_ranking": timezone_ranking,
            "market_ranking":   market_ranking,
        })
        save("technical-ranking/index.html", html)

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

        # DB から SEO 上書きデータを取得
        seo_db = load_seo_db()

        # カテゴリ個別ページ生成（/<slug>/index.html → /<slug>/）
        for cat_name, cat_info in CATEGORY_INFO.items():
            try:
                page_data = get_category_page_data(cat_name)
                if page_data is None:
                    continue
                # DB の SEO 上書きを適用
                db_key = f"category:{cat_info['slug']}"
                if db_key in seo_db and seo_db[db_key]["title"]:
                    page_data["category"]["seo_title"] = seo_db[db_key]["title"]
                if db_key in seo_db and seo_db[db_key]["meta_description"]:
                    page_data["category"]["seo_description"] = seo_db[db_key]["meta_description"]
                html = render_html(app, "category_static.html", {
                    **page_data,
                    "updated_at": updated_at,
                    "active_page": "backtest",
                })
                save(f"{cat_info['slug']}/index.html", html)
            except Exception as e:
                logger.warning("Category page error %s: %s", cat_name, e)

        # インジケーター個別ページ生成（/<cat_slug>/<url_slug>/index.html）
        for ind_name, ind_info in INDICATOR_INFO.items():
            try:
                page_data = get_indicator_page_data(ind_name, app)
                if page_data is None:
                    continue
                # DB の SEO 上書きを適用
                url_slug = ind_info.get("url_slug", ind_info["slug"])
                db_key = f"indicator:{url_slug}"
                if db_key in seo_db and seo_db[db_key]["title"]:
                    page_data["info"]["seo_title"] = seo_db[db_key]["title"]
                if db_key in seo_db and seo_db[db_key]["meta_description"]:
                    page_data["info"]["seo_description"] = seo_db[db_key]["meta_description"]
                article_key = f"indicator_article_{url_slug}"
                raw_css    = content_db.get(f"{article_key}_css", "")
                raw_jsonld = content_db.get(f"{article_key}_jsonld", "")
                html = render_html(app, "indicator_static.html", {
                    **page_data,
                    "indicator_article":        content_db.get(article_key, ""),
                    "indicator_article_css":    scope_article_css(raw_css),
                    "indicator_article_jsonld": raw_jsonld,
                    "updated_at": updated_at,
                    "active_page": "backtest",
                })
                cat_slug = CATEGORY_SLUGS.get(ind_info["category"], "indicators")
                save(f"{cat_slug}/{url_slug}/index.html", html)
            except Exception as e:
                logger.warning("Indicator page error %s: %s", ind_name, e)

        logger.info("Static site generation complete")


if __name__ == "__main__":
    main()
