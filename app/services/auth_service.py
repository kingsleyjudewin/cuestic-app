from datetime import timedelta
from flask import current_app
from app.extensions import db
from app.models.user import User, ApiToken
from app.utils.datetime_utils import utc_now, format_iso_utc
from app.utils.errors import AuthenticationError
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    def login(username: str, password: str, device_name: str = "Mobile Client") -> dict:
        """Authenticate user credentials and generate revocable API token."""
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user or not user.check_password(password):
            raise AuthenticationError("Invalid username or password.")

        if not user.is_active:
            raise AuthenticationError("Account is inactive. Please contact your club administrator.")

        # Update last login
        user.last_login_at = utc_now()

        # Generate token with expiry
        expiry_days = current_app.config.get("TOKEN_EXPIRY_DAYS", 30)
        expires_at = utc_now() + timedelta(days=expiry_days)
        token_obj, raw_token = ApiToken.create_token(
            user_id=user.id,
            expires_at=expires_at,
            name=device_name,
        )

        db.session.add(token_obj)
        AuditService.log_action(
            action="USER_LOGIN",
            entity_type="User",
            entity_id=user.id,
            actor_user_id=user.id,
            details={"device": device_name}
        )
        db.session.commit()

        return {
            "token": raw_token,
            "token_type": "Bearer",
            "expires_at": format_iso_utc(expires_at),
            "user": user.to_dict(),
        }

    @staticmethod
    def logout(token_obj: ApiToken):
        """Revoke the current authentication token."""
        if token_obj:
            token_obj.is_revoked = True
            AuditService.log_action(
                action="USER_LOGOUT",
                entity_type="ApiToken",
                entity_id=token_obj.id,
                actor_user_id=token_obj.user_id,
            )
            db.session.commit()
