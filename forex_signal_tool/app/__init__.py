from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import datetime, timezone, timedelta

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()

JST = timezone(timedelta(hours=9))


def _utc_to_jst(value):
    """UTC日時文字列またはdatetimeをJST文字列に変換"""
    if value is None:
        return ""
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(value[:19], fmt).replace(tzinfo=timezone.utc)
                return dt.astimezone(JST).strftime("%Y/%m/%d %H:%M")
            except ValueError:
                pass
        return value[:16]
    if hasattr(value, "astimezone"):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(JST).strftime("%Y/%m/%d %H:%M")
    return str(value)


def create_app():
    app = Flask(
        __name__,
        template_folder="../app/templates",
        static_folder="../static",
    )

    from app.config import Config
    app.config.from_object(Config)

    app.jinja_env.filters["utc_to_jst"] = _utc_to_jst

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Register models so Migrate can detect them
    from app.models import price_data, signal, backtest, report, settings, simulation_trade, backtest_snapshot, session_ranking  # noqa

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.api import bp as api_bp
    from app.routes.settings_routes import bp as settings_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.backtest_v2 import bp as backtest_v2_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(backtest_v2_bp, url_prefix="/api")

    return app
