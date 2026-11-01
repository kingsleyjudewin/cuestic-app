from flask import Blueprint, request, g
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError
from app.services.notification_service import NotificationService
from app.models.device_token import DeviceToken

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/device-token", methods=["POST"])
@token_required
def register_device_token():
    """
    Register or update an FCM push notification device token for the current user.
    ---
    tags:
      - Notifications
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - token
            properties:
              token:
                type: string
                example: "fcm_token_abcdef123456"
              device_type:
                type: string
                example: "android"
              device_name:
                type: string
                example: "Pixel 8 Pro"
    responses:
      200:
        description: Device token registered successfully
      400:
        description: Validation error
      401:
        description: Unauthorized
    """
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token or not str(token).strip():
        raise ValidationError("Field 'token' is required.")

    device_type = data.get("device_type", "android").strip().lower()
    device_name = data.get("device_name")

    dev_token = NotificationService.register_device_token(
        user_id=g.current_user.id,
        token=str(token).strip(),
        device_type=device_type,
        device_name=device_name,
    )

    return success_response(
        data=dev_token.to_dict(),
        message="Device token registered successfully."
    )


@notifications_bp.route("/device-token", methods=["DELETE"])
@token_required
def unregister_device_token():
    """
    Deactivate an FCM push notification device token upon logout.
    ---
    tags:
      - Notifications
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - token
            properties:
              token:
                type: string
    responses:
      200:
        description: Device token unregistered successfully
      400:
        description: Validation error
    """
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    if not token or not str(token).strip():
        raise ValidationError("Field 'token' is required.")

    NotificationService.unregister_device_token(
        user_id=g.current_user.id,
        token=str(token).strip(),
    )
    return success_response(message="Device token unregistered successfully.")


@notifications_bp.route("/devices", methods=["GET"])
@token_required
def list_devices():
    """List registered notification devices for the authenticated user."""
    tokens = DeviceToken.query.filter_by(user_id=g.current_user.id, is_active=True).all()
    return success_response(data=[t.to_dict() for t in tokens])
