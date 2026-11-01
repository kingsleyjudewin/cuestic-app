import os
import re
import csv
import json
import secrets
from typing import Optional
from datetime import timedelta
from app.extensions import db
from app.models.user import User, PasswordSetupToken
from app.models.team import Team
from app.models.member import Member
from app.services.member_service import MemberService
from app.services.audit_service import AuditService
from app.utils.phone_numbers import normalize_phone_number
from app.utils.errors import ValidationError, PermissionDeniedError, NotFoundError
from app.utils.datetime_utils import utc_now, format_iso_utc


# The 5 Documentation team members to import
DEFAULT_DOCUMENTATION_RECORDS = [
    {
        "full_name": "John Victor",
        "phone": "+91 99863 83984",
        "class_section": None,
    },
    {
        "full_name": "Merrick",
        "phone": "+91 90224 69808",
        "class_section": None,
    },
    {
        "full_name": "Abishek Cu",
        "phone": "+91 733 879 6125",
        "class_section": None,
    },
    {
        "full_name": "Afra",
        "phone": "+91 98453 14703",
        "class_section": None,
    },
    {
        "full_name": "Prarthana Venkatesh",
        "phone": "+91 99646 97363",
        "class_section": None,
    },
]


def normalize_name_for_identifier(full_name: str) -> str:
    """
    Deterministic normalization:
    - Convert names to lowercase
    - Trim leading/trailing spaces
    - Replace spaces between name components with a period
    - Remove unsupported characters safely
    - Collapse multiple consecutive dots and strip leading/trailing dots
    """
    clean = full_name.lower().strip()
    clean = re.sub(r"\s+", ".", clean)
    clean = re.sub(r"[^a-z0-9.]", "", clean)
    clean = re.sub(r"\.+", ".", clean)
    return clean.strip(".")


def generate_proposed_email(normalized_name: str) -> str:
    """Generate proposed placeholder email address: <normalized_name>@gmail.com."""
    return f"{normalized_name}@gmail.com"


