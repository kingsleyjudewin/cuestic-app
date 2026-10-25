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
    teams = Team.query.filter_by(is_active=True).order_by(Team.name.asc()).all()
    return success_response(data=[team.to_dict(include_counts=True) for team in teams])


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
    team = db.session.get(Team, team_id)
    if not team:
        raise NotFoundError(f"Team with ID {team_id} not found.")

    members = Member.query.filter_by(team_id=team_id, is_active=True).order_by(Member.full_name.asc()).all()

    # Determine if current user is authorized to see phone numbers:
    # Admin, president, or leader of this team
    user = g.current_user
    can_view_phones = user.is_admin() or (
        user.is_team_leader() and team.leader_user_id == user.id
    )

    return success_response(data=[m.to_dict(include_sensitive=can_view_phones) for m in members])
