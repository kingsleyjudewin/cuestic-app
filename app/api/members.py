from flask import Blueprint, request, g
from app.models.member import Member
from app.schemas.member import MemberCreateSchema, MemberUpdateSchema
from app.services.member_service import MemberService
from app.utils.permissions import token_required, leader_or_admin_required, admin_required, check_can_manage_member
from app.utils.errors import success_response, ValidationError

members_bp = Blueprint("members", __name__)


@members_bp.route("", methods=["GET"])
@token_required
def list_members():
    """
    List, search and filter members with pagination.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: team_id
        schema:
          type: integer
      - in: query
        name: search
        schema:
          type: string
        description: Search by name, reg number or phone
      - in: query
        name: class_name
        schema:
          type: string
      - in: query
        name: is_active
        schema:
          type: boolean
          default: true
      - in: query
        name: page
        schema:
          type: integer
          default: 1
      - in: query
        name: per_page
        schema:
          type: integer
          default: 50
    responses:
      200:
        description: Paginated member list
    """
    team_id = request.args.get("team_id", type=int)
    search = request.args.get("search", type=str)
    class_name = request.args.get("class_name", type=str)
    is_active_arg = request.args.get("is_active")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    is_active = True
    if is_active_arg is not None:
        is_active = is_active_arg.lower() in ("true", "1")

    items, meta = MemberService.list_members(
        team_id=team_id,
        search=search,
        class_name=class_name,
        is_active=is_active,
        page=page,
        per_page=per_page
    )

    user = g.current_user
    # Admin can view all phone numbers; leader can view phone numbers for their led teams; members see masked
    led_team_ids = [t.id for t in user.led_teams.all()] if user.is_team_leader() else []

    def can_view_phone(member):
        if user.is_admin():
            return True
        if user.is_team_leader() and member.team_id in led_team_ids:
            return True
        if member.linked_user_id == user.id:
            return True
        return False

    serialized = [m.to_dict(include_sensitive=can_view_phone(m)) for m in items]
    return success_response(data=serialized, meta=meta)


@members_bp.route("/<int:member_id>", methods=["GET"])
@token_required
def get_member(member_id: int):
    """
    Get detailed member profile.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: member_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Member profile
      404:
        description: Member not found
    """
    member = MemberService.get_member_by_id(member_id)
    user = g.current_user
    can_view_phone = user.is_admin() or (
        user.is_team_leader() and member.team_id in [t.id for t in user.led_teams.all()]
    ) or (member.linked_user_id == user.id)

    return success_response(data=member.to_dict(include_sensitive=can_view_phone))


@members_bp.route("", methods=["POST"])
@leader_or_admin_required
def create_member():
    """
    Create a new member record with phone normalization and duplicate prevention.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - full_name
              - class_name
              - phone_number
              - team_id
            properties:
              full_name:
                type: string
                example: Rahul Sharma
              registration_number:
                type: string
                example: 22BCS101
              class_name:
                type: string
                example: 3rd Year CSE
              section:
                type: string
                example: A
              phone_number:
                type: string
                example: "+919876543210"
              team_id:
                type: integer
                example: 1
              whatsapp_opt_in:
                type: boolean
                example: true
    responses:
      201:
        description: Member successfully created
      400:
        description: Validation error
      409:
        description: Duplicate member or phone
    """
    data = request.get_json(silent=True) or {}
    errors = MemberCreateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on member creation.", details=errors)

    # If team leader, verify they lead this team
    user = g.current_user
    if user.is_team_leader() and not user.is_admin():
        led_team_ids = [t.id for t in user.led_teams.all()]
        if data["team_id"] not in led_team_ids:
            raise ValidationError("Team leaders can only register members into their own teams.")

    member = MemberService.create_member(data, actor_user_id=user.id)
    return success_response(data=member.to_dict(include_sensitive=True), message="Member created successfully.", status_code=201)


@members_bp.route("/<int:member_id>", methods=["PATCH"])
@leader_or_admin_required
def update_member(member_id: int):
    """
    Update member details.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: member_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Member updated successfully
      404:
        description: Member not found
    """
    member = MemberService.get_member_by_id(member_id)
    check_can_manage_member(g.current_user, member)

    data = request.get_json(silent=True) or {}
    errors = MemberUpdateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on member update.", details=errors)

    updated = MemberService.update_member(member, data, actor_user_id=g.current_user.id)
    return success_response(data=updated.to_dict(include_sensitive=True), message="Member updated successfully.")


@members_bp.route("/<int:member_id>", methods=["DELETE"])
@leader_or_admin_required
def delete_member(member_id: int):
    """
    Delete or deactivate member. If member has task history, deactivates to preserve history.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: member_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Member deactivated or deleted
      404:
        description: Member not found
    """
    member = MemberService.get_member_by_id(member_id)
    check_can_manage_member(g.current_user, member)

    was_deleted = MemberService.deactivate_or_delete_member(member, actor_user_id=g.current_user.id)
    msg = "Member deleted." if was_deleted else "Member has historical task assignments and was deactivated to preserve history."
    return success_response(data={"hard_deleted": was_deleted, "is_active": False}, message=msg)
