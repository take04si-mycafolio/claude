import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルをconfig.pyの2つ上のディレクトリ（プロジェクトルート）から読み込む
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mysql+pymysql://root:@localhost/forex_signal_db?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Alpha Vantage
    ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

    # Google Gemini
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")
    REPORT_RECIPIENTS = [
        e.strip()
        for e in os.environ.get("REPORT_RECIPIENTS", "").split(",")
        if e.strip()
    ]

    # Supported currency pairs
    CURRENCY_PAIRS = ["USDJPY", "GBPJPY", "EURJPY"]

    # Alpha Vantage pair mapping (from_currency, to_currency)
    AV_PAIR_MAP = {
        "USDJPY": ("USD", "JPY"),
        "GBPJPY": ("GBP", "JPY"),
        "EURJPY": ("EUR", "JPY"),
    }

    # Supported timeframes
    TIMEFRAMES = ["5min", "15min", "30min", "1hr", "4hr", "daily"]

    # Alpha Vantage interval mapping
    AV_INTERVAL_MAP = {
        "5min": "5min",
        "15min": "15min",
        "30min": "30min",
        "1hr": "60min",
    }

    # Backtesting defaults (overridden by DB settings)
    DEFAULT_INITIAL_CAPITAL = 1_000_000  # 100万円
    DEFAULT_LOT_SIZE = 100_000          # 1標準ロット
    DEFAULT_SL_PIPS = 20.0
    DEFAULT_TP_PIPS = 40.0
    DEFAULT_BACKTEST_HOURS = 12

    # Signal thresholds
    MIN_WIN_RATE = 55.0         # 勝率55%以上をアクティブシグナルとする
    MIN_TRADES_COUNT = 3        # 最低取引数
    HIGH_CONFIDENCE_THRESHOLD = 70.0

    # Pip value for JPY pairs (standard lot)
    JPY_PAIR_PIP_VALUE = 1000   # 1pip = ¥1,000 (1標準ロット)
