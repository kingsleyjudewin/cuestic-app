import os
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


# The 5 member records supplied by the user for the Documentation team
DEFAULT_DOCUMENTATION_RECORDS = [
    {
        "full_name": "Surasmita",
        "phone": "+91 8078 156 512",
        "class_section": "6BTELCS",
    },
    {
        "full_name": "Salomi",
        "phone": "+91 85920 88048",
        "class_section": "6BTEC",
    },
    {
        "full_name": "Kavin",
        "phone": "+91 63793 38335",
        "class_section": "4BTEC",
    },
    {
        "full_name": "Manyatha",
        "phone": "+91 63022 12235",
        "class_section": "4BTEC",
    },
    {
        "full_name": "Pooja",
        "phone": "+91 821 780 6896",
        "class_section": "4BTEC",
    },
]


class DocumentationImportService:
    """Service to safely inspect, validate, and register Documentation team members."""

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
            raise ValidationError(
                f"Authorizing operator '{ident}' is currently deactivated.",
                details={"user_id": operator.id}
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
        Returns pre-validation diagnostics and duplicate checks.
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

        for idx, raw in enumerate(records, start=1):
            name = (raw.get("full_name") or raw.get("name") or "").strip()
            raw_phone = raw.get("phone") or raw.get("phone_number") or ""
            class_sec = (raw.get("class_section") or raw.get("class_name") or raw.get("class") or "").strip()
            reg_no = raw.get("registration_number")
            if reg_no:
                reg_no = str(reg_no).strip() or None

            issues = []
            status = "READY"
            normalized_phone = None

            if not name:
                issues.append("Missing full_name")
                status = "INVALID"

            if not raw_phone:
                issues.append("Missing phone number")
                status = "INVALID"
            else:
                try:
                    pinfo = normalize_phone_number(raw_phone, "IN")
                    normalized_phone = pinfo["e164"]
                except ValidationError as ve:
                    issues.append(f"Phone validation failed: {str(ve)}")
                    status = "INVALID"

            if not class_sec:
                issues.append("Missing class_name")
                status = "INVALID"

            # Check intra-batch duplicate phone
            if normalized_phone:
                if normalized_phone in seen_phones:
                    issues.append(f"Duplicate phone {normalized_phone} within input list")
                    status = "DUPLICATE_IN_BATCH"
                else:
                    seen_phones.add(normalized_phone)

            # Database duplicate checks
            if status == "READY" and normalized_phone:
                dup_phone = Member.query.filter_by(phone_number=normalized_phone, is_active=True).first()
                if dup_phone:
                    issues.append(
                        f"Phone '{normalized_phone}' already registered to active member '{dup_phone.full_name}' "
                        f"(Member ID: {dup_phone.id}, Team: {dup_phone.team.name if dup_phone.team else dup_phone.team_id})"
                    )
                    status = "EXISTS_IN_DB"

                dup_name = Member.query.filter(
                    Member.team_id == team.id,
                    Member.full_name.ilike(name),
                    Member.is_active == True,
                ).first()
                if dup_name:
                    issues.append(
                        f"Member '{name}' already exists in team {team.name} (Member ID: {dup_name.id})"
                    )
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
                "raw_phone": raw_phone,
                "normalized_phone": normalized_phone,
                "class_section": class_sec,
                "team_id": team.id,
                "team_name": team.name,
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
        Execute or dry-run registration of Documentation team members.
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

        payloads_to_create = []
        skipped_records = []

        for inspected in preview["inspected_records"]:
            if inspected["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH"):
                skipped_records.append({
                    "name": inspected["full_name"],
                    "phone": inspected["normalized_phone"] or inspected["raw_phone"],
                    "reason": "; ".join(inspected["issues"]),
                })
                continue

            if inspected["status"] == "INVALID":
                continue

            payloads_to_create.append({
                "full_name": inspected["full_name"],
                "phone_number": inspected["normalized_phone"],
                "class_name": inspected["class_section"],
                "country_code": "+91",
            })

        result = MemberService.bulk_create_members(
            records=payloads_to_create,
            team_id=team.id,
            actor_user_id=operator.id,
            atomic=True,
            skip_duplicates=True,
        )

        all_skipped = skipped_records + result.get("skipped", [])

        return {
            "dry_run": False,
            "confirmed": True,
            "success": result["success"],
            "team_id": team.id,
            "team_name": team.name,
            "total_input": preview["total_records"],
            "created": result.get("created", []),
            "skipped": all_skipped,
            "failed": result.get("failed", []),
        }
