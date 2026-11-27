import json
import click
from flask.cli import with_appcontext
from app.services.volunteer_import_service import (
    VolunteerImportService,
    DEFAULT_VOLUNTEER_RECORDS,
)
from app.services.documentation_import_service import (
    DocumentationImportService,
    DEFAULT_DOCUMENTATION_RECORDS,
)
from app.services.media_import_service import (
    MediaImportService,
    DEFAULT_MEDIA_RECORDS,
)


@click.command("import-volunteers")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview proposed accounts and validate data without writing any records.",
)
@click.option(
    "--confirm",
    "--yes",
    "confirm",
    is_flag=True,
    default=False,
    help="Explicitly confirm writing accounts to the database.",
)
@click.option(
    "--operator",
    default="clubadmin",
    help="President or Admin username authorizing the account creation.",
)
@click.option(
    "--file",
    "file_path",
    default=None,
    help="Optional path to a custom JSON or CSV file containing volunteer records.",
)
@click.option(
    "--skip-ambiguous",
    is_flag=True,
    default=False,
    help="Skip records flagged as ambiguous (e.g. uncertain phone mapping).",
)
@click.option(
    "--json-output",
    is_flag=True,
    default=False,
    help="Output summary in JSON format.",
)
@with_appcontext
def import_volunteers_command(dry_run, confirm, operator, file_path, skip_ambiguous, json_output):
    """
    Bulk-create volunteer accounts for the Volunteering team.
    
    Safe, repeatable import tool that validates all records, enforces President
    authorization, hashes passwords securely, and rolls back on unexpected failure.
    Runs in DRY-RUN mode by default unless --confirm is explicitly passed.
    """
    # If confirm is not set, default to dry-run
    is_dry_run = dry_run or not confirm

    try:
        preview = VolunteerImportService.inspect_and_preview(
            operator_identifier=operator,
            file_path=file_path,
        )
    except Exception as e:
        raise click.ClickException(f"Pre-import verification failed: {str(e)}")

    if not is_dry_run and not confirm:
        # Prompt user interactively if in terminal
        if click.confirm(
            f"\nWould you like to proceed with creating accounts for these volunteers?",
            default=False
        ):
            confirm = True
            is_dry_run = False
        else:
            is_dry_run = True

    result = VolunteerImportService.execute_import(
        operator_identifier=operator,
        file_path=file_path,
        dry_run=is_dry_run,
        confirm=confirm,
        skip_ambiguous=skip_ambiguous,
    )

    if json_output:
        import json
        clean_result = {
            "mode": "dry_run" if is_dry_run else "live",
            "operator": preview["operator"]["username"],
            "team": preview["team"]["name"],
            "team_id": preview["team"]["id"],
            "total_input": result["preview"]["total_records"],
            "created_count": len(result.get("created", [])),
            "skipped_count": len(result.get("skipped", [])),
            "failed_count": len(result.get("failed", [])),
            "created": result.get("created", []),
            "skipped": result.get("skipped", []),
            "failed": result.get("failed", []),
        }
        click.echo(json.dumps(clean_result, indent=2))
        return

    # Formatted terminal display
    click.echo("\n" + "=" * 95)
    header_mode = "[DRY RUN — PREVIEW ONLY]" if is_dry_run else "[LIVE IMPORT EXECUTED]"
    click.echo(f"  DEPARTMENT CLUB VOLUNTEER IMPORT  {header_mode}")
    click.echo("=" * 95)
    click.echo(f"  Authorizing Operator : {preview['operator']['username']} (Role: {preview['operator']['role']})")
    click.echo(f"  Target Team          : {preview['team']['name']} (Database ID: {preview['team']['id']})")
    click.echo(f"  Input Source         : {file_path if file_path else 'Default Supplied Volunteer Records'}")
    click.echo("-" * 95)

    click.echo(f"{'#':<3} {'Full Name':<18} {'Phone (Raw/Norm)':<26} {'Class':<10} {'Username':<18} {'Status':<14}")
    click.echo("-" * 95)

    for item in preview["inspected_records"]:
        norm_phone = item["normalized_phone"] or item["raw_phone"]
        phone_display = f"{item['raw_phone'][:12]}.. / {norm_phone}" if len(item['raw_phone']) > 12 else f"{item['raw_phone']} / {norm_phone}"
        status_color = "green" if item["status"] == "READY" else ("yellow" if item["status"] in ("AMBIGUOUS", "EXISTS_IN_DB") else "red")
        
        click.secho(
            f"{item['index']:<3} {item['full_name']:<18} {norm_phone:<26} {item['class_section']:<10} {item['username']:<18} {item['status']:<14}",
            fg=status_color
        )
        if item.get("notes"):
            click.secho(f"    ↳ Note: {item['notes']}", fg="cyan")
        if item.get("issues"):
            for issue in item["issues"]:
                click.secho(f"    ↳ Issue: {issue}", fg="yellow")

    click.echo("-" * 95)
    click.echo("  Account Generation & Password Security Rules:")
    click.echo("    - Proposed Identifier : <normalized.name>@gmail.com (Username: <normalized.name>)")
    click.echo("    - Role                : member (Strictly volunteer permissions; no elevation)")
    click.echo("    - Password Security   : werkzeug scrypt/pbkdf2 hash of <normalized.name>@123")
    click.echo("    - Password Protection : Plaintext passwords are NEVER printed, logged, or sent over WhatsApp.")
    click.echo("=" * 95)

    if is_dry_run:
        click.secho(
            "\n[DRY RUN SUMMARY] 0 accounts written to database.",
            fg="yellow",
            bold=True
        )
        click.echo(
            f"  Total records inspected: {preview['total_records']}\n"
            f"  Ready for import: {preview['ready_count']}\n"
            f"  Ambiguous/flagged: {preview['ambiguous_count']}\n"
            f"  Existing/duplicate: {preview['duplicate_count']}\n"
            f"  Invalid: {preview['invalid_count']}\n"
        )
        click.secho(
            "To execute this import and create these accounts, rerun with --confirm:\n"
            f"  flask import-volunteers --confirm --operator {preview['operator']['username']}\n",
            bold=True
        )
    else:
        click.secho(
            f"\n[EXECUTION SUMMARY] {len(result['created'])} created, {len(result['skipped'])} skipped, {len(result['failed'])} failed.",
            fg="green" if result["success"] else "red",
            bold=True
        )
        if result["created"]:
            click.echo("\nSuccessfully Created Accounts:")
            for acc in result["created"]:
                click.echo(
                    f"  [+] {acc['full_name']} | Username: {acc['username']} | Email: {acc['email']} "
                    f"| Member ID: {acc['member_id']} | User ID: {acc['user_id']} | Team: {acc['team_name']}"
                )

        if result["skipped"]:
            click.echo("\nSkipped Records:")
            for sk in result["skipped"]:
                click.echo(f"  [.] {sk.get('name', 'Record')} - {sk.get('reason', 'Skipped')}")

        if result["failed"]:
            click.echo("\nFailed Records:")
            for fa in result["failed"]:
                click.echo(f"  [!] {fa.get('name', 'Record')} - {fa.get('error', 'Error')}")
        click.echo("")


