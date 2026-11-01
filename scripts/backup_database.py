import os
import sys
import sqlite3
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()


def backup(source_db_path: str, backup_dir: str) -> str:
    """Perform atomic online backup of SQLite database with restricted permissions."""
    if not os.path.exists(source_db_path):
        raise FileNotFoundError(f"Source database file not found: {source_db_path}")

    os.makedirs(backup_dir, exist_ok=True)
    # Restrict backup directory permissions (0700: user read/write/execute only)
    os.chmod(backup_dir, 0o700)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"department_club_backup_{timestamp}.sqlite"
    backup_path = os.path.join(backup_dir, backup_filename)

    print(f"Backing up database from '{source_db_path}' to '{backup_path}'...")
    src_conn = sqlite3.connect(source_db_path)
    dst_conn = sqlite3.connect(backup_path)

    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        # Restrict backup file permissions (0600: read/write for owner only)
        os.chmod(backup_path, 0o600)
        print(f"[OK] Database backup successful: {backup_path}")
        print(f"[OK] Permissions set to 0600 (Owner read/write only).")
    finally:
        dst_conn.close()
        src_conn.close()

    return backup_path


def restore(backup_path: str, target_db_path: str):
    """Restore database from backup file."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    print(f"Restoring database from '{backup_path}' to '{target_db_path}'...")
    src_conn = sqlite3.connect(backup_path)
    dst_conn = sqlite3.connect(target_db_path)

    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        os.chmod(target_db_path, 0o600)
        print(f"[OK] Database successfully restored to: {target_db_path}")
    finally:
        dst_conn.close()
        src_conn.close()


def main():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    instance_db = os.path.join(base_dir, "instance", "department_club.db")
    default_db_path = instance_db if os.path.exists(instance_db) else "department_club.db"

    parser = argparse.ArgumentParser(description="Department Club SQLite Database Backup & Restore Tool")
    parser.add_argument("--backup", action="store_true", help="Perform online database backup")
    parser.add_argument("--restore", type=str, help="Restore database from specified backup file")
    parser.add_argument("--db", type=str, default=default_db_path, help="Path to database file")
    parser.add_argument("--dir", type=str, default="database/backups", help="Directory to store backups")

    args = parser.parse_args()

    if args.restore:
        restore(args.restore, args.db)
    else:
        backup(args.db, args.dir)


if __name__ == "__main__":
    main()
