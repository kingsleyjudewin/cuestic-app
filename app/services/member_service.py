from sqlalchemy import or_
from app.extensions import db
from app.models.member import Member
from app.models.team import Team
from app.utils.phone_numbers import normalize_phone_number
from app.utils.errors import ValidationError, NotFoundError, ConflictError
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
        query = Member.query

        if team_id is not None:
            query = query.filter(Member.team_id == team_id)

        if is_active is not None:
            query = query.filter(Member.is_active == is_active)

        if class_name:
            query = query.filter(Member.class_name.ilike(f"%{class_name.strip()}%"))

        if search:
            s = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Member.full_name.ilike(s),
                    Member.registration_number.ilike(s),
                    Member.phone_number.ilike(s),
                )
            )

        query = query.order_by(Member.full_name.asc())
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
            registration_number=reg_no if reg_no else None,
            class_name=data["class_name"].strip(),
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
            member.class_name = data["class_name"].strip()
        if "section" in data:
            member.section = data["section"].strip() if data["section"] else None
        if "whatsapp_opt_in" in data:
            member.whatsapp_opt_in = bool(data["whatsapp_opt_in"])
        if "is_active" in data:
            member.is_active = bool(data["is_active"])
        if "linked_user_id" in data:
            member.linked_user_id = data["linked_user_id"]

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
            db.session.delete(member)
            AuditService.log_action(
                action="MEMBER_DELETED",
                entity_type="Member",
                entity_id=member.id,
                actor_user_id=actor_user_id,
            )
            db.session.commit()
            return True  # Hard deleted