class DocumentationImportService:
    """Service to safely inspect, validate, and create accounts for Documentation team members."""

    @staticmethod
    def get_documentation_team() -> Team:
        """
        Find the existing Documentation team by its database ID or slug.
        Never creates a duplicate team.
        """
        team = Team.query.filter(
            (Team.slug == "documentation") | (Team.name.ilike("documentation"))
        ).first()

        if not team:
            raise NotFoundError(
                "Documentation team was not found in the database. Ensure database baseline is seeded."
            )
        if not team.is_active:
            raise ValidationError(
                f"Documentation team (ID: {team.id}) is currently marked inactive.",
                details={"team_id": team.id}
            )
        return team

    @staticmethod
    def verify_operator(operator_identifier: str = "clubadmin") -> User:
        """
        Verify that the authorizing operator exists, is active, and has President or Admin role.
        """
        if not operator_identifier:
            raise ValidationError("Authorizing operator identifier is required.")

        ident = str(operator_identifier).strip()
        operator = User.query.filter(
            (User.username == ident) | (User.email == ident)
        ).first()

        if not operator:
            raise NotFoundError(
                f"Authorizing operator '{ident}' was not found in the user database."
            )

        if not operator.is_active:
            raise PermissionDeniedError(
                f"Authorizing operator account '{ident}' is inactive or disabled."
            )

        if not operator.is_admin():
            raise PermissionDeniedError(
                f"Operator '{operator.username}' (role: {operator.role}) is not authorized to register team members. "
                "Only President or Administrator can authorize.",
                details={"operator": operator.username, "role": operator.role}
            )

        return operator

    @classmethod
    def load_records_from_file(cls, file_path: str) -> list[dict]:
        """Load documentation member records from an external JSON or CSV file."""
        if not os.path.exists(file_path):
            raise NotFoundError(f"Input file '{file_path}' does not exist.")

        records = []
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and "members" in data:
                    records = data["members"]
                else:
                    raise ValidationError("JSON file must contain an array of member records or a 'members' list.")
        elif file_path.endswith(".csv"):
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append({
                        "full_name": row.get("name") or row.get("full_name") or row.get("Name"),
                        "phone": row.get("phone") or row.get("Phone") or row.get("phone_number"),
                        "class_section": row.get("class_section") or row.get("class") or row.get("Class/section") or row.get("class_name"),
                        "registration_number": row.get("registration_number") or row.get("reg_no") or None,
                    })
        else:
            raise ValidationError("Unsupported file format. Please provide a .json or .csv file.")

        return records

    @classmethod
    def inspect_and_preview(
        cls,
        records: Optional[list[dict]] = None,
        operator_identifier: str = "clubadmin",
        file_path: Optional[str] = None,
    ) -> dict:
        """
        Inspect member records against database state without writing any records.
        Returns pre-validation diagnostics, collision detection, and duplicate checks.
        """
        team = cls.get_documentation_team()
        operator = cls.verify_operator(operator_identifier)

        if records is None:
            if file_path:
                records = cls.load_records_from_file(file_path)
            else:
                records = DEFAULT_DOCUMENTATION_RECORDS

        inspected = []
        ready_count = 0
        duplicate_count = 0
        invalid_count = 0

        seen_phones = set()
        seen_usernames = set()
        seen_emails = set()

        for idx, raw in enumerate(records, start=1):
            name = (raw.get("full_name") or raw.get("name") or "").strip()
            raw_phone = raw.get("phone") or raw.get("phone_number") or ""
            class_sec = (raw.get("class_section") or raw.get("class_name") or raw.get("class") or "").strip() or None
            reg_no = (raw.get("registration_number") or raw.get("reg_no") or "").strip() or None

            normalized_name = normalize_name_for_identifier(name) if name else ""
            proposed_email = generate_proposed_email(normalized_name) if normalized_name else ""

            issues = []
            status = "READY"
            normalized_phone = None

            # Validation
            if not name or len(name) < 2:
                issues.append("Name must be at least 2 characters.")
                status = "INVALID"

            if not normalized_name or len(normalized_name) < 3:
                issues.append(f"Generated username '{normalized_name}' is too short.")
                status = "INVALID"

            if not raw_phone:
                issues.append("Missing phone number.")
                status = "INVALID"
            else:
                try:
                    pinfo = normalize_phone_number(raw_phone, "IN")
                    normalized_phone = pinfo["e164"]
                except ValidationError as ve:
                    issues.append(f"Phone validation failed: {str(ve)}")
                    status = "INVALID"

            # Check intra-batch duplicate phone, username, email
            if normalized_phone:
                if normalized_phone in seen_phones:
                    issues.append(f"Duplicate phone '{normalized_phone}' within input list.")
                    status = "DUPLICATE_IN_BATCH"
                else:
                    seen_phones.add(normalized_phone)

            if normalized_name:
                if normalized_name in seen_usernames:
                    issues.append(f"Duplicate username '{normalized_name}' within input list.")
                    status = "DUPLICATE_IN_BATCH"
                else:
                    seen_usernames.add(normalized_name)

            if proposed_email:
                if proposed_email in seen_emails:
                    issues.append(f"Duplicate email '{proposed_email}' within input list.")
                    status = "DUPLICATE_IN_BATCH"
                else:
                    seen_emails.add(proposed_email)

            # Database duplicate checks
            if status == "READY":
                if normalized_phone:
                    dup_phone = Member.query.filter_by(phone_number=normalized_phone, is_active=True).first()
                    if dup_phone:
                        issues.append(
                            f"Phone '{normalized_phone}' already registered to member '{dup_phone.full_name}' "
                            f"(Member ID: {dup_phone.id}, Team: {dup_phone.team.name if dup_phone.team else dup_phone.team_id})."
                        )
                        status = "EXISTS_IN_DB"

                dup_user = User.query.filter(User.username.ilike(normalized_name)).first()
                if dup_user:
                    issues.append(f"Username '{normalized_name}' already exists in database (User ID: {dup_user.id}).")
                    status = "EXISTS_IN_DB"

                if proposed_email:
                    dup_email = User.query.filter(User.email.ilike(proposed_email)).first()
                    if dup_email:
                        issues.append(f"Email '{proposed_email}' already registered in database (User ID: {dup_email.id}).")
                        status = "EXISTS_IN_DB"

            if status == "READY":
                ready_count += 1
            elif status in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH"):
                duplicate_count += 1
            else:
                invalid_count += 1

            inspected.append({
                "index": idx,
                "full_name": name,
                "username": normalized_name,
                "proposed_email": proposed_email,
                "raw_phone": raw_phone,
                "normalized_phone": normalized_phone,
                "class_section": class_sec,
                "registration_number": reg_no,
                "team_id": team.id,
                "team_name": team.name,
                "role": User.ROLE_MEMBER,
                "account_status": "active",
                "credential_setup_status": "pending",
                "status": status,
                "issues": issues,
            })

        return {
            "operator": {
                "id": operator.id,
                "username": operator.username,
                "role": operator.role,
            },
            "team": {
                "id": team.id,
                "name": team.name,
                "slug": team.slug,
                "current_member_count": team.members.filter_by(is_active=True).count(),
            },
            "total_records": len(records),
            "ready_count": ready_count,
            "duplicate_count": duplicate_count,
            "invalid_count": invalid_count,
            "inspected_records": inspected,
            "raw_records": records,
        }

    @classmethod
    def execute_import(
        cls,
        records: Optional[list[dict]] = None,
        operator_identifier: str = "clubadmin",
        file_path: Optional[str] = None,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> dict:
        """
        Execute or dry-run registration of Documentation team members with single-use setup tokens.
        Never writes records unless confirm is True and dry_run is False.
        """
        preview = cls.inspect_and_preview(
            records=records,
            operator_identifier=operator_identifier,
            file_path=file_path,
        )

        if dry_run or not confirm:
            return {
                "dry_run": True,
                "confirmed": False,
                "preview": preview,
                "message": "DRY RUN complete. 0 records written to database. Review records and rerun with --confirm to execute.",
                "created": [],
                "skipped": [r for r in preview["inspected_records"] if r["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH")],
                "failed": [r for r in preview["inspected_records"] if r["status"] == "INVALID"],
            }

        team = cls.get_documentation_team()
        operator = cls.verify_operator(operator_identifier)

        created_accounts = []
        skipped_records = []
        failed_records = []

        expiry_hours = 72

        for inspected in preview["inspected_records"]:
            if inspected["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH"):
                skipped_records.append({
                    "name": inspected["full_name"],
                    "username": inspected["username"],
                    "phone": inspected["normalized_phone"] or inspected["raw_phone"],
                    "reason": "; ".join(inspected["issues"]),
                })
                continue

            if inspected["status"] == "INVALID":
                failed_records.append({
                    "name": inspected["full_name"],
                    "reason": "; ".join(inspected["issues"]),
                })
                continue

            # Generate high-entropy cryptographically random initial password (never predictable name@123)
            temp_secret_password = secrets.token_urlsafe(32)

            # Build account data
            account_data = {
                "full_name": inspected["full_name"],
                "phone_number": inspected["normalized_phone"],
                "class_name": inspected["class_section"],
                "country_code": "+91",
                "registration_number": inspected["registration_number"],
                "team_id": team.id,
                "username": inspected["username"],
                "email": inspected["proposed_email"],
                "password": temp_secret_password,
                "role": User.ROLE_MEMBER,
                "whatsapp_opt_in": True,
            }

            try:
                # Create user and member atomically
                member, user = MemberService.create_member_account(
                    data=account_data,
                    actor_user_id=operator.id,
                    commit=False,
                )
                user.credential_setup_status = "pending"

                # Generate single-use password setup token (store only SHA-256 hash in DB)
                token_obj, raw_setup_token = PasswordSetupToken.create_token(
                    user_id=user.id,
                    expires_at=utc_now() + timedelta(hours=expiry_hours),
                    created_by=operator.id,
                )
                db.session.add(token_obj)
                db.session.flush()

                created_accounts.append({
                    "member_id": member.id,
                    "user_id": user.id,
                    "full_name": member.full_name,
                    "username": user.username,
                    "proposed_email": user.email,
                    "phone_number": member.phone_number,
                    "class_name": member.class_name,
                    "role": user.role,
                    "team_id": member.team_id,
                    "team_name": team.name,
                    "account_status": "active",
                    "credential_setup_status": "pending",
                    "setup_token": raw_setup_token,
                    "setup_expires_at": format_iso_utc(token_obj.expires_at),
                    "created_at": format_iso_utc(member.created_at),
                })
            except Exception as e:
                db.session.rollback()
                failed_records.append({
                    "name": inspected["full_name"],
                    "error": str(e),
                })

        if created_accounts and not failed_records:
            db.session.commit()
            return {
                "dry_run": False,
                "confirmed": True,
                "success": True,
                "team_id": team.id,
                "team_name": team.name,
                "total_input": preview["total_records"],
                "created": created_accounts,
                "skipped": skipped_records,
                "failed": [],
            }
        else:
            db.session.rollback()
            return {
                "dry_run": False,
                "confirmed": True,
                "success": False,
                "team_id": team.id,
                "team_name": team.name,
                "total_input": preview["total_records"],
                "created": [],
                "skipped": skipped_records,
                "failed": failed_records,
            }
