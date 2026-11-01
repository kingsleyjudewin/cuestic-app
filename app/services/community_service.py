import re
import time
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload, selectinload
from app.extensions import db
from app.models.community import Community, CommunityChannel, CommunityMember, ChatMessage
from app.models.team import Team, slugify
from app.models.member import Member
from app.models.user import User
from app.utils.errors import PermissionDeniedError, NotFoundError, ValidationError
from app.utils.datetime_utils import utc_now, format_iso_utc

# In-Memory Fast Caches for Sub-Millisecond Retrieval
_COMMUNITIES_CACHE = None
_COMMUNITIES_CACHE_AT = 0.0
_COMMUNITIES_CACHE_TTL = 1800.0  # 30 minutes
_COMMUNITIES_MAP = {}  # community_id -> community_dict
_COMMUNITY_MEMBER_SETS = {}  # community_id -> set(user_ids)
_CHANNEL_MESSAGES_CACHE = {}  # channel_id -> list of message dicts
_COMMUNITIES_PROVISIONED = False


def invalidate_communities_cache():
    """Invalidate in-memory communities cache on write operations."""
    global _COMMUNITIES_CACHE, _COMMUNITIES_CACHE_AT, _COMMUNITIES_MAP, _COMMUNITY_MEMBER_SETS
    _COMMUNITIES_CACHE = None
    _COMMUNITIES_CACHE_AT = 0.0
    _COMMUNITIES_MAP = {}
    _COMMUNITY_MEMBER_SETS = {}


def can_user_access_community(user: User, community) -> bool:
    """Strict Discord community access rule:
    - President and Admin have universal access across ALL communities.
    - Team leaders and members only have access to their own team community.
    """
    if not user or not user.is_active:
        return False

    # President & Admin have universal access
    if user.role in User.ADMIN_ROLES:
        return True

    # If dict representation passed
    if isinstance(community, dict):
        team_id = community.get("team_id")
        comm_id = community.get("id")
        member_ids = _COMMUNITY_MEMBER_SETS.get(comm_id) or set(community.get("member_user_ids") or [])
        if team_id:
            if user.linked_member and user.linked_member.team_id == team_id:
                return True
            if user.id in member_ids:
                return True
            return False
        if not community.get("is_team_restricted", True):
            return True
        return user.id in member_ids

    # If Model instance passed
    if community.team_id:
        if user.linked_member and user.linked_member.team_id == community.team_id:
            return True
        mem = CommunityMember.query.filter_by(
            community_id=community.id,
            user_id=user.id
        ).first()
        if mem:
            return True
        return False

    if not community.is_team_restricted:
        return True

    return CommunityMember.query.filter_by(
        community_id=community.id,
        user_id=user.id
    ).first() is not None


