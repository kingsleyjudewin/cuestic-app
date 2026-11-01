import time
from flask import Blueprint, request, g
from app.extensions import db
from app.models.team import Team, slugify
from app.models.user import User
from app.models.member import Member
from app.schemas.team import TeamCreateSchema, TeamUpdateSchema
from app.utils.permissions import token_required, admin_required
from app.utils.errors import success_response, ValidationError, NotFoundError, ConflictError
from app.services.audit_service import AuditService

teams_bp = Blueprint("teams", __name__)

_TEAMS_CACHE = None
_TEAMS_CACHE_AT = 0.0
_TEAMS_CACHE_TTL = 1800.0  # 30 minutes TTL


def invalidate_teams_cache():
    global _TEAMS_CACHE, _TEAMS_CACHE_AT
    _TEAMS_CACHE = None
    _TEAMS_CACHE_AT = 0.0


def _load_teams_into_cache() -> list[dict]:
    global _TEAMS_CACHE, _TEAMS_CACHE_AT
    now = time.time()
    if _TEAMS_CACHE is not None and (now - _TEAMS_CACHE_AT < _TEAMS_CACHE_TTL):
        return _TEAMS_CACHE

    from sqlalchemy import func
    from sqlalchemy.orm import joinedload
    teams = Team.query.options(joinedload(Team.leader)).filter_by(is_active=True).order_by(Team.name.asc()).all()
    counts = dict(
        db.session.query(Member.team_id, func.count(Member.id))
        .filter(Member.is_active == True)
        .group_by(Member.team_id)
        .all()
    )
    data = []
    for team in teams:
        td = team.to_dict(include_counts=False)
        td["member_count"] = counts.get(team.id, 0)
        data.append(td)

    _TEAMS_CACHE = data
    _TEAMS_CACHE_AT = now
    return _TEAMS_CACHE


def get_user_led_team_ids(user: User) -> list[int]:
    """Get IDs of teams led by this user without querying the database."""
    teams = _load_teams_into_cache()
    return [t["id"] for t in teams if t.get("leader_user_id") == user.id]


@teams_bp.route("", methods=["GET"])
@token_required
def list_teams():
    """
    List all active club teams with membership counts.
    ---
    tags:
      - Teams
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of teams with member counts
    """
    data = _load_teams_into_cache()
    return success_response(data=data)


@teams_bp.route("/<int:team_id>", methods=["GET"])
@token_required
def get_team(team_id: int):
    """
    Get detailed information about a specific team.
    ---
    tags:
      - Teams
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: team_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Team details
      404:
        description: Team not found
    """
    team = db.session.get(Team, team_id)
    if not team:
        raise NotFoundError(f"Team with ID {team_id} not found.")
    return success_response(data=team.to_dict(include_counts=True))


@teams_bp.route("", methods=["POST"])
@admin_required
def create_team():
    """
    Create a new team (such as configuring the fourth departmental team).
    ---
    tags:
      - Teams
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
            properties:
              name:
                type: string
                example: Logistics
              description:
                type: string
                example: Manages venue setup, equipment and physical supplies
              leader_user_id:
                type: integer
                example: 2
    responses:
      201:
        description: Team successfully created
      400:
        description: Validation error
      409:
        description: Team name or slug conflict
    """
    data = request.get_json(silent=True) or {}
    errors = TeamCreateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on team creation.", details=errors)

    name = data["name"].strip()
    slug = data.get("slug", "").strip() or slugify(name)

    # Conflict check
    if Team.query.filter(Team.name.ilike(name)).first():
        raise ConflictError(f"A team named '{name}' already exists.")
    if Team.query.filter_by(slug=slug).first():
        raise ConflictError(f"A team with slug '{slug}' already exists.")

    leader_user_id = data.get("leader_user_id")
    if leader_user_id:
        leader_user = db.session.get(User, leader_user_id)
        if not leader_user or not leader_user.is_active:
            raise ValidationError(f"Leader user with ID {leader_user_id} does not exist or is inactive.")

    team = Team(
        name=name,
        slug=slug,
        description=data.get("description", "").strip() if data.get("description") else None,
        leader_user_id=leader_user_id,
        is_active=True
    )
    db.session.add(team)
    db.session.flush()

    AuditService.log_action(
        action="TEAM_CREATED",
        entity_type="Team",
        entity_id=team.id,
        actor_user_id=g.current_user.id,
        details={"name": team.name, "slug": team.slug}
    )
    db.session.commit()
    invalidate_teams_cache()

    return success_response(data=team.to_dict(include_counts=True), message="Team created successfully.", status_code=201)


