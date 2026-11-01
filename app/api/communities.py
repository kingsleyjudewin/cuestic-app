from flask import Blueprint, request, jsonify, g
from app.extensions import limiter
from app.utils.permissions import token_required
from app.utils.errors import ValidationError
from app.schemas.community import CommunityCreateSchema, ChannelCreateSchema, MessageCreateSchema
from app.services import community_service

communities_bp = Blueprint("communities", __name__)
limiter.exempt(communities_bp)


@communities_bp.route("", methods=["GET"])
@token_required
def list_communities():
    """List Discord-like communities accessible to the current user."""
    communities = community_service.get_user_communities(g.current_user)
    return jsonify({
        "success": True,
        "data": communities,
        "count": len(communities)
    }), 200


@communities_bp.route("", methods=["POST"])
@token_required
def create_community():
    """Create a new community."""
    payload = request.get_json(silent=True) or {}
    schema = CommunityCreateSchema()
    errors = schema.validate(payload)
    if errors:
        raise ValidationError("Invalid community data.", payload=errors)

    comm = community_service.create_community(g.current_user, payload)
    return jsonify({
        "success": True,
        "data": comm,
        "message": f"Community '{comm['name']}' created successfully."
    }), 201


@communities_bp.route("/<int:community_id>", methods=["GET"])
@token_required
def get_community(community_id: int):
    """Retrieve details, channels, and members of a community."""
    comm = community_service.get_community(community_id, g.current_user)
    return jsonify({
        "success": True,
        "data": comm
    }), 200


@communities_bp.route("/<int:community_id>/channels", methods=["GET"])
@token_required
def list_channels(community_id: int):
    """List all channels in a community."""
    comm = community_service.get_community(community_id, g.current_user, include_details=True)
    return jsonify({
        "success": True,
        "data": comm.get("channels", [])
    }), 200


@communities_bp.route("/<int:community_id>/channels", methods=["POST"])
@token_required
def create_channel(community_id: int):
    """Create a new channel or group chat within a community."""
    payload = request.get_json(silent=True) or {}
    schema = ChannelCreateSchema()
    errors = schema.validate(payload)
    if errors:
        raise ValidationError("Invalid channel data.", payload=errors)

    channel = community_service.create_channel(community_id, g.current_user, payload)
    return jsonify({
        "success": True,
        "data": channel,
        "message": f"Channel '#{channel['name']}' created successfully."
    }), 201


@communities_bp.route("/<int:community_id>/channels/<int:channel_id>/messages", methods=["GET"])
@token_required
def get_channel_messages(community_id: int, channel_id: int):
    """Get message history for a community channel."""
    limit = request.args.get("limit", default=50, type=int)
    before_id = request.args.get("before_id", default=None, type=int)

    messages = community_service.get_channel_messages(
        community_id=community_id,
        channel_id=channel_id,
        user=g.current_user,
        limit=min(limit, 100),
        before_id=before_id
    )
    return jsonify({
        "success": True,
        "data": messages,
        "count": len(messages)
    }), 200


@communities_bp.route("/<int:community_id>/channels/<int:channel_id>/messages", methods=["POST"])
@token_required
def post_channel_message(community_id: int, channel_id: int):
    """Post a message to a community channel."""
    payload = request.get_json(silent=True) or {}
    schema = MessageCreateSchema()
    errors = schema.validate(payload)
    if errors:
        raise ValidationError("Invalid message content.", payload=errors)

    message = community_service.send_message(
        community_id=community_id,
        channel_id=channel_id,
        user=g.current_user,
        data=payload
    )
    return jsonify({
        "success": True,
        "data": message
    }), 201


@communities_bp.route("/<int:community_id>/members", methods=["GET"])
@token_required
def list_community_members(community_id: int):
    """List members of a community."""
    members = community_service.get_community_members(community_id, g.current_user)
    return jsonify({
        "success": True,
        "data": members,
        "count": len(members)
    }), 200


@communities_bp.route("/sync", methods=["POST"])
@token_required
def sync_communities():
    """Synchronize team communities and memberships (Admin/President only)."""
    if g.current_user.role not in ("president", "admin"):
        from app.utils.errors import PermissionDeniedError
        raise PermissionDeniedError("Only President or Admin can trigger community synchronization.")

    result = community_service.provision_default_communities()
    return jsonify({
        "success": True,
        "data": result,
        "message": "Team communities and memberships synchronized successfully."
    }), 200