def provision_default_communities() -> dict:
    """Idempotently provisions default Discord communities for all operational teams:
    - Volunteering Team Community
    - Documentation Team Community
    - Media Team Community
    And synchronizes all active team members into their respective community servers.
    """
    global _COMMUNITIES_PROVISIONED
    teams = Team.query.all()
    created_count = 0
    synced_members_count = 0

    team_configs = {
        "volunteering": {
            "name": "Volunteering Team Community",
            "slug": "volunteering-community",
            "desc": "Official Discord Community for CUestIC Volunteering Team members.",
            "icon": "volunteer_activism",
            "color": "#10B981",
            "channels": [
                ("general", "General discussion and volunteer announcements", "text"),
                ("announcements", "Crucial broadcasts from Team Leads and President", "announcement"),
                ("volunteers-chat", "Day-to-day event volunteer coordination", "group_chat"),
            ]
        },
        "documentation": {
            "name": "Documentation Team Community",
            "slug": "documentation-community",
            "desc": "Official Discord Community for CUestIC Documentation Team members.",
            "icon": "description",
            "color": "#8B5CF6",
            "channels": [
                ("general", "General discussion and documentation guidelines", "text"),
                ("announcements", "Reporting deadlines, review notes, and alerts", "announcement"),
                ("reports-chat", "Activity report drafts, minutes, and peer reviews", "group_chat"),
            ]
        },
        "media": {
            "name": "Media Team Community",
            "slug": "media-community",
            "desc": "Official Discord Community for CUestIC Media Team members.",
            "icon": "photo_camera",
            "color": "#F59E0B",
            "channels": [
                ("general", "Media coverage planning and creative discussion", "text"),
                ("announcements", "Event equipment scheduling and drive updates", "announcement"),
                ("media-desk", "Live photo selection, reel edits, and poster reviews", "group_chat"),
            ]
        }
    }

    president = User.query.filter_by(role=User.ROLE_PRESIDENT).first()
    admin = User.query.filter_by(role=User.ROLE_ADMIN).first()

    for team in teams:
        team_key = team.slug.lower() if team.slug else team.name.lower()
        config = team_configs.get(team_key, {
            "name": f"{team.name} Team Community",
            "slug": f"{slugify(team.name)}-community",
            "desc": f"Official Discord Community for CUestIC {team.name} Team members.",
            "icon": "groups",
            "color": "#2563EB",
            "channels": [
                ("general", "General team chat and collaboration", "text"),
                ("announcements", "Important updates and announcements", "announcement"),
                ("team-chat", "Daily team coordination", "group_chat"),
            ]
        })

        comm = Community.query.filter_by(slug=config["slug"]).first()
        if not comm:
            comm = Community(
                name=config["name"],
                slug=config["slug"],
                description=config["desc"],
                icon=config["icon"],
                color=config["color"],
                team_id=team.id,
                is_team_restricted=True,
                created_by=president.id if president else None
            )
            db.session.add(comm)
            db.session.flush()
            created_count += 1

        for idx, (ch_name, ch_topic, ch_type) in enumerate(config["channels"]):
            existing_ch = CommunityChannel.query.filter_by(community_id=comm.id, name=ch_name).first()
            if not existing_ch:
                new_ch = CommunityChannel(
                    community_id=comm.id,
                    name=ch_name,
                    topic=ch_topic,
                    channel_type=ch_type,
                    position=idx,
                    created_by=president.id if president else None
                )
                db.session.add(new_ch)

        if president:
            if not CommunityMember.query.filter_by(community_id=comm.id, user_id=president.id).first():
                db.session.add(CommunityMember(
                    community_id=comm.id,
                    user_id=president.id,
                    role="owner",
                    nickname="Club President"
                ))
        if admin and admin.id != (president.id if president else None):
            if not CommunityMember.query.filter_by(community_id=comm.id, user_id=admin.id).first():
                db.session.add(CommunityMember(
                    community_id=comm.id,
                    user_id=admin.id,
                    role="admin",
                    nickname="Club Admin"
                ))

        team_members = Member.query.filter_by(team_id=team.id, is_active=True).all()
        for m in team_members:
            if m.linked_user_id:
                user_record = db.session.get(User, m.linked_user_id)
                if user_record and user_record.is_active:
                    existing_cm = CommunityMember.query.filter_by(
                        community_id=comm.id,
                        user_id=user_record.id
                    ).first()
                    if not existing_cm:
                        cm_role = "moderator" if user_record.role == User.ROLE_TEAM_LEADER else "member"
                        db.session.add(CommunityMember(
                            community_id=comm.id,
                            user_id=user_record.id,
                            role=cm_role,
                            nickname=m.full_name
                        ))
                        synced_members_count += 1

    db.session.commit()
    _COMMUNITIES_PROVISIONED = True
    invalidate_communities_cache()
    return {
        "created_communities": created_count,
        "synced_members": synced_members_count
    }