@teams_bp.route("/<int:team_id>", methods=["PATCH"])
@admin_required
def update_team(team_id: int):
    """
    Update team information (e.g. rename configurable team or change leader).
    ---
    tags:
      - Teams
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: team_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Team successfully updated
      404:
        description: Team not found
    """
    team = db.session.get(Team, team_id)
    if not team:
        raise NotFoundError(f"Team with ID {team_id} not found.")

    data = request.get_json(silent=True) or {}
    errors = TeamUpdateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on team update.", details=errors)

    if "name" in data:
        new_name = data["name"].strip()
        existing = Team.query.filter(Team.name.ilike(new_name), Team.id != team.id).first()
        if existing:
            raise ConflictError(f"Another team named '{new_name}' already exists.")
        team.name = new_name
        if "slug" not in data:
            team.slug = slugify(new_name)

    if "slug" in data:
        new_slug = data["slug"].strip()
        existing = Team.query.filter(Team.slug == new_slug, Team.id != team.id).first()
        if existing:
            raise ConflictError(f"Another team with slug '{new_slug}' already exists.")
        team.slug = new_slug

    if "description" in data:
        team.description = data["description"].strip() if data["description"] else None

    if "leader_user_id" in data:
        leader_id = data["leader_user_id"]
        if leader_id:
            leader_user = db.session.get(User, leader_id)
            if not leader_user or not leader_user.is_active:
                raise ValidationError("Assigned team leader does not exist or is inactive.")
            team.leader_user_id = leader_id
        else:
            team.leader_user_id = None

    if "is_active" in data:
        team.is_active = bool(data["is_active"])

    AuditService.log_action(
        action="TEAM_UPDATED",
        entity_type="Team",
        entity_id=team.id,
        actor_user_id=g.current_user.id,
        details={"changes": list(data.keys())}
    )
    db.session.commit()
    invalidate_teams_cache()

    return success_response(data=team.to_dict(include_counts=True), message="Team updated successfully.")


@teams_bp.route("/<int:team_id>/members", methods=["GET"])
@token_required
def get_team_members(team_id: int):
    """
    Get all active members belonging to a team.
    ---
    tags:
      - Teams
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: team_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: List of team members
      404:
        description: Team not found
    """
    from app.api.members import _load_all_members_into_cache
    all_members = _load_all_members_into_cache()

    global _TEAMS_CACHE
    leader_user_id = None
    if _TEAMS_CACHE:
        team_dict = next((t for t in _TEAMS_CACHE if t["id"] == team_id), None)
        if team_dict:
            leader_user_id = team_dict.get("leader_user_id")
        else:
            team = db.session.get(Team, team_id)
            if not team:
                raise NotFoundError(f"Team with ID {team_id} not found.")
            leader_user_id = team.leader_user_id
    else:
        team = db.session.get(Team, team_id)
        if not team:
            raise NotFoundError(f"Team with ID {team_id} not found.")
        leader_user_id = team.leader_user_id

    user = g.current_user
    can_view_phones = user.is_admin() or (
        user.is_team_leader() and leader_user_id == user.id
    )

    team_members = []
    for m in all_members:
        if m.get("team_id") == team_id and m.get("is_active"):
            item = dict(m)
            if not can_view_phones and item.get("linked_user_id") != user.id:
                phone = item.get("phone_number")
                if phone:
                    item["phone_number"] = phone[:3] + "*****" + phone[-4:] if len(phone) > 7 else "*****"
            team_members.append(item)

    return success_response(data=team_members)
