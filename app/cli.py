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
    Register members under the existing Documentation team.

    Safe, repeatable registration tool that validates all records, enforces President
    authorization, normalizes phone numbers to E.164 (+91), prevents duplicates,
    and commits transactionally without creating login accounts or changing roles.
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
        click.echo(json.dumps(result, indent=2, default=str))
        return

    # Formatted CLI Presentation
    click.echo("\n" + "=" * 80)
    click.secho("  DEPARTMENT CLUB — DOCUMENTATION TEAM MEMBER REGISTRATION", fg="cyan", bold=True)
    click.echo("=" * 80)
    click.echo(f"  Target Team  : {preview['team']['name']} (ID: {preview['team']['id']}, Current Members: {preview['team']['current_member_count']})")
    click.echo(f"  Authorized By: {preview['operator']['username']} (Role: {preview['operator']['role']})")
    click.echo(f"  Mode         : {'DRY RUN (Preview Only — No Database Writes)' if is_dry_run else 'LIVE COMMIT'}")
    click.echo("-" * 80)

    click.echo(f"{'#':<3} {'Full Name':<18} {'Phone (E.164)':<20} {'Class':<12} {'Team':<16} {'Status':<12}")
    click.echo("-" * 80)

    for item in preview["inspected_records"]:
        norm_phone = item["normalized_phone"] or item["raw_phone"]
        status_color = "green" if item["status"] == "READY" else ("yellow" if item["status"] in ("EXISTS_IN_DB", "DUPLICATE_IN_BATCH") else "red")

        click.secho(
            f"{item['index']:<3} {item['full_name']:<18} {norm_phone:<20} {item['class_section']:<12} {item['team_name']:<16} {item['status']:<12}",
            fg=status_color
        )
        if item.get("issues"):
            for issue in item["issues"]:
                click.secho(f"    ↳ Notice: {issue}", fg="yellow")

    click.echo("-" * 80)
    click.echo("  Registration Constraints:")
    click.echo("    - Pure member records: No user accounts, passwords, or role elevations are created.")
    click.echo("    - Phone format: Preserves country code (+91) with standard E.164 normalization.")
    click.echo("=" * 80)

    if is_dry_run:
        click.secho(
            "\n[DRY RUN SUMMARY] 0 records written to database.",
            fg="yellow",
            bold=True
        )
        click.echo(
            f"  Total records inspected: {preview['total_records']}\n"
            f"  Ready for registration: {preview['ready_count']}\n"
            f"  Existing/duplicate: {preview['duplicate_count']}\n"
            f"  Invalid: {preview['invalid_count']}\n"
        )
        click.secho(
            "To execute this registration and write records to the database, rerun with --confirm:\n"
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
            click.echo("\nSuccessfully Registered Members:")
            for m in result["created"]:
                click.echo(
                    f"  [+] {m['full_name']} | Phone: {m['phone_number']} | Class: {m['class_name']} "
                    f"| Member ID: {m['id']} | Team: {m['team_name']} (ID: {m['team_id']})"
                )

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


def register_cli_commands(app):
    """Register CLI commands with the Flask application."""
    app.cli.add_command(import_volunteers_command)
    app.cli.add_command(import_documentation_members_command)
    app.cli.add_command(import_media_members_command)
