from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException
import marshmallow


class AppError(Exception):
    """Base application exception."""
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message, code=None, details=None, status_code=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if details:
            self.details = details
        else:
            self.details = {}
        if status_code:
            self.status_code = status_code

    def to_dict(self):
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_ERROR"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnprocessableError(AppError):
    status_code = 422
    code = "UNPROCESSABLE_ENTITY"


def validate_payload(schema_cls, payload: dict) -> dict:
    """Validate and deserialize request payload using Marshmallow schema."""
    try:
        return schema_cls().load(payload or {})
    except marshmallow.ValidationError as err:
        raise ValidationError("Validation error on request payload.", details=err.messages)


def success_response(data=None, message=None, meta=None, status_code=200):
    """Generate consistent JSON response for successful operations."""
    if status_code == 204:
        return "", 204
    
    body = {"success": True}
    if data is not None:
        body["data"] = data
    if message is not None:
        body["message"] = message
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status_code


def register_error_handlers(app):
    """Register application-wide error handlers."""
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_SERVER_ERROR",
        }
        return jsonify({
            "success": False,
            "error": {
                "code": code_map.get(error.code, "HTTP_ERROR"),
                "message": error.description,
                "details": {}
            }
        }), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        # In production, do not leak raw stack traces or internal details
        if app.config.get("DEBUG") or app.config.get("TESTING"):
            details = {"exception": str(error), "type": type(error).__name__}
        else:
            details = {}
        app.logger.exception("Unexpected error occurred: %s", error)
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "details": details
            }
        }), 500
