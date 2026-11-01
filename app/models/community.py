from datetime import datetime, timezone
from app.extensions import db
from app.utils.datetime_utils import utc_now, format_iso_utc


class Community(db.Model):
    """Discord-like Community Server for team and group collaboration."""
    __tablename__ = "communities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), nullable=True)  # icon name / emoji / URL
    color = db.Column(db.String(20), nullable=True)  # hex color e.g. #2563EB
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    is_team_restricted = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    team = db.relationship("Team")
    creator = db.relationship("User", foreign_keys=[created_by])
    channels = db.relationship(
        "CommunityChannel",
        back_populates="community",
        cascade="all, delete-orphan",
        order_by="asc(CommunityChannel.position), asc(CommunityChannel.created_at)"
    )
    members = db.relationship(
        "CommunityMember",
        back_populates="community",
        cascade="all, delete-orphan"
    )

    def to_dict(
        self,
        include_channels: bool = False,
        include_members: bool = False,
        current_user=None,
        channels_data: list | None = None,
        members_data: list | None = None,
        channel_count: int | None = None,
        member_count: int | None = None,
    ) -> dict:
        c_count = channel_count if channel_count is not None else (len(self.channels) if self.channels else 0)
        m_count = member_count if member_count is not None else (len(self.members) if self.members else 0)
        data = {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "team_slug": self.team.slug if self.team else None,
            "is_team_restricted": self.is_team_restricted,
            "created_by": self.created_by,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
            "channel_count": c_count,
            "member_count": m_count,
        }
        if include_channels:
            data["channels"] = channels_data if channels_data is not None else [c.to_dict() for c in self.channels]
        if include_members:
            data["members"] = members_data if members_data is not None else [m.to_dict() for m in self.members]
        return data


class CommunityChannel(db.Model):
    """Text channel or group chat within a community."""
    __tablename__ = "community_channels"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(255), nullable=True)
    channel_type = db.Column(db.String(30), default="text", nullable=False)  # text, announcement, group_chat
    position = db.Column(db.Integer, default=0, nullable=False)
    is_private = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    community = db.relationship("Community", back_populates="channels")
    creator = db.relationship("User", foreign_keys=[created_by])
    messages = db.relationship(
        "ChatMessage",
        back_populates="channel",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="desc(ChatMessage.created_at)"
    )

    def to_dict(self, include_recent_message: bool = True, recent_message_dict: dict | None = None) -> dict:
        data = {
            "id": self.id,
            "community_id": self.community_id,
            "name": self.name,
            "topic": self.topic,
            "channel_type": self.channel_type,
            "position": self.position,
            "is_private": self.is_private,
            "created_by": self.created_by,
            "created_at": format_iso_utc(self.created_at),
        }
        if include_recent_message:
            if recent_message_dict is not None:
                data["last_message"] = recent_message_dict
            else:
                latest = self.messages.first()
                if latest:
                    data["last_message"] = {
                        "id": latest.id,
                        "sender_name": latest.sender_name,
                        "content": latest.content[:60],
                        "created_at": format_iso_utc(latest.created_at),
                    }
                else:
                    data["last_message"] = None
        return data


class CommunityMember(db.Model):
    """Membership record linking users to a community server."""
    __tablename__ = "community_members"
    __table_args__ = (
        db.UniqueConstraint("community_id", "user_id", name="uq_community_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(30), default="member", nullable=False)  # owner, admin, moderator, member
    nickname = db.Column(db.String(100), nullable=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    community = db.relationship("Community", back_populates="members")
    user = db.relationship("User")

    def to_dict(self) -> dict:
        member_name = None
        if self.user and self.user.linked_member:
            member_name = self.user.linked_member.full_name
        return {
            "id": self.id,
            "community_id": self.community_id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "display_name": member_name or (self.user.username if self.user else None),
            "role": self.role,
            "user_role": self.user.role if self.user else None,
            "nickname": self.nickname,
            "joined_at": format_iso_utc(self.joined_at),
        }


class ChatMessage(db.Model):
    """Individual chat message within a community channel."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("communities.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("community_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_name = db.Column(db.String(120), nullable=False)
    sender_role = db.Column(db.String(30), nullable=False)  # president, admin, team_leader, member
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(30), default="text", nullable=False)  # text, system, announcement
    parent_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    attachment_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    community = db.relationship("Community")
    channel = db.relationship("CommunityChannel", back_populates="messages")
    author = db.relationship("User", foreign_keys=[user_id])
    parent = db.relationship("ChatMessage", remote_side=[id], foreign_keys=[parent_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "community_id": self.community_id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "sender_name": self.sender_name,
            "sender_role": self.sender_role,
            "content": self.content,
            "message_type": self.message_type,
            "parent_id": self.parent_id,
            "attachment_url": self.attachment_url,
            "created_at": format_iso_utc(self.created_at),
            "updated_at": format_iso_utc(self.updated_at),
        }