@click.command("import-documentation-members")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview proposed members and validate data without writing any records.",
)
@click.option(
    "--confirm",
    "--yes",
    "confirm",
    is_flag=True,
    default=False,
    help="Explicitly confirm writing member records to the database.",
)
@click.option(
    "--operator",
    default="clubadmin",
    help="President or Admin username authorizing member registration.",
)
@click.option(
    "--file",
    "file_path",
    default=None,
    help="Optional path to a custom JSON or CSV file containing member records.",
)
@click.option(
    "--json-output",
    is_flag=True,
    default=False,
    help="Output summary in JSON format.",
)
@with_appcontext
def import_documentation_members_command(dry_run, confirm, operator, file_path, json_output):
    """
    Register members and provision login accounts under the existing Documentation team.

    Safe, repeatable registration tool that validates all records, enforces President
    authorization, normalizes phone numbers to E.164 (+91), prevents duplicates,
    creates user login accounts with expiring single-use setup tokens, and commits transactionally.
    Runs in DRY-RUN mode by default unless --confirm is explicitly passed.
    """
    is_dry_run = dry_run or not confirm

    try:
        preview = DocumentationImportService.inspect_and_preview(
            operator_identifier=operator,
            file_path=file_path,
        )
    except Exception as e:
        click.secho(f"Pre-check failed: {str(e)}", fg="red", err=True)
        raise SystemExit(1)

    result = DocumentationImportService.execute_import(
        operator_identifier=operator,
        file_path=file_path,
        dry_run=is_dry_run,
        confirm=confirm,
    )

    if json_output:
        clean_result = {
            "mode": "dry_run" if is_dry_run else "live",
            "operator": preview["operator"]["username"],
            "team": preview["team"]["name"],
            "team_id": preview["team"]["id"],
            "total_input": preview["total_records"],
            "created_count": len(result.get("created", [])),
            "skipped_count": len(result.get("skipped", [])),
            "failed_count": len(result.get("failed", [])),
            "created": [
                {k: v for k, v in c.items() if k != "setup_token"}
                for c in result.get("created", [])
            ],
            "skipped": result.get("skipped", []),
            "failed": result.get("failed", []),
        }
        click.echo(json.dumps(clean_result, indent=2, default=str))
        return

    # Formatted CLI Presentation
    click.echo("\n" + "=" * 95)
    click.secho("  DEPARTMENT CLUB — DOCUMENTATION TEAM ACCOUNT PROVISIONING", fg="cyan", bold=True)
    click.echo("=" * 95)
    click.echo(f"  Target Team  : {preview['team']['name']} (ID: {preview['team']['id']}, Current Members: {preview['team']['current_member_count']})")
    click.echo(f"  Authorized By: {preview['operator']['username']} (Role: {preview['operator']['role']})")
    click.echo(f"  Mode         : {'DRY RUN (Preview Only — No Database Writes)' if is_dry_run else 'LIVE COMMIT'}")
    click.echo("-" * 95)

    click.echo(f"{'#':<3} {'Full Name':<20} {'Username':<20} {'Proposed Email':<28} {'Phone (E.164)':<16} {'Status':<10}")
    click.echo("-" * 95)

    for item in preview["inspected_records"]:
        norm_phone = item["normalized_phone"] or item["raw_phone"]
        status_color = "green" if item["status"] == "READY" else ("yellow" if item["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH") else "red")

        click.secho(
            f"{item['index']:<3} {item['full_name']:<20} {item['username']:<20} {item['proposed_email']:<28} {norm_phone:<16} {item['status']:<10}",
            fg=status_color
        )
        if item.get("issues"):
            for issue in item["issues"]:
                click.secho(f"    ↳ Notice: {issue}", fg="yellow")

    click.echo("-" * 95)
    click.echo("  Security & Provisioning Policies:")
    click.echo("    - Role assignment: Standard 'member' role (no admin or president elevation).")
    click.echo("    - Passwords: High-entropy random temporary credentials with 72h single-use setup tokens.")
    click.echo("    - Phone format: Preserves country code (+91) with standard E.164 normalization.")
    click.echo("=" * 95)

    if is_dry_run:
        click.secho(
            "\n[DRY RUN SUMMARY] 0 accounts written to database.",
            fg="yellow",
            bold=True
        )
        click.echo(
            f"  Total records inspected: {preview['total_records']}\n"
            f"  Ready for import: {preview['ready_count']}\n"
            f"  Existing/duplicate: {preview['duplicate_count']}\n"
            f"  Invalid: {preview['invalid_count']}\n"
        )
        click.secho(
            "To execute this import and create these accounts in Neon PostgreSQL, rerun with --confirm:\n"
            f"  flask import-documentation-members --confirm --operator {preview['operator']['username']}\n",
            bold=True
        )
    else:
        click.secho(
            f"\n[EXECUTION SUMMARY] {len(result['created'])} created, {len(result['skipped'])} skipped, {len(result['failed'])} failed.",
            fg="green" if result["success"] else "red",
            bold=True
        )
        if result["created"]:
            click.echo("\nSuccessfully Created Documentation Team Accounts:")
            for m in result["created"]:
                click.echo(
                    f"  [+] {m['full_name']} | Username: {m['username']} | Email: {m['proposed_email']} "
                    f"| Phone: {m['phone_number']} | Status: {m['account_status']} | Setup: {m['credential_setup_status']}"
                )
                click.echo(f"      Setup Token: {m['setup_token']} (Expires: {m['setup_expires_at']})")

        if result["skipped"]:
            click.echo("\nSkipped Records (Duplicates):")
            for sk in result["skipped"]:
                click.echo(f"  [.] {sk.get('name', 'Record')} - {sk.get('reason', 'Skipped')}")

        if result["failed"]:
            click.echo("\nFailed Records:")
            for fa in result["failed"]:
                click.echo(f"  [!] {fa.get('name', 'Record')} - {fa.get('error', 'Error')}")
        click.echo("")