def _load_communities_into_cache() -> list[dict]:
    """Load all communities with eager-loaded channels and members in a single batched query."""
    global _COMMUNITIES_CACHE, _COMMUNITIES_CACHE_AT, _COMMUNITIES_MAP, _COMMUNITIES_PROVISIONED
    now = time.time()
    if _COMMUNITIES_CACHE is not None and (now - _COMMUNITIES_CACHE_AT < _COMMUNITIES_CACHE_TTL):
        return _COMMUNITIES_CACHE

    if not _COMMUNITIES_PROVISIONED:
        if Community.query.count() == 0:
            provision_default_communities()
        _COMMUNITIES_PROVISIONED = True

    communities = (
        Community.query
        .options(
            joinedload(Community.team),
            selectinload(Community.channels),
            selectinload(Community.members),
        )
        .order_by(Community.id.asc())
        .all()
    )

    # Pre-fetch latest messages for all channels in one single aggregated query
    latest_msg_ids = (
        db.session.query(db.func.max(ChatMessage.id))
        .group_by(ChatMessage.channel_id)
        .all()
    )
    msg_id_list = [row[0] for row in latest_msg_ids if row[0]]
    latest_messages = {}
    if msg_id_list:
        for m in ChatMessage.query.filter(ChatMessage.id.in_(msg_id_list)).all():
            latest_messages[m.channel_id] = {
                "id": m.id,
                "sender_name": m.sender_name,
                "content": m.content[:60],
                "created_at": format_iso_utc(m.created_at),
            }

    # Pre-cache recent messages for all channels in one batched query
    recent_messages = (
        ChatMessage.query
        .order_by(ChatMessage.created_at.desc())
        .limit(300)
        .all()
    )
    chan_msgs = {}
    for msg in reversed(recent_messages):
        chan_msgs.setdefault(msg.channel_id, []).append(msg.to_dict())
    _CHANNEL_MESSAGES_CACHE.update(chan_msgs)

    data = []
    comm_map = {}
    comm_member_sets = {}
    for c in communities:
        for ch in c.channels:
            if ch.id not in _CHANNEL_MESSAGES_CACHE:
                _CHANNEL_MESSAGES_CACHE[ch.id] = []
        channels_data = [
            ch.to_dict(include_recent_message=True, recent_message_dict=latest_messages.get(ch.id))
            for ch in c.channels
        ]
        members_data = [m.to_dict() for m in c.members]
        member_user_ids = {m.user_id for m in c.members}
        comm_member_sets[c.id] = member_user_ids

        cd = c.to_dict(
            include_channels=True,
            include_members=True,
            channels_data=channels_data,
            members_data=members_data,
            channel_count=len(channels_data),
            member_count=len(members_data)
        )
        cd["member_user_ids"] = list(member_user_ids)
        data.append(cd)
        comm_map[c.id] = cd

    _COMMUNITIES_CACHE = data
    _COMMUNITIES_MAP = comm_map
    _COMMUNITY_MEMBER_SETS = comm_member_sets
    _COMMUNITIES_CACHE_AT = now
    return _COMMUNITIES_CACHE


def get_user_communities(user: User) -> list[dict]:
    """List communities accessible to the authenticated user in sub-millisecond time."""
    all_comms = _load_communities_into_cache()

    if user.role in User.ADMIN_ROLES:
        return all_comms

    user_team_id = user.linked_member.team_id if user.linked_member else None
    filtered = []
    for c in all_comms:
        m_set = _COMMUNITY_MEMBER_SETS.get(c["id"], set())
        if (c.get("team_id") == user_team_id) or \
           (user.id in m_set) or \
           (not c.get("is_team_restricted")):
            filtered.append(c)

    return filtered


def get_community(community_id: int, user: User, include_details: bool = True) -> dict:
    """Fetch single community details from in-memory cache in sub-millisecond time."""
    _load_communities_into_cache()
    comm = _COMMUNITIES_MAP.get(community_id)

    if not comm:
        # Fallback to direct DB query if community was created externally
        comm_db = db.session.get(Community, community_id)
        if not comm_db:
            raise NotFoundError(f"Community #{community_id} not found.")
        if not can_user_access_community(user, comm_db):
            raise PermissionDeniedError("Access denied: You can only access your team community.")
        return comm_db.to_dict(include_channels=include_details, include_members=include_details, current_user=user)

    if not can_user_access_community(user, comm):
        raise PermissionDeniedError("Access denied: You can only access your team community.")

    return comm


def get_community_channels(community_id: int, user: User) -> list[dict]:
    """Retrieve community channels in sub-millisecond time."""
    comm = get_community(community_id, user, include_details=True)
    return comm.get("channels", [])


def create_community(user: User, data: dict) -> dict:
    """Create a new team/group community."""
    name = data["name"].strip()
    slug_base = slugify(name)
    slug = slug_base
    count = 1
    while Community.query.filter_by(slug=slug).first():
        slug = f"{slug_base}-{count}"
        count += 1

    team_id = data.get("team_id")
    if team_id:
        team = db.session.get(Team, team_id)
        if not team:
            raise NotFoundError(f"Team #{team_id} not found.")

    comm = Community(
        name=name,
        slug=slug,
        description=data.get("description"),
        icon=data.get("icon") or "groups",
        color=data.get("color") or "#2563EB",
        team_id=team_id,
        is_team_restricted=data.get("is_team_restricted", True),
        created_by=user.id
    )
    db.session.add(comm)
    db.session.flush()

    gen_ch = CommunityChannel(
        community_id=comm.id,
        name="general",
        topic="General chat and discussions",
        channel_type="text",
        position=0,
        created_by=user.id
    )
    db.session.add(gen_ch)

    db.session.add(CommunityMember(
        community_id=comm.id,
        user_id=user.id,
        role="owner",
        nickname=user.linked_member.full_name if user.linked_member else user.username
    ))

    db.session.commit()
    invalidate_communities_cache()
    return get_community(comm.id, user, include_details=True)


