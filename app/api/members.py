import time
from flask import Blueprint, request, g
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.member import Member
from app.schemas.member import MemberCreateSchema, MemberUpdateSchema, MemberAccountCreateSchema, PasswordResetSchema
from app.services.member_service import MemberService
from app.utils.permissions import token_required, leader_or_admin_required, admin_required, check_can_manage_member
from app.utils.errors import success_response, ValidationError

members_bp = Blueprint("members", __name__)

_ASSIGNMENT_MEMBERS_CACHE = None
_ASSIGNMENT_MEMBERS_CACHE_AT = 0.0

_MEMBERS_CACHE = None
_MEMBERS_CACHE_AT = 0.0
_MEMBERS_CACHE_TTL = 1800.0  # 30 minutes TTL


def get_assignment_member_ids():
    global _ASSIGNMENT_MEMBERS_CACHE, _ASSIGNMENT_MEMBERS_CACHE_AT
    now = time.time()
    if _ASSIGNMENT_MEMBERS_CACHE is not None and (now - _ASSIGNMENT_MEMBERS_CACHE_AT < 60.0):
        return _ASSIGNMENT_MEMBERS_CACHE
    from app.models.task_assignment import TaskAssignment
    rows = db.session.query(TaskAssignment.member_id).distinct().all()
    _ASSIGNMENT_MEMBERS_CACHE = {r[0] for r in rows if r[0] is not None}
    _ASSIGNMENT_MEMBERS_CACHE_AT = now
    return _ASSIGNMENT_MEMBERS_CACHE


def invalidate_assignment_members_cache():
    global _ASSIGNMENT_MEMBERS_CACHE, _ASSIGNMENT_MEMBERS_CACHE_AT
    _ASSIGNMENT_MEMBERS_CACHE = None
    _ASSIGNMENT_MEMBERS_CACHE_AT = 0.0


def invalidate_members_cache():
    global _MEMBERS_CACHE, _MEMBERS_CACHE_AT
    _MEMBERS_CACHE = None
    _MEMBERS_CACHE_AT = 0.0


