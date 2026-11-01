from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class Member(db.Model):
    """Member model storing student details and team association."""
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=True, index=True)
    class_name = db.Column(db.String(50), nullable=True)
    section = db.Column(db.String(20), nullable=True)
    phone_number = db.Column(db.String(30), nullable=False)  # Normalized E.164 format e.g. +919876543210
    country_code = db.Column(db.String(10), default="+91", nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True)
    linked_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    whatsapp_opt_in = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    team = db.relationship("Team", back_populates="members")
    linked_user = db.relationship("User", back_populates="linked_member")
    assignments = db.relationship("TaskAssignment", back_populates="member", lazy="dynamic")

    def has_assignment_history(self) -> bool:
        """Check if member has any historical task assignments."""
        return self.assignments.count() > 0

    def to_dict(self, include_sensitive: bool = True, has_history: bool = None) -> dict:
        """
        Serialize member to dictionary.
        If include_sensitive is False, phone_number is masked for unauthorized viewers.
        """
        phone = self.phone_number
        if not include_sensitive and phone:
            # Mask phone number, e.g. +91*****43210
            phone = phone[:3] + "*****" + phone[-4:] if len(phone) > 7 else "*****"

        effective_email = self.email or (self.linked_user.email if self.linked_user else None)

        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": effective_email,
            "registration_number": self.registration_number,
            "class_name": self.class_name,
            "section": self.section,
            "phone_number": phone,
            "country_code": self.country_code,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "linked_user_id": self.linked_user_id,
            "linked_user": {
                "id": self.linked_user.id,
                "username": self.linked_user.username,
                "email": self.linked_user.email,
                "role": self.linked_user.role,
                "is_active": self.linked_user.is_active,
                "account_status": "active" if self.linked_user.is_active else "inactive",
                "credential_setup_status": self.linked_user.credential_setup_status or "completed",
            } if self.linked_user else None,
            "whatsapp_opt_in": self.whatsapp_opt_in,
            "is_active": self.is_active,
            "has_history": has_history if has_history is not None else self.has_assignment_history(),
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
