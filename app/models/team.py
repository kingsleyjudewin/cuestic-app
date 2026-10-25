import re
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


def slugify(text: str) -> str:
    """Generate clean URL slug from string."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


class Team(db.Model):
    """Team model representing departmental club teams."""
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    leader_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    leader = db.relationship("User", back_populates="led_teams", foreign_keys=[leader_user_id])
    members = db.relationship("Member", back_populates="team", cascade="all", lazy="dynamic")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.slug and self.name:
            self.slug = slugify(self.name)

    def to_dict(self, include_counts: bool = True) -> dict:
        """Serialize team to dictionary."""
        data = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "leader_user_id": self.leader_user_id,
            "leader_name": self.leader.username if self.leader else None,
            "is_active": self.is_active,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
        if include_counts:
            data["member_count"] = self.members.filter_by(is_active=True).count()
        return data
