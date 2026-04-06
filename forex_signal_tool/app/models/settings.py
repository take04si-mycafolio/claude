from datetime import datetime, timezone
from app import db


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def get(key, default=None):
        row = Setting.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key, value, description=None):
        row = Setting.query.get(key)
        if row:
            row.value = str(value)
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = Setting(key=key, value=str(value), description=description)
            db.session.add(row)
        db.session.commit()

    @staticmethod
    def get_float(key, default=0.0):
        val = Setting.get(key)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def get_int(key, default=0):
        val = Setting.get(key)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def get_list(key, default=None):
        """カンマ区切りの値をリストとして取得"""
        val = Setting.get(key)
        if val:
            return [v.strip() for v in val.split(",") if v.strip()]
        return default or []