def create_channel(community_id: int, user: User, data: dict) -> dict:
    """Create a new channel or group chat within an authorized community."""
    comm = get_community(community_id, user, include_details=False)

    raw_name = data["name"].strip().lower()
    ch_name = re.sub(r"[^a-z0-9\-]", "-", raw_name).strip("-")
    if not ch_name:
        ch_name = "chat"

    if CommunityChannel.query.filter_by(community_id=community_id, name=ch_name).first():
        raise ValidationError(f"Channel '#{ch_name}' already exists in this community.")

    next_pos = db.session.query(db.func.max(CommunityChannel.position)).filter_by(
        community_id=community_id
    ).scalar() or 0

    channel = CommunityChannel(
        community_id=community_id,
        name=ch_name,
        topic=data.get("topic"),
        channel_type=data.get("channel_type", "text"),
        position=next_pos + 1,
        created_by=user.id
    )
    db.session.add(channel)
    db.session.commit()

    invalidate_communities_cache()
    return channel.to_dict()


def get_channel_messages(
    community_id: int,
    channel_id: int,
    user: User,
    limit: int = 50,
    before_id: int = None
) -> list[dict]:
    """Retrieve message history for a channel within an authorized community with in-memory caching."""
    # Fast authorization check in O(1)
    get_community(community_id, user, include_details=False)

    # Check cache for initial page load
    if before_id is None and channel_id in _CHANNEL_MESSAGES_CACHE:
        return _CHANNEL_MESSAGES_CACHE[channel_id][-limit:]

    channel = CommunityChannel.query.filter_by(
        id=channel_id,
        community_id=community_id
    ).first()
    if not channel:
        raise NotFoundError(f"Channel #{channel_id} not found in Community #{community_id}.")

    query = ChatMessage.query.filter_by(
        community_id=community_id,
        channel_id=channel.id
    )

    if before_id:
        query = query.filter(ChatMessage.id < before_id)

    messages = query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    messages.reverse()
    res = [m.to_dict() for m in messages]

    if before_id is None:
        _CHANNEL_MESSAGES_CACHE[channel_id] = res

    return res


def send_message(
    community_id: int,
    channel_id: int,
    user: User,
    data: dict
) -> dict:
    """Post a message to a channel in an authorized community with cache write-through."""
    comm = get_community(community_id, user, include_details=False)

    channel = CommunityChannel.query.filter_by(
        id=channel_id,
        community_id=community_id
    ).first()
    if not channel:
        raise NotFoundError(f"Channel #{channel_id} not found in Community #{community_id}.")

    content = data["content"].strip()
    if not content:
        raise ValidationError("Message content cannot be empty.")

    sender_name = user.linked_member.full_name if user.linked_member else user.username
    sender_role = user.role

    message = ChatMessage(
        community_id=community_id,
        channel_id=channel.id,
        user_id=user.id,
        sender_name=sender_name,
        sender_role=sender_role,
        content=content,
        message_type=data.get("message_type", "text"),
        parent_id=data.get("parent_id"),
        attachment_url=data.get("attachment_url")
    )
    db.session.add(message)
    db.session.commit()

    m_dict = message.to_dict()

    # Fast in-memory cache update
    if channel_id in _CHANNEL_MESSAGES_CACHE:
        _CHANNEL_MESSAGES_CACHE[channel_id].append(m_dict)
        if len(_CHANNEL_MESSAGES_CACHE[channel_id]) > 100:
            _CHANNEL_MESSAGES_CACHE[channel_id].pop(0)
    else:
        _CHANNEL_MESSAGES_CACHE[channel_id] = [m_dict]

    # Update latest_message in cached community channels
    if community_id in _COMMUNITIES_MAP:
        for ch in _COMMUNITIES_MAP[community_id].get("channels", []):
            if ch.get("id") == channel_id:
                ch["last_message"] = {
                    "id": message.id,
                    "sender_name": sender_name,
                    "content": content[:60],
                    "created_at": format_iso_utc(message.created_at),
                }

    return m_dict


def get_community_members(community_id: int, user: User) -> list[dict]:
    """Retrieve all members of a community in sub-millisecond time."""
    comm = get_community(community_id, user, include_details=True)
    return comm.get("members", [])