def _load_all_members_into_cache():
    global _MEMBERS_CACHE, _MEMBERS_CACHE_AT
    now = time.time()
    if _MEMBERS_CACHE is not None and (now - _MEMBERS_CACHE_AT < _MEMBERS_CACHE_TTL):
        return _MEMBERS_CACHE

    members = (
        Member.query.options(
            joinedload(Member.team),
            joinedload(Member.linked_user),
        )
        .order_by(Member.full_name.asc())
        .all()
    )
    active_assignment_member_ids = get_assignment_member_ids()

    _MEMBERS_CACHE = [
        m.to_dict(
            include_sensitive=True,
            has_history=(m.id in active_assignment_member_ids),
        )
        for m in members
    ]
    _MEMBERS_CACHE_AT = now
    return _MEMBERS_CACHE


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

    all_members = _load_all_members_into_cache()
    filtered = all_members

    if team_id is not None:
        filtered = [m for m in filtered if m.get("team_id") == team_id]

    if is_active is not None:
        filtered = [m for m in filtered if m.get("is_active") == is_active]

    if class_name:
        cn = class_name.strip().lower()
        filtered = [m for m in filtered if cn in (m.get("class_name") or "").lower()]

    if search:
        s = search.strip().lower()
        s_alt = s.replace('e', 'i') if 'e' in s else s.replace('i', 'e')

        def _matches(val: str | None) -> bool:
            if not val:
                return False
            v = val.lower()
            return s in v or s_alt in v

        filtered = [
            m
            for m in filtered
            if _matches(m.get("full_name"))
            or _matches(m.get("email"))
            or _matches(m.get("registration_number"))
            or _matches(m.get("phone_number"))
            or (m.get("linked_user") and (_matches(m["linked_user"].get("username")) or _matches(m["linked_user"].get("email"))))
        ]

    total = len(filtered)
    pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    paged = filtered[start:end]

    user = g.current_user
    from app.api.teams import get_user_led_team_ids
    led_team_ids = get_user_led_team_ids(user) if user.is_team_leader() else []

    def can_view_phone(m_dict):
        if user.is_admin():
            return True
        if user.is_team_leader() and m_dict.get("team_id") in led_team_ids:
            return True
        if m_dict.get("linked_user_id") == user.id:
            return True
        return False

    serialized = []
    for m in paged:
        item = dict(m)
        if not can_view_phone(item):
            phone = item.get("phone_number")
            if phone:
                item["phone_number"] = phone[:3] + "*****" + phone[-4:] if len(phone) > 7 else "*****"
        serialized.append(item)

    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_next": end < total,
        "has_prev": page > 1,
    }
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
    all_members = _load_all_members_into_cache()
    cached_m = next((m for m in all_members if m["id"] == member_id), None)
    user = g.current_user
    from app.api.teams import get_user_led_team_ids
    led_team_ids = get_user_led_team_ids(user) if user.is_team_leader() else []

    if cached_m:
        item = dict(cached_m)
        can_view_phone = user.is_admin() or (
            user.is_team_leader() and item.get("team_id") in led_team_ids
        ) or (item.get("linked_user_id") == user.id)
        if not can_view_phone and item.get("phone_number"):
            phone = item["phone_number"]
            item["phone_number"] = phone[:3] + "*****" + phone[-4:] if len(phone) > 7 else "*****"
        return success_response(data=item)

    member = MemberService.get_member_by_id(member_id)
    can_view_phone = user.is_admin() or (
        user.is_team_leader() and member.team_id in led_team_ids
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
    invalidate_members_cache()
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
    invalidate_members_cache()
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
    invalidate_members_cache()
    msg = "Member deleted." if was_deleted else "Member has historical task assignments and was deactivated to preserve history."
    return success_response(data={"hard_deleted": was_deleted, "is_active": False}, message=msg)


@members_bp.route("/account", methods=["POST"])
@admin_required
def create_member_account():
    """
    Create a new member and linked login user account for any team.
    Authorized for President and Admin accounts.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    """
    data = request.get_json(silent=True) or {}
    errors = MemberAccountCreateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on member account creation.", details=errors)

    member, user = MemberService.create_member_account(data, actor_user_id=g.current_user.id)
    invalidate_members_cache()
    return success_response(
        data={
            "member": member.to_dict(include_sensitive=True),
            "user": user.to_dict(),
        },
        message="Member account created successfully.",
        status_code=201,
    )


@members_bp.route("/<int:member_id>/reset-password", methods=["POST"])
@admin_required
def reset_member_password(member_id: int):
    """
    Reset password for a member's linked user account.
    Authorized for President and Admin accounts.
    ---
    tags:
      - Members
    security:
      - BearerAuth: []
    """
    member = MemberService.get_member_by_id(member_id)
    data = request.get_json(silent=True) or {}
    errors = PasswordResetSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on password reset.", details=errors)

    user = MemberService.reset_member_password(member, data["new_password"], actor_user_id=g.current_user.id)
    invalidate_members_cache()
    return success_response(
        data={"user_id": user.id, "username": user.username},
        message=f"Password reset successfully for member account '{user.username}'."
    )


@members_bp.route("/<int:member_id>/setup-token", methods=["POST"])
@admin_required
def generate_setup_token(member_id: int):
    """
    Generate or re-issue a single-use password setup token for a member account.
    Authorized for President and Admin.
    """
    from app.services.auth_service import AuthService
    member = MemberService.get_member_by_id(member_id)
    if not member.linked_user:
        raise ValidationError("This member does not have a linked user account.")

    token_obj, raw_token = AuthService.create_setup_token(
        user_id=member.linked_user.id,
        creator_id=g.current_user.id,
    )
    from app.utils.datetime_utils import format_iso_utc
    return success_response(
        data={
            "member_id": member.id,
            "user_id": member.linked_user.id,
            "username": member.linked_user.username,
            "setup_token": raw_token,
            "expires_at": format_iso_utc(token_obj.expires_at),
            "credential_setup_status": member.linked_user.credential_setup_status,
        },
        message="Setup token generated successfully. Provide this token to the member to establish their password."
    )


@members_bp.route("/import-media", methods=["POST"])
@admin_required
def import_media_members():
    """
    Import Media team members and create accounts.
    Authorized for President and Admin.
    """
    from app.services.media_import_service import MediaImportService
    data = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run", False))
    confirm = bool(data.get("confirm", True))
    records = data.get("records")  # Optional override

    result = MediaImportService.execute_import(
        records=records,
        operator_identifier=g.current_user.username,
        dry_run=dry_run,
        confirm=confirm,
    )
    return success_response(data=result, message="Media members import executed.")
