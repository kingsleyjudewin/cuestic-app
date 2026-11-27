from flask import Blueprint, request, g
from app.extensions import limiter
from app.schemas.auth import LoginSchema, ChangePasswordSchema
from app.services.auth_service import AuthService
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    """
    Authenticate user and issue revocable API token.
    ---
    tags:
      - Authentication
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - username
              - password
            properties:
              username:
                type: string
                example: admin
              password:
                type: string
                example: SecurePass123!
              device_name:
                type: string
                example: Admin iPhone 15
    responses:
      200:
        description: Authentication successful
      400:
        description: Validation error
      401:
        description: Invalid credentials
    """
    data = request.get_json(silent=True) or {}
    errors = LoginSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on login request.", details=errors)

    result = AuthService.login(
        username=data["username"].strip(),
        password=data["password"],
        device_name=data.get("device_name", "Mobile Client")
    )
    return success_response(data=result, message="Authentication successful.")


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    """
    Revoke current authentication token.
    ---
    tags:
      - Authentication
    security:
      - BearerAuth: []
    responses:
      200:
        description: Successfully logged out
      401:
        description: Unauthorized
    """
    AuthService.logout(g.current_token)
    return success_response(message="Successfully logged out.")


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    """
    Get profile information of currently authenticated user.
    ---
    tags:
      - Authentication
    security:
      - BearerAuth: []
    responses:
      200:
        description: Current user profile
      401:
        description: Unauthorized
    """
    return success_response(data=g.current_user.to_dict())


@auth_bp.route("/change-password", methods=["POST"])
@limiter.limit("10 per minute;30 per hour")
@token_required
def change_password():
    """
    Change the password of the signed-in user (also completes a mandatory password change).
    ---
    tags:
      - Authentication
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [current_password, new_password, confirm_password]
            properties:
              current_password: {type: string}
              new_password: {type: string, description: "12+ chars, upper, lower, number, special"}
              confirm_password: {type: string}
    responses:
      200:
        description: Password changed. Every previous session is revoked; use the returned token.
      400:
        description: INVALID_CURRENT_PASSWORD, PASSWORD_MISMATCH, WEAK_PASSWORD or VALIDATION_ERROR
      401:
        description: Session expired or revoked
    """
    data = request.get_json(silent=True) or {}
    errors = ChangePasswordSchema().validate(data)
    if errors:
        raise ValidationError("Validation error on password change.", details=errors)

    result = AuthService.change_password(
        user=g.current_user,
        current_password=data["current_password"],
        new_password=data["new_password"],
        confirm_password=data.get("confirm_password"),
        device_name=data.get("device_name") or (g.current_token.name if g.current_token else None),
    )
    result["password_change_required"] = False
    return success_response(
        data=result,
        message="Password changed successfully. All other sessions have been signed out.",
    )


@auth_bp.route("/password-policy", methods=["GET"])
def password_policy():
    """Password rules enforced by the server (for display in clients)."""
    from app.utils.password_policy import MIN_LENGTH, REQUIREMENTS
    return success_response(data={"min_length": MIN_LENGTH, "requirements": REQUIREMENTS})


@auth_bp.route("/verify-setup-token", methods=["GET"])
def verify_setup_token():
    """Verify single-use password setup token without consuming it."""
    token = request.args.get("token")
    if not token:
        raise ValidationError("Query parameter 'token' is required.")
    info = AuthService.verify_setup_token(token)
    return success_response(data=info, message="Token is valid.")


@auth_bp.route("/setup-password", methods=["POST"])
def setup_password():
    """Establish user password using single-use setup token and log user in immediately."""
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    new_password = data.get("new_password")
    device_name = data.get("device_name", "Mobile Client")

    if not token:
        raise ValidationError("Field 'token' is required.", details={"token": ["Required."]})
    if not new_password:
        raise ValidationError("Field 'new_password' is required.", details={"new_password": ["Required."]})

    result = AuthService.setup_initial_password(
        raw_token=token,
        new_password=new_password,
        device_name=device_name,
    )
    return success_response(data=result, message=result["message"])
