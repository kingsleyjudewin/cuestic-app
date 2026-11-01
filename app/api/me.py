from flask import Blueprint, request, g
from app.extensions import db
from app.models.task import Task
from app.models.task_assignment import TaskAssignment
from app.models.member import Member
from app.utils.permissions import token_required
from app.utils.errors import success_response, NotFoundError

me_bp = Blueprint("me", __name__)


@me_bp.route("/assignments", methods=["GET"])
@token_required
def get_my_assignments():
    """
    Get personal task assignments for the authenticated member / volunteer.
    Identity is strictly derived from the validated authentication token.
    Never trusts client-supplied identifiers.
    ---
    tags:
      - Personal Dashboard
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: status
        schema:
          type: string
        description: Filter assignments by status (e.g. awaiting_confirmation, accepted, in_progress, submitted)
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
        description: List of personal assignments for the authenticated volunteer
      404:
        description: User account is not linked to any member record
    """
    user = g.current_user
    member = user.linked_member

    # Account integrity check: account must have an associated member record
    if not member:
        raise NotFoundError("Your user account is not associated with any club member record.")

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)
    status_filter = request.args.get("status")

    # Strictly query assignments belonging to this authenticated member's ID
    query = (
        TaskAssignment.query
        .options(
            db.joinedload(TaskAssignment.task).joinedload(Task.event),
            db.joinedload(TaskAssignment.member).joinedload(Member.team),
        )
        .filter(TaskAssignment.member_id == member.id)
    )

    if status_filter:
        query = query.filter(TaskAssignment.status == status_filter.strip().lower())

    # Order by active status first, then upcoming deadline
    query = query.join(Task).order_by(Task.deadline.asc(), TaskAssignment.id.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response(
        data=[a.to_dict(include_sensitive=False) for a in paginated.items],
        meta={
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "member_id": member.id,
            "member_name": member.full_name,
            "team_id": member.team_id,
            "team_name": member.team.name if member.team else None,
        }
    )


@me_bp.route("/profile", methods=["GET"])
@me_bp.route("", methods=["GET"])
@token_required
def get_my_profile():
    """
    Get profile information of currently authenticated user and linked member details.
    ---
    tags:
      - Personal Dashboard
    security:
      - BearerAuth: []
    """
    user = g.current_user
    profile_data = user.to_dict()
    if user.linked_member:
        profile_data["member"] = user.linked_member.to_dict(include_sensitive=False)
    return success_response(data=profile_data)
