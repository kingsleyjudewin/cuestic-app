import os
import re
import csv
import json
from typing import Optional
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.services.member_service import MemberService
from app.utils.phone_numbers import normalize_phone_number
from app.utils.errors import ValidationError, PermissionDeniedError, NotFoundError


# The 7 volunteer records supplied by the user
DEFAULT_VOLUNTEER_RECORDS = [
    {
        "full_name": "Devananda Ajith",
        "phone": "+91 82898 29614",
        "class_section": "6BTEC",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": None,
    },
    {
        "full_name": "Jayani CU",
        "phone": "+91 81483 11354",
        "class_section": "4BTELCS",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": None,
    },
    {
        "full_name": "Pranavi Cuestic",
        "phone": "+91 7397 735 899",
        "class_section": "6BTEC",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": None,
    },
    {
        "full_name": "Sagar CU",
        "phone": "+91 90087 62143",
        "class_section": "6BTEC",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": None,
    },
    {
        "full_name": "Kanishk",
        "phone": "+91 80892 81159",
        "class_section": "6BTELCS",
        "registration_number": None,
        "is_ambiguous": True,
        "notes": "Phone number mapping formatted with potential ambiguity in source text; single name without surname; missing registration number.",
    },
    {
        "full_name": "Sanjai",
        "phone": "+91 77957 67522",
        "class_section": "6BTEC",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": "Single name without surname; missing registration number.",
    },
    {
        "full_name": "Shohil Mathew",
        "phone": "+91 94874 49346",
        "class_section": "6BTEC",
        "registration_number": None,
        "is_ambiguous": False,
        "notes": None,
    },
]


def normalize_name_for_identifier(full_name: str) -> str:
    """
    Generate normalized account identifier from person's name:
    - Normalize to lowercase
    - Remove leading/trailing whitespace
    - Replace spaces with periods
    - Remove invalid email/username characters
    - Collapse multiple consecutive dots and strip leading/trailing dots
    """
    clean = full_name.lower().strip()
    clean = re.sub(r"\s+", ".", clean)
    clean = re.sub(r"[^a-z0-9.]", "", clean)
    clean = re.sub(r"\.+", ".", clean)
    return clean.strip(".")


def generate_proposed_email(normalized_name: str) -> str:
    """Generate proposed placeholder email address."""
    return f"{normalized_name}@gmail.com"


def generate_temporary_password(normalized_name: str) -> str:
    """Generate temporary password following <normalized_name>@123 convention."""
    return f"{normalized_name}@123"


