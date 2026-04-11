from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate()
mail = Mail()


def create_app():
    app = Flask(
        __name__,
        template_folder="../app/templates",
        static_folder="../static",
    )

    from app.config import Config
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Register models so Migrate can detect them
    from app.models import price_data, signal, backtest, report, settings, simulation_trade, backtest_snapshot  # noqa

    # Register blueprints
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.api import bp as api_bp
    from app.routes.settings_routes import bp as settings_bp
    from app.routes.admin import bp as admin_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
