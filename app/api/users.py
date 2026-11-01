from flask import Blueprint, request, g
from app.schemas.member import MemberAccountCreateSchema
from app.services.member_service import MemberService
from app.utils.permissions import admin_required
from app.utils.errors import success_response, ValidationError

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["POST"])
@admin_required
def create_user():
    """
    Create a new team member login account (President-controlled account creation).
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    """
    data = request.get_json(silent=True) or {}
    errors = MemberAccountCreateSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on user account creation.", details=errors)

    member, user = MemberService.create_member_account(data, actor_user_id=g.current_user.id)
    return success_response(
        data={
            "member": member.to_dict(include_sensitive=True),
            "user": user.to_dict(),
        },
        message="Member account created successfully.",
        status_code=201,
    )