class VolunteerImportService:
    """Service to safely inspect, validate, and bulk-create volunteer accounts."""

    @staticmethod
    def get_volunteering_team() -> Team:
        """Find the existing Volunteering team by its actual database ID."""
        team = Team.query.filter(
            (Team.name.ilike("volunteering")) | (Team.slug == "volunteering")
        ).first()

        if not team:
            raise NotFoundError(
                "Volunteering team was not found in the database. Ensure database baseline is seeded."
            )
        if not team.is_active:
            raise ValidationError(
                f"Volunteering team (ID: {team.id}) is currently marked inactive.",
                details={"team_id": team.id}
            )
        return team

    @staticmethod
    def verify_operator(operator_identifier: str = "clubadmin") -> User:
        """
        Verify that the operator exists, is active, and is authorized as President or Admin.
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
                f"Operator '{ident}' has role '{operator.role}'. Only President/Admin can authorize account creation.",
                details={"operator_role": operator.role, "required_role": User.ROLE_PRESIDENT}
            )

        return operator

    @staticmethod
    def load_records_from_file(file_path: str) -> list[dict]:
        """Load volunteer records from a JSON or CSV file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Volunteer input file not found: {file_path}")

        records = []
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and "volunteers" in data:
                    records = data["volunteers"]
                else:
                    raise ValidationError("JSON file must contain an array of volunteer records or a 'volunteers' list.")
        elif file_path.endswith(".csv"):
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append({
                        "full_name": row.get("name") or row.get("full_name") or row.get("Name"),
                        "phone": row.get("phone") or row.get("Phone") or row.get("phone_number"),
                        "class_section": row.get("class_section") or row.get("class") or row.get("Class/section") or row.get("class_name"),
                        "registration_number": row.get("registration_number") or row.get("reg_no") or None,
                        "is_ambiguous": str(row.get("is_ambiguous", "")).lower() in ("true", "1", "yes"),
                        "notes": row.get("notes") or None,
                    })
        else:
            raise ValidationError("Unsupported file format. Please provide a .json or .csv file.")

        return records

    @classmethod
    def prepare_records_for_import(cls, raw_records: list[dict], team_id: int) -> list[dict]:
        """
        Transform raw volunteer records into validated payloads ready for MemberService.
        Computes normalized identifier, email, temporary password, and normalized phone.
        """
        prepared = []
        for raw in raw_records:
            full_name = (raw.get("full_name") or raw.get("name") or "").strip()
            raw_phone = raw.get("phone") or raw.get("phone_number") or ""
            class_sec = (raw.get("class_section") or raw.get("class_name") or "").strip()
            reg_no = raw.get("registration_number")
            if reg_no:
                reg_no = str(reg_no).strip() or None

            normalized_name = normalize_name_for_identifier(full_name) if full_name else ""
            proposed_email = generate_proposed_email(normalized_name) if normalized_name else ""
            temp_password = generate_temporary_password(normalized_name) if normalized_name else ""

            # Class and optional section parsing
            class_name = class_sec
            section = raw.get("section")
            if section:
                section = str(section).strip() or None

            payload = {
                "full_name": full_name,
                "phone_number": raw_phone,
                "country_code": raw.get("country_code", "+91"),
                "class_name": class_name,
                "section": section,
                "registration_number": reg_no,
                "team_id": team_id,
                "username": normalized_name,
                "email": proposed_email,
                "password": temp_password,
                "role": User.ROLE_MEMBER,  # strictly volunteer role (never elevated)
                "whatsapp_opt_in": raw.get("whatsapp_opt_in", True),
                # Metadata for reporting & dry-run
                "_raw_phone": raw_phone,
                "_is_ambiguous": bool(raw.get("is_ambiguous")),
                "_notes": raw.get("notes"),
            }
            prepared.append(payload)
        return prepared

    @classmethod
    def inspect_and_preview(
        cls,
        records: Optional[list[dict]] = None,
        operator_identifier: str = "clubadmin",
        file_path: Optional[str] = None,
    ) -> dict:
        """
        Inspect records against database state without writing any records.
        Returns detailed preview and pre-validation diagnostics.
        """
        team = cls.get_volunteering_team()
        operator = cls.verify_operator(operator_identifier)

        if records is None:
            if file_path:
                records = cls.load_records_from_file(file_path)
            else:
                records = DEFAULT_VOLUNTEER_RECORDS

        prepared = cls.prepare_records_for_import(records, team.id)

        inspected = []
        ready_count = 0
        ambiguous_count = 0
        duplicate_count = 0
        invalid_count = 0

        seen_usernames = set()
        seen_phones = set()

        for idx, item in enumerate(prepared, start=1):
            name = item["full_name"]
            username = item["username"]
            email = item["email"]
            raw_phone = item["_raw_phone"]
            is_ambiguous = item["_is_ambiguous"]
            notes = item["_notes"]

            diag = {
                "index": idx,
                "full_name": name,
                "raw_phone": raw_phone,
                "normalized_phone": None,
                "class_section": item["class_name"],
                "username": username,
                "proposed_email": email,
                "team_id": team.id,
                "team_name": team.name,
                "status": "READY",
                "issues": [],
                "is_ambiguous": is_ambiguous,
                "notes": notes,
            }

            # 1. Phone validation
            try:
                phone_info = normalize_phone_number(raw_phone, item.get("country_code", "+91"))
                diag["normalized_phone"] = phone_info["e164"]
                e164_phone = phone_info["e164"]
            except ValidationError as ve:
                diag["status"] = "INVALID"
                diag["issues"].append(f"Phone validation failed: {str(ve)}")
                invalid_count += 1
                inspected.append(diag)
                continue

            # 2. Name & username validation
            if not name or len(name) < 2:
                diag["status"] = "INVALID"
                diag["issues"].append("Name must be at least 2 characters.")
                invalid_count += 1
                inspected.append(diag)
                continue

            if not username or len(username) < 3:
                diag["status"] = "INVALID"
                diag["issues"].append(f"Generated username '{username}' is too short (min 3 chars).")
                invalid_count += 1
                inspected.append(diag)
                continue

            # 3. Batch duplicates
            if username in seen_usernames:
                diag["status"] = "DUPLICATE_IN_BATCH"
                diag["issues"].append(f"Username '{username}' duplicated within current input batch.")
                duplicate_count += 1
            seen_usernames.add(username)

            if e164_phone in seen_phones:
                diag["status"] = "DUPLICATE_IN_BATCH"
                diag["issues"].append(f"Phone '{e164_phone}' duplicated within current input batch.")
                duplicate_count += 1
            seen_phones.add(e164_phone)

            # 4. Database duplicates
            existing_user = User.query.filter(User.username.ilike(username)).first()
            if existing_user:
                diag["status"] = "EXISTS_IN_DB"
                diag["issues"].append(f"User with username '{username}' already exists in DB (ID: {existing_user.id}).")
                duplicate_count += 1

            if email:
                existing_email = User.query.filter(User.email.ilike(email)).first()
                if existing_email:
                    diag["status"] = "EXISTS_IN_DB"
                    diag["issues"].append(f"Email '{email}' already registered in DB (ID: {existing_email.id}).")
                    duplicate_count += 1

            existing_member = Member.query.filter_by(phone_number=e164_phone, is_active=True).first()
            if existing_member:
                diag["status"] = "EXISTS_IN_DB"
                diag["issues"].append(f"Active member with phone '{e164_phone}' exists ({existing_member.full_name}, ID: {existing_member.id}).")
                duplicate_count += 1

            # 5. Check ambiguity
            if is_ambiguous or notes:
                ambiguous_count += 1
                if diag["status"] == "READY":
                    diag["status"] = "AMBIGUOUS"

            if diag["status"] == "READY":
                ready_count += 1

            inspected.append(diag)

        return {
            "operator": {
                "id": operator.id,
                "username": operator.username,
                "email": operator.email,
                "role": operator.role,
            },
            "team": {
                "id": team.id,
                "name": team.name,
                "slug": team.slug,
            },
            "total_records": len(prepared),
            "ready_count": ready_count,
            "ambiguous_count": ambiguous_count,
            "duplicate_count": duplicate_count,
            "invalid_count": invalid_count,
            "inspected_records": inspected,
            "prepared_payloads": prepared,
        }

    @classmethod
    def execute_import(
        cls,
        records: Optional[list[dict]] = None,
        operator_identifier: str = "clubadmin",
        file_path: Optional[str] = None,
        dry_run: bool = True,
        confirm: bool = False,
        skip_ambiguous: bool = False,
    ) -> dict:
        """
        Execute or dry-run volunteer account creation.
        If dry_run is True or confirm is False, inspects and returns proposed accounts without writing.
        If confirm is True and dry_run is False, calls MemberService.bulk_create_member_accounts.
        """
        preview = cls.inspect_and_preview(
            records=records,
            operator_identifier=operator_identifier,
            file_path=file_path,
        )

        # Safety enforcement: If dry_run is True or confirm is False, NEVER write records
        if dry_run or not confirm:
            return {
                "dry_run": True,
                "confirmed": False,
                "preview": preview,
                "message": "DRY RUN complete. 0 records written to database. Review proposed accounts and rerun with --confirm to execute.",
                "created": [],
                "skipped": [r for r in preview["inspected_records"] if r["status"] == "EXISTS_IN_DB"],
                "failed": [r for r in preview["inspected_records"] if r["status"] == "INVALID"],
            }

        # Filter payloads to create
        payloads_to_create = []
        skipped_records = []

        for item, inspected in zip(preview["prepared_payloads"], preview["inspected_records"]):
            if inspected["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH"):
                skipped_records.append({
                    "name": item["full_name"],
                    "username": item["username"],
                    "reason": "; ".join(inspected["issues"]),
                })
                continue

            if inspected["status"] == "INVALID":
                continue

            if skip_ambiguous and inspected.get("is_ambiguous"):
                skipped_records.append({
                    "name": item["full_name"],
                    "username": item["username"],
                    "reason": f"Skipped ambiguous record: {inspected.get('notes')}",
                })
                continue

            # Strip temporary metadata keys before calling MemberService
            clean_payload = {k: v for k, v in item.items() if not k.startswith("_")}
            payloads_to_create.append(clean_payload)

        # Execute bulk creation via application service
        operator = cls.verify_operator(operator_identifier)
        result = MemberService.bulk_create_member_accounts(
            records=payloads_to_create,
            actor_user_id=operator.id,
            atomic=True,
            skip_duplicates=True,
        )

        # Combine skipped from inspection and execution
        all_skipped = skipped_records + result.get("skipped", [])

        return {
            "dry_run": False,
            "confirmed": True,
            "preview": preview,
            "success": result["success"],
            "created": result["created"],
            "skipped": all_skipped,
            "failed": result["failed"],
            "total_input": preview["total_records"],
        }
