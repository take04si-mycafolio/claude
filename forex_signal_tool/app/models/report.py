from datetime import datetime, timezone
from app import db


class AiReport(db.Model):
    __tablename__ = "ai_reports"

    id = db.Column(db.BigInteger, primary_key=True)
    report_type = db.Column(db.String(20), default="scheduled")
    content = db.Column(db.Text, nullable=False)
    model_used = db.Column(db.String(80))
    tokens_used = db.Column(db.Integer)
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.Index("idx_report_created", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "report_type": self.report_type,
            "content": self.content,
            "model_used": self.model_used,
            "email_sent": self.email_sent,
            "email_sent_at": self.email_sent_at.isoformat() if self.email_sent_at else None,
            "created_at": self.created_at.isoformat(),
        }
