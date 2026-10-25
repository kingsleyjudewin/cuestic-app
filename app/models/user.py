from datetime import datetime, timezone
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class User(db.Model):
    """User account model for authentication and role-based authorization."""
    __tablename__ = "users"

    ROLE_PRESIDENT = "president"
    ROLE_ADMIN = "admin"
    ROLE_TEAM_LEADER = "team_leader"
    ROLE_MEMBER = "member"

    ALL_ROLES = (ROLE_PRESIDENT, ROLE_ADMIN, ROLE_TEAM_LEADER, ROLE_MEMBER)
    ADMIN_ROLES = (ROLE_PRESIDENT, ROLE_ADMIN)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default=ROLE_MEMBER)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    tokens = db.relationship("ApiToken", back_populates="user", cascade="all, delete-orphan", lazy="dynamic")
    led_teams = db.relationship("Team", back_populates="leader", foreign_keys="Team.leader_user_id", lazy="dynamic")
    created_events = db.relationship("Event", back_populates="creator", foreign_keys="Event.created_by", lazy="dynamic")
    created_tasks = db.relationship("Task", back_populates="creator", foreign_keys="Task.created_by", lazy="dynamic")
    assigned_tasks = db.relationship("TaskAssignment", back_populates="assigner", foreign_keys="TaskAssignment.assigned_by", lazy="dynamic")
    linked_member = db.relationship("Member", back_populates="linked_user", uselist=False)

    def set_password(self, password: str):
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify user password against hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Check if user has president or admin privileges."""
        return self.role in self.ADMIN_ROLES

    def is_team_leader(self) -> bool:
        """Check if user is a team leader."""
        return self.role == self.ROLE_TEAM_LEADER

    def to_dict(self, include_roles: bool = True) -> dict:
        """Serialize user to dictionary."""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": format_iso_utc(self.created_at),
            "last_login_at": format_iso_utc(self.last_login_at),
        }
        if self.linked_member:
            data["member_id"] = self.linked_member.id
        return data


class ApiToken(db.Model):
    """Secure, revocable API authentication tokens for mobile clients."""
    __tablename__ = "api_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    user = db.relationship("User", back_populates="tokens")

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Generate SHA-256 hash of a raw token."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def create_token(cls, user_id: int, expires_at: datetime, name: str = None) -> tuple["ApiToken", str]:
        """Create new API token, returning the token object and raw unhashed secret."""
        raw_secret = secrets.token_urlsafe(48)
        token_hash = cls.hash_token(raw_secret)
        token_obj = cls(
            user_id=user_id,
            token_hash=token_hash,
            name=name,
            expires_at=expires_at,
            is_revoked=False,
        )
        return token_obj, raw_secret

    def is_valid(self) -> bool:
        """Check if token is not revoked and not expired."""
        if self.is_revoked:
            return False
        # compare timezone-aware
        now = utc_now()
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now < exp
