from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class DeviceToken(db.Model):
    """Stores Firebase Cloud Messaging (FCM) device registration tokens."""
    __tablename__ = "device_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = db.Column(db.String(512), unique=True, nullable=False, index=True)
    device_type = db.Column(db.String(20), default="android", nullable=False)
    device_name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", backref=db.backref("device_tokens", lazy="dynamic", cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_type": self.device_type,
            "device_name": self.device_name,
            "is_active": self.is_active,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