@click.command("import-media-members")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview proposed Media accounts without writing to database.",
)
@click.option(
    "--confirm",
    "--yes",
    "confirm",
    is_flag=True,
    default=False,
    help="Explicitly confirm writing accounts to the database.",
)
@click.option(
    "--operator",
    default="clubadmin",
    help="President or Admin username authorizing the account creation.",
)
@click.option(
    "--file",
    "file_path",
    default=None,
    help="Optional path to custom JSON or CSV file containing media member records.",
)
@click.option(
    "--json-output",
    is_flag=True,
    default=False,
    help="Output summary in JSON format.",
)
@with_appcontext
def import_media_members_command(dry_run, confirm, operator, file_path, json_output):
    """
    Import Media team members and create user accounts with secure setup tokens.
    
    Safe, repeatable import tool that validates all records, enforces President/Admin
    authorization, generates cryptographically secure single-use setup tokens, and avoids
    duplicate accounts. Runs in DRY-RUN mode by default unless --confirm is passed.
    """
    is_dry_run = dry_run or not confirm

    try:
        preview = MediaImportService.inspect_and_preview(
            operator_identifier=operator,
            file_path=file_path,
        )
    except Exception as e:
        raise click.ClickException(f"Pre-import verification failed: {str(e)}")

    if not is_dry_run and not confirm:
        if click.confirm(
            f"\nWould you like to proceed with creating accounts for these {preview['ready_count']} media members?",
            default=False
        ):
            confirm = True
            is_dry_run = False
        else:
            is_dry_run = True

    result = MediaImportService.execute_import(
        operator_identifier=operator,
        file_path=file_path,
        dry_run=is_dry_run,
        confirm=confirm,
    )

    if json_output:
        import json
        clean_result = {
            "mode": "dry_run" if is_dry_run else "live",
            "operator": preview["operator"]["username"],
            "team": preview["team"]["name"],
            "team_id": preview["team"]["id"],
            "total_input": preview["total_records"],
            "created_count": len(result.get("created", [])),
            "skipped_count": len(result.get("skipped", [])),
            "failed_count": len(result.get("failed", [])),
            "created": [
                {k: v for k, v in c.items() if k != "setup_token"}
                for c in result.get("created", [])
            ],
            "skipped": result.get("skipped", []),
            "failed": result.get("failed", []),
        }
        click.echo(json.dumps(clean_result, indent=2))
        return

    click.echo("\n" + "=" * 70)
    click.echo("  MEDIA TEAM MEMBERS IMPORT & ACCOUNT PROVISIONING")
    click.echo("=" * 70)
    click.echo(f"  Target Team       : {preview['team']['name']} (ID: {preview['team']['id']})")
    click.echo(f"  Authorizing Admin : {preview['operator']['username']} (Role: {preview['operator']['role']})")
    click.echo(f"  Execution Mode    : {'DRY RUN (Preview Only)' if is_dry_run else 'LIVE DATABASE COMMIT'}")
    click.echo(f"  Total Records     : {preview['total_records']}")
    click.echo(f"  Ready for Import  : {preview['ready_count']}")
    click.echo(f"  Duplicates/Exists : {preview['duplicate_count']}")
    click.echo(f"  Invalid Records   : {preview['invalid_count']}")
    click.echo("-" * 70)

    if is_dry_run:
        click.secho("\n[PREVIEW OF PROPOSED ACCOUNTS]", fg="yellow", bold=True)
        for r in preview["inspected_records"]:
            color = "green" if r["status"] == "READY" else ("yellow" if "DUPLICATE" in r["status"] or "EXISTS" in r["status"] else "red")
            click.secho(
                f"  [{r['status']:<15}] {r['full_name']} | Username: {r['username']} | Email: {r['proposed_email']} "
                f"| Phone: {r['normalized_phone'] or r['raw_phone']} | Class: {r['class_section']}",
                fg=color,
            )
            if r["issues"]:
                for iss in r["issues"]:
                    click.echo(f"       -> {iss}")

        click.secho(
            f"\nDry run complete. No records were written to the database.",
            fg="yellow",
            bold=True
        )
        click.echo("To create these accounts, run:")
        click.secho("  flask import-media-members --confirm\n", fg="cyan", bold=True)
    else:
        click.secho(
            f"\n[EXECUTION SUMMARY] {len(result['created'])} created, {len(result['skipped'])} skipped, {len(result['failed'])} failed.",
            fg="green" if result["success"] else "red",
            bold=True
        )
        if result["created"]:
            click.echo("\nSuccessfully Created Media Team Accounts:")
            for m in result["created"]:
                click.echo(
                    f"  [+] {m['full_name']} | Username: {m['username']} | Email: {m['proposed_email']} "
                    f"| Phone: {m['phone_number']} | Class: {m['class_name']} | Status: {m['account_status']} | Setup: {m['credential_setup_status']}"
                )
                click.echo(f"      Setup Token: {m['setup_token']} (Expires: {m['setup_expires_at']})")

        if result["skipped"]:
            click.echo("\nSkipped Records:")
            for sk in result["skipped"]:
                click.echo(f"  [.] {sk.get('name', 'Record')} - {sk.get('reason', 'Skipped')}")

        if result["failed"]:
            click.echo("\nFailed Records:")
            for fa in result["failed"]:
                click.echo(f"  [!] {fa.get('name', 'Record')} - {fa.get('error', 'Error')}")
        click.echo("")


