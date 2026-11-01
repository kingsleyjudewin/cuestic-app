from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.member import Member
from app.models.team import Team
from app.models.user import User, ApiToken
from app.utils.phone_numbers import normalize_phone_number
from app.utils.errors import ValidationError, NotFoundError, ConflictError, PermissionDeniedError
from app.utils.permissions import invalidate_token_cache
from app.services.audit_service import AuditService


class MemberService:
    @staticmethod
    def get_member_by_id(member_id: int) -> Member:
        """Fetch member by ID or raise NotFoundError."""
        member = db.session.get(Member, member_id)
        if not member:
            raise NotFoundError(f"Member with ID {member_id} was not found.")
        return member

    @staticmethod
    def list_members(team_id: int = None, search: str = None, class_name: str = None,
                     is_active: bool = None, page: int = 1, per_page: int = 50) -> tuple[list[Member], dict]:
        """List and filter members with pagination."""
        query = Member.query.options(
            joinedload(Member.team),
            joinedload(Member.linked_user),
        )

        if team_id is not None:
            query = query.filter(Member.team_id == team_id)

        if is_active is not None:
            query = query.filter(Member.is_active == is_active)

        if class_name:
            query = query.filter(Member.class_name.ilike(f"%{class_name.strip()}%"))

        if search:
            s_val = search.strip()
            patterns = [f"%{s_val}%"]
            # Support common vowel variations (e.g. Niven vs Nivin)
            alt = s_val.replace('e', 'i') if 'e' in s_val.lower() else s_val.replace('i', 'e')
            if alt.lower() != s_val.lower():
                patterns.append(f"%{alt}%")

            filter_clauses = []
            for pat in patterns:
                filter_clauses.extend([
                    Member.full_name.ilike(pat),
                    Member.registration_number.ilike(pat),
                    Member.phone_number.ilike(pat),
                ])
            query = query.filter(or_(*filter_clauses))

        query = query.order_by(Member.full_name.asc())

        # Performance optimization for page 1: avoid extra COUNT(*) query across WAN
        if page == 1:
            all_items = query.all()
            total = len(all_items)
            items = all_items[:per_page]
            pages = max(1, (total + per_page - 1) // per_page)
            meta = {
                "page": 1,
                "per_page": per_page,
                "total": total,
                "pages": pages,
                "has_next": total > per_page,
                "has_prev": False,
            }
            return items, meta

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        meta = {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        }
        return paginated.items, meta

    @staticmethod
    def create_member(data: dict, actor_user_id: int = None) -> Member:
        """Create a new member with validation and duplicate prevention."""
        team = db.session.get(Team, data["team_id"])
        if not team or not team.is_active:
            raise ValidationError(
                f"Team with ID {data['team_id']} does not exist or is inactive.",
                details={"team_id": data["team_id"]}
            )

        # Phone number normalization
        phone_info = normalize_phone_number(data["phone_number"], data.get("country_code", "IN"))
        e164_phone = phone_info["e164"]

        # Prevent duplicate registration number
        reg_no = data.get("registration_number")
        if reg_no:
            reg_no = reg_no.strip()
            existing_reg = Member.query.filter(
                Member.registration_number.ilike(reg_no)
            ).first()
            if existing_reg:
                raise ConflictError(
                    f"A member with registration number '{reg_no}' already exists.",
                    details={"registration_number": reg_no}
                )

        # Prevent duplicate active member with same phone number
        existing_phone = Member.query.filter_by(phone_number=e164_phone, is_active=True).first()
        if existing_phone:
            raise ConflictError(
                f"An active member with phone number '{e164_phone}' already exists ({existing_phone.full_name}).",
                details={"phone_number": e164_phone}
            )

        member = Member(
            full_name=data["full_name"].strip(),
            email=data.get("email").strip() if data.get("email") else None,
            registration_number=reg_no if reg_no else None,
            class_name=data.get("class_name", "").strip() or None if data.get("class_name") else None,
            section=data.get("section", "").strip() or None if data.get("section") else None,
            phone_number=e164_phone,
            country_code=phone_info["country_code"],
            team_id=team.id,
            linked_user_id=data.get("linked_user_id"),
            whatsapp_opt_in=data.get("whatsapp_opt_in", True),
            is_active=True,
        )

        db.session.add(member)
        db.session.flush()

        AuditService.log_action(
            action="MEMBER_CREATED",
            entity_type="Member",
            entity_id=member.id,
            actor_user_id=actor_user_id,
            details={"full_name": member.full_name, "team_id": member.team_id}
        )
        db.session.commit()
        return member

    @staticmethod
    def create_member_account(data: dict, actor_user_id: int = None, commit: bool = True) -> tuple[Member, User]:
        """
        Atomically create a login User account and linked Member profile for any team.
        Authorized for President and Admin accounts.
        """
        team_id = data.get("team_id")
        team = db.session.get(Team, team_id)
        if not team or not team.is_active:
            raise ValidationError(
                f"Team with ID {team_id} does not exist or is inactive.",
                details={"team_id": team_id}
            )

        # Validate username uniqueness
        username = data.get("username", "").strip()
        if not username:
            raise ValidationError("Username is required.", details={"username": ["Field is required."]})
        existing_user = User.query.filter(User.username.ilike(username)).first()
        if existing_user:
            raise ConflictError(
                f"Username '{username}' is already taken.",
                details={"username": f"Username '{username}' is already in use."}
            )

        # Validate email uniqueness if provided
        email = data.get("email")
        if email:
            email = email.strip()
            existing_email = User.query.filter(User.email.ilike(email)).first()
            if existing_email:
                raise ConflictError(
                    f"Email address '{email}' is already registered.",
                    details={"email": f"Email '{email}' is already in use."}
                )
        else:
            email = None

        # Phone number normalization
        phone_info = normalize_phone_number(data["phone_number"], data.get("country_code", "IN"))
        e164_phone = phone_info["e164"]

        # Prevent duplicate registration number if provided
        reg_no = data.get("registration_number")
        if reg_no:
            reg_no = reg_no.strip()
            existing_reg = Member.query.filter(Member.registration_number.ilike(reg_no)).first()
            if existing_reg:
                raise ConflictError(
                    f"A member with registration number '{reg_no}' already exists.",
                    details={"registration_number": f"Registration number '{reg_no}' already exists."}
                )
        else:
            reg_no = None

        # Prevent duplicate active member with same phone number
        existing_phone = Member.query.filter_by(phone_number=e164_phone, is_active=True).first()
        if existing_phone:
            raise ConflictError(
                f"An active member with phone number '{e164_phone}' already exists ({existing_phone.full_name}).",
                details={"phone_number": f"Phone number '{e164_phone}' is already registered."}
            )

        # Validate role (only member or team_leader allowed to prevent privilege escalation)
        requested_role = data.get("role", User.ROLE_MEMBER).strip().lower()
        if requested_role not in (User.ROLE_MEMBER, User.ROLE_TEAM_LEADER):
            raise ValidationError(
                f"Invalid role '{requested_role}'. Only 'member' or 'team_leader' can be created.",
                details={"role": ["Role must be 'member' or 'team_leader'."]}
            )

        # 1. Create User account with securely hashed password (never plaintext)
        user = User(
            username=username,
            email=email,
            role=requested_role,
            is_active=True,
        )
        user.set_password(data["password"])
        db.session.add(user)
        db.session.flush()

        # 2. Create Member linked to the new user account
        member = Member(
            full_name=data["full_name"].strip(),
            email=email,
            registration_number=reg_no,
            class_name=data.get("class_name", "").strip() or None if data.get("class_name") else None,
            section=data.get("section", "").strip() or None if data.get("section") else None,
            phone_number=e164_phone,
            country_code=phone_info["country_code"],
            team_id=team.id,
            linked_user_id=user.id,
            whatsapp_opt_in=data.get("whatsapp_opt_in", True),
            is_active=True,
        )
        db.session.add(member)

        # If team_leader assigned and team currently has no leader, link them
        if requested_role == User.ROLE_TEAM_LEADER and not team.leader_user_id:
            team.leader_user_id = user.id

        db.session.flush()

        # Audit log (never log password or tokens)
        AuditService.log_action(
            action="MEMBER_ACCOUNT_CREATED",
            entity_type="User",
            entity_id=user.id,
            actor_user_id=actor_user_id,
            details={
                "username": user.username,
                "role": user.role,
                "team_id": team.id,
                "team_name": team.name,
                "member_id": member.id,
                "full_name": member.full_name,
            }
        )
        if commit:
            db.session.commit()
        return member, user

    @staticmethod
    def bulk_create_member_accounts(
        records: list[dict],
        actor_user_id: int = None,
        atomic: bool = True,
        skip_duplicates: bool = True,
    ) -> dict:
        """
        Bulk create member accounts within a transactional context.
        Enforces President/Admin authorization, validates each record, prevents
        duplicates, and rolls back on unexpected database failure.
        Never returns passwords or password hashes.
        """
        # Authorization check
        if actor_user_id is not None:
            actor = db.session.get(User, actor_user_id)
            if not actor or not actor.is_admin():
                raise PermissionDeniedError(
                    "Bulk account creation requires President or Administrator authorization.",
                    details={"actor_user_id": actor_user_id}
                )

        created = []
        skipped = []
        failed = []
        valid_records = []

        seen_usernames = set()
        seen_emails = set()
        seen_phones = set()
        seen_regs = set()

        # Step 1: Pre-validation & duplicate detection across batch and database
        for idx, rec in enumerate(records, start=1):
            name = (rec.get("full_name") or "").strip()
            username = (rec.get("username") or "").strip()
            email = (rec.get("email") or "").strip() or None
            raw_phone = rec.get("phone_number")
            reg_no = (rec.get("registration_number") or "").strip() or None
            team_id = rec.get("team_id")
            role = (rec.get("role") or User.ROLE_MEMBER).strip().lower()

            if not name:
                failed.append({"index": idx, "name": name, "error": "full_name is required."})
                continue

            if not raw_phone:
                failed.append({"index": idx, "name": name, "error": "phone_number is required."})
                continue

            try:
                phone_info = normalize_phone_number(raw_phone, rec.get("country_code", "IN"))
                e164_phone = phone_info["e164"]
            except ValidationError as ve:
                failed.append({"index": idx, "name": name, "error": f"Invalid phone number: {str(ve)}"})
                continue

            if not username:
                failed.append({"index": idx, "name": name, "error": "username is required."})
                continue

            if not rec.get("password") or len(rec.get("password")) < 1:
                failed.append({"index": idx, "name": name, "error": "password must be at least 1 character."})
                continue

            if role not in (User.ROLE_MEMBER, User.ROLE_TEAM_LEADER):
                failed.append({"index": idx, "name": name, "error": f"Invalid role '{role}'. Volunteers must have 'member' role."})
                continue

            # Verify team
            team = db.session.get(Team, team_id) if team_id else None
            if not team or not team.is_active:
                failed.append({"index": idx, "name": name, "error": f"Team ID {team_id} is invalid or inactive."})
                continue

            # Check intra-batch duplicates
            u_lower = username.lower()
            if u_lower in seen_usernames:
                failed.append({"index": idx, "name": name, "error": f"Duplicate username '{username}' within import batch."})
                continue
            seen_usernames.add(u_lower)

            if email:
                e_lower = email.lower()
                if e_lower in seen_emails:
                    failed.append({"index": idx, "name": name, "error": f"Duplicate email '{email}' within import batch."})
                    continue
                seen_emails.add(e_lower)

            if e164_phone in seen_phones:
                failed.append({"index": idx, "name": name, "error": f"Duplicate phone '{e164_phone}' within import batch."})
                continue
            seen_phones.add(e164_phone)

            if reg_no:
                r_lower = reg_no.lower()
                if r_lower in seen_regs:
                    failed.append({"index": idx, "name": name, "error": f"Duplicate registration number '{reg_no}' within import batch."})
                    continue
                seen_regs.add(r_lower)

            # Check database duplicates
            dup_user = User.query.filter(User.username.ilike(username)).first()
            if dup_user:
                if skip_duplicates:
                    skipped.append({"index": idx, "name": name, "username": username, "reason": f"Username '{username}' already exists in database (User ID: {dup_user.id})."})
                    continue
                else:
                    failed.append({"index": idx, "name": name, "error": f"Username '{username}' already exists in database."})
                    continue

            if email:
                dup_email = User.query.filter(User.email.ilike(email)).first()
                if dup_email:
                    if skip_duplicates:
                        skipped.append({"index": idx, "name": name, "email": email, "reason": f"Email '{email}' already registered in database (User ID: {dup_email.id})."})
                        continue
                    else:
                        failed.append({"index": idx, "name": name, "error": f"Email '{email}' already registered."})
                        continue

            dup_phone = Member.query.filter_by(phone_number=e164_phone, is_active=True).first()
            if dup_phone:
                if skip_duplicates:
                    skipped.append({"index": idx, "name": name, "phone": e164_phone, "reason": f"Active member with phone '{e164_phone}' already exists ({dup_phone.full_name}, Member ID: {dup_phone.id})."})
                    continue
                else:
                    failed.append({"index": idx, "name": name, "error": f"Phone number '{e164_phone}' already exists."})
                    continue

            if reg_no:
                dup_reg = Member.query.filter(Member.registration_number.ilike(reg_no)).first()
                if dup_reg:
                    if skip_duplicates:
                        skipped.append({"index": idx, "name": name, "registration_number": reg_no, "reason": f"Registration number '{reg_no}' already exists in database."})
                        continue
                    else:
                        failed.append({"index": idx, "name": name, "error": f"Registration number '{reg_no}' already exists."})
                        continue

            valid_records.append(rec)

        # If atomic mode and any record has failed validation, abort completely before writing
        if atomic and failed:
            return {
                "success": False,
                "created": [],
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
            }

        # Step 2: Create records
        try:
            for rec in valid_records:
                member, user = MemberService.create_member_account(
                    data=rec,
                    actor_user_id=actor_user_id,
                    commit=False,
                )
                created.append({
                    "member_id": member.id,
                    "user_id": user.id,
                    "full_name": member.full_name,
                    "username": user.username,
                    "email": user.email,
                    "phone_number": member.phone_number,
                    "role": user.role,
                    "team_id": member.team_id,
                    "team_name": member.team.name if member.team else None,
                })
            db.session.commit()
            return {
                "success": len(failed) == 0,
                "created": created,
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
            }
        except Exception as e:
            db.session.rollback()
            failed.append({"error": f"Database transaction rollback: {str(e)}"})
            return {
                "success": False,
                "created": [],
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
            }

    @staticmethod
    def bulk_create_members(
        records: list[dict],
        team_id: int,
        actor_user_id: int = None,
        atomic: bool = True,
        skip_duplicates: bool = True,
    ) -> dict:
        """
        Bulk register pure member records under a specified team without user accounts.
        Validates data, normalizes phone numbers (+91), checks for duplicates, and commits transactionally.
        """
        team = db.session.get(Team, team_id)
        if not team or not team.is_active:
            raise ValidationError(
                f"Team with ID {team_id} does not exist or is inactive.",
                details={"team_id": team_id}
            )

        created = []
        skipped = []
        failed = []
        valid_records = []

        seen_phones = set()
        seen_regs = set()

        for idx, rec in enumerate(records, start=1):
            name = (rec.get("full_name") or rec.get("name") or "").strip()
            raw_phone = rec.get("phone_number") or rec.get("phone") or ""
            class_name = (rec.get("class_name") or rec.get("class_section") or rec.get("class") or "").strip()
            section = (rec.get("section") or "").strip() or None
            reg_no = (rec.get("registration_number") or rec.get("reg_no") or "").strip() or None

            if not name:
                failed.append({"index": idx, "name": name, "error": "full_name is required."})
                continue

            if not raw_phone:
                failed.append({"index": idx, "name": name, "error": "phone_number is required."})
                continue

            if not class_name:
                failed.append({"index": idx, "name": name, "error": "class_name is required."})
                continue

            try:
                phone_info = normalize_phone_number(raw_phone, rec.get("country_code", "IN"))
                e164_phone = phone_info["e164"]
                country_code = phone_info["country_code"]
            except ValidationError as ve:
                failed.append({"index": idx, "name": name, "error": f"Invalid phone number: {str(ve)}"})
                continue

            # Batch intra-duplicate checks
            if e164_phone in seen_phones:
                failed.append({"index": idx, "name": name, "error": f"Duplicate phone number '{e164_phone}' within this batch."})
                continue
            seen_phones.add(e164_phone)

            if reg_no:
                if reg_no.lower() in seen_regs:
                    failed.append({"index": idx, "name": name, "error": f"Duplicate registration number '{reg_no}' within this batch."})
                    continue
                seen_regs.add(reg_no.lower())

            # Database duplicate checks
            # 1. Existing active member with same phone number
            dup_phone = Member.query.filter_by(phone_number=e164_phone, is_active=True).first()
            if dup_phone:
                if skip_duplicates:
                    skipped.append({
                        "index": idx,
                        "name": name,
                        "phone": e164_phone,
                        "reason": f"Active member with phone '{e164_phone}' already exists ({dup_phone.full_name}, Member ID: {dup_phone.id}, Team: {dup_phone.team.name if dup_phone.team else dup_phone.team_id})."
                    })
                    continue
                else:
                    failed.append({"index": idx, "name": name, "error": f"Phone number '{e164_phone}' already registered to {dup_phone.full_name}."})
                    continue

            # 2. Existing active member with same name in this team
            dup_name = Member.query.filter(
                Member.team_id == team.id,
                Member.full_name.ilike(name),
                Member.is_active == True
            ).first()
            if dup_name:
                if skip_duplicates:
                    skipped.append({
                        "index": idx,
                        "name": name,
                        "phone": e164_phone,
                        "reason": f"Member named '{name}' already exists in {team.name} (Member ID: {dup_name.id})."
                    })
                    continue
                else:
                    failed.append({"index": idx, "name": name, "error": f"Member named '{name}' already exists in {team.name}."})
                    continue

            # 3. Existing registration number
            if reg_no:
                dup_reg = Member.query.filter(Member.registration_number.ilike(reg_no)).first()
                if dup_reg:
                    if skip_duplicates:
                        skipped.append({
                            "index": idx,
                            "name": name,
                            "registration_number": reg_no,
                            "reason": f"Registration number '{reg_no}' already exists in database."
                        })
                        continue
                    else:
                        failed.append({"index": idx, "name": name, "error": f"Registration number '{reg_no}' already exists."})
                        continue

            valid_records.append({
                "full_name": name,
                "phone_number": e164_phone,
                "country_code": country_code,
                "class_name": class_name,
                "section": section,
                "registration_number": reg_no,
                "whatsapp_opt_in": rec.get("whatsapp_opt_in", True),
            })

        if atomic and failed:
            return {
                "success": False,
                "created": [],
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
                "team_id": team.id,
                "team_name": team.name,
            }

        try:
            for item in valid_records:
                member = Member(
                    full_name=item["full_name"],
                    phone_number=item["phone_number"],
                    country_code=item["country_code"],
                    class_name=item["class_name"],
                    section=item["section"],
                    registration_number=item["registration_number"],
                    team_id=team.id,
                    linked_user_id=None,
                    whatsapp_opt_in=item["whatsapp_opt_in"],
                    is_active=True,
                )
                db.session.add(member)
                db.session.flush()

                AuditService.log_action(
                    action="MEMBER_CREATED",
                    entity_type="Member",
                    entity_id=member.id,
                    actor_user_id=actor_user_id,
                    details={
                        "full_name": member.full_name,
                        "team_id": member.team_id,
                        "team_name": team.name,
                        "phone_number": member.phone_number,
                    }
                )

                created.append({
                    "id": member.id,
                    "full_name": member.full_name,
                    "phone_number": member.phone_number,
                    "class_name": member.class_name,
                    "section": member.section,
                    "team_id": member.team_id,
                    "team_name": team.name,
                })

            db.session.commit()
            return {
                "success": len(failed) == 0,
                "created": created,
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
                "team_id": team.id,
                "team_name": team.name,
            }
        except Exception as e:
            db.session.rollback()
            failed.append({"error": f"Database transaction rollback: {str(e)}"})
            return {
                "success": False,
                "created": [],
                "skipped": skipped,
                "failed": failed,
                "total_input": len(records),
                "team_id": team.id,
                "team_name": team.name,
            }

    @staticmethod
    def reset_member_password(member: Member, new_password: str, actor_user_id: int = None) -> User:
        """
        Securely reset password for a member's linked login user account.
        Revokes existing API tokens to enforce re-authentication.
        """
        if not member.linked_user:
            raise ValidationError("This member does not have a linked user account.")

        if not new_password or len(new_password) < 1:
            raise ValidationError("Password must be at least 1 character.", details={"new_password": ["Minimum length is 1."]})

        user = member.linked_user
        user.set_password(new_password)

        # Revoke all existing tokens for security
        ApiToken.query.filter_by(user_id=user.id).delete()
        invalidate_token_cache(user_id=user.id)

        AuditService.log_action(
            action="PASSWORD_RESET_BY_ADMIN",
            entity_type="User",
            entity_id=user.id,
            actor_user_id=actor_user_id,
            details={"username": user.username, "member_id": member.id}
        )
        db.session.commit()
        return user

    @staticmethod
    def update_member(member: Member, data: dict, actor_user_id: int = None) -> Member:
        """Update existing member."""
        if "team_id" in data and data["team_id"] != member.team_id:
            team = db.session.get(Team, data["team_id"])
            if not team or not team.is_active:
                raise ValidationError("Specified target team is invalid or inactive.")
            member.team_id = team.id

        if "registration_number" in data:
            new_reg = data["registration_number"]
            if new_reg:
                new_reg = new_reg.strip()
                existing = Member.query.filter(
                    Member.registration_number.ilike(new_reg),
                    Member.id != member.id
                ).first()
                if existing:
                    raise ConflictError(f"Registration number '{new_reg}' is already in use by another member.")
                member.registration_number = new_reg
            else:
                member.registration_number = None

        if "phone_number" in data:
            phone_info = normalize_phone_number(data["phone_number"], data.get("country_code", "IN"))
            e164_phone = phone_info["e164"]
            existing_phone = Member.query.filter(
                Member.phone_number == e164_phone,
                Member.id != member.id,
                Member.is_active == True
            ).first()
            if existing_phone:
                raise ConflictError(f"Phone number '{e164_phone}' is already in use by another active member.")
            member.phone_number = e164_phone
            member.country_code = phone_info["country_code"]

        if "full_name" in data:
            member.full_name = data["full_name"].strip()
        if "class_name" in data:
            member.class_name = data["class_name"].strip() if data.get("class_name") else None
        if "section" in data:
            member.section = data["section"].strip() if data["section"] else None
        if "whatsapp_opt_in" in data:
            member.whatsapp_opt_in = bool(data["whatsapp_opt_in"])
        if "is_active" in data:
            member.is_active = bool(data["is_active"])
            if member.linked_user:
                member.linked_user.is_active = bool(data["is_active"])
                if not member.is_active:
                    ApiToken.query.filter_by(user_id=member.linked_user.id).delete()
                    invalidate_token_cache(user_id=member.linked_user.id)
        if "linked_user_id" in data:
            member.linked_user_id = data["linked_user_id"]
        if "email" in data:
            new_email = data["email"].strip() if data["email"] else None
            if new_email:
                existing_email = User.query.filter(
                    User.email.ilike(new_email),
                    User.id != (member.linked_user.id if member.linked_user else -1)
                ).first()
                if existing_email:
                    raise ConflictError(f"Email '{new_email}' is already in use by another user account.")
                existing_mem = Member.query.filter(
                    Member.email.ilike(new_email),
                    Member.id != member.id
                ).first()
                if existing_mem:
                    raise ConflictError(f"Email '{new_email}' is already in use by another member.")
            member.email = new_email
            if member.linked_user:
                member.linked_user.email = new_email
        if "role" in data and member.linked_user:
            new_role = data["role"].strip().lower()
            if new_role in User.ALL_ROLES:
                old_role = member.linked_user.role
                member.linked_user.role = new_role
                if new_role == User.ROLE_TEAM_LEADER and not member.team.leader_user_id:
                    member.team.leader_user_id = member.linked_user.id
                elif old_role == User.ROLE_TEAM_LEADER and new_role != User.ROLE_TEAM_LEADER:
                    if member.team.leader_user_id == member.linked_user.id:
                        member.team.leader_user_id = None

        AuditService.log_action(
            action="MEMBER_UPDATED",
            entity_type="Member",
            entity_id=member.id,
            actor_user_id=actor_user_id,
            details={"changes": list(data.keys())}
        )
        db.session.commit()
        return member

    @staticmethod
    def deactivate_or_delete_member(member: Member, actor_user_id: int = None) -> bool:
        """
        Deactivate member if historical records exist to preserve task history.
        Hard delete only if no historical assignments exist.
        """
        if member.has_assignment_history():
            member.is_active = False
            if member.linked_user:
                member.linked_user.is_active = False
                ApiToken.query.filter_by(user_id=member.linked_user.id).delete()
                invalidate_token_cache(user_id=member.linked_user.id)
            AuditService.log_action(
                action="MEMBER_DEACTIVATED",
                entity_type="Member",
                entity_id=member.id,
                actor_user_id=actor_user_id,
                details={"reason": "Preserved assignment history upon deactivation"}
            )
            db.session.commit()
            return False  # Soft deactivated
        else:
            linked_user = member.linked_user
            db.session.delete(member)
            if linked_user:
                db.session.delete(linked_user)
            AuditService.log_action(
                action="MEMBER_DELETED",
                entity_type="Member",
                entity_id=member.id,
                actor_user_id=actor_user_id,
            )
            db.session.commit()
            return True  # Hard deleted
