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
            "password_change_required": user.requires_password_change,
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
    def _issue_token(user: User, device_name: str):
        expiry_days = current_app.config.get("TOKEN_EXPIRY_DAYS", 30)
        expires_at = utc_now() + timedelta(days=expiry_days)
        token_obj, raw_token = ApiToken.create_token(user_id=user.id, expires_at=expires_at, name=device_name)
        db.session.add(token_obj)
        return token_obj, raw_token, expires_at

    @staticmethod
    def change_password(
        user: User,
        current_password: str,
        new_password: str,
        confirm_password: str = None,
        keep_token_id: int = None,
        device_name: str = None,
    ) -> dict:
        """
        Change the password of an authenticated user in one transaction.

        * Locks the user row (SELECT ... FOR UPDATE on PostgreSQL) so concurrent requests are
          serialised: the second one re-checks the current password against the new hash and fails.
        * Enforces app/utils/password_policy.py and rejects reuse of the current password.
        * Clears password_change_required / legacy "pending" flags.
        * Revokes every session of the user. keep_token_id keeps exactly one session (the caller's)
          for the legacy /research/auth/* endpoints whose existing clients keep their token.
          Otherwise a fresh session token is issued and returned.

        Passwords are never logged or echoed back.
        """
        from app.utils.password_policy import password_problems
        from app.utils.permissions import invalidate_token_cache, cache_token

        if confirm_password is not None and confirm_password != new_password:
            raise ValidationError(
                "New password and confirmation do not match.",
                code="PASSWORD_MISMATCH",
                details={"confirm_password": ["Does not match the new password."]},
            )

        locked = (
            db.session.query(User).filter(User.id == user.id).with_for_update().populate_existing().one_or_none()
        )
        if locked is None or not locked.is_active:
            db.session.rollback()
            raise AuthenticationError("User account is inactive or disabled.")

        if not locked.check_password(current_password or ""):
            db.session.rollback()
            raise ValidationError(
                "Current password is incorrect.",
                code="INVALID_CURRENT_PASSWORD",
                details={"current_password": ["Incorrect password."]},
            )

        problems = password_problems(new_password, username=locked.username)
        if locked.check_password(new_password):
            problems.insert(0, "New password must be different from your current password.")
        if problems:
            db.session.rollback()
            raise ValidationError(
                problems[0],
                code="WEAK_PASSWORD",
                details={"new_password": problems},
            )

        locked.set_password(new_password)
        locked.password_change_required = False
        locked.password_changed_at = utc_now()
        locked.credential_setup_status = "completed"
        if locked.faculty_profile:
            locked.faculty_profile.must_change_password = False
        if locked.research_student_profile:
            locked.research_student_profile.must_change_password = False

        revoke = ApiToken.query.filter(ApiToken.user_id == locked.id, ApiToken.is_revoked.is_(False))
        if keep_token_id is not None:
            revoke = revoke.filter(ApiToken.id != keep_token_id)
        revoke.update({"is_revoked": True}, synchronize_session=False)

        result = {"user": None, "token": None}
        new_token = None
        if keep_token_id is None:
            new_token, raw_token, expires_at = AuthService._issue_token(locked, device_name or "Mobile Client")
            result.update(token=raw_token, token_type="Bearer", expires_at=format_iso_utc(expires_at))

        AuditService.log_action(
            action="USER_PASSWORD_CHANGED",
            entity_type="User",
            entity_id=locked.id,
            actor_user_id=locked.id,
            details={"username": locked.username, "sessions_revoked": True},
        )
        db.session.commit()

        invalidate_token_cache(user_id=locked.id)
        if new_token is not None:
            cache_token(new_token.token_hash, new_token, locked)
        result["user"] = locked.to_dict()
        return result

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

        token_hash = PasswordSetupToken.hash_token(raw_token.strip())
        token_obj = PasswordSetupToken.query.filter_by(token_hash=token_hash).first()

        if not token_obj or not token_obj.is_valid():
            raise ValidationError("This setup token is invalid, already consumed, or has expired.")

        user = token_obj.user
        if not user or not user.is_active:
            raise ValidationError("Associated user account is deactivated.")

        from app.utils.password_policy import password_problems
        problems = password_problems(new_password, username=user.username)
        if problems:
            raise ValidationError(problems[0], code="WEAK_PASSWORD", details={"new_password": problems})

        # Hash and store password (chosen by the user, so no further change is required)
        user.set_password(new_password)
        user.credential_setup_status = "completed"
        user.password_change_required = False
        user.password_changed_at = utc_now()

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
        cache_token(api_token.token_hash, api_token, user)

        return {
            "token": raw_api_token,
            "token_type": "Bearer",
            "expires_at": format_iso_utc(expires_at),
            "user": user.to_dict(),
            "message": "Password successfully created. You are now logged in.",
        }