@click.command("reminders-scan")
@click.option("--no-notify", is_flag=True, default=False,
              help="Record reminders without sending push notifications (baseline an existing database).")
@with_appcontext
def reminders_scan_command(no_notify):
    """Run one reminder scan now (for a Render Cron Job or manual use). Safe to run concurrently."""
    from flask import current_app
    from app.services.scheduler_service import run_reminder_scan
    stats = run_reminder_scan(current_app._get_current_object(), notify=not no_notify)
    click.echo(json.dumps(stats if stats is not None else {"skipped": True}, indent=2, default=str))


@click.command("rotate-leaked-passwords")
@click.option("--leaked-file", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Text file with one leaked password per line (keep it outside Git).")
@click.option("--confirm", is_flag=True, default=False,
              help="Actually change passwords. Without this flag only a dry-run report is printed.")
@click.option("--output", default=None, type=click.Path(dir_okay=False),
              help="CSV to write new temporary passwords to (default: instance/rotated_credentials_<time>.csv).")
@with_appcontext
def rotate_leaked_passwords_command(leaked_file, confirm, output):
    """
    Find active accounts whose password is one of the leaked passwords, give each a random
    temporary password, revoke all of their API tokens, and force a password change at next login.
    """
    import csv
    import os
    import secrets
    import string
    from collections import Counter
    from datetime import datetime
    from werkzeug.security import check_password_hash
    from app.extensions import db
    from app.models.user import User, ApiToken
    from app.utils.permissions import invalidate_token_cache

    with open(leaked_file, "r", encoding="utf-8") as fh:
        leaked = [line.rstrip("\n") for line in fh if line.strip()]
    if not leaked:
        raise click.ClickException("The leaked password file is empty.")

    users = User.query.filter_by(is_active=True).all()
    affected = [u for u in users if u.password_hash and any(check_password_hash(u.password_hash, p) for p in leaked)]
    by_role = Counter(u.role for u in affected)
    click.echo(f"Active accounts: {len(users)}. Using a leaked password: {len(affected)} {dict(by_role)}")

    if not confirm:
        click.echo("Dry run only. Re-run with --confirm to rotate these passwords.")
        return

    alphabet = string.ascii_letters + string.digits
    def temp_password() -> str:
        return "".join(secrets.choice(alphabet) for _ in range(14)) + secrets.choice("!@#$%") + secrets.choice(string.digits)

    if output is None:
        os.makedirs(os.path.join(os.getcwd(), "instance"), exist_ok=True)
        output = os.path.join("instance", f"rotated_credentials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    rows = []
    for u in affected:
        new_pw = temp_password()
        u.set_password(new_pw)
        if u.role != User.ROLE_ADMIN:  # admin gets a new random password but is never forced to change it
            u.credential_setup_status = "pending"
            u.password_change_required = True
            if u.faculty_profile:
                u.faculty_profile.must_change_password = True
            if u.research_student_profile:
                u.research_student_profile.must_change_password = True
        ApiToken.query.filter_by(user_id=u.id, is_revoked=False).update({"is_revoked": True})
        rows.append({"username": u.username, "role": u.role, "temporary_password": new_pw})
    db.session.commit()
    for u in affected:
        invalidate_token_cache(user_id=u.id)

    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["username", "role", "temporary_password"])
        writer.writeheader()
        writer.writerows(rows)
    click.echo(f"Rotated {len(rows)} passwords and revoked their sessions. Temporary passwords: {output} (mode 600).")
    click.echo("Share each password privately; users must set a new one at first login. Delete the CSV afterwards.")


@click.command("password-hashes")
@click.option("--input", "input_file", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Plaintext file, one leaked password per line (keep it outside the repository).")
@click.option("--output", "output_file", required=True, type=click.Path(dir_okay=False),
              help="Where to write SHA-256 digests for LEAKED_PASSWORD_HASHES_FILE.")
def password_hashes_command(input_file, output_file):
    """Convert a plaintext leaked-password list into the hashed list the server checks against."""
    import hashlib
    import os
    with open(input_file, encoding="utf-8") as fh:
        digests = sorted({hashlib.sha256(line.rstrip("\n").encode("utf-8")).hexdigest()
                          for line in fh if line.rstrip("\n")})
    fd = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write("\n".join(digests) + "\n")
    click.echo(f"Wrote {len(digests)} hashes to {output_file}. Set LEAKED_PASSWORD_HASHES_FILE to this path.")


@click.command("require-password-change")
@click.option("--confirm", is_flag=True, help="Apply the change. Without it only a preview is printed.")
@click.option("--revert", is_flag=True, help="Undo: clear the flag for accounts that have not changed their password yet.")
@with_appcontext
def require_password_change_command(confirm, revert):
    """Require every non-admin account to set a new password at next sign-in.

    Only the exact 'admin' role is excluded. Passwords, profiles and roles are not modified.
    Safe to re-run: accounts that already completed the change (password_changed_at set) and
    accounts already flagged are skipped. Every active session of a newly flagged account keeps
    working only for the password-change screen.
    """
    from collections import Counter
    from app.extensions import db
    from app.models.user import User
    from app.services.audit_service import AuditService
    from app.utils.permissions import invalidate_token_cache

    non_admin = User.query.filter(User.role != User.ROLE_ADMIN)
    if revert:
        targets = non_admin.filter(
            User.password_change_required.is_(True),
            User.password_changed_at.is_(None),
            User.credential_setup_status != "pending",  # keep requirements that predate this command
        ).all()
        verb = "cleared"
    else:
        targets = non_admin.filter(
            User.password_change_required.is_(False),
            User.password_changed_at.is_(None),
        ).all()
        verb = "flagged"

    by_role = Counter(u.role for u in targets)
    inactive = sum(1 for u in targets if not u.is_active)
    total = User.query.count()
    click.echo(f"Accounts in database: {total}. Admin accounts excluded: "
               f"{User.query.filter(User.role == User.ROLE_ADMIN).count()}.")
    click.echo(f"Accounts that would be {verb}: {len(targets)} {dict(sorted(by_role.items()))} "
               f"(of which inactive: {inactive}).")
    click.echo("Equivalent preview SQL: SELECT role, count(*) FROM users WHERE role <> 'admin' "
               + ("AND password_change_required AND password_changed_at IS NULL AND credential_setup_status <> 'pending' "
                  if revert else "AND NOT password_change_required AND password_changed_at IS NULL ")
               + "GROUP BY role;")
    if not confirm:
        click.echo("Dry run only. Re-run with --confirm to apply.")
        return
    if not targets:
        click.echo("Nothing to do.")
        return

    for u in targets:
        u.password_change_required = not revert
    AuditService.log_action(
        action="PASSWORD_CHANGE_REQUIREMENT_REVERTED" if revert else "PASSWORD_CHANGE_REQUIRED_BULK",
        entity_type="User",
        entity_id=None,
        actor_user_id=None,
        details={"count": len(targets), "by_role": dict(by_role)},
    )
    db.session.commit()
    for u in targets:
        invalidate_token_cache(user_id=u.id)
    click.echo(f"Done: {len(targets)} accounts {verb}. Other server processes pick this up on their next request.")


@click.command("create-visitor")
@click.option("--username", default="visitor", show_default=True,
              help="Must be listed in VISITOR_USERNAMES (default setting: 'visitor').")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="Password shared with visitors.")
@with_appcontext
def create_visitor_command(username, password):
    """Create (or reset the password of) a read-only visitor account that explores the admin UI
    on an empty workspace. See app/utils/visitor_mode.py."""
    from flask import current_app
    from app.extensions import db
    from app.models.user import User
    from app.utils.permissions import invalidate_token_cache
    from app.utils.visitor_mode import visitor_usernames

    username = username.strip()
    if username.lower() not in visitor_usernames(current_app):
        raise click.ClickException(
            f"'{username}' is not in VISITOR_USERNAMES ({current_app.config.get('VISITOR_USERNAMES')!r}). "
            "Add it there first, otherwise the account would be a real administrator."
        )
    if len(password) < 8:
        raise click.ClickException("Use a password of at least 8 characters.")

    user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
    created = user is None
    if created:
        user = User(username=username, role=User.ROLE_ADMIN)
        db.session.add(user)
    elif user.role != User.ROLE_ADMIN:
        raise click.ClickException(f"User '{user.username}' exists with role '{user.role}'. Choose another username.")
    user.set_password(password)
    user.is_active = True
    user.credential_setup_status = "completed"
    user.password_change_required = False
    db.session.commit()
    invalidate_token_cache(user_id=user.id)
    click.echo(f"Visitor account '{user.username}' {'created' if created else 'updated'}.")


def register_cli_commands(app):
    """Register CLI commands with the Flask application."""
    app.cli.add_command(import_volunteers_command)
    app.cli.add_command(import_documentation_members_command)
    app.cli.add_command(import_media_members_command)
    app.cli.add_command(reminders_scan_command)
    app.cli.add_command(rotate_leaked_passwords_command)
    app.cli.add_command(require_password_change_command)
    app.cli.add_command(password_hashes_command)
    app.cli.add_command(create_visitor_command)
