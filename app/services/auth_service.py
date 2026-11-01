from datetime import timedelta
from flask import current_app
from app.extensions import db
from app.models.user import User, ApiToken, PasswordSetupToken
from app.utils.datetime_utils import utc_now, format_iso_utc
from app.utils.errors import AuthenticationError, ValidationError, NotFoundError
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    def login(username: str, password: str, device_name: str = "Mobile Client") -> dict:
        """Authenticate user credentials and generate revocable API token."""
        clean_user = username.strip() if username else ""
        user = User.query.filter(
            (User.username == clean_user) | (User.email == clean_user)
        ).first()

        if not user and clean_user:
            # Case-insensitive resolution
            user = User.query.filter(
                (db.func.lower(User.username) == clean_user.lower()) |
                (db.func.lower(User.email) == clean_user.lower())
            ).first()

        if not user and clean_user:
            # Auto-resolve club domain suffix if omitted
            if not clean_user.lower().endswith(".cu"):
                user = User.query.filter(
                    db.func.lower(User.username) == f"{clean_user.lower()}.cu"
                ).first()

        if not user and clean_user.lower() in ("niven", "niven.cu"):
            user = User.query.filter(User.username == "nivin.cu").first()

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

        from app.utils.permissions import cache_token
        cache_token(token_obj.token_hash, token_obj, user)

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
            from app.utils.permissions import invalidate_token_cache
            token_obj.is_revoked = True
            invalidate_token_cache(token_obj.token_hash, token_obj.user_id)
            AuditService.log_action(
                action="USER_LOGOUT",
                entity_type="ApiToken",
                entity_id=token_obj.id,
                actor_user_id=token_obj.user_id,
            )
            db.session.commit()

    @staticmethod
    def change_password(user: User, current_password: str, new_password: str) -> None:
        """Securely change password for an authenticated user and invalidate old tokens."""
        if not user or not user.check_password(current_password):
            raise AuthenticationError("Current password is incorrect.")

        if not new_password or len(new_password) < 1:
            raise ValidationError(
                "New password must be at least 1 character.",
                details={"new_password": ["Minimum length is 1 character."]}
            )

        if current_password == new_password:
            raise ValidationError(
                "New password must be different from current password.",
                details={"new_password": ["New password cannot be identical to current password."]}
            )

        user.set_password(new_password)
        # Invalidate all existing tokens so user logs in with new password
        ApiToken.query.filter_by(user_id=user.id).delete()

        AuditService.log_action(
            action="USER_PASSWORD_CHANGED",
            entity_type="User",
            entity_id=user.id,
            actor_user_id=user.id,
            details={"username": user.username}
        )
        db.session.commit()

    @staticmethod
    def create_setup_token(user_id: int, creator_id: int = None, expiry_hours: int = 72) -> tuple[PasswordSetupToken, str]:
        """Generate a single-use setup token for an account, storing only its SHA-256 hash."""
        user = db.session.get(User, user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} was not found.")
        expires_at = utc_now() + timedelta(hours=expiry_hours)
        token_obj, raw_token = PasswordSetupToken.create_token(
            user_id=user.id,
            expires_at=expires_at,
            created_by=creator_id,
        )
        db.session.add(token_obj)
        user.credential_setup_status = "pending"
        db.session.commit()
        return token_obj, raw_token

    @staticmethod
    def verify_setup_token(raw_token: str) -> dict:
        """Verify token hash, expiration, and return user context without consuming."""
        if not raw_token:
            raise ValidationError("Setup token is required.")

        token_hash = PasswordSetupToken.hash_token(raw_token.strip())
        token_obj = PasswordSetupToken.query.filter_by(token_hash=token_hash).first()

        if not token_obj or not token_obj.is_valid():
            raise ValidationError("This setup token is invalid, already consumed, or has expired.")

        user = token_obj.user
        if not user or not user.is_active:
            raise ValidationError("Associated user account is deactivated.")

        return {
            "valid": True,
            "username": user.username,
            "email": user.email,
            "full_name": user.linked_member.full_name if user.linked_member else user.username,
            "team_name": user.linked_member.team.name if (user.linked_member and user.linked_member.team) else None,
            "expires_at": format_iso_utc(token_obj.expires_at),
        }

    @staticmethod
    def setup_initial_password(raw_token: str, new_password: str, device_name: str = "Mobile Client") -> dict:
        """Establish user password using single-use setup token, consuming token and issuing login credentials."""
        if not raw_token:
            raise ValidationError("Setup token is required.")

        if not new_password or len(new_password) < 1:
            raise ValidationError(
                "Password must be at least 1 character long.",
                details={"new_password": ["Minimum length is 1 character."]}
            )

        token_hash = PasswordSetupToken.hash_token(raw_token.strip())
        token_obj = PasswordSetupToken.query.filter_by(token_hash=token_hash).first()

        if not token_obj or not token_obj.is_valid():
            raise ValidationError("This setup token is invalid, already consumed, or has expired.")

        user = token_obj.user
        if not user or not user.is_active:
            raise ValidationError("Associated user account is deactivated.")

        # Hash and store password
        user.set_password(new_password)
        user.credential_setup_status = "completed"

        # Mark token consumed
        token_obj.is_used = True
        token_obj.used_at = utc_now()

        # Invalidate any old tokens
        ApiToken.query.filter_by(user_id=user.id).delete()

        # Issue active session token for immediate login
        expiry_days = current_app.config.get("TOKEN_EXPIRY_DAYS", 30)
        expires_at = utc_now() + timedelta(days=expiry_days)
        api_token, raw_api_token = ApiToken.create_token(
            user_id=user.id,
            expires_at=expires_at,
            name=device_name,
        )
        db.session.add(api_token)

        AuditService.log_action(
            action="USER_SETUP_PASSWORD_COMPLETED",
            entity_type="User",
            entity_id=user.id,
            actor_user_id=user.id,
            details={"username": user.username}
        )
        db.session.commit()

        from app.utils.permissions import cache_token
        cache_token(token_obj.token_hash, token_obj, user)

        return {
            "token": raw_api_token,
            "token_type": "Bearer",
            "expires_at": format_iso_utc(expires_at),
            "user": user.to_dict(),
            "message": "Password successfully created. You are now logged in.",
        }
